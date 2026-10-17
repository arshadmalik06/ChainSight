"""
Delay Predictor Tool for ChainSight Agent.
Deterministic heuristic baseline delay estimator.
Inputs: Disruption type, severity, duration, and weather evidence.
Outputs: Estimated additional delay in hours, risk category, and transparent calculation rule.
"""
from typing import Dict, Any, Optional

from schemas import DelayPrediction, SeverityLevel, DisruptionType, WeatherEvidence

# Base delay coefficients by disruption type (in hours)
DISRUPTION_BASE_HOURS = {
    DisruptionType.CYCLONE: 48.0,
    DisruptionType.PORT_CONGESTION: 72.0,
    DisruptionType.SUPPLIER_SHUTDOWN: 96.0,
    DisruptionType.INLAND_FLOODING: 36.0,
    DisruptionType.SHIPMENT_DELAY: 24.0,
    DisruptionType.GEOPOLITICAL: 60.0,
    DisruptionType.LABOR_STRIKE: 48.0,
    DisruptionType.OTHER: 24.0,
}

SEVERITY_FACTORS = {
    SeverityLevel.LOW: 0.5,
    SeverityLevel.MEDIUM: 1.0,
    SeverityLevel.HIGH: 1.5,
    SeverityLevel.CRITICAL: 2.2,
}


def estimate_delay(
    event_id: str,
    event_type: DisruptionType,
    severity: SeverityLevel,
    affected_node: str,
    expected_duration_hours: float = 48.0,
    weather: Optional[WeatherEvidence] = None,
) -> DelayPrediction:
    """
    Transparent, deterministic baseline delay estimator.
    Formula:
    delay_hours = (base_hours * severity_factor) + (weather_penalty) + (0.25 * duration_offset)
    """
    base_hours = DISRUPTION_BASE_HOURS.get(event_type, 24.0)
    sev_factor = SEVERITY_FACTORS.get(severity, 1.0)

    weather_penalty = 0.0
    weather_note = "No adverse weather factors applied."
    if weather:
        if weather.wind_speed_kmh and weather.wind_speed_kmh > 50.0:
            weather_penalty += 12.0
            weather_note = f"High gale wind ({weather.wind_speed_kmh} km/h) adds +12h berth docking penalty."
        if weather.precipitation_mm and weather.precipitation_mm > 30.0:
            weather_penalty += 8.0
            weather_note += f" Heavy rain ({weather.precipitation_mm} mm) adds +8h crane handling delay."

    duration_factor = max(0.0, (expected_duration_hours - 24.0) * 0.25)
    total_delay = round((base_hours * sev_factor) + weather_penalty + duration_factor, 1)

    # Risk category alignment
    if total_delay > 80.0:
        cat = SeverityLevel.CRITICAL
    elif total_delay > 40.0:
        cat = SeverityLevel.HIGH
    elif total_delay > 20.0:
        cat = SeverityLevel.MEDIUM
    else:
        cat = SeverityLevel.LOW

    rule = (
        f"Deterministic heuristic: ({base_hours}h base [{event_type.value}] * {sev_factor:.1f}x severity [{severity.value}]) "
        f"+ ({weather_penalty}h weather penalty) + ({duration_factor:.1f}h duration offset) = {total_delay}h total."
    )

    inputs = {
        "event_type": event_type.value,
        "severity": severity.value,
        "expected_duration_hours": expected_duration_hours,
        "affected_node": affected_node,
        "weather_penalty_hours": weather_penalty,
        "weather_note": weather_note,
    }

    return DelayPrediction(
        event_id=event_id,
        affected_node=affected_node,
        estimated_delay_hours=total_delay,
        risk_category=cat,
        inputs_considered=inputs,
        rule_explanation=rule,
        confidence=0.85,
    )
