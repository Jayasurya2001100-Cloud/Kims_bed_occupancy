from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict
from typing import List, Dict, Any, Optional, Union
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from copy import deepcopy
from threading import Lock
import json
import logging
import time
import hashlib
import concurrent.futures
import threading

from forecast_engine import run_occupancy_forecast, run_generic_forecast
from config import config_service
from bed_engine import create_bed_engine

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Simple TTL in-memory cache (thread-safe, 10-minute expiry)
# ---------------------------------------------------------------------------
_CACHE_TTL_SECONDS = 600  # 10 minutes

class _TTLCache:
    def __init__(self):
        self._store: Dict[str, Any] = {}
        self._times: Dict[str, float] = {}
        self._lock = Lock()

    def _make_key(self, *args, **kwargs) -> str:
        raw = json.dumps({"a": args, "k": kwargs}, sort_keys=True, default=str)
        return hashlib.md5(raw.encode()).hexdigest()

    def get(self, key: str):
        with self._lock:
            if key in self._store:
                if time.monotonic() - self._times[key] < _CACHE_TTL_SECONDS:
                    return self._store[key]
                del self._store[key]
                del self._times[key]
        return None

    def set(self, key: str, value: Any):
        with self._lock:
            self._store[key] = value
            self._times[key] = time.monotonic()

    def make_key(self, *args, **kwargs) -> str:
        return self._make_key(*args, **kwargs)

    def invalidate_all(self):
        with self._lock:
            self._store.clear()
            self._times.clear()

_cache = _TTLCache()

def build_cache_key(prefix: str, params: dict) -> str:
    return _cache.make_key(prefix, **params)

def get_cached(key: str):
    return _cache.get(key)

def set_cached(key: str, value: Any):
    _cache.set(key, value)

app = FastAPI(title="Hospital Bed Occupancy Forecasting API", version="1.0.0")

# ---------------------------------------------------------------------------
# Startup cache pre-warm — runs in background so server is immediately ready
# ---------------------------------------------------------------------------
_PREWARM_WINDOWS = [30, 60, 90, 180, 365, 730]

def _prewarm_one_window(days: int):
    """Pre-warm all three heavy endpoints for a single history window."""
    # 1. Rolling occupancy forecast
    ck = build_cache_key("hist_rolling", {"days": days, "block_days": 7, "train_days": 60, "model": None, "as_of": None})
    if _cache.get(ck) is None:
        result = generate_rolling_historical_forecast(days, 7, None, None, 60)
        _cache.set(ck, result)
        logger.info("Pre-warmed hist_rolling days=%d", days)

    # 2. Staffing forecast — mirror the endpoint logic directly (sync)
    ck = build_cache_key("hist_staffing", {"days": days, "block_days": 7, "train_days": 60, "model": None, "as_of": None})
    if _cache.get(ck) is None:
        result = _generate_staffing_forecast_sync(days, 7, 60, None)
        if result is not None:
            _cache.set(ck, result)
            logger.info("Pre-warmed hist_staffing days=%d", days)

def _prewarm_cache():
    """Pre-populate cache for all history windows in parallel background threads."""
    import time as _time
    _time.sleep(3)  # let server fully start first
    logger.info("Cache pre-warm starting for windows: %s", _PREWARM_WINDOWS)
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        list(pool.map(_prewarm_one_window, _PREWARM_WINDOWS))
    logger.info("Cache pre-warm complete.")

@app.on_event("startup")
async def startup_event():
    t = threading.Thread(target=_prewarm_cache, daemon=True)
    t.start()

# Enable CORS for Angular frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:4200",
        "http://127.0.0.1:4200",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models
class OccupancyData(BaseModel):
    date: str
    occupied_beds: int
    total_beds: int
    occupancy_rate: float
    department: str
    icu_beds: int
    emergency_admissions: int
    discharges: int

class ForecastRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    days: int = 7
    department: Optional[str] = None
    model_preference: Optional[str] = None
    as_of_date: Optional[str] = None


class CopilotChatRequest(BaseModel):
    query: str
    as_of_date: Optional[str] = None
    model_preference: Optional[str] = None
    forecast_days: int = 30


class CopilotChatResponse(BaseModel):
    answer: str
    as_of_date: str
    model_preference: Optional[str] = None
    forecast_days: int
    grounded: bool = True

class ForecastResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    forecast_data: List[Dict[str, Any]]
    confidence_interval: Dict[str, List[float]]
    model_metrics: Dict[str, Any]
    forecast_model: Dict[str, str]

class GenericForecastResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    forecast_data: List[Dict[str, Any]]
    confidence_interval: Dict[str, List[float]]
    model_metrics: Dict[str, Any]
    forecast_model: Dict[str, str]

class AlertData(BaseModel):
    alert_type: str
    message: str
    severity: str
    timestamp: str
    department: Optional[str] = None

class DashboardMetrics(BaseModel):
    current_occupancy_rate: float
    occupied_beds: int
    available_beds: int
    total_beds: int
    icu_occupancy_rate: float
    icu_occupied_beds: int
    icu_available_beds: int
    icu_total_beds: int
    predicted_occupancy_7_days: float
    emergency_admissions_today: int
    avg_length_of_stay: float
    """ISO calendar date (YYYY-MM-DD) of the snapshot row(s) used for occupancy, ED, and LOS tiles."""
    data_as_of_date: str
    alerts: List[AlertData]


