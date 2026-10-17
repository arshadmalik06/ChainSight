"""
Pydantic Schemas for ChainSight Agent.
Defines structured schemas for disruption events, tools, graph propagation,
mitigations, and end-to-end resolution reports.
"""
from enum import Enum
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class DisruptionType(str, Enum):
    CYCLONE = "cyclone"
    PORT_CONGESTION = "port_congestion"
    SUPPLIER_SHUTDOWN = "supplier_shutdown"
    INLAND_FLOODING = "inland_flooding"
    SHIPMENT_DELAY = "shipment_delay"
    GEOPOLITICAL = "geopolitical"
    LABOR_STRIKE = "labor_strike"
    OTHER = "other"


class SeverityLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class SourceType(str, Enum):
    TEXT = "text"
    IMAGE_ADVISORY = "image_advisory"
    WEATHER_ALERT = "weather_alert"
    OFFICIAL_BULLETIN = "official_bulletin"
    USER_SIMULATION = "user_simulation"


class DisruptionEvent(BaseModel):
    event_id: str = Field(description="Unique identifier for the disruption event")
    event_type: DisruptionType = Field(description="Categorized type of disruption")
    description: str = Field(description="Summary of the disruption event")
    location: str = Field(description="Port, city, or regional locus of disruption")
    severity: SeverityLevel = Field(description="Assessed severity level")
    start_time: Optional[str] = Field(default=None, description="ISO timestamp or date string of event onset")
    expected_duration_hours: float = Field(default=48.0, ge=0.0, description="Estimated duration in hours")
    affected_entity_types: List[str] = Field(default_factory=list, description="Target entity types e.g. ['port', 'supplier']")
    source_type: SourceType = Field(default=SourceType.TEXT, description="Originating media or document type")
    extraction_confidence: float = Field(default=0.9, ge=0.0, le=1.0, description="Confidence score of extraction")
    assumptions: List[str] = Field(default_factory=list, description="Assumptions made when parsing partial details")
    requires_confirmation: bool = Field(default=False, description="Whether human confirmation is recommended")


class WeatherEvidence(BaseModel):
    location: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    temperature_c: Optional[float] = None
    wind_speed_kmh: Optional[float] = None
    precipitation_mm: Optional[float] = None
    weather_condition: Optional[str] = None
    forecast_summary: Optional[str] = None
    data_source: str = Field(description="'live_open_meteo', 'validated_cache', or 'unresolved'")
    cache_age_hours: Optional[float] = None
    timestamp: str
    is_fallback: bool = False


class DelayPrediction(BaseModel):
    event_id: str
    affected_node: str
    estimated_delay_hours: float = Field(ge=0.0)
    risk_category: SeverityLevel
    inputs_considered: Dict[str, Any]
    rule_explanation: str
    confidence: float = Field(ge=0.0, le=1.0)


class AffectedEntityImpact(BaseModel):
    node_id: str
    node_type: str  # supplier, port, plant, distribution_centre, customer
    name: str
    direct: bool
    risk_score: float = Field(ge=0.0, le=100.0)
    estimated_delay_hours: float
    impact_reason: str


class RiskPropagationResult(BaseModel):
    event_id: str
    direct_nodes_affected: List[str]
    downstream_nodes_affected: List[str]
    all_affected_nodes: List[AffectedEntityImpact]
    affected_shipment_ids: List[str]
    total_shipment_value_at_risk: float
    max_network_delay_hours: float
    overall_risk_score: float = Field(ge=0.0, le=100.0)
    methodology_notes: str


class MitigationAction(BaseModel):
    action_id: str
    title: str
    strategy_type: str  # alternate_port, alternate_supplier, expedite_freight, inventory_reallocation, etc.
    description: str
    is_feasible: bool
    feasibility_reason: str
    estimated_incremental_cost_usd: float
    estimated_residual_delay_hours: float
    residual_risk_score: float = Field(ge=0.0, le=100.0)
    composite_score: float = Field(description="Lower is better: balanced cost + risk + delay metric")
    constraints_checked: Dict[str, bool] = Field(default_factory=dict)
    assumptions: List[str] = Field(default_factory=list)


class MitigationRecommendationResult(BaseModel):
    event_id: str
    candidate_actions: List[MitigationAction]
    selected_action: Optional[MitigationAction]
    selection_rationale: str
    unresolved_constraints: List[str] = Field(default_factory=list)


class IncidentMemoryRecord(BaseModel):
    memory_id: Optional[int] = None
    event_type: str
    normalized_location: str
    severity: str
    affected_entities: List[str]
    selected_mitigation: str
    estimated_delay_hours: float
    estimated_cost_usd: float
    observed_outcome: Optional[str] = None
    is_simulated: bool = True
    evidence_summary: str
    created_at: str


class MockNotificationResult(BaseModel):
    recipient_segment: str
    preview_subject: str
    preview_body: str
    status: str = "SIMULATED_NOT_DISPATCHED"
    timestamp: str
    disclaimer: str = "Notice: This action is simulated for evaluation only. No physical message dispatched."


class RecoveryEvent(BaseModel):
    step: str
    tool_name: str
    attempt_number: int
    failure_reason: Optional[str] = None
    recovery_action: str  # 'retry', 'cache_fallback', 'replan', 'safe_fail'
    result: str
    data_source: str  # 'live', 'cache', 'synthetic_fallback'
    timestamp: str


class ResolutionReport(BaseModel):
    report_id: str
    timestamp: str
    event_summary: DisruptionEvent
    evidence_gathered: Dict[str, Any]
    weather_evidence: Optional[WeatherEvidence] = None
    risk_propagation: RiskPropagationResult
    mitigation_recommendation: MitigationRecommendationResult
    recovery_log: List[RecoveryEvent] = Field(default_factory=list)
    prior_memory_referenced: List[Dict[str, Any]] = Field(default_factory=list)
    simulated_notifications: List[MockNotificationResult] = Field(default_factory=list)
    action_execution_status: str = "RECOMMENDATION_ONLY_AWAITING_HUMAN_APPROVAL"
    traceability_hash: str
