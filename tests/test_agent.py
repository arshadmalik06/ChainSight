"""
Unit tests for Event Extraction and Agent Schemas.
"""
import pytest
from core.event_extractor import extract_event_rule_heuristic, extract_event_from_text
from schemas import DisruptionType, SeverityLevel, SourceType, DisruptionEvent


def test_event_schema_validation():
    """Verify that disruption events validate successfully under Pydantic."""
    raw = {
        "event_id": "EVT-TEST-001",
        "event_type": "cyclone",
        "description": "Typhoon Muifa approaches Port of Shanghai with gale warnings.",
        "location": "Shanghai, China",
        "severity": "high",
        "start_time": "2026-10-17T06:00:00Z",
        "expected_duration_hours": 48.0,
        "affected_entity_types": ["port"],
        "source_type": "text",
        "extraction_confidence": 0.95,
        "assumptions": ["Assuming 48h terminal closure."],
        "requires_confirmation": False,
    }
    event = DisruptionEvent.model_validate(raw)
    assert event.event_type == DisruptionType.CYCLONE
    assert event.severity == SeverityLevel.HIGH
    assert event.location == "Shanghai, China"
    assert event.expected_duration_hours == 48.0


def test_rule_heuristic_cyclone_detection():
    """Verify that heuristic correctly extracts cyclone events."""
    sample_text = "Severe Typhoon warning issued for Kaohsiung port terminal with 80 km/h winds."
    event = extract_event_rule_heuristic(sample_text)
    assert event.event_type == DisruptionType.CYCLONE
    assert event.location == "Kaohsiung, Taiwan"
    assert event.severity == SeverityLevel.HIGH
    assert "port" in event.affected_entity_types


def test_incomplete_evidence_does_not_produce_fabricated_certainty():
    """Verify that vague text marks requires_confirmation=True and records assumptions."""
    vague_text = "Some disruption happened somewhere in the Pacific yesterday."
    event = extract_event_rule_heuristic(vague_text)
    assert event.requires_confirmation is True
    assert event.location == "Unknown Location"
    assert len(event.assumptions) > 0
    assert event.extraction_confidence <= 0.60


def test_port_congestion_detection():
    """Verify that port congestion scenarios are identified."""
    sample_text = "Critical berth congestion at Port of Los Angeles with 20 vessels waiting at anchor."
    event = extract_event_rule_heuristic(sample_text)
    assert event.event_type == DisruptionType.PORT_CONGESTION
    assert event.location == "Los Angeles, CA, USA"
    assert event.severity == SeverityLevel.CRITICAL
