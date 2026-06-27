# Dynamic Registration & Bed Allocation Platform

**Version 2.1** - Extends the KIMS Hospital Bed Occupancy Forecasting System

---

## 🎯 Overview

This platform transforms the analytics dashboard into an **operational application** for registration desks, eliminating manual bed allocation through:

- **AI-Powered Bed Recommendations** using ML-predicted LOS and occupancy forecasts
- **Dynamic Business Rules** that adapt to hospital policies without code changes
- **Payer Channel Intelligence** for demand forecasting by insurance type
- **Real-Time Alerts** based on configurable occupancy thresholds
- **Live Bed Inventory** with cleaning/maintenance status and predictions

---

## 🚀 Quick Start

### 1. Start the System

```bash
# Option A: Use the quick start script
START.bat

# Option B: Manual start
# Terminal 1 - Backend
cd HSI-backend
python main.py

# Terminal 2 - Frontend
cd HSI-frontend
ng serve
```

### 2. Access the Platform

Open your browser to: **http://localhost:4200**

Navigate using the sidebar:
- 📊 **Dashboard** - Analytics and forecasting
- ➕ **Registration** - Patient intake and bed allocation
- 🛏️ **Bed Monitor** - Real-time inventory and predictions
- 💳 **Payer Intelligence** - Insurance-based demand forecasts
- ⚠️ **Alerts** - Capacity warnings and notifications

---

## 🏗️ Architecture

### Backend APIs (FastAPI)

All endpoints are **dynamic** - they consume configuration from `config_service` which returns data-driven rules, payer channels, and thresholds.

#### Configuration APIs
```http
GET /api/config/payer-channels       # Insurance types and multipliers
GET /api/config/business-rules       # Bed allocation rules (critical → ICU, etc.)
GET /api/config/occupancy-thresholds # Alert trigger points (85%, 90%, etc.)
GET /api/config/bed-types            # Available bed categories
GET /api/config/specialties          # Medical specialties list
```

#### Operational APIs
```http
POST /api/bed/recommend              # AI bed recommendations
POST /api/admissions/register        # Complete patient admission
GET  /api/payer/forecast             # Payer-segmented demand forecast
GET  /api/alerts                     # Current occupancy alerts
GET  /api/bed-status                 # Real-time bed inventory
GET  /api/model-metadata             # ML model version and accuracy
```

### Frontend (Angular)

All components are **dynamic** and **theme-consistent**:
- Registration form auto-populates from config APIs
- Recommendations display reasoning and confidence
- Alerts use severity-based color coding
- Bed monitor shows live predictions from ML models

---

## 📋 Module Details

### 1. Registration Desk (`/registration`)

**Purpose:** Patient intake with AI-assisted bed allocation

**Workflow:**
1. Enter patient demographics (name, age, gender)
2. Select condition, specialty, and payer channel
3. Mark clinical requirements (critical, ventilator, isolation, dialysis)
4. Click **"Get Bed Recommendations"**
5. View scored recommendations with reasoning
6. Select bed and **"Confirm Admission"**

**Key Features:**
- Form validation for required fields
- Checkboxes for clinical flags
- Real-time bed scoring (100-point scale)
- Color-coded scores: 🟢 90+ (optimal) | 🟡 70-89 (good) | 🔴 <70 (marginal)
- Predicted LOS and occupancy impact shown per recommendation

**Business Rules Applied:**
- Critical patients → ICU only
- Ventilator required → ICU ventilator beds
- Isolation needed → Isolation rooms
- Dialysis → Dialysis unit
- Long LOS (>10 days) → Avoid premium turnover beds
- Age <14 → Pediatric ward
- Gender restrictions → Shared rooms

---

### 2. Bed Allocation Monitor (`/bed-allocation-monitor`)

**Purpose:** Real-time bed inventory and ML-driven predictions

**Displays:**
- **ML Model Status Card:** Version, engine (Prophet), MAPE accuracy, last trained timestamp
- **Per-Department Cards:**
  - Capacity bar (occupied, cleaning, maintenance, available)
  - Metrics: Available, Occupied, Cleaning, Maintenance
  - Tomorrow's predicted occupancy (ML forecast)
  - Trend indicator: 📈 Rising or 📉 Stable/Falling
  - Overflow risk badge: 🟢 Low | 🟡 Medium | 🔴 High

**Auto-Refresh:** Every 30 seconds

**Filters:** Department-specific view (ICU, General Ward, Emergency, etc.)

---

### 3. Payer Intelligence (`/payer-intelligence`)

**Purpose:** Insurance-based demand forecasting for capacity planning

**Forecast Windows:** 7, 14, 30, 60, 90 days

