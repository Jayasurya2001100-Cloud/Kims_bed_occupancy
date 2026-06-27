# Frontend Visual Guide - Bed Occupancy Dashboard

## 📊 New Bed Requirements Visualization

### What You'll See

```
┌─────────────────────────────────────────────────────────────────┐
│ 📊 Bed Requirements Forecast                                    │
│ Upcoming days bed demand prediction                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│ ⚠️  Peak demand expected: Day 5                                 │
│     127 beds needed (85% occupancy)                             │
│     Action required: Prepare additional capacity                │
│                                                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  [LINE CHART]                                                   │
│  150 ┤                                                           │
│      │     ╱─────────────────  Total Capacity (green)          │
│  140 ┤    ╱                                                     │
│      │   ╱  ╱╲                                                  │
│  130 ┤  ╱  ╱  ╲ ╱╲ ╱╲    ---- Warning 90% (orange)            │
│      │ ╱  ╱    ╲╱  ╲╱ ╲                                         │
│  120 ┼────────────────╲── Forecasted (red dashed)             │
│      │███████████████  ╲                                        │
│  110 ┤███████████████   ╲                                       │
│      │███████████████                                           │
│  100 ┤███ Actual (blue solid)                                  │
│      │                                                           │
│   90 ┼───────────────────────────────────────────────────      │
│      Day 1  Day 3  Day 5  Day 7  Day 9  Day 11 Day 13          │
│                                                                  │
│  Legend:                                                        │
│  ━━━ Current Occupancy  - - - Forecasted Beds Required        │
│  ─ ─  Total Capacity    ∙∙∙∙  Warning Threshold (90%)         │
│                                                                  │
├─────────────────────────────────────────────────────────────────┤
│ Next 7 Days Breakdown                                           │
├──────┬──────┬──────┬──────┬──────┬──────┬──────────────────────┤
│ Day 1│ Day 2│ Day 3│ Day 4│ Day 5│ Day 6│ Day 7                │
│ Jan 2│ Jan 3│ Jan 4│ Jan 5│ Jan 6│ Jan 7│ Jan 8                │
│ 115  │ 118  │ 122  │ 125  │ 127  │ 124  │ 120  beds            │
│ 77%  │ 79%  │ 81%  │ 83%  │ 85%  │ 83%  │ 80%                  │
│  🟢  │  🟢  │  🟢  │  🟢  │  🟡  │  🟢  │  🟢                   │
└──────┴──────┴──────┴──────┴──────┴──────┴──────────────────────┘
```

## Color Coding

### Occupancy Indicators

- **🟢 Green** (< 85%): Normal capacity - No action needed
- **🟡 Yellow** (85-90%): High occupancy - Monitor closely  
- **🔴 Red** (> 90%): Critical - Immediate action required

### Line Chart Colors

