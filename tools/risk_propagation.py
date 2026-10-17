"""
Risk Propagation Tool Adapter for ChainSight MCP Server.
Exposes NetworkX graph propagation logic to the agent workflow.
"""
from typing import Dict, Any, List, Optional
from core.supply_chain import SupplyChainNetwork
from schemas import DisruptionEvent, RiskPropagationResult, SeverityLevel, DisruptionType


def run_risk_propagation(
    event_id: str,
    event_type: str,
    location: str,
    severity: str,
    description: str,
    estimated_delay_hours: float = 48.0,
    target_nodes: Optional[List[str]] = None,
) -> RiskPropagationResult:
    """Invokes supply chain network graph risk propagation."""
    network = SupplyChainNetwork()

    # Construct temporary event schema for propagation engine
    try:
        dtype = DisruptionType(event_type.lower())
    except Exception:
        dtype = DisruptionType.OTHER

    try:
        dsev = SeverityLevel(severity.lower())
    except Exception:
        dsev = SeverityLevel.MEDIUM

    event = DisruptionEvent(
        event_id=event_id,
        event_type=dtype,
        description=description,
        location=location,
        severity=dsev,
        expected_duration_hours=estimated_delay_hours,
    )

    return network.propagate_risk(
        event=event,
        estimated_delay_hours=estimated_delay_hours,
        target_nodes=target_nodes,
    )
