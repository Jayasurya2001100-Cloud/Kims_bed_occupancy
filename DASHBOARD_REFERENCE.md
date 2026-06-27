# 🎨 Dashboard Visual Quick Reference

## Main Screen Layout

```
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃  🏥 KIMS Hospital - Bed Occupancy Intelligence             ┃
┃  Live · 10:30  [↻ Refresh]                                 ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

┌──────────────────────────────────────────────────────────────┐
│ 📊 OVERVIEW (KPI Cards)                                      │
├──────────┬──────────┬──────────┬──────────┬──────────┬───────┤
│ Overall  │   ICU    │Available │Emergency │Avg LOS   │7-Day  │
│ Occupancy│Occupancy │  Beds    │Admissions│          │Forecast│
│  82.5%   │  95.0%   │    26    │    12    │ 4.5 days │ 85.0% │
│123/149   │ 19/20    │   beds   │  today   │          │↑Rising│
│████░░░░  │█████████ │          │          │          │       │
└──────────┴──────────┴──────────┴──────────┴──────────┴───────┘

┌──────────────────────────────────────────────────────────────┐
│ 📊 BED REQUIREMENTS FORECAST ⭐ NEW                          │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│ ⚠️  Peak demand expected: Day 5                              │
│     127 beds needed (85% occupancy)                          │
│     Action: Monitor staffing closely                         │
│                                                               │
├──────────────────────────────────────────────────────────────┤
│   [LINE CHART]                                               │
│                                                               │
│   150 ┤                      ─ ─  Total Capacity (green)    │
│   140 ┤                   ╱                                  │
│   130 ┤                ╱     ∙∙∙∙  Warning 90% (orange)    │
│   120 ┤             ╱╱ - - -  Forecasted (red dashed)      │
│   110 ┼═══════════╱                                          │
│   100 ┤███████████  ━━━  Actual (blue solid)               │
│    90 ┤                                                      │
│       └───────────────────────────────────────              │
│        Now  D1  D3  D5  D7  D9  D11 D13                     │
│                                                               │
├──────────────────────────────────────────────────────────────┤
│ 📅 Next 7 Days Breakdown                                     │
├───────┬───────┬───────┬───────┬───────┬───────┬─────────────┤
│ Day 1 │ Day 2 │ Day 3 │ Day 4 │ Day 5 │ Day 6 │ Day 7       │
│ Jan 2 │ Jan 3 │ Jan 4 │ Jan 5 │ Jan 6 │ Jan 7 │ Jan 8       │
│ 115   │ 118   │ 122   │ 125   │ 127   │ 124   │ 120  beds   │
│ 77%   │ 79%   │ 81%   │ 83%   │ 85%   │ 83%   │ 80%         │
│ 🟢    │ 🟢    │ 🟢    │ 🟢    │ 🟡    │ 🟢    │ 🟢          │
└───────┴───────┴───────┴───────┴───────┴───────┴─────────────┘

┌──────────────────────────────────────────────────────────────┐
│ 🛏 WARD-LEVEL FORECASTS                                      │
├────────────────┬────────────────┬────────────────────────────┤
│ 🚑 ICU         │ 🛏 General Ward│ ❤️ Cardiology              │
│ MAPE 97.15%    │ MAPE 27.23%    │ MAPE 45.8%                 │
│ R²: -1.22      │ R²: 0.06       │ R²: 0.20                   │
│ [Sparkline]    │ [Sparkline]    │ [Sparkline]                │
│ ╱╲  ╱╲  ╱╲    │   ╱──╲╱───     │  ╱╲  ╱╲                    │
│╱  ╲╱  ╲╱  ╲   │╱╲╱        ╲─   │╱  ╲╱  ╲                   │
│ ⚠ High error  │ ✓ Reliable     │ ~ Moderate                 │
├────────────────┼────────────────┼────────────────────────────┤
│ 🆘 Emergency   │                │                            │
│ MAPE 41.01%    │                │                            │
│ R²: -3.23      │                │                            │
│ [Sparkline]    │                │                            │
│   ╱╲  ╱        │                │                            │
│╱╲╱  ╲╱         │                │                            │
│ ~ Moderate     │                │                            │
└────────────────┴────────────────┴────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│ 🏆 MODEL LEADERBOARD                                         │
├──────┬─────────────┬──────┬──────┬──────┬────────┬──────────┤
│ Rank │ Model       │ MAPE │ MAE  │ RMSE │   R²   │ Accuracy │
├──────┼─────────────┼──────┼──────┼──────┼────────┼──────────┤
│  🥇  │ Prophet     │ 29.2 │ 4.06 │ 4.89 │ -1.032 │ ████     │
│  🥈  │ ARIMA       │ 37.2 │ 5.04 │ 5.55 │ -1.627 │ ███      │
│  🥉  │ Linear Reg  │ 50.1 │ 1.25 │ 1.62 │  0.514 │ ██       │
│   4  │ CatBoost    │ 55.1 │ 1.27 │ 1.67 │  0.482 │ ██       │
│   5  │ LightGBM    │ 58.3 │ 1.31 │ 1.80 │  0.400 │ █        │
└──────┴─────────────┴──────┴──────┴──────┴────────┴──────────┘

┌──────────────────────────────────────────────────────────────┐
│ 📈 TREND CHARTS                                              │
│ (Occupancy Deep Dive Component)                              │
│                                                               │
│ [Historical + Forecast Chart]                                │
│ [Staffing Forecast Chart]                                    │
│ [Department Comparison Chart]                                │
└──────────────────────────────────────────────────────────────┘
```

