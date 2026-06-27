"""
Test different training window sizes to find optimal MAPE.
Usage: python3 optimize_train_window.py --model prophet
"""

import pandas as pd
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from main import historical_data, filter_through_as_of_date
from forecast_engine import run_generic_forecast


def test_train_window(model_preference: str = "prophet", as_of_date: str = None):
    """Test different training window sizes (60, 90, 120, 180 days)."""
    
    df = historical_data.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    
    if df.empty or "labour_staffing" not in df.columns:
        print("ERROR: No data available")
        return
    
    scoped = filter_through_as_of_date(df, as_of_date)
    if scoped.empty:
        print("ERROR: No data for selected date")
        return
    
    # Filter to 730 days
    end = scoped["date"].dt.normalize().max()
    start = end - pd.Timedelta(days=729)
    window_df = scoped[scoped["date"].dt.normalize() >= start].copy()
    
    window_dates = sorted(window_df["date"].dt.normalize().unique())
    if not window_dates:
        print("ERROR: No valid dates")
        return
    
    print(f"Testing on {len(window_dates)} days of data\n")
    print(f"{'='*60}")
    print(f"Training Window Size Optimization ({model_preference})")
    print(f"{'='*60}\n")
    
    results = []
    block_days = 21
    
    for train_days in [60, 90, 120, 180]:
        print(f"\n--- Train Days: {train_days} ---")
        
        window_start_date = window_dates[0]
        first_pred_date = window_start_date + pd.Timedelta(days=train_days)
        
        forecast_points = []
        
        for start_idx in range(0, len(window_dates), block_days):
            block_start = window_dates[start_idx]
            
            if block_start < first_pred_date:
                continue
            
            block_horizon = min(block_days, len(window_dates) - start_idx)
            train_end = block_start - pd.Timedelta(days=1)
            train_start = block_start - pd.Timedelta(days=train_days)
            
            training_df = window_df[
                (window_df["date"].dt.normalize() >= train_start) &
                (window_df["date"].dt.normalize() <= train_end)
            ]
            
            if training_df.empty or training_df["date"].dt.normalize().nunique() < 8:
                continue
            
            agg_cols = {"labour_staffing": "sum", "total_beds": "sum"}
            if "patient_count" in training_df.columns:
                agg_cols["patient_count"] = "sum"
            daily_train = (
                training_df.groupby("date")
                .agg(agg_cols)
                .reset_index()
                .sort_values("date")
                .reset_index(drop=True)
            )
            
            try:
                block_fc = run_generic_forecast(
                    daily_train, block_horizon, "labour_staffing",
                    "Hospital Labour Staffing", model_preference,
                )
            except Exception as exc:
                continue
            
            block_points = block_fc.get("forecast_data", []) or []
            if not block_points:
                continue
            
            for point in block_points:
                forecast_points.append(point)
        
        # Calculate MAPE
        actual_daily = window_df.groupby(window_df["date"].dt.strftime("%Y-%m-%d"))["labour_staffing"].sum()
        
        errors = []
        for point in forecast_points:
            date_str = point["date"]
            pred = point["predicted_value"]
            if date_str in actual_daily.index and actual_daily[date_str] > 0:
                errors.append(abs(actual_daily[date_str] - pred) / actual_daily[date_str])
        
        mape = round(float(pd.Series(errors).mean()) * 100, 2) if errors else 0.0
        print(f"MAPE: {mape:.2f}%")
        print(f"Prediction points: {len(forecast_points)}")
        
        results.append({"train_days": train_days, "mape": mape, "points": len(forecast_points)})
    
    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(f"{'Train Days':<12} {'MAPE':<10} {'Points':<10}")
    print("-" * 35)
    for r in results:
        print(f"{r['train_days']:<12} {r['mape']:<10.2f} {r['points']:<10}")
    
    best = min(results, key=lambda x: x["mape"])
    print(f"\nBest: {best['train_days']} days with MAPE = {best['mape']}%")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Optimize training window size")
    parser.add_argument("--model", type=str, default="prophet",
                        help="Model: prophet, arimax, xgboost")
    parser.add_argument("--as-of-date", type=str, default=None,
                        help="Filter data up to date (YYYY-MM-DD)")
    
    args = parser.parse_args()
    
    test_train_window(args.model, args.as_of_date)
