"""
FastMCP Server for ChainSight Agent.
Exposes standard MCP tools for supply chain operations:
- get_weather(location): Fetch Open-Meteo weather telemetry or validated cache
- run_risk_propagation(event_id, event_type, location, severity, description, estimated_delay_hours): NetworkX graph propagation
- estimate_delay(event_type, severity, duration_hours, location): Deterministic delay calculation
- recall_memory(event_type, location, severity, limit): Query SQLite incident history
- save_memory(...): Persist mitigation outcome to incident memory
- send_notification(recipient, subject, body): Safe mock preview simulation
"""
import sys
import os
from typing import List, Dict, Any, Optional

from fastmcp import FastMCP

# Add root directory to sys.path to enable smooth imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.weather import fetch_weather
from tools.delay_predictor import estimate_delay as calc_delay
from tools.risk_propagation import run_risk_propagation as graph_risk_propagation
from tools.memory_tools import recall_incident_memory, save_incident_memory
from tools.notifications import dispatch_mock_notification
from schemas import DisruptionType, SeverityLevel

mcp = FastMCP("chainsight-server")


@mcp.tool()
def get_weather(location: str) -> Dict[str, Any]:
    """Retrieve weather telemetry for a supply chain port or location."""
    result = fetch_weather(location)
    return result.model_dump()


@mcp.tool()
def estimate_supply_chain_delay(
    event_type: str,
    severity: str,
    affected_node: str,
    expected_duration_hours: float = 48.0,
) -> Dict[str, Any]:
    """Calculate transparent deterministic delay estimate based on event severity and duration."""
    try:
        etype = DisruptionType(event_type.lower())
    except Exception:
        etype = DisruptionType.OTHER

    try:
        sev = SeverityLevel(severity.lower())
    except Exception:
        sev = SeverityLevel.MEDIUM

    pred = calc_delay(
        event_id="MCP-REQ",
        event_type=etype,
        severity=sev,
        affected_node=affected_node,
        expected_duration_hours=expected_duration_hours,
    )
    return pred.model_dump()


@mcp.tool()
def run_risk_propagation(
    event_id: str,
    event_type: str,
    location: str,
    severity: str,
    description: str,
    estimated_delay_hours: float = 48.0,
) -> Dict[str, Any]:
    """Propagate disruption impact through directed downstream nodes in the supply chain graph."""
    res = graph_risk_propagation(
        event_id=event_id,
        event_type=event_type,
        location=location,
        severity=severity,
        description=description,
        estimated_delay_hours=estimated_delay_hours,
    )
    return res.model_dump()


@mcp.tool()
def recall_memory(
    event_type: str,
    location: str,
    severity: Optional[str] = None,
    limit: int = 3,
) -> List[Dict[str, Any]]:
    """Retrieve historical incidents and mitigation outcomes from persistent SQLite memory."""
    return recall_incident_memory(
        event_type=event_type,
        location=location,
        severity=severity,
        limit=limit,
    )


@mcp.tool()
def save_memory(
    event_type: str,
    normalized_location: str,
    severity: str,
    affected_entities: List[str],
    selected_mitigation: str,
    estimated_delay_hours: float,
    estimated_cost_usd: float,
    evidence_summary: str,
    observed_outcome: Optional[str] = None,
) -> Dict[str, Any]:
    """Record a disruption resolution and outcome in the persistent memory store."""
    return save_incident_memory(
        event_type=event_type,
        normalized_location=normalized_location,
        severity=severity,
        affected_entities=affected_entities,
        selected_mitigation=selected_mitigation,
        estimated_delay_hours=estimated_delay_hours,
        estimated_cost_usd=estimated_cost_usd,
        evidence_summary=evidence_summary,
        observed_outcome=observed_outcome,
        is_simulated=True,
    )


@mcp.tool()
def send_customer_notification(
    recipient_segment: str,
    subject: str,
    body: str,
) -> Dict[str, Any]:
    """Simulate sending an operational advisory notice. Action is strictly marked SIMULATED."""
    res = dispatch_mock_notification(
        recipient_segment=recipient_segment,
        subject=subject,
        body=body,
    )
    return res.model_dump()


if __name__ == "__main__":
    mcp.run()
