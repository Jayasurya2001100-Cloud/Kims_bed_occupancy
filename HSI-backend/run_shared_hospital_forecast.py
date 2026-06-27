import os
from datetime import timedelta
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from forecast_engine import run_occupancy_forecast
from ml_pipeline import (
    add_time_series_features,
    run_ml_models,
    run_prophet as ml_run_prophet,
    run_arima as ml_run_arima,
    build_leaderboard,
)

ROOT = Path(__file__).resolve().parent
DATA_PATH = ROOT / "data" / "hospital_enhanced_full_dataset.csv"
OUT_DIR = ROOT / "output_shared_dataset"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def load_shared_data(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["date"] = pd.to_datetime(df["date"])
    return df


def aggregate_hospital_level(df: pd.DataFrame) -> pd.DataFrame:
    agg = (
        df.groupby("date", as_index=False)
        .agg(
            occupied_beds=("occupied_beds", "sum"),
            total_beds=("total_beds", "sum"),
            patient_count=("patient_count", "sum"),
        )
    )
    agg["occupancy_rate"] = (
        agg["occupied_beds"] / agg["total_beds"]
    ).clip(0.0, 0.9999)
    return agg.sort_values("date").reset_index(drop=True)


def save_forecast_excel(compare_df: pd.DataFrame, future_df: pd.DataFrame, path: Path) -> None:
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        compare_df.to_excel(writer, sheet_name="last_30_days", index=False)
        future_df.to_excel(writer, sheet_name="future_90_day_forecast", index=False)


def plot_occupancy_comparison(compare_df: pd.DataFrame, path: Path) -> None:
    plt.figure(figsize=(11, 5))
    plt.plot(compare_df["date"], compare_df["occupancy_rate"], label="Actual occupancy rate", marker="o")
    plt.plot(compare_df["date"], compare_df["predicted_occupancy_rate"], label="Forecast occupancy rate", marker="x")
    plt.title("Hospital Occupancy Rate — Actual vs Forecast (Last 30 Days)")
    plt.xlabel("Date")
    plt.ylabel("Occupancy rate")
    plt.legend()
    plt.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(path, dpi=150)
    plt.close()


def plot_future_forecast(future_df: pd.DataFrame, path: Path) -> None:
    plt.figure(figsize=(12, 5))
    plt.plot(future_df["date"], future_df["predicted_occupancy_rate"], label="Forecast occupancy rate", color="tab:blue")
    plt.fill_between(
        future_df["date"],
        future_df["lower_bound"],
        future_df["upper_bound"],
        color="tab:blue",
        alpha=0.2,
        label="Forecast interval",
    )
    plt.title("Hospital Occupancy Rate Forecast — Next 90 Days")
    plt.xlabel("Date")
    plt.ylabel("Occupancy rate")
    plt.legend()
    plt.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(path, dpi=150)
    plt.close()


def run_prophet_forecast(daily: pd.DataFrame, compare_days: int = 30, forecast_days: int = 90) -> dict:
    last_date = daily["date"].max()
    compare_start = last_date - timedelta(days=compare_days - 1)
    train = daily[daily["date"] < compare_start].copy()
    if train.empty:
        raise ValueError("Not enough data to train before the comparison window")

    result = run_occupancy_forecast(
        train,
        forecast_days,
        "Hospital total occupancy",
        model_preference="prophet",
    )
    return result


def run_ml_model_comparison(daily: pd.DataFrame, train_days: int = 90, test_days: int = 30) -> dict:
    ml_daily = daily[["date", "occupied_beds"]].copy()
    ml_daily = ml_daily.rename(columns={"date": "Date", "occupied_beds": "Occupied_Beds"})
    ml_daily["Ward_Type"] = "Hospital"

    ml_daily = add_time_series_features(ml_daily)
    last_date = ml_daily["Date"].max()
    train_end = last_date - timedelta(days=test_days)
    train_start = train_end - timedelta(days=train_days - 1)

    train = ml_daily[(ml_daily["Date"] >= train_start) & (ml_daily["Date"] <= train_end)].copy()
    test = ml_daily[(ml_daily["Date"] > train_end) & (ml_daily["Date"] <= last_date)].copy()

    train = train.dropna().reset_index(drop=True)
    test = test.dropna().reset_index(drop=True)
    if train.empty or test.empty:
        raise ValueError("Not enough train/test data for ML comparison")

    ml_results, trained = run_ml_models(train, test)
    prophet_metrics, prophet_preds, prophet_y = ml_run_prophet(train, test)
    arima_metrics, arima_preds, arima_y = ml_run_arima(train, test)

    leaderboard = build_leaderboard(ml_results, prophet_metrics, arima_metrics)
    test_dates = test["Date"].reset_index(drop=True)

    compare = pd.DataFrame({
        "date": test_dates,
        "actual_occupied_beds": test["Occupied_Beds"].values,
    })
    for name, (model, preds, y_true) in trained.items():
        compare[f"pred_{name}"] = preds
    compare["pred_prophet"] = prophet_preds
    compare["pred_arima"] = arima_preds

    return {
        "leaderboard": leaderboard,
        "comparison": compare,
        "trained": trained,
        "prophet_preds": prophet_preds,
        "prophet_y": prophet_y,
        "arima_preds": arima_preds,
        "arima_y": arima_y,
    }


def plot_model_comparison(compare: pd.DataFrame, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.plot(compare["date"], compare["actual_occupied_beds"], label="Actual occupied beds", color="black", linewidth=2)
    colors = {
        "pred_XGBoost": "tab:orange",
        "pred_LightGBM": "tab:green",
        "pred_CatBoost": "tab:red",
        "pred_RandomForest": "tab:purple",
        "pred_ExtraTrees": "tab:brown",
        "pred_LinearRegression": "tab:cyan",
        "pred_prophet": "tab:blue",
        "pred_arima": "tab:gray",
    }
    for col, color in colors.items():
        if col in compare.columns:
            ax.plot(compare["date"], compare[col], label=col.replace("pred_", ""), color=color, linestyle="--", alpha=0.85)
    ax.set_title("Hospital occupied beds — Actual vs model predictions (last 30 days)")
    ax.set_xlabel("Date")
    ax.set_ylabel("Occupied beds")
    ax.legend(loc="upper left", fontsize="small", ncol=2)
    ax.grid(alpha=0.2)
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    df = load_shared_data(DATA_PATH)
    hospital_daily = aggregate_hospital_level(df)
    hospital_daily.to_csv(OUT_DIR / "hospital_daily_aggregated.csv", index=False)

    prophet_result = run_prophet_forecast(hospital_daily)
    forecast_data = pd.DataFrame(prophet_result["forecast_data"])
    forecast_data["date"] = pd.to_datetime(forecast_data["date"])

    last_date = hospital_daily["date"].max()
    compare_start = last_date - timedelta(days=29)
    actual_last_30 = hospital_daily[hospital_daily["date"] >= compare_start][["date", "occupancy_rate", "occupied_beds"]]

    compare_df = forecast_data.copy()
    compare_df = compare_df[compare_df["date"] >= compare_start].reset_index(drop=True)
    compare_df = compare_df.merge(actual_last_30, on="date", how="left")
    compare_df.to_csv(OUT_DIR / "forecast_last_30_days_prophet.csv", index=False)

    save_forecast_excel(compare_df, forecast_data, OUT_DIR / "forecast_report_shared_dataset.xlsx")
    plot_occupancy_comparison(compare_df, OUT_DIR / "forecast_last_30_days_prophet.png")
    plot_future_forecast(forecast_data, OUT_DIR / "forecast_next_90_days_prophet.png")

    ml_results = run_ml_model_comparison(hospital_daily)
    ml_results["leaderboard"].to_csv(OUT_DIR / "model_leaderboard.csv", index=False)
    ml_results["comparison"].to_csv(OUT_DIR / "model_comparison_last_30_days.csv", index=False)
    plot_model_comparison(ml_results["comparison"], OUT_DIR / "model_comparison_last_30_days.png")

    summary = {
        "last_date": str(last_date.date()),
        "forecast_days": len(forecast_data),
        "forecast_engine": prophet_result["forecast_model"],
        "model_metrics": prophet_result["model_metrics"],
        "leaderboard_top3": ml_results["leaderboard"].head(3).to_dict(orient="records"),
    }
    pd.DataFrame([summary]).to_json(OUT_DIR / "forecast_summary.json", orient="records", indent=2)

    print("Saved shared dataset forecast outputs to:")
    for file in sorted(OUT_DIR.iterdir()):
        print(" -", file.name)


if __name__ == "__main__":
    main()
