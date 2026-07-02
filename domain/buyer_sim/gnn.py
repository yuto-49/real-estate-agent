"""Lightweight heterogeneous graph attention network in raw PyTorch.

No PyTorch Geometric dependency -- uses dense adjacency matrices which
are practical for the small graphs (< 100 nodes) in buyer simulation.
Pure domain layer -- deterministic forward pass, no I/O.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import torch
import torch.nn as nn
import torch.nn.functional as F

from domain.buyer_sim.models import BuyerProfile, PropertyFeatures

# Life-stage one-hot encoding order
_LIFE_STAGES: tuple[str, ...] = ("first_time", "upgrade", "investor", "retiree")
_LIFE_STAGE_DIM = len(_LIFE_STAGES)

# buyer feature dim: budget_norm + risk_tolerance + hazard_sensitivity
#   + yield_target_norm + life_stage_onehot (4)  =  8
BUYER_FEAT_DIM = 4 + _LIFE_STAGE_DIM


def _life_stage_onehot(stage: str) -> list[float]:
    vec = [0.0] * _LIFE_STAGE_DIM
    if stage in _LIFE_STAGES:
        vec[_LIFE_STAGES.index(stage)] = 1.0
    return vec


# ---------------------------------------------------------------------------
# Graph Attention Layer (single edge type)
# ---------------------------------------------------------------------------

class _GraphAttentionChannel(nn.Module):
    """Dot-product attention + mean aggregation for one edge type."""

    def __init__(self, hidden_dim: int) -> None:
        super().__init__()
        self.query = nn.Linear(hidden_dim, hidden_dim, bias=False)
        self.key = nn.Linear(hidden_dim, hidden_dim, bias=False)
        self.value = nn.Linear(hidden_dim, hidden_dim, bias=False)
        self._scale = hidden_dim ** 0.5

    def forward(
        self, h_src: torch.Tensor, h_dst: torch.Tensor, adj: torch.Tensor
    ) -> torch.Tensor:
        """Aggregate messages from src nodes to dst nodes.

        Args:
            h_src: (N_src, hidden_dim) source node embeddings
            h_dst: (N_dst, hidden_dim) destination node embeddings
            adj:   (N_dst, N_src) adjacency weights (0 = no edge)

        Returns:
            (N_dst, hidden_dim) aggregated messages
        """
        q = self.query(h_dst)                          # (N_dst, H)
        k = self.key(h_src)                            # (N_src, H)
        v = self.value(h_src)                          # (N_src, H)

        # raw attention: (N_dst, N_src)
        attn = torch.matmul(q, k.t()) / self._scale

        # mask out non-edges with large negative
        mask = adj == 0
        attn = attn.masked_fill(mask, -1e9)

        # softmax over src dimension; if a row is fully masked it becomes
        # uniform -- that's fine, the output will be near-zero anyway.
        attn = F.softmax(attn, dim=-1)

        # weight by adjacency edge weights (element-wise)
        attn = attn * adj

        # re-normalise so rows sum to 1 (or 0 if no neighbours)
        row_sum = attn.sum(dim=-1, keepdim=True).clamp(min=1e-12)
        attn = attn / row_sum

        return torch.matmul(attn, v)  # (N_dst, H)


# ---------------------------------------------------------------------------
# Heterogeneous GNN Layer
# ---------------------------------------------------------------------------

class _HeteroGNNLayer(nn.Module):
    """One message-passing layer with three channels."""

    def __init__(self, hidden_dim: int) -> None:
        super().__init__()
        self.pp = _GraphAttentionChannel(hidden_dim)   # property -> property
        self.bb = _GraphAttentionChannel(hidden_dim)   # buyer -> buyer
        self.bp = _GraphAttentionChannel(hidden_dim)   # buyer -> property
        self.gate_p = nn.Linear(hidden_dim * 2, hidden_dim)
        self.gate_b = nn.Linear(hidden_dim * 2, hidden_dim)

    def forward(
        self,
        h_prop: torch.Tensor,
        h_buyer: torch.Tensor,
        adj_pp: torch.Tensor,
        adj_bb: torch.Tensor,
        adj_bp: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        # messages to properties
        msg_pp = self.pp(h_prop, h_prop, adj_pp)
        msg_bp = self.bp(h_buyer, h_prop, adj_bp)
        agg_p = msg_pp + msg_bp

        # gated residual for properties
        h_prop_new = F.relu(
            self.gate_p(torch.cat([h_prop, agg_p], dim=-1))
        )

        # messages to buyers
        msg_bb = self.bb(h_buyer, h_buyer, adj_bb)
        # buyer <- property (transpose the bp adjacency)
        msg_pb = self.bp.forward(h_prop, h_buyer, adj_bp.t())
        agg_b = msg_bb + msg_pb

        h_buyer_new = F.relu(
            self.gate_b(torch.cat([h_buyer, agg_b], dim=-1))
        )

        return h_prop_new, h_buyer_new


# ---------------------------------------------------------------------------
# Full GNN
# ---------------------------------------------------------------------------

class PropertyGNN(nn.Module):
    """Heterogeneous GNN producing property embeddings and valuations."""

    def __init__(
        self,
        prop_feat_dim: int,
        buyer_feat_dim: int = BUYER_FEAT_DIM,
        hidden_dim: int = 32,
        n_layers: int = 2,
    ) -> None:
        super().__init__()
        self.prop_encoder = nn.Sequential(
            nn.Linear(prop_feat_dim, hidden_dim),
            nn.ReLU(),
        )
        self.buyer_encoder = nn.Sequential(
            nn.Linear(buyer_feat_dim, hidden_dim),
            nn.ReLU(),
        )

        self.layers = nn.ModuleList(
            [_HeteroGNNLayer(hidden_dim) for _ in range(n_layers)]
        )

        # valuation head: hidden_dim -> 1, softplus for positive output
        self.valuation_head = nn.Linear(hidden_dim, 1)

    def forward(
        self,
        prop_features: torch.Tensor,
        buyer_features: torch.Tensor,
        adj_pp: torch.Tensor,
        adj_bb: torch.Tensor,
        adj_bp: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """Run the GNN forward pass.

        Args:
            prop_features:  (N_prop, prop_feat_dim)
            buyer_features: (N_buyer, buyer_feat_dim)
            adj_pp: (N_prop, N_prop)   property-property adjacency
            adj_bb: (N_buyer, N_buyer) buyer-buyer adjacency
            adj_bp: (N_prop, N_buyer)  buyer->property adjacency

        Returns:
            property_embeddings: (N_prop, hidden_dim)
            property_valuations: (N_prop,) positive scalars (yen)
        """
        h_prop = self.prop_encoder(prop_features)
        h_buyer = self.buyer_encoder(buyer_features)

        for layer in self.layers:
            h_prop, h_buyer = layer(h_prop, h_buyer, adj_pp, adj_bb, adj_bp)

        valuations = F.softplus(self.valuation_head(h_prop).squeeze(-1))
        return h_prop, valuations


# ---------------------------------------------------------------------------
# Tensor preparation helper
# ---------------------------------------------------------------------------

def prepare_tensors(
    properties: list[PropertyFeatures],
    buyers: list[BuyerProfile],
    graph: Any,  # AgentGraph -- use Any to avoid circular import at runtime
) -> dict[str, torch.Tensor]:
    """Convert graph + features into torch tensors for the GNN.

    Returns a dict with keys:
        prop_features   (N_prop, D_feat)
        buyer_features  (N_buyer, D_buyer)
        adj_pp          (N_prop, N_prop)
        adj_bb          (N_buyer, N_buyer)
        adj_bp          (N_prop, N_buyer)
        asking_prices   (N_prop,)
        prop_ids        list[str]
        buyer_ids       list[int]
    """
    if not properties:
        raise ValueError("At least one property is required")

    # stable ordering
    prop_ids = [p.property_id for p in properties]
    buyer_ids = [b.agent_id for b in buyers]
    prop_idx = {pid: i for i, pid in enumerate(prop_ids)}
    buyer_idx = {bid: i for i, bid in enumerate(buyer_ids)}

    n_prop = len(properties)
    n_buyer = len(buyers)
    feat_dim = len(properties[0].feature_vector)

    # --- property features ---
    prop_feat = torch.zeros(n_prop, feat_dim)
    asking_prices = torch.zeros(n_prop)
    for i, p in enumerate(properties):
        prop_feat[i] = torch.tensor(p.feature_vector, dtype=torch.float32)
        asking_prices[i] = float(p.asking_price_yen)

    # --- buyer features ---
    # normalise budget relative to max in cohort
    max_budget = max(b.budget_yen for b in buyers) if buyers else 1
    max_budget = max(max_budget, 1)

    buyer_feat = torch.zeros(n_buyer, BUYER_FEAT_DIM)
    for i, b in enumerate(buyers):
        numeric = [
            b.budget_yen / max_budget,
            b.risk_tolerance,
            b.hazard_sensitivity,
            (b.yield_target or 0.0) / 0.10,  # normalise to typical 10% cap
        ]
        onehot = _life_stage_onehot(b.life_stage)
        buyer_feat[i] = torch.tensor(numeric + onehot, dtype=torch.float32)

    # --- adjacency matrices ---
    adj_pp = torch.zeros(n_prop, n_prop)
    adj_bb = torch.zeros(n_buyer, n_buyer)
    adj_bp = torch.zeros(n_prop, n_buyer)

    # property-property (comparable)
    comp_adj = graph.get_adjacency_by_type("comparable")
    for src, neighbours in comp_adj.items():
        pid_src = src.removeprefix("p:")
        if pid_src not in prop_idx:
            continue
        si = prop_idx[pid_src]
        for tgt, w in neighbours:
            pid_tgt = tgt.removeprefix("p:")
            if pid_tgt in prop_idx:
                adj_pp[si, prop_idx[pid_tgt]] = w

    # buyer-buyer (similar)
    sim_adj = graph.get_adjacency_by_type("similar")
    for src, neighbours in sim_adj.items():
        bid_src_str = src.removeprefix("b:")
        try:
            bid_src = int(bid_src_str)
        except ValueError:
            continue
        if bid_src not in buyer_idx:
            continue
        si = buyer_idx[bid_src]
        for tgt, w in neighbours:
            bid_tgt_str = tgt.removeprefix("b:")
            try:
                bid_tgt = int(bid_tgt_str)
            except ValueError:
                continue
            if bid_tgt in buyer_idx:
                adj_bb[si, buyer_idx[bid_tgt]] = w

    # buyer -> property (interest)
    int_adj = graph.get_adjacency_by_type("interest")
    for src, neighbours in int_adj.items():
        bid_str = src.removeprefix("b:")
        try:
            bid_val = int(bid_str)
        except ValueError:
            continue
        if bid_val not in buyer_idx:
            continue
        bi = buyer_idx[bid_val]
        for tgt, w in neighbours:
            pid_tgt = tgt.removeprefix("p:")
            if pid_tgt in prop_idx:
                # adj_bp is (N_prop, N_buyer): column = buyer, row = property
                adj_bp[prop_idx[pid_tgt], bi] = w

    return {
        "prop_features": prop_feat,
        "buyer_features": buyer_feat,
        "adj_pp": adj_pp,
        "adj_bb": adj_bb,
        "adj_bp": adj_bp,
        "asking_prices": asking_prices,
        "prop_ids": prop_ids,
        "buyer_ids": buyer_ids,
    }
