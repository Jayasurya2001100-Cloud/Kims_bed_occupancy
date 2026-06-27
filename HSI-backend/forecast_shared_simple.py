"""
Simple bed occupancy forecast using the shared dataset.
Focuses on core Prophet forecasting with lightweight outputs.
Avoids heavy ML pipeline imports to prevent memory overflow.
"""
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
from datetime import timedelta

from forecast_engine import run_occupancy_forecast

ROOT = Path(__file__).resolve().parent
DATA_PATH = ROOT / "data" / "hospital_enhanced_full_dataset.csv"
OUT_DIR = ROOT / "output_shared_dataset"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def load_shared_data(path: Path) -> pd.DataFrame:
    """Load the shared dataset with minimal memory overhead."""
    df = pd.read_csv(path, dtype={
        'date': str,
        'occupied_beds': 'float32',
        'total_beds': 'float32',
        'occupancy_rate': 'float32',
    })
    df['date'] = pd.to_datetime(df['date'])
    return df


def aggregate_hospital_level(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate to hospital-level daily data."""
    agg = (
        df.groupby('date', as_index=False)
        .agg(
            occupied_beds=('occupied_beds', 'sum'),
            total_beds=('total_beds', 'sum'),
        )
    )
    agg['occupancy_rate'] = (agg['occupied_beds'] / agg['total_beds']).clip(0.0, 0.9999)
    return agg.sort_values('date').reset_index(drop=True)


def main():
    print("Loading shared dataset...")
    df = load_shared_data(DATA_PATH)
    print(f"  Loaded {len(df)} records")

    print("Aggregating to hospital level...")
    daily = aggregate_hospital_level(df)
    print(f"  Aggregated to {len(daily)} days")
    daily.to_csv(OUT_DIR / "hospital_daily_aggregated.csv", index=False)

    last_date = daily['date'].max()
    print(f"  Latest date: {last_date.date()}")

    # Run Prophet forecast
    print("Running Prophet forecast on occupancy...")
    result = run_occupancy_forecast(
        daily,
        days=90,
        department_label="Hospital Bed Occupancy",
        model_preference="prophet",
    )

    forecast_df = pd.DataFrame(result['forecast_data'])
    forecast_df['date'] = pd.to_datetime(forecast_df['date'])
    
    print(f"  Forecast generated: {len(forecast_df)} rows")
    print(f"  Model: {result['forecast_model']}")
    print(f"  Metrics: {result['model_metrics']}")

    # Extract last 30 days comparison
    compare_start = last_date - timedelta(days=29)
    actual_last_30 = daily[daily['date'] >= compare_start].copy()
    forecast_last_30 = forecast_df[forecast_df['date'] >= compare_start].copy()

    comparison = actual_last_30[['date', 'occupied_beds', 'occupancy_rate']].copy()
    comparison = comparison.merge(
        forecast_last_30[['date', 'predicted_occupancy_rate', 'predicted_occupied_beds']],
        on='date',
        how='left'
    )

    comparison.to_csv(OUT_DIR / "forecast_comparison_last_30_days.csv", index=False)
    forecast_df.to_csv(OUT_DIR / "forecast_next_90_days.csv", index=False)

    # Save Excel report
    print("Creating Excel report...")
    with pd.ExcelWriter(OUT_DIR / "bed_occupancy_forecast_report.xlsx", engine='openpyxl') as writer:
        comparison.to_excel(writer, sheet_name='Last 30 Days', index=False)
        forecast_df.to_excel(writer, sheet_name='Next 90 Days Forecast', index=False)
        
        summary_data = {
            'Metric': [
                'Latest Date',
                'Forecast Days',
                'Model Used',
                'MAPE',
                'MAE',
                'RMSE',
            ],
            'Value': [
                str(last_date.date()),
                len(forecast_df),
                result['forecast_model'],
                result['model_metrics'].get('MAPE', 'N/A'),
                result['model_metrics'].get('MAE', 'N/A'),
                result['model_metrics'].get('RMSE', 'N/A'),
            ]
        }
        summary_df = pd.DataFrame(summary_data)
        summary_df.to_excel(writer, sheet_name='Summary', index=False)

    # Plot 1: Last 30 days comparison
    print("Creating comparison plot (last 30 days)...")
    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(comparison['date'], comparison['occupancy_rate'], 
            marker='o', label='Actual Occupancy Rate', linewidth=2, color='#1f77b4')
    ax.plot(comparison['date'], comparison['predicted_occupancy_rate'], 
            marker='x', label='Forecast Occupancy Rate', linewidth=2, color='#ff7f0e', linestyle='--')
    ax.set_title('Hospital Bed Occupancy - Actual vs Forecast (Last 30 Days)', fontsize=14, fontweight='bold')
    ax.set_xlabel('Date', fontsize=11)
    ax.set_ylabel('Occupancy Rate', fontsize=11)
    ax.legend(fontsize=10)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "occupancy_comparison_last_30_days.png", dpi=150, bbox_inches='tight')
    plt.close(fig)

    # Plot 2: Next 90 days forecast
    print("Creating forecast plot (next 90 days)...")
    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(forecast_df['date'], forecast_df['predicted_occupancy_rate'], 
            label='Forecast Occupancy Rate', linewidth=2, color='#2ca02c')
    
    if 'lower_bound' in forecast_df.columns and 'upper_bound' in forecast_df.columns:
        ax.fill_between(
            forecast_df['date'],
            forecast_df['lower_bound'],
            forecast_df['upper_bound'],
            alpha=0.2,
            color='#2ca02c',
            label='95% Confidence Interval'
        )
    
    ax.set_title('Hospital Bed Occupancy Forecast (Next 90 Days)', fontsize=14, fontweight='bold')
    ax.set_xlabel('Date', fontsize=11)
    ax.set_ylabel('Occupancy Rate', fontsize=11)
    ax.legend(fontsize=10)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "occupancy_forecast_next_90_days.png", dpi=150, bbox_inches='tight')
    plt.close(fig)

    # Plot 3: Occupied beds comparison
    print("Creating occupied beds plot...")
    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(comparison['date'], comparison['occupied_beds'], 
            marker='o', label='Actual Occupied Beds', linewidth=2, color='#d62728')
    
    if 'predicted_occupied_beds' in comparison.columns:
        ax.plot(comparison['date'], comparison['predicted_occupied_beds'], 
                marker='x', label='Forecast Occupied Beds', linewidth=2, color='#9467bd', linestyle='--')
    
    ax.set_title('Hospital Occupied Beds - Actual vs Forecast (Last 30 Days)', fontsize=14, fontweight='bold')
    ax.set_xlabel('Date', fontsize=11)
    ax.set_ylabel('Number of Beds', fontsize=11)
    ax.legend(fontsize=10)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "occupied_beds_comparison_last_30_days.png", dpi=150, bbox_inches='tight')
    plt.close(fig)

    print("\n✓ Forecast Complete!")
    print(f"\nOutput files saved to: {OUT_DIR}")
    print("\nGenerated files:")
    for file in sorted(OUT_DIR.glob('*')):
        if file.is_file():
            size_kb = file.stat().st_size / 1024
            print(f"  - {file.name:<45} ({size_kb:.1f} KB)")

    print("\n" + "="*70)
    print("FORECAST SUMMARY")
    print("="*70)
    print(f"Latest data date:        {last_date.date()}")
    print(f"Forecast period:         90 days forward")
    print(f"Model:                   {result['forecast_model']}")
    print(f"Comparison period:       Last 30 days")
    print(f"Last 30 days avg occ:    {comparison['occupancy_rate'].mean():.2%}")
    print(f"Forecast avg occ (90d):  {forecast_df['predicted_occupancy_rate'].mean():.2%}")
    print("="*70)


if __name__ == "__main__":
    main()
