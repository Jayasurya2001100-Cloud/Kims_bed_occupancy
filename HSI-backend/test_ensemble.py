"""
Test ensemble models (Prophet + ARIMAX + XGBoost) to reduce MAPE.
Usage: python3 test_ensemble.py
"""

import pandas as pd
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from main import historical_data, filter_through_as_of_date
from forecast_engine import run_generic_forecast


def test_ensemble(as_of_date: str = None):
    """Test ensemble of Prophet + ARIMAX + XGBoost."""
    
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
    print(f"Ensemble Model Test (60-day train → 21-day predict)")
    print(f"{'='*60}\n")
    
    train_days = 60
    block_days = 21
    models = ["prophet", "arimax", "xgboost"]
    
    window_start_date = window_dates[0]
    first_pred_date = window_start_date + pd.Timedelta(days=train_days)
    
    # Store predictions for each model
    model_predictions = {model: {} for model in models}
    
    for model in models:
        print(f"\n--- Training {model.upper()} ---")
        
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
                    "Hospital Labour Staffing", model,
                )
            except Exception as exc:
                continue
            
            block_points = block_fc.get("forecast_data", []) or []
            if not block_points:
                continue
            
            for point in block_points:
                date_str = point["date"]
                pred = point["predicted_value"]
                if date_str not in model_predictions[model]:
                    model_predictions[model][date_str] = []
                model_predictions[model][date_str].append(pred)
        
        # Average predictions per date
        for date_str in model_predictions[model]:
            model_predictions[model][date_str] = sum(model_predictions[model][date_str]) / len(model_predictions[model][date_str])
        
        # Calculate MAPE
        actual_daily = window_df.groupby(window_df["date"].dt.strftime("%Y-%m-%d"))["labour_staffing"].sum()
        
        errors = []
        for date_str, pred in model_predictions[model].items():
            if date_str in actual_daily.index and actual_daily[date_str] > 0:
                errors.append(abs(actual_daily[date_str] - pred) / actual_daily[date_str])
        
        mape = round(float(pd.Series(errors).mean()) * 100, 2) if errors else 0.0
        print(f"MAPE: {mape:.2f}%")
        print(f"Prediction points: {len(model_predictions[model])}")
    
    # Ensemble: average all three models
    print(f"\n--- Ensemble (Average of all 3 models) ---")
    
    all_dates = set()
    for model in models:
        all_dates.update(model_predictions[model].keys())
    
    ensemble_predictions = {}
    for date_str in sorted(all_dates):
        preds = []
        for model in models:
            if date_str in model_predictions[model]:
                preds.append(model_predictions[model][date_str])
        if preds:
            ensemble_predictions[date_str] = sum(preds) / len(preds)
    
    actual_daily = window_df.groupby(window_df["date"].dt.strftime("%Y-%m-%d"))["labour_staffing"].sum()
    
    errors = []
    for date_str, pred in ensemble_predictions.items():
        if date_str in actual_daily.index and actual_daily[date_str] > 0:
            errors.append(abs(actual_daily[date_str] - pred) / actual_daily[date_str])
    
    ensemble_mape = round(float(pd.Series(errors).mean()) * 100, 2) if errors else 0.0
    print(f"Ensemble MAPE: {ensemble_mape:.2f}%")
    print(f"Prediction points: {len(ensemble_predictions)}")
    
    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    
    for model in models:
        actual_daily = window_df.groupby(window_df["date"].dt.strftime("%Y-%m-%d"))["labour_staffing"].sum()
        errors = []
        for date_str, pred in model_predictions[model].items():
            if date_str in actual_daily.index and actual_daily[date_str] > 0:
                errors.append(abs(actual_daily[date_str] - pred) / actual_daily[date_str])
        mape = round(float(pd.Series(errors).mean()) * 100, 2) if errors else 0.0
        print(f"{model.upper():<10} MAPE: {mape:.2f}%")
    
    print(f"{'ENSEMBLE':<10} MAPE: {ensemble_mape:.2f}%")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Test ensemble models")
    parser.add_argument("--as-of-date", type=str, default=None,
                        help="Filter data up to date (YYYY-MM-DD)")
    
    args = parser.parse_args()
    
    test_ensemble(args.as_of_date)
