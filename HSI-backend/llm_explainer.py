"""
LLM-based forecast explanation generator using local Ollama models.
Falls back to data-driven code generation if Ollama is not available.
"""
import json
import logging
from typing import Dict, Any, List, Optional
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

def get_llm_explanation(
    forecast_data: List[Dict[str, Any]],
    historical_data: pd.DataFrame,
    model_name: str,
    trend: float,
    seasonal_patterns: Dict[str, Any] = None
) -> str:
    """
    Generate natural language explanation for forecast using local LLM or code-based logic.
    
    Args:
        forecast_data: List of forecast points
        historical_data: Historical occupancy data
        model_name: Name of forecasting model used
        trend: Trend coefficient
        seasonal_patterns: Detected seasonal patterns (optional)
    
    Returns:
        Natural language explanation string
    """
    try:
        import ollama
        use_llm = True
    except ImportError:
        logger.info("Ollama not available, using code-based explanations")
        use_llm = False
    
    # Analyze historical data
    analysis = _analyze_historical_data(historical_data, forecast_data, trend)
    
    if use_llm:
        try:
            return _generate_llm_explanation(analysis, model_name)
        except Exception as e:
            logger.warning(f"LLM explanation failed: {e}, falling back to code-based")
            return _generate_code_explanation(analysis, model_name)
    else:
        return _generate_code_explanation(analysis, model_name)


def _analyze_historical_data(
    historical_data: pd.DataFrame,
    forecast_data: List[Dict[str, Any]],
    trend: float
) -> Dict[str, Any]:
    """Analyze historical data to extract patterns"""
    historical_data = historical_data.copy()

    if 'date' in historical_data.columns:
        historical_data['date'] = pd.to_datetime(historical_data['date'])
        historical_data['weekday'] = historical_data['date'].dt.dayofweek
        historical_data['month'] = historical_data['date'].dt.month
    
    # Calculate statistics
    recent_30 = historical_data.tail(30)
    recent_avg = recent_30['occupancy_rate'].mean() if 'occupancy_rate' in recent_30.columns else 0.7
    overall_avg = historical_data['occupancy_rate'].mean() if 'occupancy_rate' in historical_data.columns else 0.7
    volatility = historical_data['occupancy_rate'].std() if 'occupancy_rate' in historical_data.columns else 0.05
    
    # Detect weekly patterns
    if 'weekday' in historical_data.columns and 'occupancy_rate' in historical_data.columns:
        weekly_pattern = historical_data.groupby('weekday')['occupancy_rate'].mean().to_dict()
        weekday_avg = np.mean([weekly_pattern.get(i, 0.7) for i in range(5)])
        weekend_avg = np.mean([weekly_pattern.get(i, 0.7) for i in [5, 6]])
    else:
        weekday_avg = recent_avg
        weekend_avg = recent_avg
        weekly_pattern = {}
    
    # Detect monthly patterns
    if 'month' in historical_data.columns and 'occupancy_rate' in historical_data.columns:
        monthly_pattern = historical_data.groupby('month')['occupancy_rate'].mean().to_dict()
    else:
        monthly_pattern = {}
    
    # Forecast analysis
    if forecast_data:
        forecast_start = forecast_data[0].get('predicted_occupancy_rate', recent_avg)
        forecast_end = forecast_data[-1].get('predicted_occupancy_rate', recent_avg)
        forecast_change = forecast_end - forecast_start
    else:
        forecast_start = recent_avg
        forecast_end = recent_avg
        forecast_change = 0
    
    # Trend direction
    if trend > 0.001:
        trend_direction = "increasing"
    elif trend < -0.001:
        trend_direction = "decreasing"
    else:
        trend_direction = "stable"
    
    return {
        "recent_avg": recent_avg,
        "overall_avg": overall_avg,
        "volatility": volatility,
        "weekday_avg": weekday_avg,
        "weekend_avg": weekend_avg,
        "weekly_pattern": weekly_pattern,
        "monthly_pattern": monthly_pattern,
        "trend": trend,
        "trend_direction": trend_direction,
        "forecast_start": forecast_start,
        "forecast_end": forecast_end,
        "forecast_change": forecast_change,
        "data_points": len(historical_data)
    }


