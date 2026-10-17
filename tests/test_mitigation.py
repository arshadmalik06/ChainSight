"""
Unit tests for Deterministic Mitigation Engine.
"""
import pytest
from core.mitigation import evaluate_and_rank_mitigations
from core.supply_chain import SupplyChainNetwork
from schemas import DisruptionEvent, DisruptionType, SeverityLevel


@pytest.fixture
def sample_propagation():
    network = SupplyChainNetwork()
    event = DisruptionEvent(
        event_id="TEST-MIT-01",
        event_type=DisruptionType.PORT_CONGESTION,
        description="Port of Los Angeles severe berthing bottleneck.",
        location="Los Angeles, CA, USA",
        severity=SeverityLevel.HIGH,
        expected_duration_hours=72.0,
    )
    return network.propagate_risk(event=event, estimated_delay_hours=72.0)


def test_feasible_action_ranking(sample_propagation):
    """Test that feasible options are ranked and evaluated."""
    event = DisruptionEvent(
        event_id="TEST-MIT-01",
        event_type=DisruptionType.PORT_CONGESTION,
        description="Port of Los Angeles bottleneck",
        location="Los Angeles, CA, USA",
        severity=SeverityLevel.HIGH,
    )
    network = SupplyChainNetwork()
    catalog = network.raw_network_data.get("mitigation_options_catalog", [])

    result = evaluate_and_rank_mitigations(event, sample_propagation, catalog)
    assert len(result.candidate_actions) > 0
    assert result.selected_action is not None
    assert result.selected_action.is_feasible is True
    assert result.selected_action.estimated_incremental_cost_usd > 0
    assert result.selected_action.residual_risk_score < sample_propagation.overall_risk_score


def test_infeasible_options_rejected():
    """Verify that options targeting irrelevant nodes are marked infeasible."""
    network = SupplyChainNetwork()
    catalog = network.raw_network_data.get("mitigation_options_catalog", [])

    # Disruption only at Detroit plant Alpha
    event = DisruptionEvent(
        event_id="TEST-MIT-LOCAL",
        event_type=DisruptionType.SUPPLIER_SHUTDOWN,
        description="Power failure at plant",
        location="Detroit, MI, USA",
        severity=SeverityLevel.MEDIUM,
    )
    propagation = network.propagate_risk(event, estimated_delay_hours=24.0)
    result = evaluate_and_rank_mitigations(event, propagation, catalog)

    # Actions targeting Asian ports or suppliers should be marked infeasible
    for action in result.candidate_actions:
        if "PORT-01" in action.description or "PORT-02" in action.description:
            assert action.is_feasible is False
            assert "Action targets" in action.feasibility_reason


def test_cheapest_option_not_selected_when_infeasible():
    """Ensure an artificially cheap but infeasible option is NOT selected over a feasible one."""
    synthetic_catalog = [
        {
            "id": "MIT-CHEAP-INFEASIBLE",
            "strategy_type": "teleportation",
            "title": "Cheap Phantom Route",
            "applicable_targets": ["NON_EXISTENT_HUB"],
            "cost_fixed_per_shipment": 10.0,
            "delay_delta_hours": -100.0,
            "residual_risk_reduction": 0.99,
        },
        {
            "id": "MIT-REAL-FEASIBLE",
            "strategy_type": "alternate_port",
            "title": "Reroute Ocean Freight to Port of Long Beach (PORT-05)",
            "applicable_targets": ["PORT-04"],
            "cost_per_teu": 420.0,
            "delay_delta_hours": -48.0,
            "residual_risk_reduction": 0.70,
            "requires_capacity_check": True,
            "max_capacity_teu": 5000,
        },
    ]

    network = SupplyChainNetwork()
    event = DisruptionEvent(
        event_id="TEST-MIT-CHEAP",
        event_type=DisruptionType.PORT_CONGESTION,
        description="LA port backlog",
        location="Los Angeles, CA, USA",
        severity=SeverityLevel.HIGH,
    )
    prop = network.propagate_risk(event, estimated_delay_hours=72.0)
    result = evaluate_and_rank_mitigations(event, prop, synthetic_catalog)

    assert result.selected_action is not None
    assert result.selected_action.action_id == "MIT-REAL-FEASIBLE"
    assert result.selected_action.is_feasible is True


def test_stable_mitigation_results_for_identical_inputs(sample_propagation):
    """Ensure mitigation ranking is deterministic across runs."""
    event = DisruptionEvent(
        event_id="TEST-MIT-STABLE",
        event_type=DisruptionType.PORT_CONGESTION,
        description="LA Port backlog",
        location="Los Angeles, CA, USA",
        severity=SeverityLevel.HIGH,
    )
    network = SupplyChainNetwork()
    cat = network.raw_network_data.get("mitigation_options_catalog", [])

    res1 = evaluate_and_rank_mitigations(event, sample_propagation, cat)
    res2 = evaluate_and_rank_mitigations(event, sample_propagation, cat)

    assert res1.selected_action.action_id == res2.selected_action.action_id
    assert res1.selected_action.composite_score == res2.selected_action.composite_score
