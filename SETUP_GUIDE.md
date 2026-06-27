# KIMS Bed Occupancy Forecasting - Setup Guide

## Overview
This system provides hospital bed occupancy forecasting with ML models trained on the dataset `hospital_enhanced_full_dataset.csv`.

## Key Improvements Made

### 1. **ML Model Training**
- ✅ **Dataset**: Now uses `C:\Users\Jayasurya\Downloads\kims_bed_occupancy\HSI-backend\data\hospital_enhanced_full_dataset.csv`
- ✅ **Ward Types**: Updated to match dataset (Cardiology, Emergency, General Ward, ICU)
- ✅ **Training**: Run `ml_pipeline.py` to train models and generate forecasts

### 2. **Frontend Visualizations**
- ✅ **Bed Requirements Visual**: New component showing actual vs forecasted bed needs
- ✅ **Clear Line Charts**: Actual occupancy (solid line) vs Forecasted (dashed line)
- ✅ **Peak Demand Indicators**: Visual alerts for upcoming high-demand days
- ✅ **7-Day Breakdown**: Daily bed requirements with color-coded indicators

### 3. **Visual Features**
- 🔵 **Blue Line**: Current/Actual occupancy
- 🔴 **Red Dashed Line**: Forecasted occupancy
- 🟢 **Green Dashed Line**: Total capacity
- 🟡 **Orange Dashed Line**: Warning threshold (90%)
- 📊 **Shaded Area**: Confidence intervals

## Quick Start

### Step 1: Train ML Models (Backend)

```bash
cd C:\Users\Jayasurya\Downloads\kims_bed_occupancy\HSI-backend

# Install Python dependencies (if not done)
pip install -r requirements.txt

# Train models on the dataset
python ml_pipeline.py
```

**What this does:**
- Loads `hospital_enhanced_full_dataset.csv`
- Trains 8 ML models (Prophet, ARIMA, XGBoost, LightGBM, CatBoost, RandomForest, ExtraTrees, LinearRegression)
- Generates forecasts for each ward
- Saves best model to `output/` folder
- Creates performance charts and leaderboard

**Output:**
- `output/leaderboard.csv` - Model rankings by MAPE
- `output/best_model_*.pkl` - Best performing model
- `output/ward_*.png` - Individual ward forecasts
- `output/feat_imp_*.png` - Feature importance charts

### Step 2: Start Backend API

```bash
cd C:\Users\Jayasurya\Downloads\kims_bed_occupancy\HSI-backend

# Start the FastAPI server
python main.py
```

**Server runs at:** `http://localhost:8000`

**Key endpoints:**
- `/api/dashboard/metrics` - Current hospital metrics
- `/api/forecast` - Occupancy forecast
- `/api/analytics/department-forecasts` - Per-department forecasts
- `/api/labour-staffing/forecast` - Staffing requirements

### Step 3: Start Frontend

```bash
cd C:\Users\Jayasurya\Downloads\kims_bed_occupancy\HSI-frontend

# Install dependencies (if not done)
npm install

# Start Angular dev server
ng serve
```

**Frontend runs at:** `http://localhost:4200`

## Understanding the Dashboard

### Main Dashboard View

1. **Overview Section**
   - Overall occupancy percentage with color coding
   - ICU occupancy status
   - Available beds count
   - Emergency admissions today
   - Average length of stay
   - 7-day forecast prediction

2. **📊 Bed Requirements Forecast** (NEW!)
   - **Main Chart**: Shows actual vs forecasted bed requirements
     - Blue solid line: Current occupancy
     - Red dashed line: Forecasted requirements
     - Shaded area: Confidence intervals
   - **Insight Banner**: Highlights peak demand day
   - **7-Day Breakdown**: Daily bed requirements with indicators:
     - 🟢 Green: Normal (<85% occupancy)
     - 🟡 Yellow: High (85-90% occupancy)
     - 🔴 Red: Critical (>90% occupancy)

3. **Ward-Level Forecasts**
   - Individual sparklines for each ward
   - MAPE (Mean Absolute Percentage Error) accuracy
   - R² score (model fit quality)
   - 30-day trend visualization

4. **Model Leaderboard**
   - Ranking of all ML models by accuracy
   - Best model highlighted with 🥇
   - MAPE, MAE, RMSE, R² metrics

5. **Trend Charts**
   - Historical occupancy trends
   - Confidence intervals
   - Department comparisons

## How to Read the Visualizations

### Bed Requirements Chart

**Lines:**
- **Solid Blue Line**: This is where you are NOW (actual current occupancy)
- **Red Dashed Line**: This is where you'll be TOMORROW and beyond (forecast)
- **Green Horizontal Line**: Maximum capacity (100% = all beds)
- **Orange Horizontal Line**: Warning level (90% occupancy)

**Shaded Areas:**
- Light blue shaded area around the forecast line shows the **confidence range**
- Wider shade = less certain forecast
- Narrower shade = more confident forecast