def _generate_llm_explanation(analysis: Dict[str, Any], model_name: str) -> str:
    """Generate explanation using Ollama LLM"""
    import ollama

    # Calculate key metrics
    change_pct = ((analysis['forecast_end'] / analysis['forecast_start']) - 1) * 100
    weekend_diff = abs(((analysis['weekend_avg'] / analysis['weekday_avg']) - 1) * 100) if analysis['weekday_avg'] > 0 else 0

    prompt = f"""You are a hospital operations expert. Write a clear, human-readable forecast explanation.

FORECAST DATA:
- Occupancy will change from {analysis['forecast_start']:.1%} to {analysis['forecast_end']:.1%} ({change_pct:+.1f}%)
- Recent 30-day average: {analysis['recent_avg']:.1%}
- Historical average: {analysis['overall_avg']:.1%}
- Trend: {analysis['trend_direction']}
- Weekend vs Weekday: {analysis['weekend_avg']:.1%} vs {analysis['weekday_avg']:.1%} ({weekend_diff:.0f}% difference)
- Volatility: {analysis['volatility']:.1%}

Write in this structure:

📊 WHAT TO EXPECT
[1-2 sentences on the prediction]

🔍 WHY THIS IS HAPPENING
[2-3 sentences explaining the trend and recent patterns]

📅 WEEKLY PATTERNS
[1-2 sentences on weekday vs weekend, with practical implications]

💡 RECOMMENDED ACTIONS
[1-2 sentences on what hospital should do]

Use plain English. No jargon. Be specific with numbers. Make it actionable."""

    try:
        response = ollama.chat(
            model='llama3.2',  # Using llama3.2
            messages=[{'role': 'user', 'content': prompt}],
            options={
                'temperature': 0.3,
                'num_predict': 400,  # Increased for more detailed response
                'top_p': 0.9
            }
        )
        explanation = response['message']['content'].strip()
        logger.info(f"LLM explanation generated successfully ({len(explanation)} chars)")
        return explanation
    except Exception as e:
        logger.error(f"Ollama API error: {e}")
        raise