def normalize_hospital_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Standardize source CSV/fallback columns so API logic uses one schema."""
    if df is None or df.empty:
        return df

    out = df.copy()
    rename_map = {}
    if "emergency_admission" in out.columns and "emergency_admissions" not in out.columns:
        rename_map["emergency_admission"] = "emergency_admissions"
    if rename_map:
        out = out.rename(columns=rename_map)

    return out


def emergency_admissions_column(df: pd.DataFrame) -> Optional[str]:
    """Return the canonical emergency admissions column when present."""
    if df is None or df.empty:
        return None
    if "emergency_admissions" in df.columns:
        return "emergency_admissions"
    if "emergency_admission" in df.columns:
        return "emergency_admission"
    return None


def resolve_as_of_date(df: pd.DataFrame, as_of_date: Optional[str] = None) -> pd.Timestamp:
    """Resolve an input date to the latest available dataset date on or before it."""
    if df is None or df.empty:
        raise HTTPException(status_code=404, detail="No data available")

    dates = pd.to_datetime(df["date"], errors="coerce").dropna().dt.normalize().sort_values()
    if dates.empty:
        raise HTTPException(status_code=404, detail="No dated records available")

    if not as_of_date:
        return dates.iloc[-1]

    try:
        target = pd.Timestamp(as_of_date).normalize()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid as_of_date '{as_of_date}'") from exc

    eligible = dates[dates <= target]
    if eligible.empty:
        raise HTTPException(
            status_code=400,
            detail=f"No records available on or before {as_of_date}",
        )
    return eligible.iloc[-1]


def filter_through_as_of_date(df: pd.DataFrame, as_of_date: Optional[str] = None) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    resolved = resolve_as_of_date(df, as_of_date)
    out = df.copy()
    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    return out[out["date"].dt.normalize() <= resolved].copy()


def filter_recent_window(
    df: pd.DataFrame,
    days: int,
    as_of_date: Optional[str] = None,
) -> tuple[pd.DataFrame, pd.Timestamp, pd.Timestamp]:
    if df is None or df.empty:
        raise HTTPException(status_code=404, detail="No data available")

    scoped = filter_through_as_of_date(df, as_of_date)
    if scoped.empty:
        raise HTTPException(status_code=404, detail="No data available for the selected date")

    end = resolve_as_of_date(scoped, None)
    start = end - pd.Timedelta(days=max(1, int(days)) - 1)
    windowed = scoped[scoped["date"].dt.normalize() >= start].copy()
    return windowed, start, end


def generate_rolling_historical_forecast(
    days: int = 90,
    block_days: int = 21,
    model_preference: Optional[str] = None,
    as_of_date: Optional[str] = None,
    train_days: int = 90,
) -> Dict[str, Any]:
    """
    Walk-forward rolling forecast: for each 3-week block inside `days`,
    train on the fixed `train_days` window immediately preceding the block,
    then predict the block. Mirrors the deep-dive script's holdout logic.
    """
    days = max(7, min(int(days), 800))
    block_days = max(7, min(int(block_days), 90))
    train_days = max(14, min(int(train_days), 730))

    window_df, _, _ = filter_recent_window(historical_data, days, as_of_date)
    if window_df.empty:
        raise HTTPException(status_code=404, detail="No historical data available")

    window_dates = sorted(window_df["date"].dt.normalize().unique())
    if not window_dates:
        raise HTTPException(status_code=404, detail="No valid daily timestamps in historical window")

    combined_metrics: Dict[str, Any] = {}
    combined_model: Dict[str, Any] = {}

    all_data = historical_data.copy()
    all_data["date"] = pd.to_datetime(all_data["date"], errors="coerce")

    # Build list of (block_start, block_horizon, daily_train) tuples upfront
    # No warm-up skip — all_data contains full history before the visible window
    blocks = []
    for start_idx in range(0, len(window_dates), block_days):
        block_start = window_dates[start_idx]
        block_horizon = min(block_days, len(window_dates) - start_idx)
        train_end = block_start - pd.Timedelta(days=1)
        train_start = block_start - pd.Timedelta(days=train_days)
        training_df = all_data[
            (all_data["date"].dt.normalize() >= train_start) &
            (all_data["date"].dt.normalize() <= train_end)
        ]
        if training_df.empty or training_df["date"].dt.normalize().nunique() < 8:
            continue
        daily_train = (
            training_df.groupby("date")
            .agg({"occupied_beds": "sum", "total_beds": "sum"})
            .reset_index()
            .sort_values("date")
            .reset_index(drop=True)
        )
        daily_train["occupancy_rate"] = (
            daily_train["occupied_beds"] / daily_train["total_beds"].replace(0, np.nan)
        ).fillna(0)
        blocks.append((block_start, block_horizon, daily_train))

    def _run_block_occ(args):
        block_start, block_horizon, daily_train = args
        try:
            return block_start, run_generic_forecast(
                daily_train, block_horizon, "occupancy_rate",
                "Hospital Occupancy", model_preference, skip_narrative=True,
            )
        except Exception as exc:
            logger.warning("Occupancy rolling block failed for %s: %s", block_start, exc)
            return block_start, None

    # Run all blocks in parallel (Prophet releases the GIL during Stan sampling)
    block_results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(blocks), 6)) as pool:
        for bs, fc in pool.map(_run_block_occ, blocks):
            block_results[bs] = fc

    forecast_points: List[Dict[str, Any]] = []
    for block_start, _, _ in blocks:
        block_fc = block_results.get(block_start)
        if block_fc is None:
            continue
        block_points = block_fc.get("forecast_data", []) or []
        if not block_points:
            continue
        if not combined_metrics:
            combined_metrics = block_fc.get("model_metrics") or {}
        if not combined_model:
            combined_model = block_fc.get("forecast_model") or {}
        for point in block_points:
            forecast_points.append({
                "date": point["date"],
                "predicted_occupancy_rate": float(point.get("predicted_value", 0)),
                "predicted_occupied_beds": 0,
            })

    # Rolling-backtest MAPE
    actual_daily = (
        window_df.groupby(window_df["date"].dt.strftime("%Y-%m-%d"))
        .agg({"occupied_beds": "sum", "total_beds": "sum"})
    )
    actual_daily["occ"] = actual_daily["occupied_beds"] / actual_daily["total_beds"].replace(0, np.nan)
    actual_rate = actual_daily["occ"].dropna().to_dict()
    rolling_errors = [
        abs(actual_rate[p["date"]] - p["predicted_occupancy_rate"]) / actual_rate[p["date"]]
        for p in forecast_points
        if p["date"] in actual_rate and actual_rate[p["date"]] > 0.01
    ]
    rolling_mape = round(float(np.mean(rolling_errors)) * 100, 2) if rolling_errors else 0.0
    combined_metrics["rolling_mape"] = rolling_mape
    combined_metrics["train_days"] = train_days
    combined_metrics["block_days"] = block_days

    return {
        "forecast_data": forecast_points,
        "confidence_interval": {"lower": [], "upper": []},
        "model_metrics": combined_metrics,
        "forecast_model": combined_model,
    }


def _generate_staffing_forecast_sync(
    days: int, block_days: int, train_days: int, model_preference: Optional[str]
) -> Optional[Dict[str, Any]]:
    """Synchronous staffing walk-forward forecast — shared by endpoint and pre-warm."""
    try:
        days = max(21, min(int(days), 800))
        block_days = max(7, min(int(block_days), 90))
        train_days = max(14, min(int(train_days), 730))

        window_df, _, _ = filter_recent_window(historical_data, days, None)
        window_dates = sorted(window_df["date"].dt.normalize().unique())
        if not window_dates or "labour_staffing" not in window_df.columns:
            return None

        all_data = historical_data.copy()
        all_data["date"] = pd.to_datetime(all_data["date"], errors="coerce")

        # No warm-up skip — all_data has full history preceding the window
        staff_blocks = []
        for start_idx in range(0, len(window_dates), block_days):
            block_start = window_dates[start_idx]
            block_horizon = min(block_days, len(window_dates) - start_idx)
            train_end = block_start - pd.Timedelta(days=1)
            train_start = block_start - pd.Timedelta(days=train_days)
            training_df = all_data[
                (all_data["date"].dt.normalize() >= train_start) &
                (all_data["date"].dt.normalize() <= train_end)
            ]
            if training_df.empty or "labour_staffing" not in training_df.columns:
                continue
            if training_df["date"].dt.normalize().nunique() < 8:
                continue
            agg_cols = {"labour_staffing": "sum", "total_beds": "sum"}
            if "patient_count" in training_df.columns:
                agg_cols["patient_count"] = "sum"
            daily_train = (
                training_df.groupby("date").agg(agg_cols)
                .reset_index().sort_values("date").reset_index(drop=True)
            )
            staff_blocks.append((block_start, block_horizon, daily_train))

        if not staff_blocks:
            return None

        def _run_sf(args):
            bs, bh, dt = args
            try:
                return bs, run_generic_forecast(dt, bh, "labour_staffing", "Hospital Labour Staffing", model_preference, skip_narrative=True)
            except Exception as exc:
                logger.warning("Staffing block failed %s: %s", bs, exc)
                return bs, None

        results = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(staff_blocks), 6)) as pool:
            for bs, fc in pool.map(_run_sf, staff_blocks):
                results[bs] = fc

        forecast_points, ci_lower_points, ci_upper_points = [], [], []
        combined_metrics: Dict[str, Any] = {}
        combined_model: Dict[str, Any] = {}
        for block_start, _, _ in staff_blocks:
            block_fc = results.get(block_start)
            if not block_fc:
                continue
            block_points = block_fc.get("forecast_data", []) or []
            if not block_points:
                continue
            if not combined_metrics:
                combined_metrics = block_fc.get("model_metrics") or {}
            if not combined_model:
                combined_model = block_fc.get("forecast_model") or {}
            for point in block_points:
                forecast_points.append(point)
            ci_lo = block_fc.get("confidence_interval", {}).get("lower", []) or []
            ci_hi = block_fc.get("confidence_interval", {}).get("upper", []) or []
            for i, point in enumerate(block_points):
                if i < len(ci_lo):
                    ci_lower_points.append({"date": point["date"], "value": ci_lo[i]})
                if i < len(ci_hi):
                    ci_upper_points.append({"date": point["date"], "value": ci_hi[i]})

        actual_staff_daily = (
            window_df.groupby(window_df["date"].dt.strftime("%Y-%m-%d"))["labour_staffing"].sum()
            if "labour_staffing" in window_df.columns else pd.Series(dtype=float)
        )
        staff_errors = [
            abs(actual_staff_daily[p["date"]] - p["predicted_value"]) / actual_staff_daily[p["date"]]
            for p in forecast_points
            if p["date"] in actual_staff_daily.index and actual_staff_daily[p["date"]] > 0
        ]
        rolling_mape = round(float(np.mean(staff_errors)) * 100, 2) if staff_errors else 0.0
        combined_metrics["rolling_mape"] = rolling_mape
        combined_metrics["train_days"] = train_days
        combined_metrics["block_days"] = block_days

        return {
            "forecast_data": forecast_points,
            "confidence_interval": {"lower": ci_lower_points, "upper": ci_upper_points},
            "model_metrics": combined_metrics,
            "forecast_model": combined_model,
        }
    except Exception as e:
        logger.warning("_generate_staffing_forecast_sync failed: %s", e)
        return None


def latest_available_dates(limit: int = 30) -> List[str]:
    dates = (
        pd.to_datetime(historical_data["date"], errors="coerce")
        .dropna()
        .dt.normalize()
        .drop_duplicates()
        .sort_values(ascending=False)
        .head(limit)
    )
    return [d.strftime("%Y-%m-%d") for d in dates]


def compact_department_watchlist(department_pack: Dict[str, Any], limit: int = 5) -> List[Dict[str, Any]]:
    departments = department_pack.get("departments", []) if isinstance(department_pack, dict) else []
    rows = []
    for dept in departments:
        points = dept.get("points") or []
        if not points or dept.get("error"):
            continue
        last = points[-1]
        rows.append(
            {
                "department": dept.get("department"),
                "predicted_rate_pct_day_horizon": round(float(last.get("rate_pct", 0.0)), 1),
                "predicted_occupied_beds_day_horizon": int(last.get("occupied", 0)),
                "total_beds": int(dept.get("total_beds", 0) or 0),
                "engine": dept.get("engine"),
                "mape": float(dept.get("mape", 0.0) or 0.0),
            }
        )
    rows.sort(key=lambda x: x["predicted_rate_pct_day_horizon"], reverse=True)
    return rows[:limit]


async def build_copilot_context(
    as_of_date: Optional[str],
    model_preference: Optional[str],
    forecast_days: int,
) -> Dict[str, Any]:
    metrics = await get_dashboard_metrics(as_of_date=as_of_date)
    normalized_as_of = metrics.data_as_of_date if hasattr(metrics, "data_as_of_date") else str(as_of_date or "")
    chart_pack = await get_chart_pack(days=30, as_of_date=normalized_as_of)
    department_pack = await get_department_forecasts(
        days=forecast_days,
        model_preference=model_preference,
        as_of_date=normalized_as_of,
    )
    hospital_forecast = forecasting_service.generate_forecast(
        days=forecast_days,
        model_preference=model_preference,
        as_of_date=normalized_as_of,
        skip_narrative=True,
    )
    ed_forecast = await get_ed_wait_time_forecast(
        ForecastRequest(
            days=forecast_days,
            model_preference=model_preference,
            as_of_date=normalized_as_of,
        )
    )

    chart_daily = chart_pack.get("daily", []) if isinstance(chart_pack, dict) else []
    latest_daily = chart_daily[-1] if chart_daily else {}
    hospital_points = hospital_forecast.get("forecast_data", [])
    hospital_first = hospital_points[0] if hospital_points else {}
    hospital_last = hospital_points[-1] if hospital_points else {}

    # Build a compact context dict for the LLM (minimize tokens for speed)
    metrics_raw = metrics.model_dump() if hasattr(metrics, "model_dump") else metrics
    current_occ = metrics_raw.get("current_occupancy_rate") or 0
    compact_metrics = {
        "occupancy_rate_pct": round(current_occ * 100, 1),
        "occupied_beds": metrics_raw.get("occupied_beds"),
        "total_beds": metrics_raw.get("total_beds"),
        "available_beds": metrics_raw.get("available_beds"),
        "icu_occupancy_rate_pct": round((metrics_raw.get("icu_occupancy_rate") or 0) * 100, 1),
        "emergency_admissions_today": metrics_raw.get("emergency_admissions_today"),
        "avg_length_of_stay": metrics_raw.get("avg_length_of_stay"),
    }

    ed_last = (ed_forecast.get("forecast_data") or [{}])[-1]

    day_1_rate = hospital_first.get("predicted_occupancy_rate") or 0
    day_horizon_rate = hospital_last.get("predicted_occupancy_rate") or 0

    return {
        "snapshot_date": normalized_as_of,
        "forecast_horizon_days": forecast_days,
        "current_metrics": compact_metrics,
        "hospital_forecast": {
            "day_1_rate_pct": round(day_1_rate * 100, 1),
            "day_horizon_rate_pct": round(day_horizon_rate * 100, 1),
            "direction": "rising" if day_horizon_rate > current_occ else "falling" if day_horizon_rate < current_occ else "stable",
        },
        "department_watchlist": compact_department_watchlist(department_pack, limit=5),
        "ed_wait_time_day_horizon": ed_last.get("predicted_value"),
        "alerts": (
            [{"message": a.message, "severity": a.severity} if hasattr(a, "message") else {"message": a.get("message",""), "severity": a.get("severity","")} for a in (metrics.alerts if hasattr(metrics, "alerts") else [])][:3]
        ),
    }


def generate_dashboard_copilot_answer(context: Dict[str, Any], query: str) -> str:
    prompt = f"""You are Dashboard Copilot for a hospital occupancy forecasting demo.

Answer the user's question only from the JSON context below.
If the answer is not in the context, say clearly that it is not available in the current dashboard context.
Do not invent metrics, dates, departments, or actions.
Keep the tone human, concise, and executive-friendly.
When useful, cite concrete numbers from the context.
For department risk questions, use only `department_watchlist`, which is already sorted from highest to lower risk.
Do not mention any department or number unless it appears explicitly in the JSON context.
All occupancy rates are already in percent (e.g. 85.0 means 85%). The `direction` field in hospital_forecast tells you whether the forecast is rising or falling relative to today.
Prefer short paragraphs or 3-5 bullets.

JSON CONTEXT:
{json.dumps(context, indent=2, default=str)}

