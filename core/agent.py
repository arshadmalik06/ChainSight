"""
ChainSight Orchestrator Agent.
Integrates:
- Event Extraction (Gemini / Multimodal / Deterministic Rule-Engine)
- Incident Memory Recall (Transparent SQLite similarity retrieval)
- Weather Telemetry (Open-Meteo with self-healing resilience and validated cache fallback)
- Supply Chain Network Risk Propagation (Directed NetworkX graph)
- Transparent Delay Heuristics (Severity, duration, weather factor integration)
- Constrained Mitigation Decision Engine (Cost vs Delay vs Residual Risk trade-off)
- Customer Notification Simulation (Mock preview, strictly safe)
- Persistent Incident Memory Logging
- Traceable Resolution Report Generation
"""
import os
import json
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path

from schemas import (
    DisruptionEvent,
    ResolutionReport,
    WeatherEvidence,
    DelayPrediction,
    RiskPropagationResult,
    MitigationRecommendationResult,
    MockNotificationResult,
    SourceType,
)
from core.event_extractor import (
    extract_event_from_text,
    extract_event_from_image,
    extract_event_rule_heuristic,
)
from core.supply_chain import SupplyChainNetwork
from core.mitigation import evaluate_and_rank_mitigations
from core.resilience import ResilienceEngine
from core.report import build_resolution_report
from tools.weather import fetch_weather
from tools.delay_predictor import estimate_delay
from tools.notifications import dispatch_mock_notification
from memory.store import IncidentMemoryStore

logger = logging.getLogger(__name__)


class ChainSightAgent:
    """
    Autonomous Supply Chain Disruption Response Agent.
    """

    def __init__(
        self,
        offline_mode: Optional[bool] = None,
        test_weather_failure: bool = False,
    ):
        base_dir = Path(__file__).resolve().parent.parent
        self.network = SupplyChainNetwork(
            network_path=base_dir / "data" / "network.json",
            shipments_path=base_dir / "data" / "shipments.csv",
        )
        self.memory_store = IncidentMemoryStore(
            db_path=base_dir / "memory" / "chainsight_memory.db"
        )
        # Ensure initial seed memories exist
        self.memory_store.seed_initial_demo_memories()

        self.resilience = ResilienceEngine(
            test_weather_failure_enabled=test_weather_failure
        )
        if offline_mode is not None:
            os.environ["CHAINSIGHT_OFFLINE_MODE"] = "true" if offline_mode else "false"

    def run(
        self,
        input_text: Optional[str] = None,
        image_bytes: Optional[bytes] = None,
        image_mime: str = "image/png",
        target_nodes: Optional[List[str]] = None,
        simulate_notification: bool = True,
        save_to_memory: bool = True,
    ) -> ResolutionReport:
        """
        Execute full end-to-end autonomous resolution workflow.
        """
        # Step 1: Disruption Event Extraction
        if image_bytes:
            event = extract_event_from_image(image_bytes, mime_type=image_mime)
        elif input_text:
            event = extract_event_from_text(input_text)
        else:
            raise ValueError("Either input_text or image_bytes must be provided.")

        # Step 2: Recall Similar Historical Incidents from Memory
        similar_records = self.memory_store.recall_similar_incidents(
            event_type=event.event_type.value,
            location=event.location,
            severity=event.severity.value,
            affected_entities=event.affected_entity_types,
            limit=3,
        )
        prior_memory = [r.model_dump() for r in similar_records]

        # Step 3: Resilient Weather Telemetry Retrieval
        weather_evidence: Optional[WeatherEvidence] = None
        if event.location and event.location != "Unknown Location":
            weather_result, data_source = self.resilience.execute_with_resilience(
                tool_name="get_weather",
                step_desc=f"Fetch weather telemetry for {event.location}",
                call_fn=lambda: fetch_weather(event.location, timeout=self.resilience.request_timeout),
                fallback_fn=lambda: self.resilience.get_validated_weather_cache(event.location),
                validate_fn=lambda w: isinstance(w, WeatherEvidence) and (w.data_source != "unresolved" or w.is_fallback),
            )
            weather_evidence = weather_result

        # Step 4: Deterministic Delay Prediction & Risk Propagation
        # Calculate baseline delay using heuristic estimator
        delay_est = estimate_delay(
            event_id=event.event_id,
            event_type=event.event_type,
            severity=event.severity,
            affected_node=event.location,
            expected_duration_hours=event.expected_duration_hours,
            weather=weather_evidence,
        )

        propagation = self.network.propagate_risk(
            event=event,
            estimated_delay_hours=delay_est.estimated_delay_hours,
            target_nodes=target_nodes,
        )

        # Step 5: Evaluate and Rank Feasible Mitigation Actions
        catalog = self.network.raw_network_data.get("mitigation_options_catalog", [])
        mitigation_result = evaluate_and_rank_mitigations(
            event=event,
            propagation=propagation,
            catalog=catalog,
        )

        # Step 6: Customer Notification Simulation
        simulated_notifications: List[MockNotificationResult] = []
        if simulate_notification and propagation.affected_shipment_ids:
            top_rec = mitigation_result.selected_action
            action_desc = top_rec.title if top_rec else "Under active operational assessment"
            sample_shipments = propagation.affected_shipment_ids[:3]
            body_text = (
                f"Urgent Advisory: Disruption detected ({event.event_type.value.upper()}) at {event.location}. "
                f"Impacted shipments: {', '.join(sample_shipments)}. "
                f"Estimated delay impact: +{propagation.max_network_delay_hours:.1f}h. "
                f"Recommended Recovery Action: {action_desc}."
            )
            notif = dispatch_mock_notification(
                recipient_segment="High-Priority Tier 1 Customers & Operations Leads",
                subject=f"[CHAINSIGHT ADVISORY] Risk Alert: {event.location} - {event.event_type.value}",
                body=body_text,
            )
            simulated_notifications.append(notif)

        # Step 7: Save Incident & Outcome to Memory
        if save_to_memory and mitigation_result.selected_action:
            top_rec = mitigation_result.selected_action
            self.memory_store.save_incident(
                event_type=event.event_type.value,
                normalized_location=event.location,
                severity=event.severity.value,
                affected_entities=event.affected_entity_types,
                selected_mitigation=top_rec.title,
                estimated_delay_hours=top_rec.estimated_residual_delay_hours,
                estimated_cost_usd=top_rec.estimated_incremental_cost_usd,
                evidence_summary=f"Affected {len(propagation.affected_shipment_ids)} shipments, total value ${propagation.total_shipment_value_at_risk:,.0f}. Max network delay {propagation.max_network_delay_hours:.1f}h.",
                observed_outcome=f"Simulated execution. Residual risk score: {top_rec.residual_risk_score:.1f}.",
                is_simulated=True,
            )

        # Step 8: Assemble Verifiable Resolution Report
        report = build_resolution_report(
            event=event,
            risk_propagation=propagation,
            mitigation_result=mitigation_result,
            weather_evidence=weather_evidence,
            recovery_log=self.resilience.recovery_events,
            prior_memory=prior_memory,
            simulated_notifications=simulated_notifications,
        )

        return report
