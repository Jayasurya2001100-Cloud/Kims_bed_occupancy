"""
Deep-dive analytics for Delhi: 3-month rolling forecasts -> 1-month holdout

This script:
- Loads `backend/data/hospital_disease_data.csv` (synthetic generator in `scripts/`)
- Applies light Delhi-specific adjustments (scale occupancy and LOS to reflect local characteristics)
- Aggregates to a hospital-level daily series (occupancy_rate, avg_length_of_stay, patient_count)
- Runs two experiments:
    1) Train on 2025-05-01 -> 2025-07-31, predict 2025-08-01 -> 2025-08-31
    2) Train on 2025-09-01 -> 2025-11-30, predict 2025-12-01 -> 2025-12-31
- For each experiment it runs forecasts for `occupancy_rate`, `avg_length_of_stay`, and `patient_count`
  using the forecasting stack (Prophet, ARIMAX (pmdarima auto_arima), XGBoost) by delegating to
  `forecast_engine.run_occupancy_forecast` and `forecast_engine.run_generic_forecast`.
- Saves CSVs and a combined plot per experiment under `backend/deep_dive_outputs/`.

Usage:
    python backend/deep_dive.py --model arimax

Notes on data preparation:
- The repository's `scripts/generate_daily_hospital_data.py` produces the base synthetic dataset.
- That generator uses fixed department totals and base occupancy rates, week/weekend, seasonal
  adjustments, and seeded randomness for reproducibility.
- Here we apply small, explicit Delhi adjustments to occupancy and average LOS to simulate
  local hospital pressure (configurable in `apply_delhi_adjustments`). If you have real
  Delhi hospital data, skip the adjustments and point `DATA_PATH` to that file instead.
"""
from __future__ import annotations

import argparse
import math
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from forecast_engine import run_occupancy_forecast, run_generic_forecast, _future_dates

# Paths
ROOT = Path(__file__).resolve().parent
DATA_PATH = ROOT / "data" / "hospital_disease_data.csv"
OUT_DIR = ROOT / "deep_dive_outputs"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def apply_delhi_adjustments(
    df: pd.DataFrame,
    occupancy_offset: float = 0.03,
    los_multiplier: float = 1.05,
    monsoon_multiplier: float = 1.12,
) -> pd.DataFrame:
    """Apply light adjustments to simulate Delhi hospital characteristics.

    - occupancy_offset: additive occupancy rate adjustment
    - los_multiplier: multiplicative avg LOS adjustment
    - monsoon_multiplier: multiplier on emergency admissions for Jul-Sep
    """
    out = df.copy()
    out["occupancy_rate"] = out["occupancy_rate"].astype(float)
    out["avg_length_of_stay"] = out["avg_length_of_stay"].astype(float)
    out["emergency_admission"] = pd.to_numeric(out["emergency_admission"], errors="coerce").fillna(0)

    out["occupancy_rate"] = (out["occupancy_rate"] + occupancy_offset).clip(0.01, 0.995)
    out["avg_length_of_stay"] = (out["avg_length_of_stay"] * los_multiplier).round(1).clip(lower=1.0)

    months = out["date"].dt.month
    monsoon_mask = months.isin([7, 8, 9])
    out.loc[monsoon_mask, "emergency_admission"] = (
        out.loc[monsoon_mask, "emergency_admission"] * monsoon_multiplier
    ).round().astype(int)

    if "total_beds" in out.columns:
        out["occupied_beds"] = (out["occupancy_rate"] * out["total_beds"]).round().astype(int)
    return out


