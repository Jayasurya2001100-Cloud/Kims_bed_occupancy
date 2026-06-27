# KIMS Hospital Bed Occupancy Forecasting System

> AI-powered bed occupancy forecasting with clear visual predictions

## 🚀 Quick Start

### Windows Quick Start (Recommended)
1. **Double-click** `START.bat`
2. Choose **option 1** (Train Models) - first time only
3. Choose **option 4** (Start Both Servers)
4. Open browser: `http://localhost:4200`

### Manual Start
```bash
# 1. Train ML models (first time only)
cd HSI-backend
python ml_pipeline.py

# 2. Start backend (Terminal 1)
cd HSI-backend
python main.py

# 3. Start frontend (Terminal 2)
cd HSI-frontend
ng serve

# 4. Open browser
# http://localhost:4200
```

## 📊 What You Get

### Visual Dashboard
- **Actual vs Forecast Chart**: Clear blue (actual) and red (forecast) lines
- **Peak Demand Indicator**: Automatically highlights highest demand day
- **7-Day Breakdown**: Exact bed requirements per day
- **Color-Coded Alerts**: 🟢 Green (safe) | 🟡 Yellow (monitor) | 🔴 Red (critical)

### ML Forecasting
- **8 Models**: Prophet, ARIMA, XGBoost, LightGBM, CatBoost, RandomForest, ExtraTrees, Linear Regression
- **Best Model**: Prophet (29% MAPE accuracy)
- **Forecast Horizon**: 7-30 days ahead
- **Confidence Intervals**: Shows prediction uncertainty

### Department-Level Insights
- Individual forecasts for ICU, Emergency, Cardiology, General Ward
- Sparkline trends for 30-day patterns
- Staffing requirement predictions

## 📁 Project Structure

```
kims_bed_occupancy/
├── START.bat                   # 🎯 Quick start script
├── SETUP_GUIDE.md             # 📖 Detailed setup instructions
├── VISUAL_GUIDE.md            # 🎨 How to read the charts
├── IMPROVEMENTS_SUMMARY.md    # ✅ What was improved
│
├── HSI-backend/               # Python + FastAPI
│   ├── data/
│   │   └── hospital_enhanced_full_dataset.csv  # Your dataset
│   ├── ml_pipeline.py         # Train ML models
│   └── main.py                # API server
│
└── HSI-frontend/              # Angular + Chart.js
    └── src/app/components/
        └── dashboard/         # Main dashboard with new visuals
```

## 🎯 Key Features

### ✅ What This System Does

1. **Predicts Bed Requirements**
   - Shows how many beds you'll need each day
   - Up to 30 days in advance
   - Department-specific forecasts

2. **Visual Clarity**
   - Actual occupancy (blue solid line)
   - Forecasted occupancy (red dashed line)
   - Peak demand highlighted in banner
   - Daily breakdown with indicators

3. **Actionable Insights**
   - "Day 5: Need 127 beds (85% occupancy) - Monitor closely"
   - Color-coded warnings (green/yellow/red)
   - Confidence intervals (how certain the forecast is)

### 📈 How It Works

1. **Data Source**: `hospital_enhanced_full_dataset.csv` (2 years of hospital data)
2. **ML Training**: 8 different algorithms compete for best accuracy
3. **Best Model Selection**: Prophet wins with 29% MAPE (Mean Absolute Percentage Error)
4. **Live Dashboard**: Real-time predictions displayed with clear visuals

## 📖 Documentation

| File | Purpose |
|------|---------|
| [SETUP_GUIDE.md](SETUP_GUIDE.md) | Complete installation and setup |
| [VISUAL_GUIDE.md](VISUAL_GUIDE.md) | How to read the dashboard |
| [IMPROVEMENTS_SUMMARY.md](IMPROVEMENTS_SUMMARY.md) | What was changed and why |

## 🔍 Understanding the Forecast

### Main Chart Components

```
┌─────────────────────────────────────────┐
│ [Peak Demand Banner]                     │
│ "Day 5: 127 beds needed (85%)"          │
├─────────────────────────────────────────┤
│                                          │
│  ─── Actual (Blue)                      │
│  ╱                                       │
│ ╱    - - - Forecast (Red)               │
│╱                                         │
│      ∙∙∙∙∙ Warning 90% (Orange)        │
│      ───── Capacity (Green)             │
│                                          │
├─────────────────────────────────────────┤
│ Day 1 │ Day 2 │ Day 3 │ Day 4 │ Day 5  │
│ 115   │ 118   │ 122   │ 125   │ 127    │
│ 🟢    │ 🟢    │ 🟢    │ 🟢    │ 🟡     │
└─────────────────────────────────────────┘
```

