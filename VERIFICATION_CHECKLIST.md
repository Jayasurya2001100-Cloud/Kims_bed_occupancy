# ✅ KIMS Bed Occupancy - Verification Checklist

Use this checklist to verify that everything is working correctly.

## 📋 Pre-Flight Check

### System Requirements
- [ ] Windows 10 or 11 installed
- [ ] Python 3.9+ installed (`python --version`)
- [ ] Node.js 18+ installed (`node --version`)
- [ ] Angular CLI installed (`ng version`)
- [ ] At least 4GB RAM available
- [ ] Ports 8000 and 4200 are free

### Files Present
- [ ] `HSI-backend/data/hospital_enhanced_full_dataset.csv` exists
- [ ] `HSI-backend/ml_pipeline.py` updated
- [ ] `HSI-frontend/src/app/components/dashboard-forecast-mini/bed-requirements-visual.component.ts` created
- [ ] `START.bat` in project root
- [ ] All documentation files (README.md, SETUP_GUIDE.md, etc.)

## 🎯 Step 1: ML Training

### Run Training
```bash
cd HSI-backend
python ml_pipeline.py
```

### Verify Training Success
- [ ] Script completes without errors
- [ ] `output/leaderboard.csv` created
- [ ] `output/best_model_Prophet.pkl` created (or another best model)
- [ ] `output/ward_*.png` files created (4 ward forecast images)
- [ ] `output/feat_imp_*.png` files created (feature importance charts)
- [ ] Terminal shows: "Best model saved"

### Check Leaderboard
```bash
type output\leaderboard.csv
```
- [ ] Prophet has lowest MAPE (~29%)
- [ ] All 8 models listed
- [ ] No NaN or error values

**Expected Output:**
```
Model            MAPE       MAE     RMSE    R²
Prophet         29.173    4.061    4.885   -1.0323
ARIMA           37.233    5.035    5.554   -1.6267
...
```

## 🔧 Step 2: Backend API

### Start Backend
```bash
cd HSI-backend
python main.py
```

### Verify Backend Running
- [ ] Terminal shows: "Uvicorn running on http://0.0.0.0:8000"
- [ ] No error messages in terminal
- [ ] Can access: `http://localhost:8000`
- [ ] Can access: `http://localhost:8000/docs` (API documentation)

### Test API Endpoints
Open browser and test these URLs:

#### Dashboard Metrics
- [ ] `http://localhost:8000/api/dashboard/metrics`
- Expected: JSON with `current_occupancy_rate`, `occupied_beds`, etc.

#### Forecast
- [ ] `http://localhost:8000/api/forecast`
- Method: POST
- Body: `{"days": 7}`
- Expected: JSON with `forecast_data` array

#### Departments
- [ ] `http://localhost:8000/api/departments`
- Expected: JSON with list of departments

**Quick API Test:**
```bash
# Open in browser
http://localhost:8000/docs

# Test these endpoints:
- GET /api/dashboard/metrics
- POST /api/forecast (body: {"days": 7})
- GET /api/analytics/department-forecasts?days=14
```

### Check API Response
- [ ] All endpoints return valid JSON
- [ ] No 500 errors
- [ ] Response times < 5 seconds
- [ ] `forecast_data` contains multiple date entries

## 🎨 Step 3: Frontend Application

### Install Dependencies (First Time)
```bash
cd HSI-frontend
npm install
```

### Start Frontend
```bash
cd HSI-frontend
ng serve
```

### Verify Frontend Running
- [ ] Terminal shows: "Angular Live Development Server is listening on localhost:4200"
- [ ] No compilation errors
- [ ] Browser opens automatically or can manually open: `http://localhost:4200`

### Check Dashboard Load
- [ ] Dashboard page loads without errors
- [ ] No white screen / blank page
- [ ] Loading spinner appears then disappears
- [ ] Data appears within 5 seconds

## 📊 Step 4: Visual Components

### Overview Section
- [ ] "Overall Occupancy" card shows percentage
- [ ] "ICU Occupancy" card shows data
- [ ] "Available Beds" card shows number
- [ ] "Emergency Admissions" card shows count
- [ ] "Avg. Length of Stay" card shows days
- [ ] "7-Day Forecast" card shows prediction
- [ ] All cards have colored progress bars

