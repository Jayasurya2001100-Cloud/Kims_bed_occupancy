"""
Hospital Bed Occupancy Forecasting — ML Pipeline
Train: first 90 days | Test: last 30 days
"""

import warnings
warnings.filterwarnings("ignore")

import os
import logging
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import joblib

from sklearn.ensemble import RandomForestRegressor, ExtraTreesRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from xgboost import XGBRegressor
from lightgbm import LGBMRegressor
from catboost import CatBoostRegressor
from prophet import Prophet
from statsmodels.tsa.arima.model import ARIMA

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)s  %(message)s")
log = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# Paths
# ─────────────────────────────────────────────
BASE_DIR   = os.path.dirname(__file__)
DATA_PATH  = os.path.join(BASE_DIR, "data", "hospital_enhanced_full_dataset.csv")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

log.info(f"Using dataset: {DATA_PATH}")

WARD_TYPES = ["Cardiology", "Emergency", "General Ward", "ICU"]


# ─────────────────────────────────────────────
# 1. Load
# ─────────────────────────────────────────────
def load_data(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["date"] = pd.to_datetime(df["date"])
    log.info("Loaded %d rows", len(df))
    return df


# ─────────────────────────────────────────────
# 2. Feature Engineering
# ─────────────────────────────────────────────
def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["Date"] = df["date"].dt.date
    df["Day_of_Week"]  = df["date"].dt.dayofweek
    df["Month"]        = df["date"].dt.month
    df["Weekend_Flag"] = (df["Day_of_Week"] >= 5).astype(int)
    return df


def aggregate_occupancy(df: pd.DataFrame) -> pd.DataFrame:
    """Daily occupied-bed counts per department."""
    agg = (
        df.groupby(["Date", "department"])["occupied_beds"]
        .sum()
        .reset_index()
        .rename(columns={"occupied_beds": "Occupied_Beds", "department": "Ward_Type"})
    )
    agg["Date"] = pd.to_datetime(agg["Date"])
    agg.sort_values(["Ward_Type", "Date"], inplace=True)
    return agg


def add_time_series_features(df: pd.DataFrame) -> pd.DataFrame:
    """Lag & rolling features per Ward_Type."""
    frames = []
    for ward, grp in df.groupby("Ward_Type"):
        grp = grp.sort_values("Date").copy()
        grp["Lag_1"]          = grp["Occupied_Beds"].shift(1)
        grp["Lag_7"]          = grp["Occupied_Beds"].shift(7)
        grp["Lag_14"]         = grp["Occupied_Beds"].shift(14)
        grp["Rolling_Mean_7"] = grp["Occupied_Beds"].shift(1).rolling(7).mean()
        grp["Rolling_Mean_14"]= grp["Occupied_Beds"].shift(1).rolling(14).mean()
        grp["Rolling_Std_7"]  = grp["Occupied_Beds"].shift(1).rolling(7).std()
        frames.append(grp)
    out = pd.concat(frames).sort_values(["Ward_Type", "Date"]).reset_index(drop=True)
    out["Day_of_Week"]  = out["Date"].dt.dayofweek
    out["Month"]        = out["Date"].dt.month
    out["Weekend_Flag"] = (out["Day_of_Week"] >= 5).astype(int)
    return out


# ─────────────────────────────────────────────
# 3. Train / Test Split  (80% train, 20% test)
# ─────────────────────────────────────────────
def train_test_split_time(df: pd.DataFrame, train_pct=0.8):
    """Split data into 80% train and 20% test."""
    min_date = df["Date"].min()
    max_date = df["Date"].max()
    total_days = (max_date - min_date).days
    train_days = int(total_days * train_pct)
    cutoff = min_date + pd.Timedelta(days=train_days)
    train = df[df["Date"] <  cutoff].dropna()
    test  = df[df["Date"] >= cutoff].dropna()
    log.info("Train rows: %d (%.1f%%) | Test rows: %d (%.1f%%)", 
             len(train), train_pct*100, len(test), (1-train_pct)*100)
    log.info("Train period: %s to %s", train["Date"].min().date(), train["Date"].max().date())
    log.info("Test period: %s to %s", test["Date"].min().date(), test["Date"].max().date())
    return train, test


# ─────────────────────────────────────────────
# 4. Metrics
# ─────────────────────────────────────────────
def calc_metrics(y_true, y_pred) -> dict:
    y_true, y_pred = np.array(y_true), np.array(y_pred)
    mae  = mean_absolute_error(y_true, y_pred)
    rmse = np.sqrt(mean_squared_error(y_true, y_pred))
    mask = y_true != 0
    mape = np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])) * 100 if mask.any() else np.nan
    r2   = r2_score(y_true, y_pred)
    return {"MAE": round(mae, 3), "RMSE": round(rmse, 3),
            "MAPE": round(mape, 3), "R2": round(r2, 4)}