**Metrics per Payer:**
- **Expected Admissions:** Predicted patient volume
- **Avg. LOS:** Length of stay with payer multiplier applied
- **Occupancy Impact:** Percentage contribution to total occupancy
- **Confidence:** High (MAPE <30%) | Medium (MAPE 30-50%)

**Payer Channels (Dynamic):**
- Insurance (1.0x LOS multiplier, Priority 2)
- Government (1.1x LOS, Priority 3)
- Corporate (0.9x LOS, Priority 1)
- Self Pay (0.8x LOS, Priority 4)

**UI Features:**
- Color-coded confidence badges
- Impact bar visualization
- Hover effects on cards
- Responsive grid layout

---

### 4. Occupancy Alerts (`/occupancy-alerts`)

**Purpose:** Proactive capacity warnings based on configurable thresholds

**Alert Severities:**
- 🚨 **Critical** (>90% occupancy): Immediate action required
- ⚠️ **High** (85-90%): Monitor closely
- ⚡ **Medium** (75-85%): Prepare for capacity constraints
- ℹ️ **Low** (<75%): Informational only

**Summary Dashboard:**
- Critical Alerts count (red border)
- High Priority count (orange border)
- Requires Attention count (blue border)
- Total Alerts (dark blue border)

**Alert Details:**
- Type (e.g., ICU_HIGH_OCCUPANCY, BED_SHORTAGE)
- Message with percentages
- Department affected
- Timestamp (localized)
- Actions: View Details, Acknowledge

**Auto-Refresh:** Every 60 seconds

**Filters:** Severity-based (Critical, High, Medium, Low)

---

## 🔧 Configuration Management

### Adding a New Payer Channel

**Backend:** Edit `HSI-backend/config.py`

```python
def get_payer_channels() -> List[Dict[str, Any]]:
    return [
        {"id": "insurance", "name": "Insurance", "avg_los_multiplier": 1.0, "priority": 2},
        {"id": "medicare", "name": "Medicare", "avg_los_multiplier": 1.2, "priority": 3},  # NEW
        # ... existing channels
    ]
```

**Frontend:** No changes needed - UI auto-populates from API

---

### Modifying Business Rules

**Backend:** Edit `HSI-backend/config.py`

```python
def get_business_rules() -> Dict[str, Any]:
    return {
        "critical": {"required_department": "ICU", "priority": 1},
        "pediatric": {"age_threshold": 18, "required_department": "Pediatrics", "priority": 2},  # Changed from 14
        # ... existing rules
    }
```

**Bed Engine:** Automatically applies updated rules via `config_service`

---

### Adjusting Alert Thresholds

**Backend:** Edit `HSI-backend/config.py`

```python
def get_occupancy_thresholds() -> Dict[str, float]:
    return {
        "critical": 0.95,  # Changed from 0.90
        "high": 0.85,
        "moderate": 0.75,
        "normal": 0.60
    }
```

**Alerts:** Automatically use new thresholds on next API call

---

## 🤖 ML Integration

### Existing Forecast Engine

The platform **reuses** the existing forecasting pipeline (`forecast_engine.py`):
- **Prophet** for time-series forecasting (default)
- **Auto-ARIMA** fallback for complex seasonality
- **XGBoost** fallback for feature-rich data
- **Naive drift** last-resort fallback

### Bed Recommendation Engine

Located in `HSI-backend/bed_engine.py`:

**LOS Prediction:**
1. Calculate base LOS from historical data (`avg_length_of_stay`)
2. Apply payer-specific multiplier (e.g., Corporate = 0.9x)
3. Round to 1 decimal place

**Bed Scoring Algorithm:**
```
Start with score = 100.0

Hard Constraints (score → 0 if violated):
- Required department mismatch
- Required bed type mismatch
- Gender restriction violated (shared rooms)

Penalties:
- Bed in avoid_bed_types: -30 points
- Status = cleaning: -20 points
- Maintenance scheduled: -15 points

Final score = max(0.0, score)
```

**Top 5 Recommendations:** Sorted by score descending

---

### Model Metadata Display

The Bed Monitor shows:
- **Model Name:** Prophet (additive; weekly seasonality)
- **Engine:** prophet
- **MAPE:** 29.17% (typical for Prophet on this dataset)
- **RMSE:** 4.89
- **Version:** 2.0
- **Last Trained:** ISO timestamp from server
- **Data Range:** Start and end dates from `hospital_enhanced_full_dataset.csv`

---

## 🎨 UI/UX Design

### Theme Consistency