### Bed Requirements Chart (NEW!)
- [ ] Section appears below overview cards
- [ ] Title: "📊 Bed Requirements Forecast"
- [ ] Insight banner shows (blue/yellow/red)
- [ ] Banner text: "Peak demand expected: Day X"
- [ ] Main line chart displays
- [ ] Chart shows blue solid line (actual)
- [ ] Chart shows red dashed line (forecast)
- [ ] Chart shows green line (capacity)
- [ ] Chart shows orange line (warning 90%)
- [ ] Shaded area visible around forecast line
- [ ] X-axis shows "Day 1, Day 2, Day 3..." labels
- [ ] Y-axis shows bed count numbers
- [ ] Legend shows all 4 lines

### Daily Breakdown Cards
- [ ] "Next 7 Days Breakdown" section appears
- [ ] 7 individual cards displayed
- [ ] Each card shows:
  - [ ] Day label ("Day 1", "Day 2", etc.)
  - [ ] Date (e.g., "Jan 2")
  - [ ] Bed count (e.g., "115 beds")
  - [ ] Occupancy percentage (e.g., "77%")
  - [ ] Indicator emoji (🟢/🟡/🔴)
- [ ] Cards are color-coded:
  - [ ] Normal cards: Light gray background
  - [ ] High demand cards: Yellow background
  - [ ] Critical cards: Red background

### Ward-Level Forecasts
- [ ] "Ward-Level Forecast" section appears
- [ ] Shows projected increasing wards (if any)
- [ ] Ward cards display for each department
- [ ] Each card shows:
  - [ ] Ward icon and name
  - [ ] MAPE percentage
  - [ ] R², MAE, RMSE metrics
  - [ ] Sparkline chart (mini line chart)
  - [ ] Status indicator (✓ / ~ / ⚠)

### Model Leaderboard
- [ ] "Model Leaderboard" section appears
- [ ] Table shows all 8 models
- [ ] Prophet has 🥇 medal (rank 1)
- [ ] ARIMA has 🥈 medal (rank 2)
- [ ] Columns show: Rank, Model, MAPE, MAE, RMSE, R², Accuracy Band
- [ ] Accuracy bars display (colored based on MAPE)
- [ ] Best model banner shows at bottom

### Trend Charts
- [ ] "Occupancy Trend & Forecast" section appears
- [ ] Historical chart displays
- [ ] Forecast line continues from last historical point
- [ ] No gaps between actual and forecast lines
- [ ] Confidence intervals shown

## 🔍 Step 5: Functionality Tests

### Chart Interactions
- [ ] Hover over chart shows tooltip
- [ ] Tooltip displays date, bed count, occupancy %
- [ ] Zoom in/out works (if enabled)
- [ ] Legend items can be clicked to hide/show lines

### Data Accuracy
- [ ] Current occupancy matches last data point
- [ ] Forecast starts from current date + 1
- [ ] Peak day number is correct (1-30 range)
- [ ] Peak beds number is realistic (not negative, not > capacity)
- [ ] Occupancy percentages are 0-100%

### Responsive Design
- [ ] Dashboard works on full screen
- [ ] Dashboard works on smaller window (resize browser)
- [ ] Cards stack properly on narrow screen
- [ ] Charts resize appropriately
- [ ] Text remains readable

### Color Coding
- [ ] Green indicator for < 85% occupancy
- [ ] Yellow indicator for 85-90% occupancy
- [ ] Red indicator for > 90% occupancy
- [ ] Banner color matches severity (blue/yellow/red)

## 🚀 Step 6: End-to-End Test

### Scenario: View Tomorrow's Forecast
1. [ ] Open dashboard: `http://localhost:4200`
2. [ ] Look at "Next 7 Days Breakdown"
3. [ ] Find "Day 1" card
4. [ ] Note the bed count (e.g., "115 beds")
5. [ ] Check the indicator (should be 🟢 if < 85%)
6. [ ] Look at main chart
7. [ ] Find Day 1 on red dashed line
8. [ ] Verify it matches the card's bed count