def calibrate_delhi_params(
    df: pd.DataFrame,
    cal_start: str,
    cal_end: str,
    target_mean_occ: float,
    target_mean_los: float,
) -> Tuple[float, float, float]:
    """Calibrate occupancy offset, LOS multiplier, monsoon multiplier to match targets.

    Simple grid search over reasonable ranges. Returns (occ_offset, los_mult, monsoon_mult).
    """
    sub = df.copy()
    sub["date"] = pd.to_datetime(sub["date"]).dt.normalize()
    mask = (sub["date"] >= pd.to_datetime(cal_start)) & (sub["date"] <= pd.to_datetime(cal_end))
    sub = sub[mask]
    if sub.empty:
        raise ValueError("Calibration window empty")

    # Ranges
    occ_offsets = np.linspace(-0.02, 0.06, 9)  # additive
    los_mults = np.linspace(0.9, 1.2, 7)  # multiplicative
    monsoon_mults = np.linspace(0.95, 1.3, 8)

    months = sub["date"].dt.month
    monsoon_mask = months.isin([7, 8, 9])

    best = None
    best_score = float("inf")
    for oo in occ_offsets:
        for lm in los_mults:
            for mm in monsoon_mults:
                tmp = sub.copy()
                tmp["occupancy_rate"] = (tmp["occupancy_rate"].astype(float) + oo).clip(0.01, 0.995)
                tmp["avg_length_of_stay"] = (tmp["avg_length_of_stay"].astype(float) * lm).clip(lower=1.0)
                tmp.loc[monsoon_mask, "emergency_admission"] = (
                    tmp.loc[monsoon_mask, "emergency_admission"].astype(float) * mm
                ).round()

                mean_occ = float(tmp["occupancy_rate"].mean())
                mean_los = float(tmp["avg_length_of_stay"].mean())
                score = (mean_occ - target_mean_occ) ** 2 + (mean_los - target_mean_los) ** 2
                if score < best_score:
                    best_score = score
                    best = (float(oo), float(lm), float(mm))

    return best