USER QUESTION:
{query}
"""
    try:
        import ollama
        response = ollama.chat(
            model="llama3.2",
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0.15, "num_predict": 250, "top_p": 0.9},
        )
        return response["message"]["content"].strip()
    except Exception as ollama_err:
        logger.warning(f"Ollama unavailable ({ollama_err}), using rule-based fallback.")
        return _copilot_rule_based_answer(context, query)


def _copilot_rule_based_answer(context: Dict[str, Any], query: str) -> str:
    """Simple rule-based copilot fallback when Ollama is unavailable."""
    metrics = context.get("current_metrics", {})
    occ = metrics.get("occupancy_rate", 0)
    occ_pct = round(occ * 100, 1) if occ <= 1 else round(occ, 1)
    total_beds = metrics.get("total_beds", "N/A")
    occupied = metrics.get("occupied_beds", "N/A")
    hosp = context.get("hospital_forecast", {})
    mape = hosp.get("mape", "N/A")
    engine = hosp.get("engine", "prophet")
    day_horizon = hosp.get("day_horizon", {})
    horizon_rate = day_horizon.get("predicted_occupancy_rate", None)
    horizon_pct = round(horizon_rate * 100, 1) if horizon_rate and horizon_rate <= 1 else horizon_rate
    watchlist = context.get("department_watchlist", [])
    alerts = context.get("alerts", [])
    horizon_days = context.get("forecast_horizon_days", 30)

    lines = [
        f"**Current occupancy:** {occ_pct}% ({occupied}/{total_beds} beds occupied).",
        f"**{horizon_days}-day forecast:** {horizon_pct}% occupancy by day {horizon_days} (model: {engine}, MAPE: {mape}).",
    ]
    if watchlist:
        dept_lines = [f"  - {d.get('department','?')}: {round((d.get('rate',0))*100,1)}% ({d.get('occupied','?')}/{d.get('total_beds','?')} beds)" for d in watchlist[:5]]
        lines.append("**High-risk departments:**\n" + "\n".join(dept_lines))
    if alerts:
        lines.append(f"**Active alerts:** {len(alerts)} alert(s) — {alerts[0].get('message','') if alerts else ''}.")
    lines.append("\n*(Ollama/LLM not available — showing rule-based summary from dashboard context.)*")
    return "\n\n".join(lines)


BACKEND_DIR = Path(__file__).resolve().parent
DEFAULT_CSV_PATH = BACKEND_DIR / "data" / "hospital_enhanced_full_dataset.csv"

# Initialize data loader from CSV
class HospitalDataLoader:
    def __init__(self, csv_file_path: Union[str, Path] = DEFAULT_CSV_PATH):
        self.csv_file_path = str(csv_file_path)
        self.departments = ["ICU", "Emergency Ward", "General Ward", "Private Room", "Semi-Private"]
        self.data = None
        self.total_beds_per_department: Dict[str, int] = {}
        self.load_data()
    
    def load_data(self):
        """Load and transform patient stay CSV data into daily occupancy history."""
        try:
            raw = pd.read_csv(self.csv_file_path)
            
            # Check if this is already aggregated hospital data (enhanced format)
            if all(col in raw.columns for col in ['date', 'occupied_beds', 'total_beds', 'occupancy_rate']):
                logger.info("Detected aggregated hospital format (enhanced dataset)")
                self._load_aggregated_format(raw)
                return
            
            # Otherwise, use original patient-stay format
            logger.info("Using patient-stay format loader")
            self._load_patient_stay_format(raw)
            
        except Exception as e:
            logger.error(f"Error loading CSV data: {str(e)}")
            raise

    def _load_aggregated_format(self, raw: pd.DataFrame):
        """Load pre-aggregated daily hospital data (enhanced format)."""
        raw["date"] = pd.to_datetime(raw["date"])
        raw["department"] = raw.get("department", "General Ward")
        
        # If no department column, aggregate to hospital level
        if "department" not in raw.columns or raw["department"].isnull().all():
            daily_agg = raw.groupby("date", as_index=False).agg({
                "occupied_beds": "sum",
                "total_beds": "sum",
                "patient_count": "sum",
            }).copy()
            daily_agg["department"] = "Hospital"
        else:
            daily_agg = raw[["date", "department", "occupied_beds", "total_beds"]].copy()
            daily_agg["patient_count"] = raw.get("patient_count", daily_agg["occupied_beds"])
        
        daily_agg["occupancy_rate"] = (daily_agg["occupied_beds"] / daily_agg["total_beds"]).fillna(0).clip(0, 1.0)
        daily_agg["icu_beds"] = raw.get("icu_required", 0).sum() if "icu_required" in raw.columns else 0
        daily_agg["emergency_admissions"] = raw.get("emergency_admission", 0).sum() if "emergency_admission" in raw.columns else 0
        daily_agg["discharges"] = raw.get("discharges", 0).sum() if "discharges" in raw.columns else 0
        daily_agg["length_of_stay"] = raw.get("avg_length_of_stay", 0).mean() if "avg_length_of_stay" in raw.columns else 0
        daily_agg["avg_length_of_stay"] = daily_agg["length_of_stay"]
        daily_agg["labour_staffing"] = (daily_agg["occupied_beds"] * 0.6 + 4).round().astype(int)
        
        daily_agg = daily_agg.sort_values(["date", "department"]).reset_index(drop=True)
        self.data = normalize_hospital_dataframe(daily_agg)
        self.departments = sorted(self.data["department"].astype(str).unique())
        self.total_beds_per_department = {
            dept: int(max(1, self.data.loc[self.data["department"] == dept, "total_beds"].max()))
            for dept in self.departments
        }
        self.file_signature = self.current_file_signature()
        logger.info(f"Loaded {len(self.data)} daily occupancy rows from {self.csv_file_path} (aggregated format)")

    def _load_patient_stay_format(self, raw: pd.DataFrame):
        """Load patient-stay format (original format with Admission_DateTime, Discharge_DateTime)."""
        raw["Admission_DateTime"] = pd.to_datetime(raw["Admission_DateTime"], errors="coerce")
        raw["Discharge_DateTime"] = pd.to_datetime(raw["Discharge_DateTime"], errors="coerce")
        raw["Admission_Date"] = raw["Admission_DateTime"].dt.normalize()
        raw["Discharge_Date"] = raw["Discharge_DateTime"].dt.normalize()
        raw["Discharge_Date"] = raw["Discharge_Date"].fillna(raw["Admission_Date"] + pd.Timedelta(days=1))
        raw["Discharge_Date"] = raw["Discharge_Date"].where(raw["Discharge_Date"] > raw["Admission_Date"], raw["Admission_Date"] + pd.Timedelta(days=1))
        raw["Ward_Type"] = raw["Ward_Type"].fillna("General Ward")
        raw["Emergency_Admission"] = raw["Admission_Type"].fillna("") == "Emergency"

        rows = []
        for _, row in raw.iterrows():
            stay_start = row["Admission_Date"]
            stay_end = row["Discharge_Date"]
            if pd.isna(stay_start) or pd.isna(stay_end):
                continue
            if stay_end <= stay_start:
                stay_end = stay_start + pd.Timedelta(days=1)
            for date in pd.date_range(start=stay_start, end=stay_end - pd.Timedelta(days=1), freq="D"):
                rows.append({
                    "date": date,
                    "department": row["Ward_Type"],
                    "occupied_beds": 1,
                    "icu_beds": 1 if str(row.get("Ward_Type", "")).strip() == "ICU" or int(row.get("ICU_Requirement_Flag", 0) or 0) == 1 else 0,
                    "emergency_admissions": 1 if row["Emergency_Admission"] and date == stay_start else 0,
                    "discharges": 1 if date == stay_end - pd.Timedelta(days=1) else 0,
                    "length_of_stay": float(row.get("Length_of_Stay", 0) or 0),
                    "patient_count": 1,
                })

        if not rows:
            raise ValueError("Loaded CSV has no valid stay rows")

        daily = pd.DataFrame(rows)
        daily_agg = daily.groupby(["date", "department"], as_index=False).agg({
            "occupied_beds": "sum",
            "icu_beds": "sum",
            "emergency_admissions": "sum",
            "discharges": "sum",
            "length_of_stay": "mean",
            "patient_count": "sum",
        })
        daily_agg["date"] = pd.to_datetime(daily_agg["date"])
        daily_agg["total_beds"] = daily_agg["department"].map(self._infer_total_beds).fillna(100).astype(int)
        daily_agg["occupancy_rate"] = (daily_agg["occupied_beds"] / daily_agg["total_beds"]).fillna(0).clip(upper=1.0)
        daily_agg["avg_length_of_stay"] = daily_agg["length_of_stay"].fillna(0)
        daily_agg["labour_staffing"] = (daily_agg["occupied_beds"] * 0.6 + 4).round().astype(int)
        daily_agg = daily_agg.sort_values(["date", "department"]).reset_index(drop=True)

        self.data = normalize_hospital_dataframe(daily_agg)
        self.departments = sorted(self.data["department"].astype(str).unique())
        self.total_beds_per_department = {
            dept: int(max(1, self.data.loc[self.data["department"] == dept, "total_beds"].max()))
            for dept in self.departments
        }
        self.file_signature = self.current_file_signature()
        logger.info(f"Loaded {len(self.data)} daily occupancy rows from {self.csv_file_path} (patient-stay format)")

    def _infer_total_beds(self, department: str) -> int:
        capacity_map = {
            "ICU": 20,
            "Emergency Ward": 40,
            "Emergency": 40,
            "General Ward": 120,
            "Private Room": 25,
            "Private": 25,
            "Semi-Private": 35,
            "Semi Private": 35,
        }
        return capacity_map.get(str(department).strip(), 100)

    def current_file_signature(self) -> Optional[Dict[str, Any]]:
        try:
            path = Path(self.csv_file_path)
            stat = path.stat()
            return {
                "mtime": stat.st_mtime,
                "size": stat.st_size,
            }
        except Exception:
            return None

    def refresh_if_data_changed(self) -> bool:
        """Reload the source CSV if it changed and return True when reload occurred."""
        current_sig = self.current_file_signature()
        if current_sig != getattr(self, "file_signature", None):
            logger.info("Data change detected in %s; reloading data and clearing caches.", self.csv_file_path)
            self.load_data()
            self.file_signature = self.current_file_signature()
            return True
        return False
    
    def get_data(self) -> pd.DataFrame:
        """Get the loaded data"""
        return self.data
    
    def get_latest_data(self) -> pd.DataFrame:
        """Get the most recent data"""
        if self.data is not None and not self.data.empty:
            latest_date = self.data['date'].max()
            return self.data[self.data['date'] == latest_date]
        return pd.DataFrame()
    
    def get_disease_data(self) -> pd.DataFrame:
        """Get disease-specific data from CSV"""
        if self.data is not None and 'disease_category' in self.data.columns:
            return self.data
        return pd.DataFrame()

# Initialize data loader
data_loader = HospitalDataLoader()
historical_data = data_loader.get_data()

cache_lock = Lock()
api_cache: Dict[str, Any] = {}

def build_cache_key(endpoint: str, params: Dict[str, Any]) -> str:
    normalized = "+".join(
        f"{k}={params[k]}" for k in sorted(params) if params[k] is not None
    )
    return f"{endpoint}:{normalized}"


def get_cached(key: str) -> Optional[Any]:
    """Return cached result. Cache is permanent until data changes or server restarts."""
    with cache_lock:
        entry = api_cache.get(key)
        if entry is None:
            return None
        logger.info("[CACHE HIT] %s", key)
        return entry


def set_cached(key: str, data: Any) -> None:
    """Store result in cache. Cleared only on CSV data change or server restart."""
    with cache_lock:
        api_cache[key] = data


def refresh_data_cache_if_changed() -> None:
    global historical_data
    data_changed = data_loader.refresh_if_data_changed()
    if data_changed:
        historical_data = data_loader.get_data()
        with cache_lock:
            api_cache.clear()

class ForecastingService:
    """Delegates to forecast_engine (Prophet → ARIMAX (pmdarima) → XGBoost → naive)."""

    def generate_forecast(
        self,
        days: int = 7,
        department: str = None,
        model_preference: Optional[str] = None,
        as_of_date: Optional[str] = None,
        skip_narrative: bool = False,
    ) -> Dict[str, Any]:
        try:
            scoped = filter_through_as_of_date(historical_data, as_of_date)
            if department:
                dept_data = scoped[scoped["department"] == department]
            else:
                dept_data = scoped

            daily_data = (
                dept_data.groupby("date")
                .agg({"occupied_beds": "sum", "total_beds": "sum"})
                .reset_index()
            )
            daily_data["occupancy_rate"] = (
                daily_data["occupied_beds"] / daily_data["total_beds"]
            )
            daily_data = daily_data.sort_values("date").reset_index(drop=True)
            dept_label = department or "All departments (hospital total)"
            return run_occupancy_forecast(daily_data, days, dept_label, model_preference, skip_narrative=skip_narrative)
        except Exception as e:
            logger.error(f"Error generating forecast: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Forecast generation failed: {str(e)}")

    def generate_patient_count_forecast(
        self,
        days: int = 7,
        model_preference: Optional[str] = None,
        as_of_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        try:
            scoped = filter_through_as_of_date(historical_data, as_of_date)
            if scoped.empty:
                raise HTTPException(status_code=404, detail="No historical patient count data available")

            daily_data = (
                scoped.groupby("date")
                .agg({"patient_count": "sum", "total_beds": "max"})
                .reset_index()
            )
            daily_data = daily_data.sort_values("date").reset_index(drop=True)
            dept_label = "Hospital patient count"
            return run_generic_forecast(daily_data, days, "patient_count", dept_label, model_preference)
        except Exception as e:
            logger.error(f"Error generating patient count forecast: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Patient count forecast failed: {str(e)}")

    def generate_disease_admissions_forecast(
        self,
        disease: str,
        days: int = 7,
        department: Optional[str] = None,
        model_preference: Optional[str] = None,
        as_of_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate forecast for disease-specific admissions"""
        try:
            disease_data = filter_through_as_of_date(data_loader.get_disease_data(), as_of_date)
            if disease_data.empty:
                raise HTTPException(status_code=404, detail="No disease data available")
            
            # Filter for disease category or specific disease
            if 'disease_category' in disease_data.columns and disease in disease_data['disease_category'].values:
                filtered_data = disease_data[disease_data['disease_category'] == disease]
            else:
                filtered_data = disease_data[disease_data['specific_disease'] == disease]
            
            if department and department != "All":
                filtered_data = filtered_data[filtered_data['department'] == department]
            
            if filtered_data.empty:
                raise HTTPException(status_code=404, detail=f"No data found for disease '{disease}'" + (f" in department '{department}'" if department and department != "All" else ""))
            
            # Aggregate by date
            daily_data = (
                filtered_data.groupby("date")
                .agg({"patient_count": "sum"})
                .reset_index()
            )
            daily_data = daily_data.sort_values("date").reset_index(drop=True)
            
            # Add total_beds column for compatibility (use max from original data)
            daily_data["total_beds"] = int(disease_data["total_beds"].max()) if not disease_data.empty else 100
            
            dept_label = f"Disease: {disease}" + (f" in {department}" if department and department != "All" else "")
            return run_generic_forecast(daily_data, days, "patient_count", dept_label, model_preference)
        except Exception as e:
            logger.error(f"Error generating disease admissions forecast: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Disease admissions forecast failed: {str(e)}")

    def generate_disease_discharges_forecast(
        self,
        disease: str,
        days: int = 7,
        department: Optional[str] = None,
        model_preference: Optional[str] = None,
        as_of_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate forecast for disease-specific discharges"""
        try:
            disease_data = filter_through_as_of_date(data_loader.get_disease_data(), as_of_date)
            if disease_data.empty:
                raise HTTPException(status_code=404, detail="No disease data available")
            
            # Filter for disease category or specific disease
            if 'disease_category' in disease_data.columns and disease in disease_data['disease_category'].values:
                filtered_data = disease_data[disease_data['disease_category'] == disease]
            else:
                filtered_data = disease_data[disease_data['specific_disease'] == disease]
            
            if department and department != "All":
                filtered_data = filtered_data[filtered_data['department'] == department]
            
            if filtered_data.empty:
                raise HTTPException(status_code=404, detail=f"No data found for disease '{disease}'" + (f" in department '{department}'" if department and department != "All" else ""))
            
            # Aggregate by date
            daily_data = (
                filtered_data.groupby("date")
                .agg({"discharges": "sum"})
                .reset_index()
            )
            daily_data = daily_data.sort_values("date").reset_index(drop=True)
            
            # Add total_beds column for compatibility (use max from original data)
            daily_data["total_beds"] = int(disease_data["total_beds"].max()) if not disease_data.empty else 100
            
            dept_label = f"Disease: {disease}" + (f" in {department}" if department and department != "All" else "")
            return run_generic_forecast(daily_data, days, "discharges", dept_label, model_preference)
        except Exception as e:
            logger.error(f"Error generating disease discharges forecast: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Disease discharges forecast failed: {str(e)}")

    def generate_disease_los_forecast(
        self,
        disease: str,
        days: int = 7,
        department: Optional[str] = None,
        model_preference: Optional[str] = None,
        as_of_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate forecast for disease-specific average length of stay"""
        try:
            disease_data = filter_through_as_of_date(data_loader.get_disease_data(), as_of_date)
            if disease_data.empty:
                raise HTTPException(status_code=404, detail="No disease data available")
            
            # Filter for disease category or specific disease
            if 'disease_category' in disease_data.columns and disease in disease_data['disease_category'].values:
                filtered_data = disease_data[disease_data['disease_category'] == disease]
            else:
                filtered_data = disease_data[disease_data['specific_disease'] == disease]
            
            if department and department != "All":
                filtered_data = filtered_data[filtered_data['department'] == department]
            
            if filtered_data.empty:
                raise HTTPException(status_code=404, detail=f"No data found for disease '{disease}'" + (f" in department '{department}'" if department and department != "All" else ""))
            
            # Aggregate by date (mean LOS)
            daily_data = (
                filtered_data.groupby("date")
                .agg({"avg_length_of_stay": "mean"})
                .reset_index()
            )
            daily_data = daily_data.sort_values("date").reset_index(drop=True)
            # Forecast the operational LOS trend instead of the raw daily mean.
            # The source data is intentionally noisy day-to-day, while the client-facing
            # planning signal is the short-horizon LOS trend used for staffing/capacity.
            daily_data["avg_length_of_stay"] = (
                daily_data["avg_length_of_stay"]
                .rolling(window=7, min_periods=1)
                .mean()
            )
            
            # Add total_beds column for compatibility (use max from original data)
            daily_data["total_beds"] = int(disease_data["total_beds"].max()) if not disease_data.empty else 100
            
            dept_label = (
                f"Disease: {disease}" + (f" in {department}" if department and department != "All" else "")
                + " (7-day rolling LOS trend)"
            )
            return run_generic_forecast(daily_data, days, "avg_length_of_stay", dept_label, model_preference)
        except Exception as e:
            logger.error(f"Error generating disease LOS forecast: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Disease LOS forecast failed: {str(e)}")

# Initialize forecasting service
forecasting_service = ForecastingService()

# Initialize bed recommendation engine
bed_engine = None

def get_bed_engine():
    global bed_engine
    if bed_engine is None:
        bed_engine = create_bed_engine(historical_data)
    return bed_engine

class AlertService:
    def __init__(self):
        pass
    
    def generate_alerts(self, as_of_date: Optional[str] = None) -> List[AlertData]:
        """Generate operational alerts based on current data"""
        alerts = []
        scoped = filter_through_as_of_date(data_loader.get_data(), as_of_date)
        current_data = pd.DataFrame()
        if not scoped.empty:
            latest_date = scoped['date'].max()
            current_data = scoped[scoped['date'] == latest_date]
        
        if current_data.empty:
            latest_date = historical_data['date'].max()
            current_data = historical_data[historical_data['date'] == latest_date]
        
        # Check ICU occupancy
        icu_data = current_data[current_data['department'] == 'ICU']
        if not icu_data.empty:
            icu_occupancy = icu_data['occupancy_rate'].iloc[0]
            if icu_occupancy > 0.85:
                alerts.append(AlertData(
                    alert_type="ICU_HIGH_OCCUPANCY",
                    message=f"ICU occupancy at {icu_occupancy:.1%} - critical level",
                    severity="HIGH",
                    timestamp=datetime.now().isoformat(),
                    department="ICU"
                ))
            elif icu_occupancy > 0.75:
                alerts.append(AlertData(
                    alert_type="ICU_MODERATE_OCCUPANCY",
                    message=f"ICU occupancy at {icu_occupancy:.1%} - monitor closely",
                    severity="MEDIUM",
                    timestamp=datetime.now().isoformat(),
                    department="ICU"
                ))
        
        # Check overall occupancy
        total_occupied = current_data['occupied_beds'].sum()
        total_beds = current_data['total_beds'].sum()
        overall_occupancy = total_occupied / total_beds
        
        if overall_occupancy > 0.90:
            alerts.append(AlertData(
                alert_type="HIGH_OCCUPANCY",
                message=f"Overall hospital occupancy at {overall_occupancy:.1%} - bed shortage imminent",
                severity="HIGH",
                timestamp=datetime.now().isoformat()
            ))
        
        # Check emergency admissions
        emergency_data = current_data[current_data['department'] == 'Emergency']
        emergency_col = emergency_admissions_column(emergency_data)
        if not emergency_data.empty:
            emergency_admissions = int(emergency_data[emergency_col].iloc[0]) if emergency_col else 0
            if emergency_admissions > 10:
                alerts.append(AlertData(
                    alert_type="HIGH_EMERGENCY_ADMISSIONS",
                    message=f"High emergency admissions: {emergency_admissions} patients today",
                    severity="MEDIUM",
                    timestamp=datetime.now().isoformat(),
                    department="Emergency"
                ))
        
        return alerts

# Initialize alert service
alert_service = AlertService()

# Disease-specific forecast endpoints
@app.post("/api/disease/{disease}/admissions/forecast")
async def get_disease_admissions_forecast(disease: str, request: ForecastRequest):
    """Generate forecast for disease-specific emergency admissions"""
    refresh_data_cache_if_changed()
    cache_key = build_cache_key("disease_admissions", {
        "disease": disease, "days": request.days,
        "model": request.model_preference, "dept": request.department,
        "as_of": request.as_of_date,
    })
    cached = get_cached(cache_key)
    if cached is not None:
        return cached
    try:
        days = max(1, min(int(request.days), 365))
        result = forecasting_service.generate_disease_admissions_forecast(
            disease=disease,
            days=days,
            department=request.department,
            model_preference=request.model_preference,
            as_of_date=request.as_of_date,
        )
        set_cached(cache_key, result)
        return result
    except Exception as e:
        logger.error(f"Error generating disease admissions forecast: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Disease admissions forecast failed: {str(e)}")

@app.post("/api/disease/{disease}/discharges/forecast")
async def get_disease_discharges_forecast(disease: str, request: ForecastRequest):
    """Generate forecast for disease-specific discharges"""
    refresh_data_cache_if_changed()
    cache_key = build_cache_key("disease_discharges", {
        "disease": disease, "days": request.days,
        "model": request.model_preference, "dept": request.department,
        "as_of": request.as_of_date,
    })
    cached = get_cached(cache_key)
    if cached is not None:
        return cached
    try:
        days = max(1, min(int(request.days), 365))
        result = forecasting_service.generate_disease_discharges_forecast(
            disease=disease,
            days=days,
            department=request.department,
            model_preference=request.model_preference,
            as_of_date=request.as_of_date,
        )
        set_cached(cache_key, result)
        return result
    except Exception as e:
        logger.error(f"Error generating disease discharges forecast: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Disease discharges forecast failed: {str(e)}")

@app.post("/api/disease/{disease}/los/forecast")
async def get_disease_los_forecast(disease: str, request: ForecastRequest):
    """Generate forecast for disease-specific average length of stay"""
    refresh_data_cache_if_changed()
    cache_key = build_cache_key("disease_los", {
        "disease": disease, "days": request.days,
        "model": request.model_preference, "dept": request.department,
        "as_of": request.as_of_date,
    })
    cached = get_cached(cache_key)
    if cached is not None:
        return cached
    try:
        days = max(1, min(int(request.days), 365))
        result = forecasting_service.generate_disease_los_forecast(
            disease=disease,
            days=days,
            department=request.department,
            model_preference=request.model_preference,
            as_of_date=request.as_of_date,
        )
        set_cached(cache_key, result)
        return result
    except Exception as e:
        logger.error(f"Error generating disease LOS forecast: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Disease LOS forecast failed: {str(e)}")

@app.get("/")
async def root():
    return {"message": "Hospital Bed Occupancy Forecasting API"}

@app.get("/api/dashboard/available-dates")
async def get_dashboard_available_dates(limit: int = 30):
    """Latest available snapshot dates for the dashboard date picker."""
    try:
        limit = max(1, min(int(limit), 365))
        return {"dates": latest_available_dates(limit)}
    except Exception as e:
        logger.error(f"Error getting available dashboard dates: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get dashboard dates: {str(e)}")


@app.get("/api/dashboard/metrics", response_model=DashboardMetrics)
async def get_dashboard_metrics(as_of_date: Optional[str] = None):
    """Get current dashboard metrics from CSV data"""
    _ck = build_cache_key("dashboard_metrics", {"as_of": as_of_date})
    _hit = get_cached(_ck)
    if _hit is not None:
        return _hit
    try:
        scoped = filter_through_as_of_date(historical_data, as_of_date)
        latest_date = resolve_as_of_date(scoped, None)
        current_data = scoped[scoped['date'].dt.normalize() == latest_date]
        
        # If no latest data, get most recent date
        if current_data.empty:
            latest_date = historical_data['date'].max()
            current_data = historical_data[historical_data['date'] == latest_date]
        
        # Calculate overall metrics
        total_occupied = current_data['occupied_beds'].sum()
        total_beds = current_data['total_beds'].sum()
        current_occupancy_rate = total_occupied / total_beds
        
        # ICU metrics
        icu_data = current_data[current_data['department'] == 'ICU']
        if not icu_data.empty:
            icu_occupancy_rate = icu_data['occupancy_rate'].iloc[0]
            icu_occupied_beds = int(icu_data['occupied_beds'].iloc[0])
            icu_total_beds = int(icu_data['total_beds'].iloc[0])
            icu_available_beds = icu_total_beds - icu_occupied_beds
        else:
            icu_occupancy_rate = 0.0
            icu_occupied_beds = 0
            icu_total_beds = 0
            icu_available_beds = 0
        
        # Available beds
        available_beds = total_beds - total_occupied
        
        # Get 7-day forecast
        forecast = forecasting_service.generate_forecast(days=7, as_of_date=as_of_date)
        predicted_occupancy_7_days = forecast['forecast_data'][-1]['predicted_occupancy_rate']
        
        # Emergency admissions today
        emergency_data = current_data[current_data['department'] == 'Emergency']
        emergency_col = emergency_admissions_column(emergency_data)
        emergency_admissions_today = int(emergency_data[emergency_col].sum()) if not emergency_data.empty and emergency_col else 0
        
        # Average length of stay from CSV
        avg_length_of_stay = current_data['avg_length_of_stay'].mean() if 'avg_length_of_stay' in current_data.columns else 4.5

        raw_as_of = current_data['date'].iloc[0]
        if hasattr(raw_as_of, "strftime"):
            data_as_of_date = raw_as_of.strftime("%Y-%m-%d")
        else:
            data_as_of_date = str(raw_as_of)[:10]
        
        # Generate alerts
        alerts = alert_service.generate_alerts(as_of_date=as_of_date)
        
        _result = DashboardMetrics(
            current_occupancy_rate=current_occupancy_rate,
            occupied_beds=int(total_occupied),
            available_beds=available_beds,
            total_beds=total_beds,
            icu_occupancy_rate=icu_occupancy_rate,
            icu_occupied_beds=icu_occupied_beds,
            icu_available_beds=icu_available_beds,
            icu_total_beds=icu_total_beds,
            predicted_occupancy_7_days=predicted_occupancy_7_days,
            emergency_admissions_today=emergency_admissions_today,
            avg_length_of_stay=avg_length_of_stay,
            data_as_of_date=data_as_of_date,
            alerts=alerts
        )
        set_cached(_ck, _result)
        return _result
        
    except Exception as e:
        logger.error(f"Error getting dashboard metrics: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get dashboard metrics: {str(e)}")

@app.post("/api/forecast", response_model=ForecastResponse)
async def generate_forecast(request: ForecastRequest):
    """Generate occupancy forecast"""
    refresh_data_cache_if_changed()
    cache_key = build_cache_key("occupancy_forecast", {
        "days": request.days, "dept": request.department,
        "model": request.model_preference, "as_of": request.as_of_date,
    })
    cached = get_cached(cache_key)
    if cached is not None:
        return cached
    try:
        days = max(1, min(int(request.days), 365))
        result = forecasting_service.generate_forecast(
            days=days,
            department=request.department,
            model_preference=request.model_preference,
            as_of_date=request.as_of_date,
        )
        set_cached(cache_key, result)
        return result
    except Exception as e:
        logger.error(f"Error generating forecast: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Forecast generation failed: {str(e)}")


@app.post("/api/patient-count/forecast", response_model=GenericForecastResponse)
async def generate_patient_count_forecast(request: ForecastRequest):
    """Generate hospital-level patient count forecast"""
    refresh_data_cache_if_changed()
    cache_key = build_cache_key("patient_count_forecast", {
        "days": request.days, "model": request.model_preference, "as_of": request.as_of_date,
    })
    cached = get_cached(cache_key)
    if cached is not None:
        return cached
    try:
        days = max(1, min(int(request.days), 365))
        result = forecasting_service.generate_patient_count_forecast(
            days=days,
            model_preference=request.model_preference,
            as_of_date=request.as_of_date,
        )
        set_cached(cache_key, result)
        return result
    except Exception as e:
        logger.error(f"Error generating patient count forecast: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Patient count forecast failed: {str(e)}")


@app.post("/api/copilot/chat", response_model=CopilotChatResponse)
async def dashboard_copilot_chat(request: CopilotChatRequest):
    """Grounded dashboard chatbot backed by local llama3.2 via Ollama."""
    try:
        question = (request.query or "").strip()
        if not question:
            raise HTTPException(status_code=400, detail="Query must not be empty")

        forecast_days = max(7, min(int(request.forecast_days), 30))
        context = await build_copilot_context(
            as_of_date=request.as_of_date,
            model_preference=request.model_preference,
            forecast_days=forecast_days,
        )
        answer = generate_dashboard_copilot_answer(context, question)
        return CopilotChatResponse(
            answer=answer,
            as_of_date=context["snapshot_date"],
            model_preference=request.model_preference or "prophet",
            forecast_days=forecast_days,
            grounded=True,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating copilot answer: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Copilot chat failed: {str(e)}")

@app.get("/api/historical-data")
async def get_historical_data(days: int = 30, as_of_date: Optional[str] = None):
    """Get historical occupancy data"""
    try:
        filtered_data, _, _ = filter_recent_window(historical_data, days, as_of_date)
        return filtered_data.to_dict('records')
    except Exception as e:
        logger.error(f"Error getting historical data: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get historical data: {str(e)}")


@app.get("/api/analytics/chart-pack")
async def get_chart_pack(days: int = 30, as_of_date: Optional[str] = None):
    """
    Aggregated series for deep-dive charts: daily hospital trend, department mix,
    weekday heatmap, pressure scatter, disease mix, per-department rate series.
    """
    _ck = build_cache_key("chart_pack", {"days": days, "as_of_date": as_of_date})
    _hit = get_cached(_ck)
    if _hit is not None:
        return _hit
    try:
        days = max(7, min(int(days), 800))
        df = historical_data.copy()
        if df.empty:
            return {
                "date_range": {"start": None, "end": None},
                "daily": [],
                "departments_latest": [],
                "heatmap": {"weekdays": [], "departments": [], "values": []},
                "scatter_pressure": [],
                "disease_mix": [],
            }

        dff, start, end = filter_recent_window(df, days, as_of_date)

        emerg_col = emergency_admissions_column(dff)
        dis_col = "discharges" if "discharges" in dff.columns else None
        los_col = "avg_length_of_stay" if "avg_length_of_stay" in dff.columns else None
        pat_col = "patient_count" if "patient_count" in dff.columns else None
        dis_cat = "disease_category" if "disease_category" in dff.columns else None
        staff_col = "labour_staffing" if "labour_staffing" in dff.columns else None

        dff["day"] = dff["date"].dt.strftime("%Y-%m-%d")
        agg_map = {
            "occupied_beds": "sum",
            "total_beds": "sum",
        }
        if emerg_col:
            agg_map[emerg_col] = "sum"
        if dis_col:
            agg_map[dis_col] = "sum"
        if los_col:
            agg_map[los_col] = "mean"
        if pat_col:
            agg_map[pat_col] = "sum"
        if staff_col:
            agg_map[staff_col] = "sum"

        daily_g = dff.groupby("day", as_index=False).agg(agg_map)
        daily_g.rename(columns={"day": "date"}, inplace=True)
        if emerg_col:
            daily_g.rename(columns={emerg_col: "emergency_admissions"}, inplace=True)
        else:
            daily_g["emergency_admissions"] = 0
        if dis_col:
            daily_g.rename(columns={dis_col: "discharges"}, inplace=True)
        else:
            daily_g["discharges"] = 0
        if los_col:
            daily_g.rename(columns={los_col: "avg_los"}, inplace=True)
        else:
            daily_g["avg_los"] = 0.0
        if pat_col:
            daily_g.rename(columns={pat_col: "patient_count"}, inplace=True)
        else:
            daily_g["patient_count"] = 0
        if staff_col:
            daily_g.rename(columns={staff_col: "labour_staffing"}, inplace=True)
        else:
            daily_g["labour_staffing"] = 0

        daily_g["occupancy_rate"] = daily_g["occupied_beds"] / daily_g["total_beds"].replace(0, np.nan)
        daily_g["occupancy_rate"] = daily_g["occupancy_rate"].fillna(0)
        daily = daily_g.sort_values("date")

        latest_date = dff["date"].max()
        latest = dff[dff["date"] == latest_date]
        departments_latest = []
        for _, row in latest.iterrows():
            departments_latest.append(
                {
                    "department": row["department"],
                    "occupied_beds": int(row["occupied_beds"]),
                    "total_beds": int(row["total_beds"]),
                    "occupancy_rate": float(row["occupancy_rate"]),
                }
            )

        dff["dow"] = dff["date"].dt.dayofweek
        heat = (
            dff.groupby(["dow", "department"])["occupancy_rate"]
            .mean()
            .unstack(fill_value=0.0)
        )
        weekday_labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        heat_depts = list(heat.columns)
        mat = []
        for dow in range(7):
            row = []
            for dep in heat_depts:
                if dow in heat.index:
                    row.append(round(float(heat.loc[dow, dep]) * 100, 2))
                else:
                    row.append(0.0)
            mat.append(row)

        scatter_pressure = [
            {
                "date": r["date"],
                "emergency_admissions": int(r["emergency_admissions"]),
                "occupancy_rate": round(float(r["occupancy_rate"]) * 100, 2),
                "occupied_beds": int(r["occupied_beds"]),
            }
            for _, r in daily.iterrows()
        ]

        disease_mix = []
        if dis_cat and pat_col:
            dm = (
                dff.groupby(dis_cat)[pat_col]
                .sum()
                .sort_values(ascending=False)
                .head(12)
            )
            disease_mix = [
                {"category": str(k), "patient_count": int(v)} for k, v in dm.items()
            ]

        return {
            "date_range": {
                "start": start.strftime("%Y-%m-%d"),
                "end": end.strftime("%Y-%m-%d"),
            },
            "daily": daily.to_dict("records"),
            "departments_latest": departments_latest,
            "heatmap": {
                "weekdays": weekday_labels,
                "departments": heat_depts,
                "values": mat,
            },
            "scatter_pressure": scatter_pressure,
            "disease_mix": disease_mix,
        }
        set_cached(_ck, _result)
        return _result
    except Exception as e:
        logger.error(f"Error building chart pack: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Chart pack failed: {str(e)}")


@app.get("/api/analytics/historical-rolling-forecast")
async def get_historical_rolling_forecast(
    days: int = 90,
    block_days: int = 21,
    train_days: int = 90,
    model_preference: Optional[str] = None,
    as_of_date: Optional[str] = None,
):
    """Walk-forward rolling forecast: train on `train_days` window, predict `block_days` blocks."""
    _ck = build_cache_key("hist_rolling", {"days": days, "block_days": block_days, "train_days": train_days, "model": model_preference, "as_of": as_of_date})
    _hit = get_cached(_ck)
    if _hit is not None:
        return _hit
    try:
        _result = generate_rolling_historical_forecast(days, block_days, model_preference, as_of_date, train_days)
        set_cached(_ck, _result)
        return _result
    except Exception as e:
        logger.error(f"Error building historical rolling forecast: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Historical rolling forecast failed: {str(e)}")


@app.get("/api/analytics/historical-staffing-forecast")
async def get_historical_staffing_forecast(
    days: int = 90,
    block_days: int = 21,
    train_days: int = 90,
    model_preference: Optional[str] = None,
    as_of_date: Optional[str] = None,
):
    """Walk-forward rolling forecast for labour staffing: train on `train_days`, predict `block_days` blocks."""
    _ck = build_cache_key("hist_staffing", {"days": days, "block_days": block_days, "train_days": train_days, "model": model_preference, "as_of": as_of_date})
    _hit = get_cached(_ck)
    if _hit is not None:
        return _hit
    try:
        _result = _generate_staffing_forecast_sync(days, block_days, train_days, model_preference)
        if _result is None:
            return {"forecast_data": [], "confidence_interval": {"lower": [], "upper": []},
                    "model_metrics": {}, "forecast_model": {}}
        set_cached(_ck, _result)
        return _result
    except Exception as e:
        logger.error(f"Error building historical staffing forecast: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Historical staffing forecast failed: {str(e)}")


@app.get("/api/analytics/expanding-window-staffing-forecast")
async def get_expanding_window_staffing_forecast(
    model_preference: Optional[str] = None,
    as_of_date: Optional[str] = None,
):
    """
    Expanding window rolling forecast: 48 iterations.
    - Base training: Year 1 (52 weeks = 364 days)
    - Each iteration adds 1 week from Year 2 to training
    - Predicts 12 weeks (84 days) ahead each iteration
    - Stores Week 1, Week 2, Week 3 predictions separately for evaluation
    """
    try:
        df = historical_data.copy()
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        if df.empty or "labour_staffing" not in df.columns:
            return {"forecast_data": [], "week1_predictions": [], "week2_predictions": [], "week3_predictions": [],
                    "model_metrics": {"week1_mape": 0, "week2_mape": 0, "week3_mape": 0},
                    "forecast_model": {}}

        # Apply as_of_date filter
        scoped = filter_through_as_of_date(df, as_of_date)
        if scoped.empty:
            return {"forecast_data": [], "week1_predictions": [], "week2_predictions": [], "week3_predictions": [],
                    "model_metrics": {"week1_mape": 0, "week2_mape": 0, "week3_mape": 0},
                    "forecast_model": {}}

        # Sort dates
        all_dates = sorted(scoped["date"].dt.normalize().unique())
        if len(all_dates) < 364 + 84:  # Need at least Year 1 + 12 weeks
            return {"forecast_data": [], "week1_predictions": [], "week2_predictions": [], "week3_predictions": [],
                    "model_metrics": {"week1_mape": 0, "week2_mape": 0, "week3_mape": 0},
                    "forecast_model": {}}

        # Year 1 end date (364 days from start)
        year1_end_date = all_dates[363]  # Index 363 = day 364
        year2_dates = [d for d in all_dates if d > year1_end_date]
        
        if len(year2_dates) < 48 * 7:  # Need 48 weeks of Year 2 data
            logger.warning("Insufficient Year 2 data for 48 iterations")
            return {"forecast_data": [], "week1_predictions": [], "week2_predictions": [], "week3_predictions": [],
                    "model_metrics": {"week1_mape": 0, "week2_mape": 0, "week3_mape": 0},
                    "forecast_model": {}}

        # Storage for week-specific predictions
        week1_preds: List[Dict[str, Any]] = []
        week2_preds: List[Dict[str, Any]] = []
        week3_preds: List[Dict[str, Any]] = []
        all_forecast_points: List[Dict[str, Any]] = []

        # 48 iterations
        for i in range(48):
            # Training end: add i weeks from Year 2
            train_end_idx = 364 + (i * 7)
            if train_end_idx >= len(all_dates):
                break
            
            train_end_date = all_dates[train_end_idx]
            
            # Training data: from start to train_end_date
            training_df = scoped[scoped["date"].dt.normalize() <= train_end_date]
            if training_df.empty or training_df["date"].dt.normalize().nunique() < 52:
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
                logger.warning("Expanding window iteration %d failed: %s", i + 1, exc)
                continue

            block_points = block_fc.get("forecast_data", []) or []
            if not block_points:
                continue

            # Store predictions by week-out horizon
            # Week 1: days 1-7 (indices 0-6)
            # Week 2: days 8-14 (indices 7-13)
            # Week 3: days 15-21 (indices 14-20)
            for idx, point in enumerate(block_points):
                date_str = point["date"]
                value = point["predicted_value"]
                
                # Store in all forecast points
                all_forecast_points.append({
                    "date": date_str,
                    "predicted_value": value,
                    "iteration": i + 1,
                })

                # Week-specific storage
                if 0 <= idx < 7:  # Week 1
                    week1_preds.append({"date": date_str, "predicted_value": value, "iteration": i + 1})
                elif 7 <= idx < 14:  # Week 2
                    week2_preds.append({"date": date_str, "predicted_value": value, "iteration": i + 1})
                elif 14 <= idx < 21:  # Week 3
                    week3_preds.append({"date": date_str, "predicted_value": value, "iteration": i + 1})

        # Calculate MAPE per week-out horizon
        actual_daily = (
            scoped.groupby(scoped["date"].dt.strftime("%Y-%m-%d"))["labour_staffing"].sum()
            if "labour_staffing" in scoped.columns else pd.Series(dtype=float)
        )

        def calc_mape(preds: List[Dict[str, Any]]) -> float:
            errors = [
                abs(actual_daily[p["date"]] - p["predicted_value"]) / actual_daily[p["date"]]
                for p in preds
                if p["date"] in actual_daily.index and actual_daily[p["date"]] > 0
            ]
            return round(float(np.mean(errors)) * 100, 2) if errors else 0.0

        week1_mape = calc_mape(week1_preds)
        week2_mape = calc_mape(week2_preds)
        week3_mape = calc_mape(week3_preds)

        combined_metrics = {
            "week1_mape": week1_mape,
            "week2_mape": week2_mape,
            "week3_mape": week3_mape,
            "iterations_completed": len(all_forecast_points) // 84 if all_forecast_points else 0,
        }

        combined_model = block_fc.get("forecast_model") if 'block_fc' in locals() else {}

        return {
            "forecast_data": all_forecast_points,
            "week1_predictions": week1_preds,
            "week2_predictions": week2_preds,
            "week3_predictions": week3_preds,
            "model_metrics": combined_metrics,
            "forecast_model": combined_model,
        }
    except Exception as e:
        logger.error(f"Error building expanding window staffing forecast: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Expanding window staffing forecast failed: {str(e)}")


@app.get("/api/analytics/department-forecasts")
async def get_department_forecasts(
    days: int = 14,
    time_window: Optional[str] = None,
    model_preference: Optional[str] = None,
    as_of_date: Optional[str] = None,
):
    """
    Per-department bed occupancy forecast (same engine stack as /api/forecast).
    Horizons are capped to keep response time reasonable (Prophet × many depts).
    
    time_window options: "14_days", "30_days", "90_days", "6_months", "12_months"
    """
    try:
        # Map time_window to days
        time_window_map = {
            "14_days": 14,
            "30_days": 30,
            "90_days": 90,
            "6_months": 180,
            "12_months": 365
        }
        
        if time_window and time_window in time_window_map:
            days = time_window_map[time_window]
        
        days = max(7, min(int(days), 365))
        _ck = build_cache_key("dept_forecasts", {"days": days, "model": model_preference, "as_of": as_of_date})
        _hit = get_cached(_ck)
        if _hit is not None:
            return _hit
        out_list: List[Dict[str, Any]] = []

        def _forecast_dept(dept: str) -> Dict[str, Any]:
            try:
                fc = forecasting_service.generate_forecast(
                    days=days,
                    department=dept,
                    model_preference=model_preference,
                    as_of_date=as_of_date,
                    skip_narrative=True,
                )
                fd = fc.get("forecast_data") or []
                if not fd:
                    return {"department": dept, "error": "no_forecast_rows", "points": []}
                sub = filter_through_as_of_date(historical_data, as_of_date)
                sub = sub[sub["department"] == dept]
                if not sub.empty:
                    sub = sub.sort_values("date")
                    total_beds = int(sub["total_beds"].iloc[-1])
                else:
                    r0 = float(fd[0]["predicted_occupancy_rate"])
                    total_beds = int(round(float(fd[0]["predicted_occupied_beds"]) / max(r0, 1e-9)))
                mm = fc.get("model_metrics") or {}
                fm = fc.get("forecast_model") or {}
                points = []
                for p in fd:
                    pr = float(p["predicted_occupancy_rate"])
                    lo = float(p["lower_bound"])
                    hi = float(p["upper_bound"])
                    lower_beds = max(0, min(int(round(lo * float(total_beds))), total_beds))
                    upper_beds = max(0, min(int(round(hi * float(total_beds))), total_beds))
                    if upper_beds < lower_beds:
                        lower_beds, upper_beds = upper_beds, lower_beds
                    points.append({
                        "date": p["date"],
                        "rate_pct": round(pr * 100.0, 2),
                        "occupied": int(p["predicted_occupied_beds"]),
                        "lower_pct": round(lo * 100.0, 2),
                        "upper_pct": round(hi * 100.0, 2),
                        "lower_beds": lower_beds,
                        "upper_beds": upper_beds,
                    })
                return {
                    "department": dept,
                    "total_beds": total_beds,
                    "engine": str(mm.get("engine", "")),
                    "mape": float(mm.get("mape", 0.0)),
                    "rmse": float(mm.get("rmse", 0.0)),
                    "model_name": str(fm.get("name", "")),
                    "points": points,
                }
            except Exception as ex:
                logger.warning("Department forecast failed for %s: %s", dept, ex)
                return {"department": dept, "error": str(ex), "points": []}

        with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(data_loader.departments), 6)) as pool:
            out_list = list(pool.map(_forecast_dept, data_loader.departments))
        # Build summary with calculation explanation
        model_label = model_preference or "automatic default order"
        summary = {
            "time_window_days": days,
            "time_window_label": f"{days} days",
            "calculation_method": (
                f"Department-level forecasting using the requested model preference "
                f"('{model_label}') with safe fallbacks when a model cannot fit the data."
            ),
            "models_used": list(set([d.get("engine", "") for d in out_list if d.get("engine")])),
            "forecast_approach": (
                "The endpoint respects the selected model when possible and otherwise falls back "
                "through the supported forecasting stack until one succeeds.\n"
                "1. Prophet: additive time-series model for recurring seasonal patterns\n"
                "2. ARIMAX (pmdarima auto_arima): statistical model for autocorrelation and trend structure\n"
                "3. XGBoost: feature-based machine learning model with lag signals\n"
                "4. Naive Drift: last-resort fallback when richer models cannot fit"
            ),
            "seasonal_factors_analyzed": [
                "Weekly patterns (weekday vs weekend admission trends)",
                "Monthly/seasonal variations (summer vs winter disease patterns)",
                "Recent trend direction (accelerating vs decelerating)",
                "Volatility and uncertainty bounds"
            ],
            "why_this_prediction": (
                "The predicted trend reflects the department's historical occupancy path, "
                "recent direction of change, and the model family that successfully fit that series.\n"
                f"- Forecast horizon analyzed: {days} days\n"
                f"- Requested model preference: {model_label}\n"
                "- Returned engine list shows which models actually fit each department\n"
                "- Confidence intervals widen when volatility is higher"
            )
        }
        
        _result = {
            "forecast_days": days,
            "summary": summary,
            "departments": out_list
        }
        set_cached(_ck, _result)
        return _result
    except Exception as e:
        logger.error(f"Error building department forecasts: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Department forecasts failed: {str(e)}"
        )