### Scenario: Identify Peak Demand
1. [ ] Look at insight banner
2. [ ] Note peak day (e.g., "Day 5")
3. [ ] Note peak beds (e.g., "127 beds")
4. [ ] Find Day 5 card in breakdown
5. [ ] Verify card shows same bed count
6. [ ] Check card color (should be yellow/red if high)
7. [ ] Plan action based on indicator

### Scenario: Compare Departments
1. [ ] Scroll to "Ward-Level Forecast"
2. [ ] Compare MAPE values across wards
3. [ ] Find ward with lowest MAPE (most accurate)
4. [ ] Find ward with highest MAPE (least accurate)
5. [ ] Note which wards have ✓ (reliable) status
6. [ ] Plan resources accordingly

## 📈 Step 7: Accuracy Validation

### Historical Validation (Optional)
If your dataset has recent data:

1. [ ] Use date picker (if available) to select a past date
2. [ ] Generate forecast for that date
3. [ ] Compare forecast vs actual (what actually happened)
4. [ ] Check if MAPE matches (should be ~29% error)

### Cross-Check with Output Files
1. [ ] Open `HSI-backend/output/ward_ICU.png`
2. [ ] Compare visual trend with dashboard ICU card
3. [ ] Verify similar patterns
4. [ ] Check if numbers are in same range

## 🎓 Step 8: Documentation Review

### User Guides
- [ ] README.md is clear and concise
- [ ] SETUP_GUIDE.md has step-by-step instructions
- [ ] VISUAL_GUIDE.md explains all chart elements
- [ ] IMPROVEMENTS_SUMMARY.md lists all changes

### Quick Start Works
- [ ] `START.bat` runs without errors
- [ ] Menu options work correctly
- [ ] Option 1 trains models successfully
- [ ] Option 4 starts both servers
- [ ] Option 6 shows system status

## 🐛 Troubleshooting Checklist

If something doesn't work, check:

### Backend Issues
- [ ] Python version is 3.9+ (`python --version`)
- [ ] All packages installed (`pip install -r requirements.txt`)
- [ ] Port 8000 is free (`netstat -ano | findstr :8000`)
- [ ] Dataset file exists and is readable
- [ ] No firewall blocking port 8000

### Frontend Issues
- [ ] Node.js version is 18+ (`node --version`)
- [ ] Angular CLI installed (`ng version`)
- [ ] `npm install` completed successfully
- [ ] Port 4200 is free (`netstat -ano | findstr :4200`)
- [ ] Backend is running before starting frontend
- [ ] Browser cache cleared (Ctrl+Shift+Delete)

### Visual Issues
- [ ] Browser is modern (Chrome/Firefox/Edge)
- [ ] JavaScript is enabled
- [ ] No ad blockers interfering
- [ ] Console shows no errors (F12)
- [ ] Chart.js library loaded

## ✅ Final Verification

### All Systems Go
- [ ] ML models trained and saved
- [ ] Backend API running on port 8000
- [ ] Frontend app running on port 4200
- [ ] Dashboard loads with all components
- [ ] Bed requirements chart displays correctly
- [ ] Peak demand banner shows
- [ ] Daily breakdown cards appear
- [ ] All indicators and colors working
- [ ] No errors in browser console
- [ ] No errors in terminal windows

### Success Criteria Met
- [ ] Can see actual occupancy (blue line)
- [ ] Can see forecast occupancy (red line)
- [ ] Can identify peak demand day
- [ ] Can read bed requirements per day
- [ ] Can understand color indicators
- [ ] System is ready for production use

## 🎉 Completion

**If all items are checked:** ✅ Your system is fully operational!

**If any items failed:** Review the [SETUP_GUIDE.md](SETUP_GUIDE.md) troubleshooting section.

**Next Steps:**
1. Share dashboard URL with team: `http://localhost:4200`
2. Set up automated daily retraining
3. Configure alerting for high occupancy
4. Train staff on reading forecasts

---

**Date Verified**: _________________
**Verified By**: _________________
**Notes**: _________________

---

**Quick Reference:**
- Backend: `python HSI-backend/main.py`
- Frontend: `ng serve` in `HSI-frontend/`
- Dashboard: `http://localhost:4200`
- API Docs: `http://localhost:8000/docs`
