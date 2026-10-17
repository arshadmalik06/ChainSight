"""
Memory Tool Adapter for ChainSight MCP Server.
Provides recall and save operations over SQLite store.
"""
from typing import List, Dict, Any, Optional
from memory.store import IncidentMemoryStore
from schemas import IncidentMemoryRecord


def recall_incident_memory(
    event_type: str,
    location: str,
    severity: Optional[str] = None,
    affected_entities: Optional[List[str]] = None,
    limit: int = 3,
) -> List[Dict[str, Any]]:
    """Query memory store for historically relevant incidents."""
    store = IncidentMemoryStore()
    store.seed_initial_demo_memories()
    records = store.recall_similar_incidents(
        event_type=event_type,
        location=location,
        severity=severity,
        affected_entities=affected_entities,
        limit=limit,
    )
    return [r.model_dump() for r in records]


def save_incident_memory(
    event_type: str,
    normalized_location: str,
    severity: str,
    affected_entities: List[str],
    selected_mitigation: str,
    estimated_delay_hours: float,
    estimated_cost_usd: float,
    evidence_summary: str,
    observed_outcome: Optional[str] = None,
    is_simulated: bool = True,
) -> Dict[str, Any]:
    """Save an incident to SQLite memory."""
    store = IncidentMemoryStore()
    mem_id = store.save_incident(
        event_type=event_type,
        normalized_location=normalized_location,
        severity=severity,
        affected_entities=affected_entities,
        selected_mitigation=selected_mitigation,
        estimated_delay_hours=estimated_delay_hours,
        estimated_cost_usd=estimated_cost_usd,
        evidence_summary=evidence_summary,
        observed_outcome=observed_outcome,
        is_simulated=is_simulated,
    )
    return {
        "status": "SAVED",
        "memory_id": mem_id,
        "is_simulated": is_simulated,
        "location": normalized_location,
    }
