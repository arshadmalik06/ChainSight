"""
Supply chain network model and risk propagation engine using NetworkX.
Graph flow: Supplier -> Port -> Plant -> Distribution Centre -> Customer
"""
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Set, Tuple, Optional
import networkx as nx
import pandas as pd

from schemas import (
    RiskPropagationResult,
    AffectedEntityImpact,
    SeverityLevel,
    DisruptionEvent,
)

logger = logging.getLogger(__name__)

SEVERITY_WEIGHTS = {
    SeverityLevel.LOW: 0.25,
    SeverityLevel.MEDIUM: 0.50,
    SeverityLevel.HIGH: 0.75,
    SeverityLevel.CRITICAL: 1.0,
}

PRIORITY_MULTIPLIERS = {
    "LOW": 0.8,
    "MEDIUM": 1.0,
    "HIGH": 1.25,
    "CRITICAL": 1.5,
}


class SupplyChainNetwork:
    def __init__(self, network_path: Optional[Path] = None, shipments_path: Optional[Path] = None):
        base_dir = Path(__file__).resolve().parent.parent
        self.network_path = network_path or (base_dir / "data" / "network.json")
        self.shipments_path = shipments_path or (base_dir / "data" / "shipments.csv")
        self.graph = nx.DiGraph()
        self.raw_network_data: Dict[str, Any] = {}
        self.shipments_df: pd.DataFrame = pd.DataFrame()
        self.load_network()
        self.load_shipments()

    def load_network(self) -> None:
        """Load nodes and directed edges into NetworkX DiGraph."""
        if not self.network_path.exists():
            raise FileNotFoundError(f"Network file not found: {self.network_path}")

        with open(self.network_path, "r", encoding="utf-8") as f:
            self.raw_network_data = json.load(f)

        self.graph.clear()
        for node in self.raw_network_data.get("nodes", []):
            self.graph.add_node(
                node["id"],
                name=node.get("name", node["id"]),
                type=node.get("type", "unknown"),
                location=node.get("location", ""),
                base_risk=node.get("base_risk", 5.0),
                metadata=node,
            )

        for edge in self.raw_network_data.get("edges", []):
            self.graph.add_edge(
                edge["source"],
                edge["target"],
                mode=edge.get("mode", "unspecified"),
                transit_hours=edge.get("transit_hours", 24),
                metadata=edge,
            )

    def load_shipments(self) -> None:
        """Load shipments from CSV file."""
        if not self.shipments_path.exists():
            raise FileNotFoundError(f"Shipments file not found: {self.shipments_path}")
        self.shipments_df = pd.read_csv(self.shipments_path)

    def find_nodes_by_location_or_keyword(self, query: str) -> List[str]:
        """Match nodes by location, name, or node_id."""
        query_norm = query.lower().strip()
        matched: List[str] = []
        for node_id, data in self.graph.nodes(data=True):
            name = str(data.get("name", "")).lower()
            location = str(data.get("location", "")).lower()
            if query_norm in name or query_norm in location or query_norm == node_id.lower():
                matched.append(node_id)
        return matched

    def propagate_risk(
        self,
        event: DisruptionEvent,
        estimated_delay_hours: float = 48.0,
        target_nodes: Optional[List[str]] = None,
    ) -> RiskPropagationResult:
        """
        Propagate disruption impact through directed downstream dependencies.
        Deterministic scoring: 0-100 scale.
        """
        # Determine directly affected nodes
        if target_nodes:
            direct_nodes = [n for n in target_nodes if n in self.graph]
        else:
            direct_nodes = self.find_nodes_by_location_or_keyword(event.location)
            if not direct_nodes:
                # Fallback matching by event description keywords
                for token in event.description.split():
                    clean_token = token.strip(",.!?()\"'")
                    if len(clean_token) > 4:
                        direct_nodes.extend(self.find_nodes_by_location_or_keyword(clean_token))
                direct_nodes = list(dict.fromkeys(direct_nodes))

        if not direct_nodes:
            # Explicit unresolved impact handling
            return RiskPropagationResult(
                event_id=event.event_id,
                direct_nodes_affected=[],
                downstream_nodes_affected=[],
                all_affected_nodes=[],
                affected_shipment_ids=[],
                total_shipment_value_at_risk=0.0,
                max_network_delay_hours=0.0,
                overall_risk_score=0.0,
                methodology_notes=f"No matching nodes identified for location '{event.location}' in the network graph. No downstream propagation triggered.",
            )

        # Downstream traversal using NetworkX descendants
        downstream_nodes: Set[str] = set()
        for d_node in direct_nodes:
            downstream_nodes.update(nx.descendants(self.graph, d_node))

        all_impacted_node_ids = set(direct_nodes).union(downstream_nodes)

        # Filter affected shipments avoiding double counting
        shipment_mask = (
            self.shipments_df["supplier_id"].isin(all_impacted_node_ids)
            | self.shipments_df["port_id"].isin(all_impacted_node_ids)
            | self.shipments_df["plant_id"].isin(all_impacted_node_ids)
            | self.shipments_df["distribution_centre_id"].isin(all_impacted_node_ids)
            | self.shipments_df["customer_id"].isin(all_impacted_node_ids)
        )
        affected_shipments = self.shipments_df[shipment_mask].copy()
        affected_shipment_ids = affected_shipments["shipment_id"].tolist()
        total_value_at_risk = float(affected_shipments["shipment_value"].sum()) if not affected_shipments.empty else 0.0

        severity_factor = SEVERITY_WEIGHTS.get(event.severity, 0.5)

        impact_list: List[AffectedEntityImpact] = []
        max_delay = estimated_delay_hours

        # Compute impact for each affected node
        for node_id in sorted(all_impacted_node_ids):
            node_data = self.graph.nodes[node_id]
            node_type = node_data.get("type", "unknown")
            node_name = node_data.get("name", node_id)
            is_direct = node_id in direct_nodes

            # Distance attenuation: direct nodes take full severity, downstream decays by shortest path
            if is_direct:
                attenuation = 1.0
                delay_node = estimated_delay_hours
                reason = f"Directly affected by {event.event_type.value} at {event.location}."
            else:
                # Find min path length from any direct node
                min_hops = min(
                    nx.shortest_path_length(self.graph, d, node_id)
                    for d in direct_nodes
                    if nx.has_path(self.graph, d, node_id)
                )
                attenuation = max(0.2, 1.0 - (0.22 * min_hops))
                delay_node = round(estimated_delay_hours * attenuation, 1)
                reason = f"Downstream dependency {min_hops} hop(s) away from direct disruption locus."

            base_risk = float(node_data.get("base_risk", 5.0))
            calculated_risk = round(min(100.0, (base_risk * 1.5) + (severity_factor * 85.0 * attenuation)), 1)

            impact_list.append(
                AffectedEntityImpact(
                    node_id=node_id,
                    node_type=node_type,
                    name=node_name,
                    direct=is_direct,
                    risk_score=calculated_risk,
                    estimated_delay_hours=delay_node,
                    impact_reason=reason,
                )
            )

        # Composite overall risk score: weighted average of direct impact, shipment exposure, and critical customer tier
        if impact_list:
            direct_scores = [n.risk_score for n in impact_list if n.direct]
            avg_direct = sum(direct_scores) / len(direct_scores) if direct_scores else 50.0
            overall_score = round(min(100.0, (avg_direct * 0.6) + (min(total_value_at_risk / 50000.0, 40.0))), 1)
        else:
            overall_score = 0.0

        methodology = (
            f"Deterministic NetworkX topological propagation. Direct nodes: {len(direct_nodes)}; "
            f"Downstream impacted: {len(downstream_nodes)}. Attenuation factor: -22% per hop. "
            f"Shipments evaluated: {len(affected_shipment_ids)} without double-counting."
        )

        return RiskPropagationResult(
            event_id=event.event_id,
            direct_nodes_affected=direct_nodes,
            downstream_nodes_affected=sorted(list(downstream_nodes)),
            all_affected_nodes=impact_list,
            affected_shipment_ids=affected_shipment_ids,
            total_shipment_value_at_risk=total_value_at_risk,
            max_network_delay_hours=max_delay,
            overall_risk_score=overall_score,
            methodology_notes=methodology,
        )