def _generate_code_explanation(analysis: Dict[str, Any], model_name: str) -> str:
    """Generate human-readable explanation in plain ASCII text."""
    start = float(analysis.get('forecast_start', 0.0) or 0.0)
    end = float(analysis.get('forecast_end', 0.0) or 0.0)
    base = max(abs(start), 0.01)
    change_pct = ((end - start) / base) * 100
    recent_avg = float(analysis.get('recent_avg', 0.0) or 0.0)
    overall_avg = float(analysis.get('overall_avg', 0.0) or 0.0)
    volatility = float(analysis.get('volatility', 0.0) or 0.0)
    weekday_avg = float(analysis.get('weekday_avg', recent_avg) or recent_avg)
    weekend_avg = float(analysis.get('weekend_avg', recent_avg) or recent_avg)
    trend_direction = analysis.get('trend_direction', 'stable')
    data_points = int(analysis.get('data_points', 0) or 0)

    if abs(change_pct) >= 1.0:
        change_sentence = (
            f"Bed occupancy is expected to {'increase' if change_pct > 0 else 'decrease'} "
            f"by about {abs(change_pct):.1f}% across the forecast window, moving from "
            f"{start:.1%} to {end:.1%}."
        )
    else:
        change_sentence = (
            f"Bed occupancy is expected to stay broadly stable around {recent_avg:.1%} "
            f"with only limited day-to-day movement."
        )

    if trend_direction == "increasing":
        trend_sentence = (
            f"Recent demand is running above the longer-term norm ({recent_avg:.1%} vs "
            f"{overall_avg:.1%}), so the model projects continued pressure on capacity."
        )
    elif trend_direction == "decreasing":
        trend_sentence = (
            f"Recent demand is below the longer-term norm ({recent_avg:.1%} vs "
            f"{overall_avg:.1%}), so the model projects easing pressure."
        )
    else:
        trend_sentence = (
            f"Recent demand is close to the longer-term norm ({recent_avg:.1%} vs "
            f"{overall_avg:.1%}), so the model projects a mostly steady operating state."
        )

    weekly_lines = []
    if abs(weekday_avg - weekend_avg) > 0.02 and weekday_avg > 0:
        diff_pct = abs(((weekend_avg - weekday_avg) / weekday_avg) * 100)
        if weekend_avg > weekday_avg:
            weekly_lines.append(
                f"Weekends run about {diff_pct:.0f}% busier than weekdays "
                f"({weekend_avg:.1%} vs {weekday_avg:.1%})."
            )
            weekly_lines.append(
                "That pattern supports extra weekend staffing and bed-turnover planning."
            )
        else:
            weekly_lines.append(
                f"Weekdays run about {diff_pct:.0f}% busier than weekends "
                f"({weekday_avg:.1%} vs {weekend_avg:.1%})."
            )
            weekly_lines.append(
                "That pattern suggests scheduled work is driving a larger share of demand."
            )
    else:
        weekly_lines.append("No strong weekday-versus-weekend swing stands out in the recent data.")

    if volatility > 0.08:
        confidence_sentence = (
            f"Occupancy is fairly volatile (+/-{volatility * 100:.1f} percentage points), "
            "so forecast ranges should be treated as wide planning bounds."
        )
    elif volatility > 0.04:
        confidence_sentence = (
            f"Occupancy shows moderate variability (+/-{volatility * 100:.1f} percentage points), "
            "so the forecast is directionally useful with some uncertainty."
        )
    else:
        confidence_sentence = (
            f"Occupancy is relatively stable (+/-{volatility * 100:.1f} percentage points), "
            "so the forecast should be comparatively reliable."
        )

    model_text = model_name or "forecasting model"
    actions = []
    if trend_direction == "increasing":
        actions.append("Review discharge planning and surge-capacity options.")
        actions.append("Watch higher-pressure departments for staffing or transfer bottlenecks.")
    elif trend_direction == "decreasing":
        actions.append("Use the softer demand window to absorb elective work or backlog safely.")
        actions.append("Keep monitoring for any reversal in the most recent trend.")
    else:
        actions.append("Maintain current staffing and escalation rules.")
        actions.append("Monitor exceptions rather than planning for a major system-wide shift.")

    sections = [
        "WHAT TO EXPECT",
        change_sentence,
        "",
        "WHY THIS IS HAPPENING",
        trend_sentence,
        "",
        "WEEKLY PATTERNS",
        *weekly_lines,
        "",
        "CONFIDENCE LEVEL",
        confidence_sentence,
        "",
        "HOW THIS WAS PREDICTED",
        f"The explanation is based on {data_points} historical data points and the selected engine: {model_text}.",
        "",
        "RECOMMENDED ACTIONS",
        f"- {actions[0]}",
        f"- {actions[1]}",
    ]
    return "\n".join(sections)


def _strip_json_fence(text: str) -> str:
    text = (text or "").strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