# ─────────────────────────────────────────────
# 5. ML Models (feature-based)
# ─────────────────────────────────────────────
FEATURES = ["Lag_1", "Lag_7", "Lag_14",
            "Rolling_Mean_7", "Rolling_Mean_14", "Rolling_Std_7",
            "Day_of_Week", "Month", "Weekend_Flag"]

ML_MODELS = {
    "XGBoost":           XGBRegressor(n_estimators=200, learning_rate=0.05,
                                      max_depth=5, random_state=42, verbosity=0),
    "LightGBM":          LGBMRegressor(n_estimators=200, learning_rate=0.05,
                                       random_state=42, verbose=-1),
    "CatBoost":          CatBoostRegressor(iterations=200, learning_rate=0.05,
                                           depth=5, random_seed=42, verbose=0),
    "RandomForest":      RandomForestRegressor(n_estimators=200, random_state=42),
    "ExtraTrees":        ExtraTreesRegressor(n_estimators=200, random_state=42),
    "LinearRegression":  LinearRegression(),
}


def run_ml_models(train: pd.DataFrame, test: pd.DataFrame) -> tuple[dict, dict]:
    X_train = train[FEATURES]
    y_train = train["Occupied_Beds"]
    X_test  = test[FEATURES]
    y_test  = test["Occupied_Beds"]

    results, trained = {}, {}
    for name, model in ML_MODELS.items():
        model.fit(X_train, y_train)
        preds = model.predict(X_test)
        results[name]  = calc_metrics(y_test, preds)
        trained[name]  = (model, preds, y_test.values)
        log.info("%-20s  MAPE=%.2f%%", name, results[name]["MAPE"])
    return results, trained


# ─────────────────────────────────────────────
# 6. Prophet
# ─────────────────────────────────────────────
def run_prophet(train: pd.DataFrame, test: pd.DataFrame) -> tuple[dict, np.ndarray]:
    ts_train = (
        train.groupby("Date")["Occupied_Beds"].sum()
        .reset_index().rename(columns={"Date": "ds", "Occupied_Beds": "y"})
    )
    ts_test = (
        test.groupby("Date")["Occupied_Beds"].sum()
        .reset_index().rename(columns={"Date": "ds", "Occupied_Beds": "y"})
    )
    m = Prophet(yearly_seasonality=False, weekly_seasonality=True, daily_seasonality=False)
    m.fit(ts_train)
    forecast = m.predict(ts_test[["ds"]])
    preds = forecast["yhat"].values
    y_test = ts_test["y"].values
    return calc_metrics(y_test, preds), preds, y_test


# ─────────────────────────────────────────────
# 7. ARIMA
# ─────────────────────────────────────────────
def run_arima(train: pd.DataFrame, test: pd.DataFrame) -> tuple[dict, np.ndarray]:
    ts_train = train.groupby("Date")["Occupied_Beds"].sum().sort_index()
    ts_test  = test.groupby("Date")["Occupied_Beds"].sum().sort_index()
    model = ARIMA(ts_train, order=(2, 1, 2))
    fit   = model.fit()
    preds = fit.forecast(steps=len(ts_test))
    return calc_metrics(ts_test.values, preds.values), preds.values, ts_test.values


# ─────────────────────────────────────────────
# 8. Leaderboard
# ─────────────────────────────────────────────
def build_leaderboard(ml_results: dict, prophet_metrics: dict,
                      arima_metrics: dict) -> pd.DataFrame:
    rows = []
    for name, m in ml_results.items():
        rows.append({"Model": name, **m})
    rows.append({"Model": "Prophet", **prophet_metrics})
    rows.append({"Model": "ARIMA",   **arima_metrics})
    lb = pd.DataFrame(rows).sort_values("MAPE").reset_index(drop=True)
    lb.index += 1
    log.info("\n%s", lb.to_string())
    return lb