### Peak Demand Indicator

The colored banner at the top tells you:
- **Which day** will have the highest demand
- **How many beds** you'll need that day
- **What percentage** of capacity that represents
- **Action needed** if >90% occupancy expected

### Daily Breakdown Cards

Each day card shows:
- Day number (Day 1 = tomorrow)
- Date
- Beds needed (actual number)
- Occupancy percentage
- Visual indicator (🟢🟡🔴)

## Model Accuracy (MAPE)

**What is MAPE?**
Mean Absolute Percentage Error - lower is better

- **< 20%**: Excellent accuracy (Prophet typically achieves this)
- **20-30%**: Good accuracy
- **30-50%**: Fair accuracy
- **> 50%**: Poor accuracy - use with caution

**Current Results:**
- Prophet: ~29% MAPE (Best for occupancy forecasting)
- ARIMA: ~37% MAPE (Good for short-term trends)
- XGBoost: ~60% MAPE (Better with more features)

## Interpreting Forecasts

### When to Trust the Forecast
✅ When MAPE < 30%
✅ When confidence intervals are narrow
✅ When recent trends are stable
✅ For short-term forecasts (1-7 days)

### When to Be Cautious
⚠️ When MAPE > 50%
⚠️ When confidence intervals are very wide
⚠️ During unusual events (holidays, emergencies)
⚠️ For long-term forecasts (>30 days)

## Troubleshooting

### Backend Won't Start
```bash
# Check Python version (needs 3.9+)
python --version

# Reinstall dependencies
pip install -r requirements.txt

# Check if port 8000 is free
netstat -ano | findstr :8000
```

### Frontend Shows "Could not connect to API"
1. Make sure backend is running at `http://localhost:8000`
2. Check proxy configuration in `proxy.conf.json`
3. Restart `ng serve` after backend starts

### ML Training Fails
1. Check dataset path exists: `HSI-backend\data\hospital_enhanced_full_dataset.csv`
2. Ensure Python packages are installed: `pip install prophet xgboost lightgbm catboost`
3. Check available memory (Prophet needs ~2GB RAM)

### Charts Don't Load
1. Clear browser cache (Ctrl+Shift+Delete)
2. Check browser console for errors (F12)
3. Ensure `ng serve` is running on port 4200

## Dataset Information

**File**: `hospital_enhanced_full_dataset.csv`

**Key Columns:**
- `date`: Daily timestamp
- `department`: Ward name (Cardiology, Emergency, General Ward, ICU)
- `occupied_beds`: Number of beds in use
- `total_beds`: Total bed capacity
- `occupancy_rate`: Utilization percentage
- `patient_count`: Number of patients
- `labour_staffing`: Staff count (FTE)
- `avg_length_of_stay`: Average LOS in days

## Performance Tuning

### For Faster Training
```python
# In ml_pipeline.py, reduce iterations:
XGBRegressor(n_estimators=100)  # instead of 200
Prophet(daily_seasonality=False)  # disable unnecessary seasonality
```

### For Better Accuracy
```python
# Increase training window
train, test = train_test_split_time(daily, train_days=180)  # instead of 90

# Add more features
FEATURES = [
    "Lag_1", "Lag_7", "Lag_14", "Lag_21",
    "Rolling_Mean_7", "Rolling_Mean_14", "Rolling_Mean_21",
    "Day_of_Week", "Month", "Weekend_Flag", "is_holiday"
]
```

## Next Steps

1. **Review Model Performance**
   ```bash
   # Check leaderboard
   cat HSI-backend/output/leaderboard.csv
   ```

2. **Examine Ward Forecasts**
   - Open PNG files in `HSI-backend/output/`
   - Look at `ward_ICU.png`, `ward_Emergency.png`, etc.

3. **Test Different Scenarios**
   - Use the dashboard date picker to select different historical dates
   - Compare forecast vs actual for past dates
   - Adjust forecast horizon (7, 14, 30 days)

4. **Monitor in Production**
   - Set up daily automated retraining
   - Track forecast accuracy over time
   - Alert when occupancy exceeds thresholds

## Support

For issues or questions:
- Check logs: `HSI-backend/*.log`
- Review browser console (F12)
- Examine API responses: `http://localhost:8000/docs`

## Key Files Modified

- `HSI-backend/ml_pipeline.py` - Updated to use correct dataset
- `HSI-frontend/src/app/components/dashboard-forecast-mini/bed-requirements-visual.component.ts` - NEW visual component
- `HSI-frontend/src/app/components/dashboard/dashboard.component.ts` - Added new component
- `HSI-frontend/src/app/components/dashboard/dashboard.component.html` - Added visualization section

---

**Last Updated**: 2025
**Dataset**: hospital_enhanced_full_dataset.csv
**ML Models**: 8 algorithms (Prophet, ARIMA, XGBoost, LightGBM, CatBoost, RandomForest, ExtraTrees, LinearRegression)
