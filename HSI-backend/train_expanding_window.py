"""
Train the staffing forecast model using the expanding window approach (48 iterations).
Run this from the command line: python train_expanding_window.py
"""

import pandas as pd
import sys
import os

# Add backend directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from main import historical_data, filter_through_as_of_date
from forecast_engine import run_generic_forecast


def train_expanding_window(model_preference: str = "prophet", as_of_date: str = None):
    """
    Run the 48-iteration expanding window forecast for staffing.
    
    Args:
        model_preference: "prophet", "arimax", "xgboost", or None (auto-select)
        as_of_date: Optional date string to filter data (e.g., "2026-05-16")
    """
    print(f"=== Expanding Window Staffing Forecast Training ===")
    print(f"Model preference: {model_preference or 'auto-select'}")
    print(f"As of date: {as_of_date or 'latest'}")
    print()
    
    df = historical_data.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    
    if df.empty or "labour_staffing" not in df.columns:
        print("ERROR: No data available or labour_staffing column missing")
        return
    
    # Apply as_of_date filter
    scoped = filter_through_as_of_date(df, as_of_date)
    if scoped.empty:
        print("ERROR: No data available for the selected date")
        return
    
    # Sort dates
    all_dates = sorted(scoped["date"].dt.normalize().unique())
    print(f"Total dates available: {len(all_dates)}")
    print(f"Date range: {all_dates[0].date()} → {all_dates[-1].date()}")
    print()
    
    if len(all_dates) < 364 + 84:
        print(f"ERROR: Insufficient data. Need at least {364 + 84} days (Year 1 + 12 weeks), got {len(all_dates)}")
        return
    
    # Year 1 end date (364 days from start)
    year1_end_date = all_dates[363]
    year2_dates = [d for d in all_dates if d > year1_end_date]
    
    if len(year2_dates) < 48 * 7:
        print(f"WARNING: Only {len(year2_dates)} days in Year 2, need {48 * 7} for 48 iterations")
        print("Proceeding with available iterations...")
        max_iterations = len(year2_dates) // 7
    else:
        max_iterations = 48
    
    print(f"Year 1 end: {year1_end_date.date()}")
    print(f"Year 2 days: {len(year2_dates)}")
    print(f"Max iterations: {max_iterations}")
    print()
    
    # Storage for week-specific predictions
    week1_preds = []
    week2_preds = []
    week3_preds = []
    all_forecast_points = []
    
    # 48 iterations
    for i in range(max_iterations):
        print(f"[{i+1}/{max_iterations}] Training...", end=" ", flush=True)
        
        train_end_idx = 364 + (i * 7)
        if train_end_idx >= len(all_dates):
            print("SKIPPED (insufficient data)")
            break
        
        train_end_date = all_dates[train_end_idx]
        
        # Training data: from start to train_end_date
        training_df = scoped[scoped["date"].dt.normalize() <= train_end_date]
        if training_df.empty or training_df["date"].dt.normalize().nunique() < 52:
            print("SKIPPED (insufficient unique dates)")
            continue
        
        # Aggregate daily
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
        
        # Predict 12 weeks (84 days)
        try:
            block_fc = run_generic_forecast(
                daily_train, 84, "labour_staffing",
                "Hospital Labour Staffing", model_preference,
            )
        except Exception as exc:
            print(f"FAILED: {exc}")
            continue
        
        block_points = block_fc.get("forecast_data", []) or []
        if not block_points:
            print("SKIPPED (no predictions)")
            continue
        
        # Store predictions by week-out horizon
        for idx, point in enumerate(block_points):
            date_str = point["date"]
            value = point["predicted_value"]
            
            all_forecast_points.append({
                "date": date_str,
                "predicted_value": value,
                "iteration": i + 1,
            })
            
            if 0 <= idx < 7:  # Week 1
                week1_preds.append({"date": date_str, "predicted_value": value, "iteration": i + 1})
            elif 7 <= idx < 14:  # Week 2
                week2_preds.append({"date": date_str, "predicted_value": value, "iteration": i + 1})
            elif 14 <= idx < 21:  # Week 3
                week3_preds.append({"date": date_str, "predicted_value": value, "iteration": i + 1})
        
        print(f"DONE (predicted {len(block_points)} days)")
    
    print()
    print("=== Training Complete ===")
    print(f"Iterations completed: {len(all_forecast_points) // 84 if all_forecast_points else 0}")
    print(f"Total prediction points: {len(all_forecast_points)}")
    print(f"Week 1 predictions: {len(week1_preds)}")
    print(f"Week 2 predictions: {len(week2_preds)}")
    print(f"Week 3 predictions: {len(week3_preds)}")
    print()
    
    # Calculate MAPE per week-out horizon
    actual_daily = (
        scoped.groupby(scoped["date"].dt.strftime("%Y-%m-%d"))["labour_staffing"].sum()
        if "labour_staffing" in scoped.columns else pd.Series(dtype=float)
    )
    
    def calc_mape(preds):
        errors = [
            abs(actual_daily[p["date"]] - p["predicted_value"]) / actual_daily[p["date"]]
            for p in preds
            if p["date"] in actual_daily.index and actual_daily[p["date"]] > 0
        ]
        return round(float(pd.Series(errors).mean()) * 100, 2) if errors else 0.0
    
    week1_mape = calc_mape(week1_preds)
    week2_mape = calc_mape(week2_preds)
    week3_mape = calc_mape(week3_preds)
    
    print("=== Week-Out Horizon Accuracy ===")
    print(f"Week 1 MAPE: {week1_mape}%")
    print(f"Week 2 MAPE: {week2_mape}%")
    print(f"Week 3 MAPE: {week3_mape}%")
    print()
    
    # Save results to CSV
    output_dir = "deep_dive_outputs"
    os.makedirs(output_dir, exist_ok=True)
    
    timestamp = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
    
    # Save week-specific predictions
    if week1_preds:
        pd.DataFrame(week1_preds).to_csv(
            f"{output_dir}/expanding_window_week1_{timestamp}.csv", index=False
        )
        print(f"Saved: {output_dir}/expanding_window_week1_{timestamp}.csv")
    
    if week2_preds:
        pd.DataFrame(week2_preds).to_csv(
            f"{output_dir}/expanding_window_week2_{timestamp}.csv", index=False
        )
        print(f"Saved: {output_dir}/expanding_window_week2_{timestamp}.csv")
    
    if week3_preds:
        pd.DataFrame(week3_preds).to_csv(
            f"{output_dir}/expanding_window_week3_{timestamp}.csv", index=False
        )
        print(f"Saved: {output_dir}/expanding_window_week3_{timestamp}.csv")
    
    # Save summary
    summary = pd.DataFrame([{
        "model_preference": model_preference or "auto",
        "iterations_completed": len(all_forecast_points) // 84 if all_forecast_points else 0,
        "week1_mape": week1_mape,
        "week2_mape": week2_mape,
        "week3_mape": week3_mape,
        "as_of_date": as_of_date or "latest",
        "timestamp": timestamp,
    }])
    summary.to_csv(f"{output_dir}/expanding_window_summary_{timestamp}.csv", index=False)
    print(f"Saved: {output_dir}/expanding_window_summary_{timestamp}.csv")
    
    print()
    print("Recommendation:")
    if week1_mape <= week2_mape and week1_mape <= week3_mape:
        print("  → Week 1 horizon has the best accuracy (lowest MAPE)")
    elif week2_mape <= week1_mape and week2_mape <= week3_mape:
        print("  → Week 2 horizon has the best accuracy (lowest MAPE)")
    else:
        print("  → Week 3 horizon has the best accuracy (lowest MAPE)")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Train staffing forecast using expanding window approach")
    parser.add_argument("--model", type=str, default="all",
                        help="Model preference: prophet, arimax, xgboost, auto, or all (default: all)")
    parser.add_argument("--as-of-date", type=str, default=None,
                        help="Filter data up to this date (YYYY-MM-DD, default: latest)")
    
    args = parser.parse_args()
    
    models_to_train = []
    if args.model == "all":
        models_to_train = ["prophet", "arimax", "xgboost"]
    elif args.model == "auto":
        models_to_train = [None]
    else:
        models_to_train = [args.model]
    
    print(f"=== Training {len(models_to_train)} model(s) ===")
    print()
    
    for model in models_to_train:
        model_name = model if model else "auto"
        print(f"\n{'='*60}")
        print(f"Training model: {model_name}")
        print(f"{'='*60}\n")
        train_expanding_window(model, args.as_of_date)
        print()
    
    print(f"\n{'='*60}")
    print("All training complete!")
    print(f"{'='*60}\n")