# ─────────────────────────────────────────────
# 9. Feature Importance Plots
# ─────────────────────────────────────────────
def plot_feature_importance(trained: dict):
    tree_models = ["XGBoost", "LightGBM", "CatBoost", "RandomForest", "ExtraTrees"]
    for name in tree_models:
        if name not in trained:
            continue
        model = trained[name][0]
        imp = getattr(model, "feature_importances_", None)
        if imp is None:
            continue
        fig, ax = plt.subplots(figsize=(8, 4))
        pd.Series(imp, index=FEATURES).sort_values().plot.barh(ax=ax, color="steelblue")
        ax.set_title(f"Feature Importance — {name}")
        ax.set_xlabel("Importance")
        fig.tight_layout()
        path = os.path.join(OUTPUT_DIR, f"feat_imp_{name}.png")
        fig.savefig(path, dpi=120)
        plt.close(fig)
        log.info("Saved %s", path)


# ─────────────────────────────────────────────
# 10. Actual vs Predicted Plots (Test Data)
# ─────────────────────────────────────────────
def plot_actual_vs_predicted(trained: dict, test: pd.DataFrame,
                             prophet_preds, prophet_y,
                             arima_preds, arima_y):
    """Plot actual vs forecasted on test data."""
    test_dates = test.groupby("Date")["Occupied_Beds"].sum().sort_index()

    # ML models — aggregate predictions by date
    for name, (model, preds, y_true) in trained.items():
        dates = test["Date"].values
        df_plot = pd.DataFrame({"Date": dates, "Actual": y_true, "Forecasted": preds})
        df_plot = df_plot.groupby("Date").mean().sort_index()
        
        fig, ax = plt.subplots(figsize=(12, 5))
        ax.plot(df_plot.index, df_plot["Actual"], label="Actual (Test Data)", 
                color="#007DB0", linewidth=2.5)
        ax.plot(df_plot.index, df_plot["Forecasted"], label="Forecasted", 
                color="#FF0000", linestyle="--", linewidth=2.5)
        ax.set_title(f"Test Data: Actual vs Forecasted — {name}", fontsize=14, fontweight='bold')
        ax.legend(loc='best', fontsize=11)
        ax.set_xlabel("Date", fontsize=12)
        ax.set_ylabel("Occupied Beds", fontsize=12)
        ax.grid(True, alpha=0.3)
        fig.tight_layout()
        path = os.path.join(OUTPUT_DIR, f"test_avp_{name}.png")
        fig.savefig(path, dpi=120)
        plt.close(fig)
        log.info("Saved %s", path)

    # Prophet
    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(range(len(prophet_y)), prophet_y, label="Actual (Test Data)", 
            color="#007DB0", linewidth=2.5)
    ax.plot(range(len(prophet_preds)), prophet_preds, label="Forecasted", 
            color="#FF0000", linestyle="--", linewidth=2.5)
    ax.set_title("Test Data: Actual vs Forecasted — Prophet", fontsize=14, fontweight='bold')
    ax.legend(loc='best', fontsize=11)
    ax.set_xlabel("Day", fontsize=12)
    ax.set_ylabel("Occupied Beds (total)", fontsize=12)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(OUTPUT_DIR, "test_avp_Prophet.png"), dpi=120)
    plt.close(fig)

    # ARIMA
    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(range(len(arima_y)), arima_y, label="Actual (Test Data)", 
            color="#007DB0", linewidth=2.5)
    ax.plot(range(len(arima_preds)), arima_preds, label="Forecasted", 
            color="#FF0000", linestyle="--", linewidth=2.5)
    ax.set_title("Test Data: Actual vs Forecasted — ARIMA", fontsize=14, fontweight='bold')
    ax.legend(loc='best', fontsize=11)
    ax.set_xlabel("Day", fontsize=12)
    ax.set_ylabel("Occupied Beds (total)", fontsize=12)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(OUTPUT_DIR, "test_avp_ARIMA.png"), dpi=120)
    plt.close(fig)


# ─────────────────────────────────────────────
# 11. Ward-Level Forecasts
# ─────────────────────────────────────────────
def ward_level_forecasts(best_model, train: pd.DataFrame, test: pd.DataFrame):
    log.info("── Ward-Level Forecasts ──")
    ward_results = {}
    for ward in WARD_TYPES:
        tr = train[train["Ward_Type"] == ward]
        te = test[test["Ward_Type"]  == ward]
        if te.empty or tr.empty:
            log.warning("No data for ward: %s", ward)
            continue
        X_tr = tr[FEATURES]; y_tr = tr["Occupied_Beds"]
        X_te = te[FEATURES]; y_te = te["Occupied_Beds"]
        best_model.fit(X_tr, y_tr)
        preds = best_model.predict(X_te)
        m = calc_metrics(y_te, preds)
        ward_results[ward] = m
        log.info("  %-20s  MAPE=%.2f%%  R2=%.4f", ward, m["MAPE"], m["R2"])

        # Plot
        dates = te["Date"].values
        df_p  = pd.DataFrame({"Date": dates, "Actual": y_te.values, "Predicted": preds})
        df_p  = df_p.groupby("Date").mean().sort_index()
        fig, ax = plt.subplots(figsize=(11, 4))
        ax.plot(df_p.index, df_p["Actual"],    label="Actual",    color="black")
        ax.plot(df_p.index, df_p["Predicted"], label="Predicted", color="steelblue", linestyle="--")
        ax.set_title(f"Ward Forecast — {ward}")
        ax.legend(); ax.set_xlabel("Date"); ax.set_ylabel("Occupied Beds")
        fig.tight_layout()
        path = os.path.join(OUTPUT_DIR, f"ward_{ward.replace(' ','_')}.png")
        fig.savefig(path, dpi=120); plt.close(fig)
    return ward_results


