import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parent
IN_CSV = ROOT / "output_shared_dataset" / "model_comparison_last_30_days.csv"
OUT_PNG = ROOT / "output_shared_dataset" / "model_comparison_last_30_days.png"


def main():
    df = pd.read_csv(IN_CSV, parse_dates=["date"])
    if df.empty:
        raise SystemExit(f"No data in {IN_CSV}")

    plt.figure(figsize=(10, 5))
    plt.plot(df["date"], df["actual_occupied_beds"], label="Actual occupied beds", color="black", linewidth=2)

    pred_cols = [c for c in df.columns if c.startswith("pred_")]
    color_map = {
        "pred_ExtraTrees": "tab:orange",
        "pred_RandomForest": "tab:green",
        "pred_CatBoost": "tab:red",
        "pred_LightGBM": "tab:purple",
        "pred_XGBoost": "tab:brown",
        "pred_LinearRegression": "tab:cyan",
        "pred_prophet": "tab:blue",
        "pred_arima": "tab:gray",
    }
    for col in pred_cols:
        plt.plot(df["date"], df[col], label=col.replace("pred_", ""), linestyle="--", alpha=0.9, color=color_map.get(col, None))

    plt.title("Hospital occupied beds — Actual vs model predictions (last 30 days)")
    plt.xlabel("Date")
    plt.ylabel("Occupied beds")
    plt.legend(fontsize="small", ncol=2)
    plt.grid(alpha=0.25)
    plt.tight_layout()
    plt.savefig(OUT_PNG, dpi=150)
    plt.close()
    print(f"Saved {OUT_PNG}")


if __name__ == "__main__":
    main()
