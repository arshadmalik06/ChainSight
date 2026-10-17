"""
Unit tests for Supply Chain Network and Risk Propagation Engine.
"""
import pytest
from core.supply_chain import SupplyChainNetwork
from schemas import DisruptionEvent, DisruptionType, SeverityLevel


@pytest.fixture
def network():
    return SupplyChainNetwork()


def test_graph_loading(network):
    """Test that nodes and directed edges are loaded correctly from network.json."""
    assert network.graph.number_of_nodes() >= 15
    assert network.graph.number_of_edges() >= 15
    assert "PORT-01" in network.graph
    assert "PORT-04" in network.graph
    assert "PLANT-01" in network.graph
    assert "DC-01" in network.graph
    assert "CUST-01" in network.graph


def test_downstream_impact_propagation(network):
    """Test that disruption at a port propagates to downstream plants, DCs, and customers."""
    event = DisruptionEvent(
        event_id="TEST-EVT-01",
        event_type=DisruptionType.PORT_CONGESTION,
        description="Port of Los Angeles terminal congestion and container backlog.",
        location="Los Angeles, CA, USA",
        severity=SeverityLevel.HIGH,
        expected_duration_hours=72.0,
    )
    result = network.propagate_risk(event=event, estimated_delay_hours=72.0)

    assert "PORT-04" in result.direct_nodes_affected
    # Downstream of PORT-04 includes ASSEMBLY PLANTS, DCS, and CUSTOMERS
    assert len(result.downstream_nodes_affected) > 0
    assert "PLANT-01" in result.downstream_nodes_affected or "PLANT-02" in result.downstream_nodes_affected
    assert len(result.affected_shipment_ids) > 0
    assert result.total_shipment_value_at_risk > 0.0
    assert 0.0 < result.overall_risk_score <= 100.0


def test_unknown_entity_handling(network):
    """Test that an unmapped location returns safe zero/empty result without exceptions."""
    event = DisruptionEvent(
        event_id="TEST-EVT-UNKNOWN",
        event_type=DisruptionType.OTHER,
        description="Minor delay at completely unknown location Atlantis.",
        location="Atlantis Underwater Facility",
        severity=SeverityLevel.LOW,
    )
    result = network.propagate_risk(event=event)
    assert len(result.direct_nodes_affected) == 0
    assert len(result.downstream_nodes_affected) == 0
    assert len(result.affected_shipment_ids) == 0
    assert result.overall_risk_score == 0.0


def test_no_duplicate_shipment_counting(network):
    """Verify that shipments linking multiple affected nodes are counted exactly once."""
    event = DisruptionEvent(
        event_id="TEST-EVT-DUP",
        event_type=DisruptionType.CYCLONE,
        description="Super cyclone impacting Kaohsiung port and surrounding assembly plants.",
        location="Kaohsiung, Taiwan",
        severity=SeverityLevel.CRITICAL,
        expected_duration_hours=48.0,
    )
    result = network.propagate_risk(event=event)
    # Check that affected_shipment_ids contains no duplicates
    assert len(result.affected_shipment_ids) == len(set(result.affected_shipment_ids))


def test_stable_deterministic_risk_calculations(network):
    """Ensure identical inputs yield identical risk scores."""
    event = DisruptionEvent(
        event_id="TEST-EVT-STABLE",
        event_type=DisruptionType.PORT_CONGESTION,
        description="Shanghai container gate strike.",
        location="Shanghai, China",
        severity=SeverityLevel.MEDIUM,
        expected_duration_hours=36.0,
    )
    res1 = network.propagate_risk(event=event, estimated_delay_hours=36.0)
    res2 = network.propagate_risk(event=event, estimated_delay_hours=36.0)

    assert res1.overall_risk_score == res2.overall_risk_score
    assert res1.total_shipment_value_at_risk == res2.total_shipment_value_at_risk
    assert res1.affected_shipment_ids == res2.affected_shipment_ids