# ─────────────────────────────────────────────
# 12. Save Best Model
# ─────────────────────────────────────────────
def save_best_model(leaderboard: pd.DataFrame, trained: dict,
                    train: pd.DataFrame, test: pd.DataFrame):
    best_name = leaderboard.iloc[0]["Model"]
    log.info("Best model: %s (MAPE=%.2f%%)", best_name, leaderboard.iloc[0]["MAPE"])

    if best_name in trained:
        model_obj = trained[best_name][0]
    else:
        # Re-fit Prophet or ARIMA as fallback
        model_obj = ML_MODELS.get(
            "XGBoost",
            XGBRegressor(n_estimators=200, learning_rate=0.05, max_depth=5,
                         random_state=42, verbosity=0)
        )
        X = pd.concat([train, test])[FEATURES].dropna()
        y = pd.concat([train, test])["Occupied_Beds"].loc[X.index]
        model_obj.fit(X, y)
        best_name = "XGBoost_fallback"

    path = os.path.join(OUTPUT_DIR, f"best_model_{best_name}.pkl")
    joblib.dump(model_obj, path)
    log.info("Saved best model → %s", path)
    return model_obj, best_name


# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────
def main():
    # 1. Load
    raw = load_data(DATA_PATH)

    # 2. Feature engineering on raw patient rows
    raw = engineer_features(raw)

    # 3. Aggregate to daily ward-level
    daily = aggregate_occupancy(raw)

    # 4. Add lag / rolling features
    daily = add_time_series_features(daily)

    # 5. Train / test split (80/20)
    train, test = train_test_split_time(daily, train_pct=0.8)

    # 6. ML models
    ml_results, trained = run_ml_models(train, test)

    # 7. Prophet
    prophet_metrics, prophet_preds, prophet_y = run_prophet(train, test)
    log.info("%-20s  MAPE=%.2f%%", "Prophet", prophet_metrics["MAPE"])

    # 8. ARIMA
    arima_metrics, arima_preds, arima_y = run_arima(train, test)
    log.info("%-20s  MAPE=%.2f%%", "ARIMA", arima_metrics["MAPE"])

    # 9. Leaderboard
    leaderboard = build_leaderboard(ml_results, prophet_metrics, arima_metrics)
    lb_path = os.path.join(OUTPUT_DIR, "leaderboard.csv")
    leaderboard.to_csv(lb_path)
    log.info("Leaderboard saved → %s", lb_path)

    # 10. Feature importance plots
    plot_feature_importance(trained)

    # 11. Actual vs Predicted plots
    plot_actual_vs_predicted(trained, test, prophet_preds, prophet_y,
                             arima_preds, arima_y)

    # 12. Save best model
    best_model_obj, best_name = save_best_model(leaderboard, trained, train, test)

    # 13. Ward-level forecasts (using best tree-based model for interpretability)
    best_ml = trained.get(best_name, list(trained.values())[0])[0] \
              if best_name in trained else best_model_obj
    ward_results = ward_level_forecasts(best_ml, train, test)

    # Summary
    print("\n" + "=" * 55)
    print("  LEADERBOARD (ranked by MAPE ↑)")
    print("=" * 55)
    print(leaderboard.to_string(index=True))
    print("\n  WARD-LEVEL RESULTS")
    print("-" * 55)
    for w, m in ward_results.items():
        print(f"  {w:<22}  MAPE={m['MAPE']:.2f}%  R²={m['R2']:.4f}")
    print("=" * 55)
    print(f"\n  Best model : {leaderboard.iloc[0]['Model']}")
    print(f"  Saved to   : {OUTPUT_DIR}")
    print("=" * 55)


if __name__ == "__main__":
    main()
