"""
ChainSight Streamlit Dashboard & Control Center.
Autonomous Supply Chain Risk Detection, Recovery & Memory System.

Features:
- Live Interactive Scenario Dispatcher (5 Pre-configured Real-World Scenarios)
- Multimodal & Free-text Disruption Input
- Visual End-to-End Resolution Pipeline
- Network Graph Impact & Shipment Value at Risk
- Candidate Mitigation Trade-off Matrix (Cost vs. Residual Delay vs. Risk)
- Verifiable Audit Fingerprint & Traceability Hash
- SQLite Incident Memory Viewer & Seed Records
- Self-Healing Resilience Logs (Retries, Backoffs, Cache Fallback)
"""
import sys
import os
import json
from pathlib import Path
from datetime import datetime, timezone

import streamlit as st
import pandas as pd

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.agent import ChainSightAgent
from schemas import DisruptionType, SeverityLevel
from memory.store import IncidentMemoryStore

# Page Config
st.set_page_config(
    page_title="ChainSight | Autonomous Supply Chain Risk & Recovery",
    page_icon="🌐",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom Styling
st.markdown(
    """
    <style>
    .metric-card {
        background-color: #0E1117;
        border: 1px solid #262730;
        border-radius: 8px;
        padding: 16px;
        margin-bottom: 12px;
    }
    .badge-high {
        background-color: #ff4b4b22;
        color: #ff4b4b;
        padding: 2px 8px;
        border-radius: 4px;
        font-weight: 600;
    }
    .badge-success {
        background-color: #00cc9622;
        color: #00cc96;
        padding: 2px 8px;
        border-radius: 4px;
        font-weight: 600;
    }
    .stAlert {
        border-radius: 8px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# Initialize Session State
if "report" not in st.session_state:
    st.session_state.report = None
if "agent" not in st.session_state:
    st.session_state.agent = ChainSightAgent(offline_mode=True)

# Sidebar: Controls & Scenarios
st.sidebar.image("https://raw.githubusercontent.com/feathericons/feather/master/icons/anchor.svg", width=42)
st.sidebar.title("ChainSight Agent")
st.sidebar.caption("Autonomous Risk Detection, Recovery & Memory")

mode = st.sidebar.radio(
    "Execution Mode",
    ["Offline Heuristic & Validated Cache", "Gemini 2.5 Live Agent (API Key)"],
    index=0,
)
offline_flag = mode.startswith("Offline")

test_failure_toggle = st.sidebar.checkbox(
    "Inject Weather Tool Failure (Self-Healing Demo)",
    value=False,
    help="Deliberately causes remote API timeout to demonstrate backoff retry and cache fallback.",
)

st.sidebar.divider()
st.sidebar.subheader("Quick-Load Benchmark Scenarios")

preset_options = {
    "Select a pre-configured scenario...": "",
    "Scenario 1: Cyclone at Port of Kaohsiung": "Severe Typhoon warning issued for Kaohsiung port terminal with 85 km/h sustained gale winds and expected 48-hour berth closure.",
    "Scenario 2: Port Congestion in Shanghai": "Major container backlog and vessel congestion at Port of Shanghai causing 72-hour average vessel waiting times.",
    "Scenario 3: Cleanroom Fire in Taiwan (Apex Semi)": "Cleanroom fire and equipment shutdown reported at Apex Semiconductor supplier facility in Kaohsiung. Production halted for 96 hours.",
    "Scenario 4: Inland Intermodal Rail Washout": "Severe freight train derailment and bridge washouts halting rail corridors from West Coast Port of Los Angeles to Assembly Plant 01.",
    "Scenario 5: Self-Healing Demo": "Typhoon alert reported for Kaohsiung port terminal with severe weather disruptions.",
}

selected_preset = st.sidebar.selectbox("Choose Scenario", list(preset_options.keys()))
default_text = preset_options[selected_preset] if selected_preset != "Select a pre-configured scenario..." else ""

# Main App Layout
st.title("🌐 ChainSight Autonomous Supply Chain Risk Platform")
st.markdown(
    "Real-time event extraction, dependency propagation, memory-informed mitigation, and self-healing resilience."
)

col_input, col_meta = st.columns([2, 1])

with col_input:
    input_text = st.text_area(
        "Disruption Alert / Incident Report",
        value=default_text or "Severe Typhoon warning issued for Kaohsiung port terminal with 85 km/h sustained gale winds and expected 48-hour berth closure.",
        height=110,
    )
    uploaded_file = st.file_uploader("Or Upload Port/Weather Advisory Image", type=["png", "jpg", "jpeg"])

with col_meta:
    st.markdown("### Agent Controls")
    sim_notif = st.checkbox("Simulate Customer Advisory Dispatch", value=True)
    save_mem = st.checkbox("Persist Outcome to Incident Memory", value=True)
    run_btn = st.button("🚀 Analyze Disruption & Generate Resolution", type="primary", use_container_width=True)

if run_btn:
    with st.spinner("Executing ChainSight Agent resolution pipeline..."):
        agent = ChainSightAgent(
            offline_mode=offline_flag,
            test_weather_failure=test_failure_toggle,
        )
        img_bytes = uploaded_file.read() if uploaded_file else None
        report = agent.run(
            input_text=input_text if not img_bytes else None,
            image_bytes=img_bytes,
            simulate_notification=sim_notif,
            save_to_memory=save_mem,
        )
        st.session_state.report = report

# Render Report if available
report = st.session_state.report
if report:
    st.divider()
    
    # Header Banner
    evt = report.event_summary
    risk = report.risk_propagation
    mit = report.mitigation_recommendation
    rec = mit.selected_action

    st.subheader(f"Resolution Report: {report.report_id}")
    st.caption(f"Traceability SHA-256: `{report.traceability_hash}` | Generated: {report.timestamp}")

    # Top KPI row
    kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)
    with kpi1:
        st.metric("Disruption Type", evt.event_type.value.upper(), evt.severity.value)
    with kpi2:
        st.metric("Affected Location", evt.location)
    with kpi3:
        st.metric("At-Risk Shipments", len(risk.affected_shipment_ids))
    with kpi4:
        st.metric("Value at Risk", f"${risk.total_shipment_value_at_risk:,.0f}")
    with kpi5:
        st.metric("Max Delay Impact", f"+{risk.max_network_delay_hours:.1f} hrs")

    # Tabs for detailed breakdown
    tab_rec, tab_graph, tab_resilience, tab_memory, tab_audit = st.tabs([
        "🎯 Recommended Recovery Action",
        "🗺️ Network Impact & Shipments",
        "🛡️ Self-Healing & Telemetry",
        "🧠 Historical Memory Recall",
        "🔒 Traceability & Raw Audit",
    ])

    with tab_rec:
        st.markdown("### Optimal Recovery Action")
        if rec:
            st.success(f"**Recommended: [{rec.action_id}] {rec.title}**")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Incremental Cost", f"${rec.estimated_incremental_cost_usd:,.2f}")
            c2.metric("Residual Delay", f"{rec.estimated_residual_delay_hours:.1f} hrs")
            c3.metric("Residual Risk", f"{rec.residual_risk_score:.1f} / 100")
            c4.metric("Composite Score", f"{rec.composite_score:.2f} (lower is better)")
            
            st.markdown(f"**Selection Rationale:** {mit.selection_rationale}")
            st.markdown(f"**Feasibility Details:** {rec.feasibility_reason}")
        else:
            st.error("No candidate actions satisfied all operational constraints. Human escalation required.")

        st.markdown("#### All Evaluated Candidate Actions (Trade-Off Matrix)")
        actions_data = []
        for a in mit.candidate_actions:
            actions_data.append({
                "Action ID": a.action_id,
                "Title": a.title,
                "Feasible": "✅ Yes" if a.is_feasible else "❌ No",
                "Cost ($)": f"${a.estimated_incremental_cost_usd:,.2f}",
                "Residual Delay (h)": a.estimated_residual_delay_hours,
                "Residual Risk": a.residual_risk_score,
                "Composite Score": a.composite_score,
            })
        st.dataframe(pd.DataFrame(actions_data), use_container_width=True)

        if report.simulated_notifications:
            st.markdown("#### Customer Advisory Preview (Simulated)")
            for n in report.simulated_notifications:
                with st.expander(f"Preview: {n.preview_subject}", expanded=True):
                    st.write(f"**Recipient Segment:** {n.recipient_segment}")
                    st.info(n.preview_body)
                    st.caption(f"Status: {n.status} | {n.disclaimer}")

    with tab_graph:
        st.markdown("### Supply Chain Graph Impact")
        col_nodes, col_shipments = st.columns([1, 2])
        with col_nodes:
            st.markdown("**Directly Affected Nodes:**")
            for d in risk.direct_nodes_affected:
                st.markdown(f"- 🔴 `{d}`")
            st.markdown("**Downstream Dependent Nodes:**")
            for dn in risk.downstream_nodes_affected:
                st.markdown(f"- 🟠 `{dn}`")
            st.caption(f"Methodology: {risk.methodology_notes}")

        with col_shipments:
            st.markdown(f"**Affected In-Transit Shipments ({len(risk.affected_shipment_ids)} total):**")
            store = IncidentMemoryStore()
            net = st.session_state.agent.network
            impacted_df = net.shipments_df[net.shipments_df["shipment_id"].isin(risk.affected_shipment_ids)]
            st.dataframe(
                impacted_df[["shipment_id", "origin", "port_id", "plant_id", "product", "priority", "shipment_value"]].head(15),
                use_container_width=True,
            )

    with tab_resilience:
        st.markdown("### Self-Healing & Resilience Engine Log")
        st.caption("Verifiable log of tool invocations, retry backoffs, and contingency fallbacks.")
        
        if report.recovery_log:
            rec_data = []
            for ev in report.recovery_log:
                rec_data.append({
                    "Timestamp": ev.timestamp,
                    "Tool": ev.tool_name,
                    "Attempt": ev.attempt_number,
                    "Action": ev.recovery_action,
                    "Result": ev.result,
                    "Data Source": ev.data_source,
                })
            st.dataframe(pd.DataFrame(rec_data), use_container_width=True)
        else:
            st.info("No recovery events logged (all tools succeeded on initial attempt).")

        if report.weather_evidence:
            st.markdown("#### Weather Evidence Gathered")
            we = report.weather_evidence
            st.json(we.model_dump())

    with tab_memory:
        st.markdown("### Persistent Incident Memory")
        st.caption("Prior incidents recalled to guide current response strategy.")
        if report.prior_memory_referenced:
            for m in report.prior_memory_referenced:
                with st.expander(f"Incident #{m.get('id')}: {m.get('event_type')} at {m.get('normalized_location')}", expanded=False):
                    st.write(f"**Selected Mitigation:** {m.get('selected_mitigation')}")
                    st.write(f"**Observed/Simulated Outcome:** {m.get('observed_outcome')}")
                    st.write(f"**Cost:** ${m.get('estimated_cost_usd'):,.2f} | **Delay:** {m.get('estimated_delay_hours')} hrs")
                    st.caption(f"Evidence: {m.get('evidence_summary')}")
        else:
            st.info("No prior matching memories met the similarity threshold.")

    with tab_audit:
        st.markdown("### Auditable Traceability Fingerprint")
        st.code(f"Traceability Hash (SHA-256): {report.traceability_hash}", language="bash")
        st.json(report.model_dump())
