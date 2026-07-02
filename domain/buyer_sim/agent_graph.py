"""OASIS-inspired heterogeneous agent graph for buyer simulation.

Manages a bipartite buyer-property graph with spatial property-property
edges and buyer similarity edges. Pure domain layer -- no I/O.
"""

from __future__ import annotations

import math
from typing import Any

import networkx as nx

from domain.buyer_sim.models import BuyerProfile, PropertyFeatures

_EARTH_RADIUS_KM = 6_371.0


def _haversine_km(
    lat1: float, lng1: float, lat2: float, lng2: float
) -> float:
    """Return great-circle distance in km between two lat/lng points."""
    lat1_r, lat2_r = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlng / 2) ** 2
    )
    return 2 * _EARTH_RADIUS_KM * math.asin(math.sqrt(a))


class AgentGraph:
    """Bipartite buyer-property graph with spatial property-property edges."""

    def __init__(self) -> None:
        self.graph: nx.DiGraph = nx.DiGraph()

    # ---- node management ------------------------------------------------

    def add_property(self, prop: PropertyFeatures) -> None:
        self.graph.add_node(
            f"p:{prop.property_id}",
            node_type="property",
            data=prop,
        )

    def add_buyer(self, buyer: BuyerProfile) -> None:
        self.graph.add_node(
            f"b:{buyer.agent_id}",
            node_type="buyer",
            data=buyer,
        )

    def remove_property(self, property_id: str) -> None:
        nid = f"p:{property_id}"
        if nid in self.graph:
            self.graph.remove_node(nid)

    def remove_buyer(self, buyer_id: int) -> None:
        nid = f"b:{buyer_id}"
        if nid in self.graph:
            self.graph.remove_node(nid)

    # ---- edge management ------------------------------------------------

    def add_interest_edge(
        self, buyer_id: int, property_id: str, score: float
    ) -> None:
        self.graph.add_edge(
            f"b:{buyer_id}",
            f"p:{property_id}",
            edge_type="interest",
            weight=score,
        )

    def add_comparable_edge(
        self, prop_id_1: str, prop_id_2: str, distance_km: float
    ) -> None:
        w = 1.0 / (1.0 + distance_km)
        self.graph.add_edge(
            f"p:{prop_id_1}",
            f"p:{prop_id_2}",
            edge_type="comparable",
            weight=w,
        )

    def add_similar_buyer_edge(
        self, buyer_id_1: int, buyer_id_2: int, similarity: float
    ) -> None:
        self.graph.add_edge(
            f"b:{buyer_id_1}",
            f"b:{buyer_id_2}",
            edge_type="similar",
            weight=similarity,
        )

    # ---- bulk edge builders ---------------------------------------------

    def build_spatial_edges(self, max_distance_km: float = 2.0) -> None:
        """Connect properties within *max_distance_km* of each other."""
        prop_nodes = self.get_property_nodes()
        props: list[tuple[str, PropertyFeatures]] = []
        for nid in prop_nodes:
            data: PropertyFeatures = self.graph.nodes[nid]["data"]
            props.append((nid, data))

        for i, (nid_a, pa) in enumerate(props):
            pid_a = pa.property_id
            for nid_b, pb in props[i + 1 :]:
                pid_b = pb.property_id
                dist = _haversine_km(
                    pa.latitude, pa.longitude, pb.latitude, pb.longitude
                )
                if dist <= max_distance_km:
                    self.add_comparable_edge(pid_a, pid_b, dist)
                    self.add_comparable_edge(pid_b, pid_a, dist)

    def build_similarity_edges(
        self, budget_overlap_threshold: float = 0.3
    ) -> None:
        """Connect buyers with similar profiles.

        Two buyers are linked when they share the same ``life_stage``
        **and** the overlap ratio of their budget ranges exceeds
        *budget_overlap_threshold*.  Overlap is measured as
        ``min(b1, b2) / max(b1, b2)`` so 1.0 means identical budgets.
        """
        buyer_nodes = self.get_buyer_nodes()
        buyers: list[tuple[str, BuyerProfile]] = []
        for nid in buyer_nodes:
            data: BuyerProfile = self.graph.nodes[nid]["data"]
            buyers.append((nid, data))

        for i, (_, ba) in enumerate(buyers):
            for _, bb in buyers[i + 1 :]:
                if ba.life_stage != bb.life_stage:
                    continue
                max_b = max(ba.budget_yen, bb.budget_yen)
                if max_b == 0:
                    continue
                overlap = min(ba.budget_yen, bb.budget_yen) / max_b
                if overlap >= budget_overlap_threshold:
                    similarity = overlap
                    self.add_similar_buyer_edge(
                        ba.agent_id, bb.agent_id, similarity
                    )
                    self.add_similar_buyer_edge(
                        bb.agent_id, ba.agent_id, similarity
                    )

    # ---- queries --------------------------------------------------------

    def get_property_nodes(self) -> list[str]:
        return [
            n
            for n, d in self.graph.nodes(data=True)
            if d.get("node_type") == "property"
        ]

    def get_buyer_nodes(self) -> list[str]:
        return [
            n
            for n, d in self.graph.nodes(data=True)
            if d.get("node_type") == "buyer"
        ]

    def get_adjacency_by_type(
        self, edge_type: str
    ) -> dict[str, list[tuple[str, float]]]:
        """Return ``{source: [(target, weight), ...]}`` for a given edge type."""
        adj: dict[str, list[tuple[str, float]]] = {}
        for u, v, d in self.graph.edges(data=True):
            if d.get("edge_type") == edge_type:
                adj.setdefault(u, []).append((v, d.get("weight", 1.0)))
        return adj