def _analyze_series_forecast(
    historical_data: pd.DataFrame,
    forecast_data: List[Dict[str, Any]],
    trend: float,
    value_label: str,
    unit: str,
    model_metrics: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    historical = historical_data.copy()
    if "date" in historical.columns:
        historical["date"] = pd.to_datetime(historical["date"], errors="coerce")
        historical["weekday"] = historical["date"].dt.dayofweek

    value_col = None
    for candidate in ("predicted_value", "predicted_occupancy_rate"):
        if forecast_data and candidate in forecast_data[0]:
            value_col = candidate
            break

    hist_value_col = None
    for candidate in ("avg_length_of_stay", "patient_count", "discharges", "ed_wait_time_minutes", "occupancy_rate"):
        if candidate in historical.columns:
            hist_value_col = candidate
            break

    series = historical[hist_value_col].astype(float) if hist_value_col else pd.Series(dtype=float)
    recent = series.tail(30) if not series.empty else pd.Series(dtype=float)
    recent_avg = float(recent.mean()) if not recent.empty else 0.0
    overall_avg = float(series.mean()) if not series.empty else recent_avg
    volatility = float(series.std()) if len(series) > 1 else 0.0

    weekday_avg = recent_avg
    weekend_avg = recent_avg
    if "weekday" in historical.columns and hist_value_col:
        grouped = historical.groupby("weekday")[hist_value_col].mean().to_dict()
        weekday_avg = float(np.mean([grouped.get(i, recent_avg) for i in range(5)]))
        weekend_avg = float(np.mean([grouped.get(i, recent_avg) for i in (5, 6)]))

    if forecast_data and value_col:
        forecast_start = float(forecast_data[0][value_col])
        forecast_end = float(forecast_data[-1][value_col])
        lower_avg = float(np.mean([p.get("lower_bound", forecast_start) for p in forecast_data]))
        upper_avg = float(np.mean([p.get("upper_bound", forecast_end) for p in forecast_data]))
    else:
        forecast_start = recent_avg
        forecast_end = recent_avg
        lower_avg = recent_avg
        upper_avg = recent_avg

    if trend > 1e-3:
        trend_direction = "increasing"
    elif trend < -1e-3:
        trend_direction = "decreasing"
    else:
        trend_direction = "stable"

    base = max(abs(forecast_start), 1e-3)
    change_pct = ((forecast_end - forecast_start) / base) * 100.0
    uncertainty_span = max(0.0, upper_avg - lower_avg)

    return {
        "value_label": value_label,
        "unit": unit,
        "recent_avg": recent_avg,
        "overall_avg": overall_avg,
        "volatility": volatility,
        "weekday_avg": weekday_avg,
        "weekend_avg": weekend_avg,
        "forecast_start": forecast_start,
        "forecast_end": forecast_end,
        "change_pct": change_pct,
        "trend": trend,
        "trend_direction": trend_direction,
        "uncertainty_span": uncertainty_span,
        "horizon_days": len(forecast_data),
        "data_points": int(len(historical)),
        "mape": float((model_metrics or {}).get("mape", 0.0) or 0.0),
        "rmse": float((model_metrics or {}).get("rmse", 0.0) or 0.0),
    }


def _generate_code_series_narrative(analysis: Dict[str, Any], model_name: str) -> Dict[str, Any]:
    label = analysis["value_label"]
    unit = analysis["unit"]
    start = analysis["forecast_start"]
    end = analysis["forecast_end"]
    change_pct = analysis["change_pct"]
    recent_avg = analysis["recent_avg"]
    overall_avg = analysis["overall_avg"]
    trend_direction = analysis["trend_direction"]
    horizon_days = analysis["horizon_days"]
    mape = analysis["mape"] * 100 if analysis["mape"] <= 1 else analysis["mape"]
    uncertainty_span = analysis["uncertainty_span"]
    weekday_avg = analysis["weekday_avg"]
    weekend_avg = analysis["weekend_avg"]
    volatility = analysis["volatility"]

    if abs(change_pct) >= 1.0:
        summary = (
            f"{label.title()} is forecast to {'rise' if change_pct > 0 else 'fall'} by about "
            f"{abs(change_pct):.1f}% over the next {horizon_days} days, moving from "
            f"{start:.1f} to {end:.1f} {unit}."
        )
    else:
        summary = (
            f"{label.title()} is forecast to stay broadly stable over the next {horizon_days} days, "
            f"holding near {end:.1f} {unit}."
        )

    explanation_lines = [
        summary,
        (
            f"The recent average is {recent_avg:.1f} {unit} versus a longer-run average of "
            f"{overall_avg:.1f} {unit}, so the current direction is {trend_direction}."
        ),
    ]
    if abs(weekday_avg - weekend_avg) > max(0.15, 0.04 * max(recent_avg, 1.0)):
        explanation_lines.append(
            f"Weekday versus weekend behavior is material: weekdays average {weekday_avg:.1f} {unit}, "
            f"while weekends average {weekend_avg:.1f} {unit}."
        )
    explanation = " ".join(explanation_lines)

    insights = [
        (
            f"Forecast endpoint: {end:.1f} {unit} by day {horizon_days}, "
            f"{'up' if change_pct > 0.5 else 'down' if change_pct < -0.5 else 'roughly flat'} from the opening forecast day."
        ),
        (
            f"Expected planning range is about {max(0.0, end - uncertainty_span / 2):.1f} to "
            f"{end + uncertainty_span / 2:.1f} {unit} based on the current uncertainty band."
        ),
        (
            f"Observed variability is {volatility:.2f} {unit}; "
            f"{'keep capacity flexible' if volatility > 1.0 else 'short-term planning should be relatively stable'}."
        ),
    ]
    return {"summary": summary, "explanation": explanation, "insights": insights}


def _generate_llm_series_narrative(analysis: Dict[str, Any], model_name: str) -> Dict[str, Any]:
    import ollama

    prompt = f"""You are generating forecast commentary for a hospital operations dashboard.

Return valid JSON with this exact schema:
{{
  "summary": "one short paragraph",
  "explanation": "one short paragraph",
  "insights": ["bullet 1", "bullet 2", "bullet 3"]
}}

DATA:
- Metric: {analysis['value_label']}
- Unit: {analysis['unit']}
- Forecast horizon: {analysis['horizon_days']} days
- Forecast start: {analysis['forecast_start']:.2f}
- Forecast end: {analysis['forecast_end']:.2f}
- Change percent: {analysis['change_pct']:+.2f}%
- Recent average: {analysis['recent_avg']:.2f}
- Historical average: {analysis['overall_avg']:.2f}
- Volatility: {analysis['volatility']:.2f}
- Weekday average: {analysis['weekday_avg']:.2f}
- Weekend average: {analysis['weekend_avg']:.2f}
- Model: {model_name}

Rules:
- Base every statement on the data above.
- Do not mention MAPE, RMSE, holdout scores, or any accuracy metrics.
- Do not mention the model name or technical model details.
- Do not use placeholders.
- Keep it concise and client-friendly.
"""
    raw = ollama.chat(
        model="llama3.2",
        messages=[{"role": "user", "content": prompt}],
        options={"temperature": 0.2, "num_predict": 300, "top_p": 0.9},
    )["message"]["content"]
    parsed = json.loads(_strip_json_fence(raw))
    insights = parsed.get("insights") or []
    if not isinstance(insights, list):
        insights = [str(insights)]
    return {
        "summary": str(parsed.get("summary", "")).strip(),
        "explanation": str(parsed.get("explanation", "")).strip(),
        "insights": [str(x).strip() for x in insights if str(x).strip()][:3],
    }


def get_series_forecast_narrative(
    forecast_data: List[Dict[str, Any]],
    historical_data: pd.DataFrame,
    model_name: str,
    trend: float,
    value_label: str,
    unit: str,
    model_metrics: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    analysis = _analyze_series_forecast(
        historical_data=historical_data,
        forecast_data=forecast_data,
        trend=trend,
        value_label=value_label,
        unit=unit,
        model_metrics=model_metrics,
    )
    try:
        import ollama  # noqa: F401
        return _generate_llm_series_narrative(analysis, model_name)
    except Exception as exc:
        logger.info("Series narrative fallback engaged: %s", exc)
        return _generate_code_series_narrative(analysis, model_name)


def get_bed_recommendation_reasoning(
    patient_data: Dict[str, Any],
    bed: Dict[str, Any],
    score: float,
    breakdown: Dict[str, float],
    dept_occupancy: Optional[Dict[str, float]] = None,
    payer_name: Optional[str] = None,
) -> str:
    """
    Generate natural language reasoning for a bed recommendation using local LLM.
    Falls back to code-based reasoning if Ollama is not available.

    Args:
        patient_data: Patient registration data
        bed: Bed details (id, department, type, room, status)
        score: Total suitability score (0-100)
        breakdown: Score breakdown by category
        dept_occupancy: Current occupancy rates per department
        payer_name: Patient's payer channel name

    Returns:
        Natural language reasoning string
    """
    try:
        import ollama
        # Quick health check - if Ollama server isn't running, don't attempt LLM call
        try:
            ollama.list()
            use_llm = True
        except Exception:
            use_llm = False
    except ImportError:
        use_llm = False

    if use_llm:
        try:
            return _generate_llm_bed_reasoning(patient_data, bed, score, breakdown, dept_occupancy, payer_name)
        except Exception as e:
            logger.warning(f"LLM bed reasoning failed: {e}, falling back to code-based")
            return _generate_code_bed_reasoning(patient_data, bed, score, breakdown, dept_occupancy, payer_name)
    else:
        return _generate_code_bed_reasoning(patient_data, bed, score, breakdown, dept_occupancy, payer_name)


def _generate_llm_bed_reasoning(
    patient_data: Dict[str, Any],
    bed: Dict[str, Any],
    score: float,
    breakdown: Dict[str, float],
    dept_occupancy: Optional[Dict[str, float]],
    payer_name: Optional[str],
) -> str:
    """Generate bed recommendation reasoning using Ollama LLM."""
    import ollama
    import signal

    # Timeout handler - prevent hanging if Ollama is slow
    def _timeout_handler(signum, frame):
        raise TimeoutError("Ollama LLM call timed out after 15 seconds")

    # Build context for the LLM
    occ_info = ""
    if dept_occupancy:
        occ_rate = dept_occupancy.get(bed["department"], 0.0)
        occ_info = f"Department occupancy: {occ_rate:.0%}"

    clinical_flags = []
    if patient_data.get("is_critical"):
        clinical_flags.append("Critical condition")
    if patient_data.get("requires_ventilator"):
        clinical_flags.append("Requires ventilator")
    if patient_data.get("requires_isolation"):
        clinical_flags.append("Requires isolation")
    if patient_data.get("requires_dialysis"):
        clinical_flags.append("Requires dialysis")

    prompt = f"""You are a hospital bed allocation expert. Explain why this bed was recommended for this patient.

BED ALLOCATION RULES (9 Rule Groups):
Rule Group 1 - Clinical Priority:
  IF Severity = Critical THEN Allocate ICU Bed Only
  IF Ventilator Required = Yes THEN Allocate Ventilator Bed Only
  IF Isolation Required = Yes THEN Allocate Isolation Bed Only
  IF Dialysis Required = Yes THEN Allocate Dialysis Unit Bed Only

Rule Group 2 - Specialty:
  IF Specialty = Cardiology THEN Prefer Cardiology Beds
  IF Specialty = Neurology THEN Prefer Neurology Beds
  IF Specialty = Oncology THEN Prefer Oncology Beds

Rule Group 3 - Pediatric:
  IF Age < 14 THEN Allocate Pediatric Beds Only

Rule Group 4 - Gender:
  IF Shared Room AND Gender = Female THEN Allocate Female Shared Room
  IF Shared Room AND Gender = Male THEN Allocate Male Shared Room

Rule Group 5 - Payer:
  IF Payer = International THEN Prefer Private / Deluxe Rooms
  IF Payer = Corporate THEN Validate Corporate Eligibility
  IF Payer = Insurance THEN Validate Insurance Eligibility
  IF Payer = CGHS THEN Validate CGHS Room Entitlement
  IF Payer = Cash THEN Allocate Based On Patient Preference

Rule Group 6 - Length of Stay:
  IF LOS > 10 Days THEN Avoid Premium High-Turnover Beds
  IF LOS < 2 Days THEN Allow Short Stay Beds

Rule Group 7 - Availability:
  IF Bed Status != Available THEN DO NOT Allocate
  IF Cleaning Pending THEN DO NOT Allocate
  IF Under Maintenance THEN DO NOT Allocate
  IF Reserved THEN DO NOT Allocate

Rule Group 8 - Occupancy Optimization:
  IF Department Occupancy > 95% THEN Recommend Overflow Capacity
  IF ICU Occupancy > 98% THEN Trigger Capacity Alert
  IF Department Occupancy > 90% THEN Trigger Early Discharge Review

Rule Group 9 - Revenue Optimization:
  IF Private Room Eligible AND Available THEN Recommend Private Room
  IF Corporate Package Covers Deluxe THEN Recommend Deluxe Room
  IF International Patient THEN Prioritize Premium Inventory

PATIENT:
- Name: {patient_data.get('first_name', '')} {patient_data.get('last_name', '')}
- Age: {patient_data.get('age', 'N/A')}, Gender: {patient_data.get('gender', 'N/A')}
- Condition: {patient_data.get('condition', 'N/A')}
- Specialty: {patient_data.get('specialty', 'N/A')}
- Payer: {payer_name or 'N/A'}
- Clinical flags: {', '.join(clinical_flags) if clinical_flags else 'None'}
- Predicted LOS: {breakdown.get('los', 0)} days

BED:
- Bed ID: {bed.get('id', 'N/A')}
- Department: {bed.get('department', 'N/A')}
- Room Type: {bed.get('type', 'N/A')}
- Room: {bed.get('room', 'N/A')}
- {occ_info}

SCORE BREAKDOWN (out of 100):
- Clinical Match: {breakdown.get('clinical', 0)}/40
- Specialty Match: {breakdown.get('specialty', 0)}/20
- Severity Match: {breakdown.get('severity', 0)}/15
- Payer Match: {breakdown.get('payer', 0)}/10
- LOS Match: {breakdown.get('los', 0)}/5
- Occupancy Optimization: {breakdown.get('occupancy', 0)}/5
- Revenue Optimization: {breakdown.get('revenue', 0)}/5
- TOTAL: {score}/100

Using the 9 rule groups above, write a concise 3-4 sentence explanation of why this bed was recommended. Reference the specific rule groups that influenced the decision. Mention the strongest scoring factors and any concerns. Use plain English."""

    # Set 15-second timeout for Ollama call
    old_handler = signal.signal(signal.SIGALRM, _timeout_handler)
    signal.alarm(15)
    try:
        response = ollama.chat(
            model='llama3.2',
            messages=[{'role': 'user', 'content': prompt}],
            options={
                'temperature': 0.3,
                'num_predict': 300,
                'top_p': 0.9
            }
        )
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)
    reasoning = response['message']['content'].strip()
    logger.info(f"LLM bed reasoning generated ({len(reasoning)} chars)")
    return reasoning


def _generate_code_bed_reasoning(
    patient_data: Dict[str, Any],
    bed: Dict[str, Any],
    score: float,
    breakdown: Dict[str, float],
    dept_occupancy: Optional[Dict[str, float]],
    payer_name: Optional[str],
) -> str:
    """Generate code-based bed recommendation reasoning (fallback)."""
    reasons = []

    # Clinical
    if breakdown.get("clinical", 0) >= 35:
        reasons.append("Excellent clinical match")
    elif breakdown.get("clinical", 0) >= 25:
        reasons.append("Good clinical match")
    elif breakdown.get("clinical", 0) > 0:
        reasons.append("Acceptable clinical match")

    # Specialty
    if breakdown.get("specialty", 0) >= 20:
        reasons.append(f"Exact specialty match ({bed['department']})")
    elif breakdown.get("specialty", 0) >= 10:
        reasons.append("Specialty-neutral")

    # Severity
    if breakdown.get("severity", 0) >= 15:
        reasons.append("Optimal severity-tier match")
    elif breakdown.get("severity", 0) >= 10:
        reasons.append("Good severity-tier match")

    # Payer
    if breakdown.get("payer", 0) >= 10:
        reasons.append(f"Payer-preferred room type for {payer_name}")
    elif breakdown.get("payer", 0) >= 7:
        reasons.append(f"Payer-eligible room type for {payer_name}")

    # Occupancy
    if dept_occupancy:
        occ_rate = dept_occupancy.get(bed["department"], 0.0)
        occ_pct = round(occ_rate * 100)
        if breakdown.get("occupancy", 0) >= 5:
            reasons.append(f"Low occupancy ({occ_pct}%) in {bed['department']}")
        elif breakdown.get("occupancy", 0) <= 1:
            reasons.append(f"High occupancy ({occ_pct}%) - overflow risk")

    # Revenue
    if breakdown.get("revenue", 0) >= 5:
        if payer_name == "International":
            reasons.append("Premium inventory for International patient")
        elif payer_name == "Corporate":
            reasons.append("Deluxe Room covered by Corporate package")
        else:
            reasons.append("Revenue-optimized room selection")

    # Score summary
    if score >= 90:
        reasons.append(f"Total score {score}/100 - optimal recommendation")
    elif score >= 70:
        reasons.append(f"Total score {score}/100 - strong match")
    else:
        reasons.append(f"Total score {score}/100 - acceptable match")

    return " | ".join(reasons)