@app.get("/api/departments")
async def get_departments():
    """Get list of departments"""
    return {"departments": data_loader.departments}


def disease_dataset_date_range(df: pd.DataFrame) -> Dict[str, Optional[str]]:
    """Min/max calendar dates in disease-related rows (for UI captions)."""
    if df is None or df.empty or "date" not in df.columns:
        return {"start": None, "end": None}
    s = pd.to_datetime(df["date"], errors="coerce").dropna()
    if s.empty:
        return {"start": None, "end": None}
    return {"start": s.min().strftime("%Y-%m-%d"), "end": s.max().strftime("%Y-%m-%d")}


# Disease Analytics Endpoints
@app.get("/api/disease/list")
async def get_disease_list():
    """Get list of all diseases in CSV data"""
    try:
        disease_data = data_loader.get_disease_data()
        if not disease_data.empty and 'specific_disease' in disease_data.columns:
            diseases = disease_data['specific_disease'].unique().tolist()
            return {"diseases": diseases}
        return {"diseases": []}
    except Exception as e:
        logger.error(f"Error getting disease list: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get disease list: {str(e)}")

@app.get("/api/disease/insights/{disease}")
async def get_disease_insights(disease: str):
    """Get insights for a specific disease from CSV data"""
    try:
        disease_data = data_loader.get_disease_data()
        if disease_data.empty:
            return {"error": "No disease data available"}
        
        # Filter for specific disease
        disease_specific = disease_data[disease_data['specific_disease'] == disease]
        
        if disease_specific.empty:
            return {"error": f"Disease '{disease}' not found"}
        
        # Calculate insights
        insights = {
            "disease_name": disease,
            "total_cases": int(disease_specific['patient_count'].sum()),
            "avg_occupancy_rate": float(disease_specific['occupancy_rate'].mean()),
            "avg_length_of_stay": float(disease_specific['avg_length_of_stay'].mean()),
            "departments": disease_specific['department'].unique().tolist(),
            "severity_distribution": disease_specific['severity'].value_counts().to_dict(),
            "peak_months": disease_specific.groupby('month')['patient_count'].sum().nlargest(3).index.tolist() if 'month' in disease_specific.columns else [],
            "icu_required_rate": float(disease_specific[disease_specific['icu_required'] == True]['patient_count'].sum() / disease_specific['patient_count'].sum()) if 'icu_required' in disease_specific.columns else 0,
            "emergency_rate": (
                float(
                    disease_specific[disease_specific[emergency_admissions_column(disease_specific)] > 0]['patient_count'].sum()
                    / disease_specific['patient_count'].sum()
                )
                if emergency_admissions_column(disease_specific)
                else 0
            ),
            "date_range": disease_dataset_date_range(disease_specific),
        }
        
        return insights
    except Exception as e:
        logger.error(f"Error getting disease insights: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get disease insights: {str(e)}")

