"""
Report generation utilities for ChainSight Agent.
Generates structured JSON resolution reports and human-readable executive summaries.
Traceability hash calculation for verifiable auditing.
"""
import hashlib
import json
from datetime import datetime, timezone
from typing import Dict, Any

from schemas import (
    ResolutionReport,
    DisruptionEvent,
    RiskPropagationResult,
    MitigationRecommendationResult,
    WeatherEvidence,
    RecoveryEvent,
    MockNotificationResult,
)


def generate_traceability_hash(data: Dict[str, Any]) -> str:
    """Create reproducible SHA-256 fingerprint of the resolution report."""
    serialized = json.dumps(data, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:16]


def build_resolution_report(
    event: DisruptionEvent,
    risk_propagation: RiskPropagationResult,
    mitigation_result: MitigationRecommendationResult,
    weather_evidence: WeatherEvidence | None = None,
    recovery_log: list[RecoveryEvent] | None = None,
    prior_memory: list[Dict[str, Any]] | None = None,
    simulated_notifications: list[MockNotificationResult] | None = None,
) -> ResolutionReport:
    """Construct complete traceable ResolutionReport."""
    now_iso = datetime.now(timezone.utc).isoformat()
    report_id = f"REP-{event.event_id}-{now_iso[:10]}"

    evidence_dict = {
        "event_id": event.event_id,
        "event_type": event.event_type.value,
        "location": event.location,
        "severity": event.severity.value,
        "confidence": event.extraction_confidence,
        "assumptions": event.assumptions,
        "requires_confirmation": event.requires_confirmation,
        "weather_source": weather_evidence.data_source if weather_evidence else "not_requested",
        "affected_shipments_count": len(risk_propagation.affected_shipment_ids),
        "total_value_at_risk_usd": risk_propagation.total_shipment_value_at_risk,
    }

    raw_audit = {
        "report_id": report_id,
        "event": event.model_dump(),
        "risk": risk_propagation.model_dump(),
        "mitigation": mitigation_result.model_dump(),
    }
    trace_hash = generate_traceability_hash(raw_audit)

    return ResolutionReport(
        report_id=report_id,
        timestamp=now_iso,
        event_summary=event,
        evidence_gathered=evidence_dict,
        weather_evidence=weather_evidence,
        risk_propagation=risk_propagation,
        mitigation_recommendation=mitigation_result,
        recovery_log=recovery_log or [],
        prior_memory_referenced=prior_memory or [],
        simulated_notifications=simulated_notifications or [],
        action_execution_status="RECOMMENDATION_ONLY_AWAITING_HUMAN_APPROVAL",
        traceability_hash=trace_hash,
    )