def aggregate_hospital_level(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate department-level rows to a single hospital-level daily series.

    Produces columns: date, occupied_beds, total_beds, occupancy_rate, avg_length_of_stay, patient_count
    """
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    agg = (
        df.groupby("date").agg(
            occupied_beds=("occupied_beds", "sum"),
            total_beds=("total_beds", "sum"),
            patient_count=("patient_count", "sum"),
            labour_staffing=("labour_staffing", "sum"),
        )
    )
    # occupancy_rate
    agg["occupancy_rate"] = (agg["occupied_beds"] / agg["total_beds"]).clip(0.0, 0.9999)

    # Weighted average LOS by patient_count
    df_los = df.copy()
    df_los["patient_count"] = df_los["patient_count"].astype(float)
    los = (
        df_los.groupby("date").apply(
            lambda g: (g["avg_length_of_stay"].astype(float) * g["patient_count"]).sum()
            / max(1.0, g["patient_count"].sum())
        )
    )
    agg["avg_length_of_stay"] = los.round(2)
    agg = agg.reset_index()
    return agg


def run_experiment(
    hospital_df: pd.DataFrame,
    train_start: str,
    train_end: str,
    pred_start: str,
    pred_end: str,
    model_pref: str = "arimax",
) -> Dict[str, any]:
    """Run forecasts for occupancy_rate, avg_length_of_stay, and patient_count.

    Returns a dict with predicted vs actual DataFrames and simple metrics.
    """
    ts = hospital_df.copy()
    ts["date"] = pd.to_datetime(ts["date"]).dt.normalize()

    tr_mask = (ts["date"] >= pd.to_datetime(train_start)) & (ts["date"] <= pd.to_datetime(train_end))
    pr_mask = (ts["date"] >= pd.to_datetime(pred_start)) & (ts["date"] <= pd.to_datetime(pred_end))

    train = ts[tr_mask].reset_index(drop=True)
    actual = ts[pr_mask].reset_index(drop=True)
    days = len(actual)
    if days == 0 or train.empty:
        raise ValueError("Empty train or prediction window")

    results: Dict[str, pd.DataFrame] = {}
    metrics: Dict[str, Dict[str, float]] = {}

    # Occupancy: run all three models (prophet, arimax, xgboost) so we can compare
    occ_models = {
        "prophet": run_occupancy_forecast(train, days, "Delhi Hospital", model_preference="prophet"),
        "arimax": run_occupancy_forecast(train, days, "Delhi Hospital", model_preference="arimax"),
        "xgboost": run_occupancy_forecast(train, days, "Delhi Hospital", model_preference="xgboost"),
    }

    # Merge actual with each model's predictions into one DataFrame
    occ_actual = actual[["date", "occupancy_rate", "occupied_beds"]].copy()
    occ_merge = occ_actual.copy()
    for name, res_m in occ_models.items():
        dfm = pd.DataFrame(res_m["forecast_data"]) if res_m is not None else pd.DataFrame()
        if not dfm.empty:
            dfm["date"] = pd.to_datetime(dfm["date"])
            occ_merge = occ_merge.merge(dfm[["date", "predicted_occupancy_rate", "predicted_occupied_beds"]].rename(
                columns={"predicted_occupancy_rate": f"pred_{name}", "predicted_occupied_beds": f"pred_beds_{name}"}
            ), on="date", how="left")
        else:
            occ_merge[f"pred_{name}"] = np.nan
            occ_merge[f"pred_beds_{name}"] = np.nan

    # Use the selected model_pref for primary metrics (if available), else arimax
    primary = model_pref if model_pref in occ_models else "arimax"
    occ_merge["occ_error_abs"] = (occ_merge[f"pred_{primary}"] - occ_merge["occupancy_rate"]).abs()
    s_occ = (occ_merge["occ_error_abs"] / occ_merge["occupancy_rate"].replace(0, np.nan)).to_numpy(dtype=float)
    mape_occ = np.nanmean(s_occ)
    if np.isnan(mape_occ):
        mape_occ = 0.0
    metrics["occupancy_rate"] = {
        "mape": float(mape_occ),
        "rmse": float(np.sqrt(np.nanmean((occ_merge[f"pred_{primary}"] - occ_merge["occupancy_rate"]) ** 2))),
        "primary_model": primary,
    }
    results["occupancy"] = occ_merge

    # Avg length of stay
    los_res = run_generic_forecast(train, days, "avg_length_of_stay", "Delhi Hospital", model_preference=model_pref)
    los_pred = pd.DataFrame(los_res["forecast_data"])  # fields: date, predicted_value
    los_pred["date"] = pd.to_datetime(los_pred["date"])
    los_actual = actual[["date", "avg_length_of_stay"]].copy()
    los_merge = los_actual.merge(los_pred, on="date")
    los_merge["los_error_abs"] = (los_merge["predicted_value"] - los_merge["avg_length_of_stay"]).abs()
    s_los = (los_merge["los_error_abs"] / los_merge["avg_length_of_stay"].replace(0, np.nan)).to_numpy(dtype=float)
    mape_los = np.nanmean(s_los)
    if np.isnan(mape_los):
        mape_los = 0.0
    metrics["avg_length_of_stay"] = {
        "mape": float(mape_los),
        "rmse": float(np.sqrt(np.mean((los_merge["predicted_value"] - los_merge["avg_length_of_stay"]) ** 2))),
    }
    results["los"] = los_merge

    # Patient count (third line) - predict using generic forecaster
    pc_res = run_generic_forecast(train, days, "patient_count", "Delhi Hospital", model_preference=model_pref)
    pc_pred = pd.DataFrame(pc_res["forecast_data"])  # date, predicted_value
    pc_pred["date"] = pd.to_datetime(pc_pred["date"])
    pc_actual = actual[["date", "patient_count"]].copy()
    pc_merge = pc_actual.merge(pc_pred, on="date")
    pc_merge["pc_error_abs"] = (pc_merge["predicted_value"] - pc_merge["patient_count"]).abs()
    s_pc = (pc_merge["pc_error_abs"] / pc_merge["patient_count"].replace(0, np.nan)).to_numpy(dtype=float)
    mape_pc = np.nanmean(s_pc)
    if np.isnan(mape_pc):
        mape_pc = 0.0
    metrics["patient_count"] = {
        "mape": float(mape_pc),
        "rmse": float(np.sqrt(np.mean((pc_merge["predicted_value"] - pc_merge["patient_count"]) ** 2))),
    }
    results["patient_count"] = pc_merge

    # Labour staffing forecast
    staffing_res = run_generic_forecast(train, days, "labour_staffing", "Delhi Hospital", model_preference=model_pref)
    staffing_pred = pd.DataFrame(staffing_res["forecast_data"])
    staffing_pred["date"] = pd.to_datetime(staffing_pred["date"])
    staffing_actual = actual[["date", "labour_staffing"]].copy()
    staffing_merge = staffing_actual.merge(staffing_pred, on="date", how="left")
    s_staff = (
        (staffing_merge["predicted_value"] - staffing_merge["labour_staffing"]).abs()
        / staffing_merge["labour_staffing"].replace(0, np.nan)
    ).to_numpy(dtype=float)
    mape_staff = float(np.nanmean(s_staff))
    if np.isnan(mape_staff):
        mape_staff = 0.0
    metrics["labour_staffing"] = {
        "mape": mape_staff,
        "rmse": float(np.sqrt(np.nanmean((staffing_merge["predicted_value"] - staffing_merge["labour_staffing"]) ** 2))),
        "engine": staffing_res.get("model_metrics", {}).get("engine", model_pref),
    }
    results["staffing"] = staffing_merge

    model_used = metrics["occupancy_rate"].get("primary_model", "arimax")
    return {"results": results, "metrics": metrics, "model_used": model_used}


def plot_experiment(exp_name: str, out_path: Path, data_dict: Dict[str, pd.DataFrame]):
    """Create a 4-row plot comparing actual vs predicted for occupancy, LOS, patient_count, and staffing."""
    fig, axes = plt.subplots(4, 1, figsize=(12, 16), sharex=True)

    # Occupancy: plot actual and all three model prediction columns
    occ = data_dict["occupancy"]
    axes[0].plot(occ["date"], occ["occupancy_rate"], label="Actual occupancy rate", color="tab:blue", linewidth=2)
    pred_cols = [c for c in occ.columns if c.startswith("pred_") and not c.startswith("pred_beds_")]
    colors = {"prophet": "tab:orange", "arimax": "tab:green", "xgboost": "tab:red"}
    for pc in pred_cols:
        model_name = pc.replace("pred_", "")
        axes[0].plot(occ["date"], occ[pc], label=f"Predicted ({model_name})",
                     color=colors.get(model_name), linestyle="--")
    axes[0].set_ylabel("Occupancy rate")
    axes[0].set_title("Bed Occupancy Rate")
    axes[0].legend(fontsize=8)
    axes[0].grid(True, alpha=0.3)

    # LOS
    los = data_dict["los"]
    axes[1].plot(los["date"], los["avg_length_of_stay"], label="Actual avg LOS", color="tab:blue", linewidth=2)
    axes[1].plot(los["date"], los["predicted_value"], label="Predicted avg LOS", color="tab:orange", linestyle="--")
    axes[1].set_ylabel("Days")
    axes[1].set_title("Average Length of Stay")
    axes[1].legend(fontsize=8)
    axes[1].grid(True, alpha=0.3)

    # Patient count
    pcd = data_dict["patient_count"]
    axes[2].plot(pcd["date"], pcd["patient_count"], label="Actual patient count", color="tab:blue", linewidth=2)
    axes[2].plot(pcd["date"], pcd["predicted_value"], label="Predicted patient count", color="tab:orange", linestyle="--")
    axes[2].set_ylabel("Patients")
    axes[2].set_title("Patient Count")
    axes[2].legend(fontsize=8)
    axes[2].grid(True, alpha=0.3)

    # Labour staffing
    stf = data_dict["staffing"]
    axes[3].plot(stf["date"], stf["labour_staffing"], label="Actual staffing (FTE)", color="tab:blue", linewidth=2)
    axes[3].plot(stf["date"], stf["predicted_value"], label="Model predicted staffing", color="tab:purple", linestyle="--")
    axes[3].set_ylabel("Staff (FTE)")
    axes[3].set_title("Labour Staffing Requirements")
    axes[3].legend(fontsize=8)
    axes[3].grid(True, alpha=0.3)

    plt.suptitle(exp_name, fontsize=13, fontweight="bold")
    plt.tight_layout(rect=[0, 0.03, 1, 0.97])
    fig.autofmt_xdate()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def main(args):
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"Data file not found: {DATA_PATH}. Run scripts/generate_daily_hospital_data.py first.")

    df = pd.read_csv(DATA_PATH)
    df["date"] = pd.to_datetime(df["date"])

    if args.calibrate:
        print(
            f"Calibrating Delhi adjustments for {args.cal_start} to {args.cal_end} "
            f"against target occupancy={args.target_occ} and LOS={args.target_los}"
        )
        occ_off, los_mult, monsoon_mult = calibrate_delhi_params(
            df,
            args.cal_start,
            args.cal_end,
            args.target_occ,
            args.target_los,
        )
        print(
            f"Calibration result: occupancy_offset={occ_off:.4f}, los_multiplier={los_mult:.3f}, monsoon_multiplier={monsoon_mult:.3f}"
        )
    else:
        occ_off, los_mult, monsoon_mult = 0.03, 1.05, 1.12

    df_delhi = apply_delhi_adjustments(df, occ_off, los_mult, monsoon_mult)
    hosp = aggregate_hospital_level(df_delhi)

    experiments = [
        ("May–Jul 2025 → 3-week forecast Aug 2025", "2025-05-01", "2025-07-31", "2025-08-01", "2025-08-21"),
        ("Sep–Nov 2025 → 3-week forecast Dec 2025", "2025-09-01", "2025-11-30", "2025-12-01", "2025-12-21"),
    ]

    for name, ts, te, ps, pe in experiments:
        print(f"Running experiment: {name} using model {args.model}")
        out = run_experiment(hosp, ts, te, ps, pe, model_pref=args.model)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_base = OUT_DIR / f"deep_dive_{args.model}_{ps}_to_{pe}_{timestamp}"

        # Save CSVs
        for k, dfk in out["results"].items():
            dfk.to_csv(csv_base.with_name(csv_base.name + f"_{k}.csv"), index=False)

        # Save metrics
        metrics_path = csv_base.with_suffix(".metrics.txt")
        with open(metrics_path, "w") as mf:
            mf.write(f"Experiment : {name}\n")
            mf.write(f"Model      : {args.model}\n")
            mf.write(f"Holdout    : 3 weeks ({ps} to {pe})\n\n")
            for metric_key, metric_vals in out["metrics"].items():
                mf.write(f"{metric_key}:\n")
                for k, v in metric_vals.items():
                    mf.write(f"  {k}: {v}\n")
                mf.write("\n")

        # Plot
        plot_path = csv_base.with_suffix(".png")
        plot_experiment(name + f" ({args.model})", plot_path, out["results"])
        print(f"Wrote outputs to {csv_base}*")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", choices=["prophet", "arimax", "auto_arima", "xgboost"], default="prophet")
    ap.add_argument("--calibrate", action="store_true", help="Auto-calibrate Delhi adjustments to target stats")
    ap.add_argument("--target_occ", type=float, default=None, help="Target mean occupancy (e.g. 0.74)")
    ap.add_argument("--target_los", type=float, default=None, help="Target mean avg length of stay (e.g. 4.2)")
    ap.add_argument("--cal_start", type=str, default="2025-05-01", help="Calibration window start date")
    ap.add_argument("--cal_end", type=str, default="2025-07-31", help="Calibration window end date")
    args = ap.parse_args()
    # If calibration requested, ensure targets provided
    if args.calibrate:
        if args.target_occ is None or args.target_los is None:
            ap.error("--calibrate requires --target_occ and --target_los to be set")
    main(args)