@app.get("/api/disease/monthly-patterns")
async def get_monthly_patterns():
    """Get monthly disease patterns from CSV data"""
    try:
        disease_data = data_loader.get_disease_data()
        if disease_data.empty:
            return {"monthly_patterns": {}, "dataset_date_range": {"start": None, "end": None}}
        
        # Convert date to month if not already present
        if 'month' not in disease_data.columns and 'date' in disease_data.columns:
            disease_data['month'] = pd.to_datetime(disease_data['date']).dt.month
        
        monthly_patterns = {}
        for month in range(1, 13):
            month_data = disease_data[disease_data['month'] == month] if 'month' in disease_data.columns else pd.DataFrame()
            if not month_data.empty:
                month_name = datetime(2025, month, 1).strftime('%B')
                monthly_patterns[month_name] = {
                    "total_patients": int(month_data['patient_count'].sum()),
                    "avg_occupancy": float(month_data['occupancy_rate'].mean()),
                    "top_diseases": month_data.groupby('specific_disease')['patient_count'].sum().nlargest(3).to_dict(),
                    "disease_categories": month_data.groupby('disease_category')['patient_count'].sum().to_dict(),
                    "severity_breakdown": month_data['severity'].value_counts().to_dict(),
                    "department_pressure": month_data.groupby('department')['occupancy_rate'].mean().to_dict()
                }
        
        return {
            "monthly_patterns": monthly_patterns,
            "dataset_date_range": disease_dataset_date_range(disease_data),
        }
    except Exception as e:
        logger.error(f"Error getting monthly patterns: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get monthly patterns: {str(e)}")