## Color Legend

### Status Indicators
```
🟢 GREEN   = Safe     (<85%)  → Normal operations
🟡 YELLOW  = High     (85-90%) → Monitor closely
🔴 RED     = Critical (>90%)   → Action required
```

### Line Colors
```
━━━ Blue    (#007DB0) = Actual/Current
- - Red     (#FF0000) = Forecast/Predicted
─ ─ Green   (#27ae60) = Capacity/Maximum
∙∙∙ Orange  (#e67e22) = Warning Threshold
░░░ Lt Blue (shaded)  = Confidence Interval
```

## Key Features Highlighted

### ⭐ NEW: Bed Requirements Chart
**Location**: Right after Overview section

**What It Shows:**
1. **Insight Banner** (top)
   - Peak demand day number
   - Maximum beds needed
   - Occupancy percentage
   - Action recommendation

2. **Main Chart** (middle)
   - Blue solid line: Where you are now
   - Red dashed line: Where you're going
   - Shaded area: Uncertainty range
   - Reference lines: Capacity and warning

3. **Daily Cards** (bottom)
   - 7 individual day cards
   - Exact bed count per day
   - Color-coded indicators
   - Easy scanning at-a-glance

### Why It's Better

**Before:**
- Just numbers and tables
- Hard to see trends
- No clear peak indicator
- Required mental calculation

**After:**
- ✅ Visual chart with clear lines
- ✅ Automatic peak detection
- ✅ Color-coded warnings
- ✅ Daily breakdown cards
- ✅ Actionable insights

## Usage Scenarios

### Scenario 1: Morning Briefing
**Goal**: Check today's status and next 7 days

1. Look at **Overview** → Current occupancy 82.5% 🟢
2. Look at **Peak Banner** → Day 5 at 85% 🟡
3. Review **Day 1-7 Cards** → Tomorrow 77% 🟢
4. Action: Monitor Day 5, prepare staff

**Time**: 30 seconds

---

### Scenario 2: Weekly Planning
**Goal**: Plan resources for next week

1. Check **Bed Requirements Chart**
2. Note trend: Rising from 77% to 85%
3. Find peak: Day 5 (127 beds)
4. Review **Ward Forecasts** → ICU at high error, General Ward reliable
5. Plan: Extra staff Days 4-6, focus on General Ward prediction

**Time**: 2 minutes

---

### Scenario 3: Emergency Response
**Goal**: Assess capacity for surge

1. Look at **Available Beds** → 26 beds free
2. Check **Peak Banner** → If red 🔴
3. Review **7-Day Breakdown** → Count critical days
4. Check **ICU Occupancy** → 95% (near max)
5. Action: Activate surge protocol

**Time**: 15 seconds

## Quick Tips

### 📍 Where to Look First
1. **Insight Banner** (yellow/red) → Peak demand
2. **Day 1 Card** (green box) → Tomorrow's need
3. **Overview Occupancy** (big %) → Current status

### 🎯 Key Questions Answered
| Question | Look At |
|----------|---------|
| "How are we doing now?" | Overview → Overall Occupancy |
| "What about tomorrow?" | Breakdown → Day 1 card |
| "When's the peak?" | Banner → "Day X" |
| "How many beds needed?" | Banner → "X beds needed" |
| "Which ward most accurate?" | Leaderboard → Lowest MAPE |
| "Should I worry?" | Card colors → 🟢/🟡/🔴 |

### 💡 Pro Tips
- **Banner color** = Urgency level
- **Line crossing warning** = Critical point
- **Narrow shaded area** = High confidence
- **Wide shaded area** = Low confidence
- **Sparkline going up** = Increasing occupancy

## Mobile View (Responsive)

```
┌─────────────┐
│ Overall Occ │
│   82.5%     │
│ 123/149 beds│
└─────────────┘
┌─────────────┐
│[Chart Stack]│
│             │
│ Blue Line   │
│ Red Line    │
└─────────────┘
┌──────┬──────┐
│ Day 1│ Day 2│
│ 115  │ 118  │
│ 🟢   │ 🟢   │
└──────┴──────┘
```

## Print View

Perfect for daily briefings:
- Top half: KPIs + Chart
- Bottom half: Ward forecasts + Leaderboard
- Color-coded for easy scanning
- Fits on 1-2 pages

---

**🔑 Remember:**
- **Blue** = Actual (past/present)
- **Red** = Forecast (future)
- **Green/Yellow/Red** = Status (safe/caution/critical)

**💡 Quick Check:**
Banner + Day 1 Card = Everything you need for morning briefing!
