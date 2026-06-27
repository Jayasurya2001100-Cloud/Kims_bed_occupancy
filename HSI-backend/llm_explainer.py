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