@app.get("/api/disease/top-diseases")
async def get_top_diseases():
    """Get top diseases by patient count from CSV data"""
    try:
        disease_data = data_loader.get_disease_data()
        if disease_data.empty:
            return {"top_diseases": {}, "dataset_date_range": {"start": None, "end": None}}
        
        top_diseases = disease_data.groupby('specific_disease')['patient_count'].sum().nlargest(10).to_dict()
        
        return {
            "top_diseases": {k: int(v) for k, v in top_diseases.items()},
            "dataset_date_range": disease_dataset_date_range(disease_data),
        }
    except Exception as e:
        logger.error(f"Error getting top diseases: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get top diseases: {str(e)}")

@app.get("/api/disease/current-month-analysis")
async def get_current_month_analysis():
    """Get analysis for current month from CSV data"""
    try:
        disease_data = data_loader.get_disease_data()
        if disease_data.empty:
            return {"error": "No disease data available"}
        
        disease_data = disease_data.copy()
        disease_data['date'] = pd.to_datetime(disease_data['date'], errors='coerce')
        disease_data = disease_data.dropna(subset=['date'])
        if disease_data.empty:
            return {"error": "No disease data available"}

        latest_date = disease_data['date'].max()
        current_month = latest_date.month
        current_month_name = latest_date.strftime('%B')
        current_year = latest_date.year
        disease_data['month'] = disease_data['date'].dt.month
        disease_data['year'] = disease_data['date'].dt.year
        month_data = disease_data[
            (disease_data['month'] == current_month) & (disease_data['year'] == current_year)
        ]
        
        if month_data.empty:
            return {"error": f"No data available for {current_month_name}"}
        
        date_range = {"start": None, "end": None}
        if "date" in month_data.columns:
            dt_series = pd.to_datetime(month_data["date"], errors="coerce").dropna()
            if not dt_series.empty:
                date_range["start"] = dt_series.min().strftime("%Y-%m-%d")
                date_range["end"] = dt_series.max().strftime("%Y-%m-%d")

        year_display: Union[int, str] = current_year

        analysis = {
            "month": current_month_name,
            "year": year_display,
            "date_range": date_range,
            "total_patients": int(month_data['patient_count'].sum()),
            "avg_occupancy": float(month_data['occupancy_rate'].mean()),
            "top_diseases": month_data.groupby('specific_disease')['patient_count'].sum().nlargest(3).to_dict(),
            "disease_categories": month_data.groupby('disease_category')['patient_count'].sum().to_dict(),
            "department_pressure": month_data.groupby('department')['occupancy_rate'].mean().to_dict(),
            "severity_breakdown": month_data['severity'].value_counts().to_dict(),
            "recommendations": generate_monthly_recommendations(current_month, month_data)
        }
        
        return analysis
    except Exception as e:
        logger.error(f"Error getting current month analysis: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get current month analysis: {str(e)}")