| Color | Meaning | Line Style |
|-------|---------|------------|
| Blue (#007DB0) | Actual occupancy | Solid thick line |
| Red (#FF0000) | Forecasted occupancy | Dashed line |
| Green (#27ae60) | Total capacity | Dashed line |
| Orange (#e67e22) | Warning threshold (90%) | Dotted line |
| Light blue (shaded) | Confidence interval | Filled area |

## Dashboard Sections

### 1. Overview KPI Cards

```
┌──────────────────────────────────────────────────────────────────┐
│ Overall Occupancy     ICU Occupancy     Available Beds           │
│      82.5%                95.0%              26 beds             │
│   123 / 149 beds      19 / 20 beds                              │
│ ████████████░░░░    ████████████████     Emergency Admissions   │
│                                                 12 today         │
└──────────────────────────────────────────────────────────────────┘
```

### 2. Bed Requirements Chart (NEW!)

This is the **main visual** that shows:

**Top Section - Insight Banner:**
- Peak demand day (which day will be busiest)
- Maximum beds needed
- Percentage of capacity
- Action recommendations

**Middle Section - Line Chart:**
- X-axis: Days ahead (Day 1 = tomorrow)
- Y-axis: Number of beds
- **Blue area** = Current occupancy (where you are now)
- **Red dashed line** = Forecast (where you're going)
- **Shaded area** = Uncertainty range (confidence intervals)
- **Green line** = Maximum capacity
- **Orange line** = Warning level (90%)

**Bottom Section - Daily Cards:**
- Individual cards for next 7 days
- Shows exact bed count needed each day
- Color-coded status indicators
- Date and occupancy percentage

### 3. Ward-Level Forecasts

```
┌─────────────────────┐ ┌─────────────────────┐ ┌─────────────────────┐
│ 🚑 ICU              │ │ 🛏 General Ward     │ │ ❤️ Cardiology       │
│ Intensive Care Unit │ │ General Admission   │ │ Cardiovascular Care │
│ MAPE 97.15%         │ │ MAPE 27.23%         │ │ MAPE 45.8%          │
│                     │ │                     │ │                     │
│ R² -1.22  MAE 3.8  │ │ R² 0.06   MAE 4.2  │ │ R² 0.20   MAE 2.8  │
│                     │ │                     │ │                     │
│ [Sparkline Chart]   │ │ [Sparkline Chart]   │ │ [Sparkline Chart]   │
│ ╱╲    ╱╲    ╱╲     │ │   ╱─────╲╱────     │ │    ╱╲    ╱╲        │
│╱  ╲╱╲╱  ╲╱╲╱  ╲   │ │╱╲╱           ╲─    │ │ ╱╲╱  ╲╱╲╱  ╲      │
│                     │ │                     │ │                     │
│ ⚠ High uncertainty  │ │ ✓ Reliable forecast │ │ ~ Moderate forecast │
└─────────────────────┘ └─────────────────────┘ └─────────────────────┘
```

### 4. Model Leaderboard

```
┌──────────────────────────────────────────────────────────────────┐
│ Model Leaderboard                                                 │
│ Ranked by lowest MAPE — test set (last 30 days)                 │
├──────┬─────────────────┬──────────┬──────┬──────┬────────┬───────┤
│ Rank │ Model           │ MAPE % ↑ │ MAE  │ RMSE │   R²   │ Acc.  │
├──────┼─────────────────┼──────────┼──────┼──────┼────────┼───────┤
│  🥇  │ ● Prophet       │  29.17   │ 4.06 │ 4.89 │ -1.032 │ ████  │
│  🥈  │ ● ARIMA         │  37.23   │ 5.04 │ 5.55 │ -1.627 │ ███   │
│  🥉  │ ● Linear Reg    │  50.08   │ 1.25 │ 1.62 │  0.514 │ ██    │
│   4  │ ● CatBoost      │  55.12   │ 1.27 │ 1.67 │  0.482 │ ██    │
│   5  │ ● LightGBM      │  58.30   │ 1.31 │ 1.80 │  0.400 │ █     │
│   6  │ ● RandomForest  │  59.99   │ 1.29 │ 1.70 │  0.463 │ █     │
│   7  │ ● XGBoost       │  60.45   │ 1.31 │ 1.78 │  0.413 │ █     │
│   8  │ ● ExtraTrees    │  63.55   │ 1.33 │ 1.70 │  0.459 │ █     │
└──────┴─────────────────┴──────────┴──────┴──────┴────────┴───────┘

🏆 Best Model: Prophet
    MAPE 29.17% · RMSE 4.89 · Saved as best_model_Prophet.pkl
```

## How to Read the Charts

### Understanding the Main Forecast Chart

**Question**: "How many beds will I need tomorrow?"

**Answer**: Look at Day 1 on the red dashed line. The number where it intersects Day 1 on the Y-axis is your forecast.

**Example**:
```
If the red line is at 115 on Day 1:
→ You'll need approximately 115 beds tomorrow
→ With 149 total beds, that's 77% occupancy (safe level)
```

**Question**: "When should I prepare for high demand?"

**Answer**: Look at the insight banner at the top. It will tell you:
- Peak demand day: "Day 5"
- Beds needed: "127 beds"
- Occupancy: "85%"
- Action: "Monitor closely" or "Prepare additional capacity"

**Question**: "How confident is this forecast?"

**Answer**: Look at the shaded area around the red line:
- **Narrow shade**: High confidence (±5 beds)
- **Wide shade**: Low confidence (±20 beds)

## Interactive Features

### Date Selector
- Pick historical dates to see actual vs forecasted comparison
- Validate model accuracy on past data

### Forecast Horizon
- Choose 7, 14, or 30 days ahead
- Shorter = more accurate
- Longer = more strategic planning

### Department Selector
- View forecasts by specific ward
- Compare ICU vs General Ward vs Emergency

### Model Preference
- Select which ML model to use
- Prophet = best for occupancy
- ARIMA = best for staffing

## Mobile View

On smaller screens, the layout adapts:

```
┌──────────────────┐
│ Overall Occupancy│
│      82.5%       │
│  123 / 149 beds  │
└──────────────────┘
┌──────────────────┐
│ [Chart - Stack]  │
│                  │
│  [Forecast Line] │
│                  │
└──────────────────┘
┌──────────────────┐
│ Day 1 │ Day 2    │
│ 115   │ 118      │
│ 🟢    │ 🟢       │
└──────────────────┘
```

## Quick Reference Guide

| I want to... | Look at... |
|-------------|-----------|
| See current occupancy | Top KPI card (blue number) |
| See tomorrow's forecast | Day 1 card in breakdown section |
| Find peak demand | Insight banner (yellow/red if critical) |
| Check forecast accuracy | Model leaderboard MAPE column |
| Compare wards | Ward-level forecast cards |
| View confidence range | Shaded area on main chart |
| See ICU pressure | ICU card (red if >90%) |

## Alerts and Warnings

### Visual Cues

1. **🔴 Red Banner**: Peak > 95% - Critical action needed
2. **🟡 Yellow Banner**: Peak > 90% - Monitor closely
3. **🟢 Blue Banner**: Peak < 90% - Normal operations

### When to Act

- **Immediate (🔴)**: >95% forecasted
  - Action: Activate surge capacity protocol
  - Timeline: Within 24 hours

- **Soon (🟡)**: 90-95% forecasted
  - Action: Prepare additional staff
  - Timeline: Within 2-3 days

- **Monitor (🟢)**: <90% forecasted
  - Action: Continue normal operations
  - Timeline: Regular reviews

---

**💡 Pro Tip**: The most important information is always at the top:
1. Insight banner → Tells you the peak day and action needed
2. Main chart → Shows the trend (going up or down)
3. Daily cards → Gives you specific numbers for each day

**🎯 Goal**: Help you answer:
- "How many beds do I need?"
- "When will I need them?"
- "How confident should I be in this forecast?"