### Color Indicators
- 🟢 **Green** (< 85%): Safe level - Normal operations
- 🟡 **Yellow** (85-90%): High occupancy - Monitor closely
- 🔴 **Red** (> 90%): Critical level - Action required

### Forecast Accuracy
- **Excellent** (< 20% MAPE): Trust for decisions
- **Good** (20-30% MAPE): Use for planning ← Prophet is here
- **Fair** (30-50% MAPE): Guidance only
- **Poor** (> 50% MAPE): Use with caution

## ⚙️ Requirements

### Backend
- Python 3.9 or higher
- Packages: FastAPI, Prophet, XGBoost, LightGBM, CatBoost, pandas, numpy

### Frontend
- Node.js 18 or higher
- Angular CLI 17+
- Modern web browser (Chrome, Firefox, Edge)

### System
- Windows 10/11 (batch script provided)
- 4GB RAM minimum (8GB recommended)
- Internet connection (first-time setup)

## 🆘 Troubleshooting

### Backend Won't Start
```bash
# Check Python version
python --version

# Reinstall dependencies
cd HSI-backend
pip install -r requirements.txt
```

### Frontend Shows "Cannot connect to API"
1. Make sure backend is running: `http://localhost:8000`
2. Check proxy config in `HSI-frontend/proxy.conf.json`
3. Restart frontend: `ng serve`

### Charts Not Displaying
1. Clear browser cache (Ctrl+Shift+Delete)
2. Check browser console (F12) for errors
3. Verify both servers are running

### For More Help
- Check [SETUP_GUIDE.md](SETUP_GUIDE.md) for detailed troubleshooting
- Run `START.bat` → Option 6 for system status check

## 📊 Sample Output

### After Training (`python ml_pipeline.py`)
```
==============================================
  LEADERBOARD (ranked by MAPE ↑)
==============================================
Rank  Model            MAPE %   MAE    RMSE   R²
 🥇   Prophet          29.17    4.06   4.89   -1.032
 🥈   ARIMA            37.23    5.04   5.55   -1.627
 🥉   LinearRegression 50.08    1.25   1.62    0.514
  4   CatBoost         55.12    1.27   1.67    0.482
  5   LightGBM         58.30    1.31   1.80    0.400
...
==============================================

Best model: Prophet
Saved to: output/best_model_Prophet.pkl
```

### Dashboard Shows
- **Current**: 82.5% occupancy (123/149 beds)
- **Tomorrow**: 77% occupancy (115 beds predicted) 🟢
- **Peak Day 5**: 85% occupancy (127 beds predicted) 🟡
- **Action**: Monitor staffing for Day 5

## 🎓 Learning Resources

1. **Start Here**: [VISUAL_GUIDE.md](VISUAL_GUIDE.md)
   - See what each chart means
   - Learn how to read forecasts
   - Understand color coding

2. **Setup**: [SETUP_GUIDE.md](SETUP_GUIDE.md)
   - Installation steps
   - Configuration options
   - Performance tuning

3. **Technical Details**: [IMPROVEMENTS_SUMMARY.md](IMPROVEMENTS_SUMMARY.md)
   - What was changed
   - ML model details
   - API documentation

## 🌟 Key Improvements Made

1. ✅ **ML Training**: Configured to use your `hospital_enhanced_full_dataset.csv`
2. ✅ **Visual Component**: New bed requirements chart with actual vs forecast
3. ✅ **Peak Demand**: Automatic detection and highlighting
4. ✅ **Daily Breakdown**: 7-day forecast with color indicators
5. ✅ **Documentation**: Complete guides for setup and usage
6. ✅ **Quick Start**: Batch script for easy launching

## 📞 Support

**Issues?**
- Check the [SETUP_GUIDE.md](SETUP_GUIDE.md) troubleshooting section
- Use `START.bat` option 6 for system diagnostics
- Review API docs: `http://localhost:8000/docs`

**Questions about forecasts?**
- See [VISUAL_GUIDE.md](VISUAL_GUIDE.md) for interpretation help
- Check model leaderboard in dashboard for accuracy
- Review confidence intervals (shaded areas) for certainty

## 📅 Workflow

### Daily Use
1. Open dashboard: `http://localhost:4200`
2. Check peak demand banner
3. Review 7-day breakdown
4. Plan staffing and resources

### Weekly Review
1. Compare forecast vs actual (use date picker)
2. Check model accuracy trends
3. Retrain if accuracy drops below 30%

### Monthly Maintenance
1. Retrain ML models with new data
2. Review department-level forecasts
3. Adjust thresholds if needed

---

**Version**: 2.0  
**Last Updated**: January 2025  
**Dataset**: hospital_enhanced_full_dataset.csv (2 years)  
**Best Model**: Prophet (29% MAPE)  

**🚀 Ready to start? Double-click `START.bat`!**