def generate_monthly_recommendations(month: int, month_data: pd.DataFrame) -> List[str]:
    """Generate month-specific recommendations based on disease patterns"""
    recommendations = []
    
    # Seasonal recommendations
    if month in [12, 1, 2]:  # Winter
        recommendations.extend([
            "Prepare for respiratory illness season",
            "Ensure adequate flu vaccine supplies",
            "Prepare for increased cardiac events during holidays"
        ])
    elif month in [6, 7, 8]:  # Summer
        recommendations.extend([
            "Prepare for heat-related illnesses",
            "Ensure water safety protocols",
            "Prepare for sports injuries"
        ])
    elif month in [3, 4, 5]:  # Spring
        recommendations.extend([
            "Prepare for allergy season",
            "Prepare for spring sports injuries",
            "Monitor for early respiratory issues"
        ])
    else:  # Fall
        recommendations.extend([
            "Prepare for fall allergy season",
            "Prepare for back-to-school illnesses",
            "Monitor for early flu season"
        ])
    
    # Department-specific recommendations based on data
    if not month_data.empty:
        dept_pressure = month_data.groupby('department')['occupancy_rate'].mean()
        high_pressure_depts = [dept for dept, occ in dept_pressure.items() if occ > 0.8]
        if high_pressure_depts:
            recommendations.append(f"High pressure expected in: {', '.join(high_pressure_depts)}")
    
    return recommendations


@app.get("/api/disease/categories")
async def get_disease_categories():
    """Get list of disease categories from CSV data"""
    try:
        disease_data = data_loader.get_disease_data()
        if disease_data.empty:
            return {"categories": []}
        
        if 'disease_category' in disease_data.columns:
            categories = disease_data['disease_category'].unique().tolist()
        else:
            categories = []
        
        return {"categories": categories}
    except Exception as e:
        logger.error(f"Error getting disease categories: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get disease categories: {str(e)}")


@app.post("/api/labour-staffing/forecast")
async def get_labour_staffing_forecast(request: ForecastRequest):
    """Generate forecast for total hospital labour staffing requirements."""
    refresh_data_cache_if_changed()
    cache_key = build_cache_key("labour_staffing_forecast", {
        "days": request.days, "model": request.model_preference,
        "dept": request.department, "as_of": request.as_of_date,
    })
    cached = get_cached(cache_key)
    if cached is not None:
        return cached
    try:
        days = max(1, min(int(request.days), 365))
        scoped = filter_through_as_of_date(historical_data, request.as_of_date)
        if scoped.empty or "labour_staffing" not in scoped.columns:
            raise HTTPException(status_code=404, detail="No labour staffing data available")
        agg_cols = {"labour_staffing": "sum", "total_beds": "sum"}
        if "patient_count" in scoped.columns:
            agg_cols["patient_count"] = "sum"
        daily_data = (
            scoped.groupby("date")
            .agg(agg_cols)
            .reset_index()
            .sort_values("date")
            .reset_index(drop=True)
        )
        result = run_generic_forecast(
            daily_data, days, "labour_staffing",
            "Hospital Labour Staffing", request.model_preference,
        )
        set_cached(cache_key, result)
        return result
    except Exception as e:
        logger.error(f"Error generating labour staffing forecast: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Labour staffing forecast failed: {str(e)}")


@app.post("/api/ed/wait-time/forecast")
async def get_ed_wait_time_forecast(request: ForecastRequest):
    """Generate forecast for Emergency Department wait times."""
    refresh_data_cache_if_changed()
    cache_key = build_cache_key("ed_wait_time", {
        "days": request.days, "model": request.model_preference, "as_of": request.as_of_date,
    })
    cached = get_cached(cache_key)
    if cached is not None:
        return cached
    try:
        days = max(1, min(int(request.days), 365))
        scoped = filter_through_as_of_date(historical_data, request.as_of_date)
        ed_data = scoped[scoped['department'] == 'Emergency'].copy()
        if ed_data.empty or 'ed_wait_time_minutes' not in ed_data.columns:
            raise HTTPException(status_code=404, detail="No Emergency Department wait time data available")

        daily_data = (
            ed_data.groupby("date")
            .agg({"ed_wait_time_minutes": "mean", "total_beds": "sum"})
            .reset_index()
            .sort_values("date")
            .reset_index(drop=True)
        )
        daily_data["ed_wait_time_minutes"] = (
            daily_data["ed_wait_time_minutes"]
            .rolling(window=3, min_periods=1)
            .mean()
        )
        result = run_generic_forecast(
            daily_data,
            days,
            "ed_wait_time_minutes",
            "Emergency Department wait time",
            request.model_preference,
        )
        set_cached(cache_key, result)
        return result
    except Exception as e:
        logger.error(f"Error generating ED wait time forecast: {str(e)}")
        raise HTTPException(status_code=500, detail=f"ED wait time forecast failed: {str(e)}")