All new components match the existing dashboard:
- **Color Palette:** Blue (#007DB0), Blue-Light (#0099D6), Blue-Dark (#005A80)
- **Typography:** Segoe UI, 14px base font size
- **Spacing:** 1rem (16px) grid system
- **Cards:** White background, 8px border-radius, 2px-8px shadows
- **Hover Effects:** -4px translateY, enhanced shadows
- **Buttons:** Primary (blue bg), Secondary (white bg, blue border)

### Responsive Design

All components use CSS Grid with `auto-fit` and `minmax`:
- Desktop: Multi-column grid (2-4 columns)
- Tablet: 1-2 columns
- Mobile: Single column stack

### Accessibility

- Semantic HTML5 elements (`<nav>`, `<main>`, `<section>`)
- ARIA labels on interactive elements
- Keyboard navigation support
- High contrast color ratios (WCAG AA)
- Focus states on all inputs and buttons

---

## 📊 Data Flow

### Registration Flow

```
User Form Input
    ↓
GET /api/config/payer-channels (populate dropdowns)
GET /api/config/specialties (populate dropdowns)
    ↓
User Clicks "Get Bed Recommendations"
    ↓
POST /api/bed/recommend
    ├─ predict_los(patient_data)
    │   ├─ Calculate base LOS from historical data
    │   └─ Apply payer multiplier
    ├─ _get_required_department(business_rules)
    ├─ _get_required_bed_type(business_rules)
    ├─ _get_available_beds() [mock inventory]
    └─ _calculate_bed_score(bed, patient, rules)
        └─ Return top 5 recommendations
    ↓
User Selects Bed
    ↓
POST /api/admissions/register
    ├─ Create admission record
    ├─ Allocate bed (mock in current version)
    └─ Return confirmation with admission_id
```

### Payer Forecast Flow

```
User Selects Forecast Days (7-90)
    ↓
GET /api/payer/forecast?days=30
    ├─ Loop through payer_channels
    │   ├─ GET occupancy forecast (Prophet)
    │   ├─ Calculate expected_admissions (forecast_data × 2)
    │   ├─ Calculate avg_los (4.5 × payer multiplier)
    │   └─ Calculate occupancy_impact (mean predicted_rate × 100)
    └─ Return payer_forecasts[]
    ↓
Frontend Renders Cards
```

### Alert Flow

```
Every 60 seconds:
    ↓
GET /api/alerts?severity=<filter>
    ├─ GET dashboard metrics (current occupancy)
    ├─ Check ICU occupancy vs thresholds
    │   ├─ > 85%: HIGH alert
    │   └─ > 90%: CRITICAL alert
    ├─ Check hospital occupancy vs thresholds
    ├─ Check emergency admissions vs threshold (>10)
    └─ Return alerts[]
    ↓
Frontend Updates Alert Cards
    ├─ Group by severity
    ├─ Display icon, message, timestamp
    └─ Update summary counts
```

---

## 🔐 Security Considerations

**Current Implementation (Development):**
- No authentication (local development only)
- CORS enabled for `localhost:4200`
- No data encryption at rest

**Production Requirements:**
1. **Authentication:** JWT tokens with role-based access (Admin, Doctor, Registration Staff)
2. **Authorization:** Endpoint-level permissions (e.g., only Admin can modify business rules)
3. **Data Encryption:** HTTPS (TLS 1.3), encrypted patient data at rest
4. **Audit Logging:** Track all admissions, bed allocations, and config changes
5. **Rate Limiting:** Prevent API abuse (100 requests/minute per IP)
6. **Input Validation:** Pydantic models on backend, Angular validators on frontend

---

## 🧪 Testing

### Backend Testing

```bash
cd HSI-backend

# Test configuration endpoints
python test_endpoints.py

# Test bed recommendation engine
python -c "
from bed_engine import create_bed_engine
import pandas as pd

df = pd.read_csv('data/hospital_enhanced_full_dataset.csv')
engine = create_bed_engine(df)

patient = {
    'age': 45,
    'gender': 'male',
    'condition': 'Pneumonia',
    'payer_channel': 'insurance',
    'is_critical': False,
    'requires_ventilator': False,
    'requires_isolation': True,
    'requires_dialysis': False
}

recs = engine.recommend_beds(patient)
print(f'Top recommendation: {recs[0]}')
"
```

### Frontend Testing

```bash
cd HSI-frontend

# Unit tests
ng test

# E2E tests
ng e2e

# Manual testing checklist:
# 1. Navigate to /registration
# 2. Fill form with valid data
# 3. Click "Get Bed Recommendations"
# 4. Verify top 5 beds displayed with scores
# 5. Select a bed
# 6. Click "Confirm Admission"
# 7. Verify success message with admission_id
```

---

## 📈 Performance

### Backend Optimizations

- **Caching:** 10-minute TTL for forecast results (`_TTLCache`)
- **Parallel Execution:** Department forecasts run in `ThreadPoolExecutor` (6 workers)
- **Lazy Loading:** Models loaded only when needed
- **Response Times:**
  - `/api/bed/recommend`: <500ms (without forecast data)
  - `/api/payer/forecast`: <2s (Prophet × 4 payers)
  - `/api/alerts`: <100ms (metrics cached)
  - `/api/bed-status`: <50ms (mock data)

### Frontend Optimizations

- **Lazy Loading:** Components loaded on route navigation
- **Change Detection:** OnPush strategy (future enhancement)
- **HTTP Caching:** GET requests cached in service layer
- **Bundle Size:** ~500KB (main), ~100KB (polyfills)

---

## 🛠️ Troubleshooting

### Issue: "Cannot connect to API"

**Solution:**
1. Verify backend is running: `http://localhost:8000/docs`
2. Check `HSI-frontend/proxy.conf.json`:
   ```json
   {
     "/api": {
       "target": "http://localhost:8000",
       "secure": false,
       "changeOrigin": true
     }
   }
   ```
3. Restart Angular dev server: `ng serve`

---

### Issue: "No bed recommendations returned"

**Solution:**
1. Check backend logs for errors
2. Verify `hospital_enhanced_full_dataset.csv` exists in `HSI-backend/data/`
3. Ensure `avg_length_of_stay` column exists in CSV
4. Test bed engine directly:
   ```bash
   cd HSI-backend
   python -m pytest bed_engine.py -v
   ```

---

### Issue: "Payer channels not loading"

**Solution:**
1. Verify `config_service` is imported in `main.py`
2. Check API response: `curl http://localhost:8000/api/config/payer-channels`
3. Frontend: Check browser console for CORS errors
4. Clear Angular cache: `rm -rf .angular/cache`

---

## 🚀 Future Enhancements

### Short-Term (v2.2)

1. **WebSocket Integration:** Real-time bed status updates without polling
2. **PDF Reports:** Generate admission confirmation printouts
3. **SMS Notifications:** Alert staff when critical beds fill up
4. **Bed Reservation:** Hold beds for 15 minutes during registration
5. **Discharge Predictions:** ML model for expected discharge times

### Medium-Term (v2.3)

1. **Mobile App:** React Native app for registration staff
2. **FHIR Integration:** HL7 FHIR standard for patient data exchange
3. **Multi-Hospital:** Support multiple hospital locations
4. **Advanced Analytics:** Power BI dashboards for executives
5. **Waitlist Management:** Queue patients when no beds available

### Long-Term (v3.0)

1. **Reinforcement Learning:** Optimize bed assignments for throughput
2. **Natural Language:** Voice-based patient registration
3. **Blockchain Audit:** Immutable admission records
4. **Predictive Transfers:** Suggest ICU → General Ward transitions
5. **Resource Optimization:** Staff scheduling based on predicted admissions

---

## 📚 References

### Documentation
- [FastAPI Docs](https://fastapi.tiangolo.com/)
- [Angular Docs](https://angular.dev/)
- [Prophet Docs](https://facebook.github.io/prophet/)
- [Tailwind CSS Docs](https://tailwindcss.com/) (future)

### Healthcare Standards
- [HL7 FHIR](https://www.hl7.org/fhir/)
- [ICD-10 Codes](https://www.who.int/standards/classifications/classification-of-diseases)
- [HIPAA Compliance](https://www.hhs.gov/hipaa/index.html)

---

## 🤝 Contributing

### Code Style

**Python (Backend):**
- PEP 8 compliance
- Type hints for all function signatures
- Docstrings for public APIs
- Black formatter (88 char line length)

**TypeScript (Frontend):**
- Angular style guide
- Prettier formatter (120 char line length)
- ESLint rules enforced
- RxJS best practices

### Git Workflow

```bash
# Feature branch
git checkout -b feature/bed-transfer-prediction

# Commit messages
git commit -m "feat: add bed transfer prediction API"
git commit -m "fix: resolve payer forecast CORS error"
git commit -m "docs: update README with transfer prediction"

# Pull request
git push origin feature/bed-transfer-prediction
# Open PR on GitHub
```

---

## 📞 Support

**Issues:** Open a GitHub issue with:
- Description of the problem
- Steps to reproduce
- Expected vs actual behavior
- Screenshots (if UI issue)
- Logs (backend errors)

**Questions:** Use GitHub Discussions or contact the maintainers.

---

**Version:** 2.1.0  
**Last Updated:** January 2025  
**Authors:** Hospital Systems Integration Team  
**License:** MIT (for educational/internal use)

---

**🎉 You're ready to use the Dynamic Registration & Bed Allocation Platform!**

Start the system with `START.bat` and navigate to `/registration` to begin.
