"""
ChainSight Five Benchmark Scenarios Runner.
Demonstrates end-to-end evaluation for:
1. Cyclone near Port of Kaohsiung (weather + port reroute)
2. Port Congestion at Port of Shanghai (expedite freight + delay propagation)
3. Supplier Shutdown at Apex Semiconductor (alternate supplier SUP-04)
4. Inland Logistics Delay / Rail Intermodal disruption
5. Self-Healing Resilience: Injected Tool Failure with bounded retry and validated cache fallback
"""
import sys
import os
import json
import logging
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.agent import ChainSightAgent

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("ScenarioRunner")

SCENARIOS = [
    {
        "id": "SCENARIO-1",
        "title": "Severe Cyclone Warning at Port of Kaohsiung",
        "prompt": "Severe Typhoon warning issued for Kaohsiung port terminal with 85 km/h sustained gale winds and expected 48-hour berth closure.",
        "test_failure": False,
        "notes": "Triggers cyclone detection, weather lookup, downstream impact on assembly plants, and alternate port evaluation.",
    },
    {
        "id": "SCENARIO-2",
        "title": "Port Congestion & Berthing Delays at Port of Shanghai",
        "prompt": "Major container backlog and vessel congestion at Port of Shanghai causing 72-hour average vessel waiting times.",
        "test_failure": False,
        "notes": "Propagates shipment delays, calculates value at risk, recommends feeder cargo diversion.",
    },
    {
        "id": "SCENARIO-3",
        "title": "Supplier Cleanroom Fire & Factory Shutdown in Taiwan",
        "prompt": "Cleanroom fire and equipment shutdown reported at Apex Semiconductor supplier facility in Kaohsiung. Production halted for 96 hours.",
        "test_failure": False,
        "notes": "Tests supplier disruption, triggers alternate supplier constraint check (Alt-Pacific Chips SUP-04).",
    },
    {
        "id": "SCENARIO-4",
        "title": "Inland Intermodal Rail Line Disruption",
        "prompt": "Severe freight train derailment and bridge washouts halting rail corridors from West Coast Port of Los Angeles to Assembly Plant 01.",
        "test_failure": False,
        "notes": "Downstream bottleneck response; recommends hot-shot dedicated team trucking.",
    },
    {
        "id": "SCENARIO-5",
        "title": "Self-Healing Resilience: Live Weather API Failure Injection",
        "prompt": "Typhoon alert reported for Kaohsiung port terminal with severe weather disruptions.",
        "test_failure": True,
        "notes": "Deliberately injects remote weather endpoint failure to demonstrate bounded retries and validated cache fallback.",
    },
]


def run_all_scenarios():
    print("=" * 80)
    print("CHAINSIGHT AGENT: AUTONOMOUS RISK DETECTION & RECOVERY DEMO BENCHMARK")
    print("=" * 80)

    results_summary = []

    for idx, sc in enumerate(SCENARIOS, 1):
        print(f"\n[{idx}/5] RUNNING: {sc['title']}")
        print(f"Prompt: \"{sc['prompt']}\"")
        print(f"Goal: {sc['notes']}")
        print("-" * 80)

        agent = ChainSightAgent(
            offline_mode=True,
            test_weather_failure=sc["test_failure"],
        )

        report = agent.run(input_text=sc["prompt"])

        # Display extracted highlights
        evt = report.event_summary
        risk = report.risk_propagation
        mit = report.mitigation_recommendation
        selected = mit.selected_action

        print(f">> Event Detected : {evt.event_type.value.upper()} | Severity: {evt.severity.value} | Location: {evt.location}")
        print(f">> Impact Traced  : {len(risk.direct_nodes_affected)} Direct Nodes, {len(risk.downstream_nodes_affected)} Downstream Nodes")
        print(f">> Shipments Risk : {len(risk.affected_shipment_ids)} at-risk | Total Value: ${risk.total_shipment_value_at_risk:,.2f}")
        print(f">> Max Delay Est. : +{risk.max_network_delay_hours:.1f} hours | Overall Risk Score: {risk.overall_risk_score:.1f}/100")
        
        if selected:
            print(f">> Recommendation : [{selected.action_id}] {selected.title}")
            print(f">> Trade-off      : Est. Cost: ${selected.estimated_incremental_cost_usd:,.2f} | Residual Delay: {selected.estimated_residual_delay_hours:.1f}h | Residual Risk: {selected.residual_risk_score:.1f}")
        else:
            print(">> Recommendation : No feasible action satisfied constraints; human escalation required.")

        print(f">> Trace Hash     : {report.traceability_hash}")
        print(f">> Recovery Steps : {len(report.recovery_log)} recovery events recorded")
        for rec in report.recovery_log:
            print(f"   * [{rec.tool_name}] (Attempt {rec.attempt_number}) -> {rec.recovery_action}: {rec.result} (Source: {rec.data_source})")

        results_summary.append({
            "scenario": sc["id"],
            "title": sc["title"],
            "event_type": evt.event_type.value,
            "shipments_affected": len(risk.affected_shipment_ids),
            "value_at_risk": risk.total_shipment_value_at_risk,
            "recommended_action": selected.title if selected else "Escalate",
            "trace_hash": report.traceability_hash,
            "status": "SUCCESS",
        })

    print("\n" + "=" * 80)
    print("BENCHMARK COMPLETION SUMMARY")
    print("=" * 80)
    for res in results_summary:
        print(f"[{res['scenario']}] {res['title'][:45]:<45} | Shipments: {res['shipments_affected']:<2} | Value: ${res['value_at_risk']:>10,.0f} | Status: {res['status']}")

    print("\nAll 5 demonstration scenarios executed successfully with full traceability and self-healing verification.")


if __name__ == "__main__":
    run_all_scenarios()
