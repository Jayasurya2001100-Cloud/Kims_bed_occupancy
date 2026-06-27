"""
Simple shared dataset forecast using only Prophet/ARIMA (no heavy ML modules).
"""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd
from datetime import timedelta
from pathlib import Path

from forecast_engine import run_occupancy_forecast

ROOT = Path(__file__).resolve().parent
DATA_PATH = ROOT / "data" / "hospital_enhanced_full_dataset.csv"
OUT_DIR = ROOT / "output_shared_dataset"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def load_data(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["date"] = pd.to_datetime(df["date"])
    return df


def aggregate_hospital(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate to hospital-level daily data."""
    agg = (
        df.groupby("date", as_index=False)
        .agg(
            occupied_beds=("occupied_beds", "sum"),
            total_beds=("total_beds", "sum"),
            patient_count=("patient_count", "sum"),
        )
    )
    agg["occupancy_rate"] = (agg["occupied_beds"] / agg["total_beds"]).clip(0.0, 0.9999)
    return agg.sort_values("date").reset_index(drop=True)


def plot_occupancy_comparison(compare_df: pd.DataFrame, path: Path) -> None:
    """Plot actual vs forecast occupancy for last 30 days."""
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.plot(compare_df["date"], compare_df["occupancy_rate"], label="Actual occupancy rate", marker="o", markersize=4)
    ax.plot(compare_df["date"], compare_df["predicted_occupancy_rate"], label="Forecast occupancy rate", marker="x", markersize=4)
    ax.set_title("Hospital Occupancy Rate — Actual vs Forecast (Last 30 Days)")
    ax.set_xlabel("Date")
    ax.set_ylabel("Occupancy rate")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved {path}")


def plot_future_forecast(future_df: pd.DataFrame, path: Path) -> None:
    """Plot 90-day occupancy forecast with confidence interval."""
    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(future_df["date"], future_df["predicted_occupancy_rate"], label="Forecast occupancy rate", color="tab:blue")
    ax.fill_between(
        future_df["date"],
        future_df["lower_bound"],
        future_df["upper_bound"],
        color="tab:blue",
        alpha=0.2,
        label="Forecast interval",
    )
    ax.set_title("Hospital Occupancy Rate Forecast — Next 90 Days")
    ax.set_xlabel("Date")
    ax.set_ylabel("Occupancy rate")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved {path}")


def main():
    print("Loading shared dataset...")
    df = load_data(DATA_PATH)
    print(f"  Loaded {len(df)} rows, date range: {df['date'].min()} to {df['date'].max()}")
    
    print("Aggregating to hospital level...")
    hospital_daily = aggregate_hospital(df)
    print(f"  {len(hospital_daily)} daily records")
    hospital_daily.to_csv(OUT_DIR / "hospital_daily_aggregated.csv", index=False)
    
    print("Running occupancy forecast (Prophet)...")
    result = run_occupancy_forecast(
        hospital_daily,
        forecast_days=90,
        series_name="Hospital total occupancy",
        model_preference="prophet",
    )
    
    print(f"  Model: {result['forecast_model']}")
    print(f"  Metrics: {result['model_metrics']}")
    
    forecast_data = pd.DataFrame(result["forecast_data"])
    forecast_data["date"] = pd.to_datetime(forecast_data["date"])
    
    # Compare last 30 days actual vs forecast
    last_date = hospital_daily["date"].max()
    compare_start = last_date - timedelta(days=29)
    actual_last_30 = hospital_daily[hospital_daily["date"] >= compare_start][
        ["date", "occupancy_rate", "occupied_beds"]
    ]
    
    compare_df = forecast_data[forecast_data["date"] >= compare_start].copy()
    compare_df = compare_df.merge(actual_last_30, on="date", how="left")
    compare_df.to_csv(OUT_DIR / "forecast_last_30_days_prophet.csv", index=False)
    
    # Save full 90-day forecast
    forecast_data.to_csv(OUT_DIR / "forecast_next_90_days_prophet.csv", index=False)
    
    # Plot comparisons
    print("Generating plots...")
    plot_occupancy_comparison(compare_df, OUT_DIR / "forecast_last_30_days_prophet.png")
    plot_future_forecast(forecast_data, OUT_DIR / "forecast_next_90_days_prophet.png")
    
    # Save summary
    summary = {
        "last_date": str(last_date.date()),
        "forecast_days": len(forecast_data),
        "forecast_model": result["forecast_model"],
        "model_rmse": result["model_metrics"].get("rmse"),
        "model_mape": result["model_metrics"].get("mape"),
        "hospital_occupied_beds_avg": hospital_daily["occupied_beds"].mean(),
        "hospital_occupancy_rate_avg": hospital_daily["occupancy_rate"].mean(),
    }
    pd.DataFrame([summary]).to_json(OUT_DIR / "forecast_summary.json", orient="records", indent=2)
    
    print("\n✓ All outputs saved to:")
    for file in sorted(OUT_DIR.iterdir()):
        print(f"  - {file.name}")


if __name__ == "__main__":
    main()