# Disease-category endpoints (alias for disease endpoints)
@app.post("/api/disease-category/{category}/admissions/forecast")
async def get_disease_category_admissions_forecast(category: str, request: ForecastRequest):
    """Generate forecast for disease category admissions"""
    refresh_data_cache_if_changed()
    cache_key = build_cache_key("cat_admissions", {
        "category": category, "days": request.days,
        "model": request.model_preference, "dept": request.department,
        "as_of": request.as_of_date,
    })
    cached = get_cached(cache_key)
    if cached is not None:
        return cached
    try:
        days = max(1, min(int(request.days), 365))
        result = forecasting_service.generate_disease_admissions_forecast(
            disease=category,
            days=days,
            department=request.department,
            model_preference=request.model_preference,
            as_of_date=request.as_of_date,
        )
        set_cached(cache_key, result)
        return result
    except Exception as e:
        logger.error(f"Error generating disease category admissions forecast: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Disease category admissions forecast failed: {str(e)}")


@app.post("/api/disease-category/{category}/discharges/forecast")
async def get_disease_category_discharges_forecast(category: str, request: ForecastRequest):
    """Generate forecast for disease category discharges"""
    refresh_data_cache_if_changed()
    cache_key = build_cache_key("cat_discharges", {
        "category": category, "days": request.days,
        "model": request.model_preference, "dept": request.department,
        "as_of": request.as_of_date,
    })
    cached = get_cached(cache_key)
    if cached is not None:
        return cached
    try:
        days = max(1, min(int(request.days), 365))
        result = forecasting_service.generate_disease_discharges_forecast(
            disease=category,
            days=days,
            department=request.department,
            model_preference=request.model_preference,
            as_of_date=request.as_of_date,
        )
        set_cached(cache_key, result)
        return result
    except Exception as e:
        logger.error(f"Error generating disease category discharges forecast: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Disease category discharges forecast failed: {str(e)}")


@app.post("/api/disease-category/{category}/los/forecast")
async def get_disease_category_los_forecast(category: str, request: ForecastRequest):
    """Generate forecast for disease category LOS"""
    refresh_data_cache_if_changed()
    cache_key = build_cache_key("cat_los", {
        "category": category, "days": request.days,
        "model": request.model_preference, "dept": request.department,
        "as_of": request.as_of_date,
    })
    cached = get_cached(cache_key)
    if cached is not None:
        return cached
    try:
        days = max(1, min(int(request.days), 365))
        result = forecasting_service.generate_disease_los_forecast(
            disease=category,
            days=days,
            department=request.department,
            model_preference=request.model_preference,
            as_of_date=request.as_of_date,
        )
        set_cached(cache_key, result)
        return result
    except Exception as e:
        logger.error(f"Error generating disease category LOS forecast: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Disease category LOS forecast failed: {str(e)}")


# =============================================================================
# REGISTRATION & BED ALLOCATION ENDPOINTS
# =============================================================================

class PatientRegistration(BaseModel):
    """Patient registration request."""
    first_name: str
    last_name: str
    age: int
    gender: str
    condition: str
    specialty: str
    payer_channel: str
    is_critical: bool = False
    requires_ventilator: bool = False
    requires_isolation: bool = False
    requires_dialysis: bool = False
    notes: Optional[str] = None

class BedRecommendationRequest(BaseModel):
    """Bed recommendation request."""
    patient_data: Dict[str, Any]
    include_forecast: bool = True

class AdmissionRequest(BaseModel):
    """Complete admission request with patient and bed."""
    patient: PatientRegistration
    bed_id: Optional[str] = None

@app.get("/api/config/payer-channels")
async def get_payer_channels():
    """Get dynamic payer channel configuration."""
    return {"payer_channels": config_service.get_payer_channels()}

@app.get("/api/config/business-rules")
async def get_business_rules():
    """Get dynamic business rules for bed allocation."""
    return {"business_rules": config_service.get_business_rules()}

@app.get("/api/config/occupancy-thresholds")
async def get_occupancy_thresholds():
    """Get dynamic occupancy alert thresholds."""
    return {"thresholds": config_service.get_occupancy_thresholds()}

@app.get("/api/config/bed-types")
async def get_bed_types():
    """Get available bed types."""
    return {"bed_types": config_service.get_bed_types()}

@app.get("/api/config/specialties")
async def get_specialties():
    """Get medical specialty list."""
    return {"specialties": config_service.get_specialty_list()}

@app.get("/api/model-metadata")
async def get_model_metadata():
    """Get ML model metadata including version and accuracy."""
    try:
        # Get latest forecast to extract model info
        forecast = forecasting_service.generate_forecast(days=7, skip_narrative=True)
        
        return {
            "model_name": forecast.get("forecast_model", {}).get("name", "Prophet"),
            "engine": forecast.get("model_metrics", {}).get("engine", "prophet"),
            "mape": forecast.get("model_metrics", {}).get("mape", 0),
            "rmse": forecast.get("model_metrics", {}).get("rmse", 0),
            "last_trained": datetime.now().isoformat(),
            "data_range": {
                "start": historical_data["date"].min().isoformat() if not historical_data.empty else None,
                "end": historical_data["date"].max().isoformat() if not historical_data.empty else None
            },
            "version": "2.0"
        }
    except Exception as e:
        logger.error(f"Error getting model metadata: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Model metadata failed: {str(e)}")

@app.post("/api/bed/recommend")
async def recommend_beds(request: BedRecommendationRequest):
    """Get AI-powered bed recommendations."""
    try:
        engine = get_bed_engine()
        
        # Get forecast data if requested
        forecast_data = None
        if request.include_forecast:
            try:
                forecast = forecasting_service.generate_forecast(days=7, skip_narrative=True)
                forecast_data = forecast
            except Exception as e:
                logger.warning(f"Could not fetch forecast data: {e}")
        
        recommendations = engine.recommend_beds(request.patient_data, forecast_data)
        
        return {
            "recommendations": recommendations,
            "timestamp": datetime.now().isoformat(),
            "patient_summary": {
                "predicted_los": engine.predict_los(request.patient_data),
                "payer_channel": request.patient_data.get("payer_channel"),
                "priority": "high" if request.patient_data.get("is_critical") else "normal"
            }
        }
    except Exception as e:
        logger.error(f"Error recommending beds: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Bed recommendation failed: {str(e)}")

@app.post("/api/admissions/register")
async def register_admission(request: AdmissionRequest):
    """Register a new patient admission."""
    try:
        engine = get_bed_engine()
        
        # Get bed recommendations if no bed specified
        if not request.bed_id:
            patient_dict = request.patient.model_dump()
            recommendations = engine.recommend_beds(patient_dict)
            
            if not recommendations:
                raise HTTPException(status_code=404, detail="No available beds found")
            
            recommended_bed = recommendations[0]
        else:
            recommended_bed = {"bed_id": request.bed_id}
        
        # In production, this would:
        # 1. Create patient record
        # 2. Allocate bed
        # 3. Update inventory
        # 4. Trigger notifications
        
        admission_id = f"ADM{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        return {
            "admission_id": admission_id,
            "patient": request.patient.model_dump(),
            "allocated_bed": recommended_bed,
            "predicted_los": engine.predict_los(request.patient.model_dump()),
            "status": "confirmed",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error registering admission: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Admission registration failed: {str(e)}")

@app.get("/api/payer/forecast")
async def get_payer_forecast(days: int = 30, payer_channel: Optional[str] = None):
    """Get payer-specific demand forecast."""
    try:
        days = max(7, min(int(days), 90))
        payer_channels = config_service.get_payer_channels()
        
        # Generate forecast per payer
        forecasts = []
        for payer in payer_channels:
            if payer_channel and payer["id"] != payer_channel:
                continue
            
            # Mock payer-specific forecast
            # In production, segment by payer_channel column
            base_forecast = forecasting_service.generate_forecast(days=days, skip_narrative=True)
            
            forecasts.append({
                "payer_channel": payer["id"],
                "payer_name": payer["name"],
                "expected_admissions": len(base_forecast["forecast_data"]) * 2,
                "avg_los": 4.5 * payer["avg_los_multiplier"],
                "predicted_occupancy_impact": round(np.mean([p["predicted_occupancy_rate"] for p in base_forecast["forecast_data"]]) * 100, 1),
                "confidence": "high" if base_forecast["model_metrics"]["mape"] < 30 else "medium"
            })
        
        return {
            "forecast_days": days,
            "payer_forecasts": forecasts,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting payer forecast: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Payer forecast failed: {str(e)}")

@app.get("/api/alerts")
async def get_alerts(severity: Optional[str] = None):
    """Get current occupancy alerts."""
    try:
        thresholds = config_service.get_occupancy_thresholds()
        metrics = await get_dashboard_metrics()
        
        alerts_list = []
        
        # Hospital-level alerts
        if metrics.current_occupancy_rate >= thresholds["critical"]:
            alerts_list.append({
                "type": "occupancy_critical",
                "severity": "critical",
                "message": f"Hospital at {metrics.current_occupancy_rate*100:.1f}% occupancy - Critical level",
                "department": "Hospital",
                "timestamp": datetime.now().isoformat()
            })
        elif metrics.current_occupancy_rate >= thresholds["high"]:
            alerts_list.append({
                "type": "occupancy_high",
                "severity": "high",
                "message": f"Hospital at {metrics.current_occupancy_rate*100:.1f}% occupancy - Monitor closely",
                "department": "Hospital",
                "timestamp": datetime.now().isoformat()
            })
        
        # ICU alerts
        if metrics.icu_occupancy_rate >= thresholds["critical"]:
            alerts_list.append({
                "type": "icu_critical",
                "severity": "critical",
                "message": f"ICU at {metrics.icu_occupancy_rate*100:.1f}% - Critical shortage",
                "department": "ICU",
                "timestamp": datetime.now().isoformat()
            })
        
        if severity:
            alerts_list = [a for a in alerts_list if a["severity"] == severity]
        
        return {
            "alerts": alerts_list,
            "count": len(alerts_list),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting alerts: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Alerts fetch failed: {str(e)}")

@app.get("/api/bed-status")
async def get_bed_status(department: Optional[str] = None):
    """Get real-time bed status."""
    try:
        # Mock bed status - in production, query real-time inventory
        departments_data = [
            {
                "department": "ICU",
                "total_beds": 20,
                "available": 3,
                "occupied": 15,
                "cleaning": 1,
                "maintenance": 1,
                "reserved": 0
            },
            {
                "department": "General Ward",
                "total_beds": 120,
                "available": 25,
                "occupied": 90,
                "cleaning": 3,
                "maintenance": 2,
                "reserved": 0
            },
            {
                "department": "Emergency",
                "total_beds": 40,
                "available": 8,
                "occupied": 30,
                "cleaning": 1,
                "maintenance": 1,
                "reserved": 0
            }
        ]
        
        if department:
            departments_data = [d for d in departments_data if d["department"] == department]
        
        # Add predicted occupancy from forecast
        forecast = forecasting_service.generate_forecast(days=1, skip_narrative=True)
        predicted_rate = forecast["forecast_data"][0]["predicted_occupancy_rate"] if forecast["forecast_data"] else 0
        
        for dept in departments_data:
            dept["predicted_occupancy_tomorrow"] = round(predicted_rate * 100, 1)
            dept["overflow_risk"] = "high" if dept["available"] < 3 else "low"
        
        return {
            "departments": departments_data,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting bed status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Bed status failed: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
