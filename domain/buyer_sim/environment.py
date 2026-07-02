"""OASIS-inspired buyer simulation environment with GNN-powered step loop.

Runs multi-round auction simulation where buyers bid on Tokyo properties.
The GNN learns property valuations via self-supervised training each round
and feeds embeddings into buyer scoring. Pure domain layer -- no I/O.
"""

from __future__ import annotations

import statistics
from typing import TYPE_CHECKING

import torch

from domain.buyer_sim.agent_graph import AgentGraph
from domain.buyer_sim.gnn import PropertyGNN, prepare_tensors
from domain.buyer_sim.models import (
    BidBucket,
    BidRecord,
    BuyerProfile,
    BuyerSimConfig,
    BuyerSimResult,
    PropertyFeatures,
    RoundResult,
    SegmentSummary,
    Transaction,
)

if TYPE_CHECKING:
    pass

# Late import to avoid circular dependency at module load time.
# buyer_agent must expose score_property and compute_bid.
_BUYER_AGENT_LOADED = False
_score_property = None
_compute_bid = None


def _ensure_buyer_agent() -> None:
    global _BUYER_AGENT_LOADED, _score_property, _compute_bid
    if _BUYER_AGENT_LOADED:
        return
    from domain.buyer_sim.buyer_agent import compute_bid, score_property

    _score_property = score_property
    _compute_bid = compute_bid
    _BUYER_AGENT_LOADED = True


# Number of self-supervised gradient steps per simulation round
_GNN_TRAIN_STEPS = 5


class BuyerSimEnvironment:
    """Multi-round auction simulation with GNN-augmented buyer agents."""

    def __init__(self, config: BuyerSimConfig) -> None:
        self.config = config
        self.graph: AgentGraph | None = None
        self.gnn: PropertyGNN | None = None
        self._optimizer: torch.optim.Adam | None = None
        self.rounds: list[RoundResult] = []
        self.transactions: list[Transaction] = []
        self.active_buyers: list[BuyerProfile] = []
        self.active_properties: list[PropertyFeatures] = []
        self._all_bids: list[BidRecord] = []
        self._round_num: int = 0
        self._buyer_stages: dict[int, str] = {}

    # ------------------------------------------------------------------
    # setup
    # ------------------------------------------------------------------

    def reset(
        self,
        properties: list[PropertyFeatures],
        buyers: list[BuyerProfile],
    ) -> None:
        """Initialise simulation state from scratch."""
        _ensure_buyer_agent()

        if self.config.seed is not None:
            torch.manual_seed(self.config.seed)

        self.active_properties = list(properties)
        self.active_buyers = list(buyers)
        self.rounds = []
        self.transactions = []
        self._all_bids = []
        self._round_num = 0
        self._buyer_stages = {b.agent_id: b.life_stage for b in buyers}

        # build agent graph
        self.graph = AgentGraph()
        for p in properties:
            self.graph.add_property(p)
        for b in buyers:
            self.graph.add_buyer(b)

        self.graph.build_spatial_edges(max_distance_km=2.0)
        self.graph.build_similarity_edges(budget_overlap_threshold=0.3)

        # initial interest edges: every buyer interested in every
        # property within their budget
        for buyer in buyers:
            for prop in properties:
                if prop.asking_price_yen <= buyer.budget_yen * 1.2:
                    self.graph.add_interest_edge(
                        buyer.agent_id, prop.property_id, score=0.5
                    )

        # initialise GNN
        feat_dim = len(properties[0].feature_vector) if properties else 20
        self.gnn = PropertyGNN(
            prop_feat_dim=feat_dim,
            hidden_dim=self.config.gnn_hidden_dim,
            n_layers=self.config.gnn_layers,
        )
        self._optimizer = torch.optim.Adam(
            self.gnn.parameters(), lr=self.config.learning_rate
        )

    # ------------------------------------------------------------------
    # step
    # ------------------------------------------------------------------

    def step(self) -> RoundResult:
        """Run one simulation round."""
        assert self.graph is not None
        assert self.gnn is not None
        assert self._optimizer is not None
        _ensure_buyer_agent()

        self._round_num += 1

        # 1. prepare tensors
        tensors = prepare_tensors(
            self.active_properties, self.active_buyers, self.graph
        )

        # 2. GNN forward (inference)
        self.gnn.eval()
        with torch.no_grad():
            prop_emb, prop_val = self.gnn(
                tensors["prop_features"],
                tensors["buyer_features"],
                tensors["adj_pp"],
                tensors["adj_bb"],
                tensors["adj_bp"],
            )

        # 3. Self-supervised GNN training: predict asking price
        self.gnn.train()
        target_prices = tensors["asking_prices"]
        # normalise target to similar scale as softplus output
        price_scale = target_prices.mean().clamp(min=1.0)
        target_norm = target_prices / price_scale

        for _ in range(_GNN_TRAIN_STEPS):
            self._optimizer.zero_grad()
            _, pred_val = self.gnn(
                tensors["prop_features"],
                tensors["buyer_features"],
                tensors["adj_pp"],
                tensors["adj_bb"],
                tensors["adj_bp"],
            )
            loss = torch.nn.functional.mse_loss(pred_val, target_norm)
            loss.backward()
            self._optimizer.step()

        # re-run inference after training
        self.gnn.eval()
        with torch.no_grad():
            prop_emb, prop_val = self.gnn(
                tensors["prop_features"],
                tensors["buyer_features"],
                tensors["adj_pp"],
                tensors["adj_bb"],
                tensors["adj_bp"],
            )

        # map embeddings back to property ids
        prop_ids: list[str] = tensors["prop_ids"]
        emb_map: dict[str, tuple[float, ...]] = {}
        for i, pid in enumerate(prop_ids):
            emb_map[pid] = tuple(prop_emb[i].tolist())

        # 4. each buyer scores all active properties
        buyer_scores: dict[int, list[tuple[str, float, dict[str, float]]]] = {}
        for buyer in self.active_buyers:
            scored: list[tuple[str, float, dict[str, float]]] = []
            for prop in self.active_properties:
                gnn_emb = emb_map.get(prop.property_id, ())
                score, factors = _score_property(buyer, prop, gnn_emb)
                scored.append((prop.property_id, score, factors))
            # sort descending by score
            scored.sort(key=lambda x: x[1], reverse=True)
            buyer_scores[buyer.agent_id] = scored

        # 5. each buyer bids on top-scored property
        bids: list[BidRecord] = []
        for buyer in self.active_buyers:
            candidates = buyer_scores.get(buyer.agent_id, [])
            if not candidates:
                continue
            top_pid, top_score, factors = candidates[0]
            bid_yen = _compute_bid(buyer, top_score, self._asking_price(top_pid))
            bids.append(
                BidRecord(
                    round_num=self._round_num,
                    buyer_id=buyer.agent_id,
                    property_id=top_pid,
                    bid_yen=bid_yen,
                    score=top_score,
                    factors=factors,
                )
            )

        # 6. resolve: for each property with bids, highest bid wins
        prop_bids: dict[str, list[BidRecord]] = {}
        for bid in bids:
            prop_bids.setdefault(bid.property_id, []).append(bid)

        round_transactions: list[Transaction] = []
        winning_buyer_ids: set[int] = set()
        sold_prop_ids: set[str] = set()

        for pid, pbids in prop_bids.items():
            asking = self._asking_price(pid)
            # only accept bids >= 90% of asking price
            valid = [b for b in pbids if b.bid_yen >= asking * 0.9]
            if not valid:
                continue
            winner = max(valid, key=lambda b: b.bid_yen)
            txn = Transaction(
                property_id=pid,
                buyer_id=winner.buyer_id,
                price_yen=winner.bid_yen,
                round_num=self._round_num,
            )
            round_transactions.append(txn)
            winning_buyer_ids.add(winner.buyer_id)
            sold_prop_ids.add(pid)

        self.transactions.extend(round_transactions)
        self._all_bids.extend(bids)

        # 7. remove winners and sold properties
        self.active_buyers = [
            b for b in self.active_buyers if b.agent_id not in winning_buyer_ids
        ]
        self.active_properties = [
            p for p in self.active_properties if p.property_id not in sold_prop_ids
        ]

        # 8. update graph
        for pid in sold_prop_ids:
            self.graph.remove_property(pid)
        for bid in winning_buyer_ids:
            self.graph.remove_buyer(bid)

        # 9. build RoundResult
        bid_yens = [b.bid_yen for b in bids]
        median_bid = int(statistics.median(bid_yens)) if bid_yens else 0
        price_std = int(statistics.stdev(bid_yens)) if len(bid_yens) >= 2 else 0

        result = RoundResult(
            round_num=self._round_num,
            bids=tuple(bids),
            transactions=tuple(round_transactions),
            active_buyers=len(self.active_buyers),
            active_properties=len(self.active_properties),
            median_bid_yen=median_bid,
            price_std_yen=price_std,
        )
        return result

    # ------------------------------------------------------------------
    # run
    # ------------------------------------------------------------------

    def run(self) -> BuyerSimResult:
        """Run full simulation until convergence or max_rounds.

        Caller must invoke ``reset(properties, buyers)`` before ``run()``.
        """
        converged = False
        converged_at: int | None = None

        for _ in range(1, self.config.max_rounds + 1):
            if not self.active_buyers or not self.active_properties:
                break

            result = self.step()
            self.rounds.append(result)

            # convergence: median bid stable within threshold for 2 rounds
            if len(self.rounds) >= 2:
                prev_median = self.rounds[-2].median_bid_yen
                curr_median = result.median_bid_yen
                if prev_median > 0 and curr_median > 0:
                    change = abs(curr_median - prev_median) / prev_median
                    if change < self.config.convergence_threshold:
                        converged = True
                        converged_at = result.round_num
                        break

        return self._build_result(converged, converged_at)

    # ------------------------------------------------------------------
    # private helpers
    # ------------------------------------------------------------------

    def _asking_price(self, property_id: str) -> int:
        for p in self.active_properties:
            if p.property_id == property_id:
                return p.asking_price_yen
        # fallback: check transactions
        for t in self.transactions:
            if t.property_id == property_id:
                return t.price_yen
        return 0

    def _build_result(
        self, converged: bool, converged_at: int | None
    ) -> BuyerSimResult:
        # property valuations from GNN
        prop_valuations: dict[str, int] = {}
        if self.gnn is not None and self.graph is not None:
            # re-run on any remaining properties; also include sold ones
            # by using last known tensors - but for simplicity use
            # transaction prices for sold, GNN for unsold
            for t in self.transactions:
                prop_valuations[t.property_id] = t.price_yen

            # for active properties, use last GNN forward pass
            if self.active_properties and self.active_buyers:
                tensors = prepare_tensors(
                    self.active_properties, self.active_buyers, self.graph
                )
                self.gnn.eval()
                with torch.no_grad():
                    _, vals = self.gnn(
                        tensors["prop_features"],
                        tensors["buyer_features"],
                        tensors["adj_pp"],
                        tensors["adj_bb"],
                        tensors["adj_bp"],
                    )
                asking = tensors["asking_prices"]
                price_scale = asking.mean().clamp(min=1.0)
                for i, pid in enumerate(tensors["prop_ids"]):
                    prop_valuations[pid] = int(
                        vals[i].item() * price_scale.item()
                    )

        # buyer segments
        segments = self._compute_segments()

        # bid histogram
        histogram = self._compute_histogram()

        return BuyerSimResult(
            rounds=tuple(self.rounds),
            converged=converged,
            converged_at_round=converged_at,
            property_valuations=prop_valuations,
            buyer_segments=tuple(segments),
            bid_histogram=tuple(histogram),
            config=self.config,
        )

    def _compute_segments(self) -> list[SegmentSummary]:
        """Group bids by buyer life_stage and compute segment stats."""
        stage_bids: dict[str, list[int]] = {}
        stage_wins: dict[str, int] = {}
        winning_buyers = {t.buyer_id for t in self.transactions}

        for bid in self._all_bids:
            stage = self._buyer_stages.get(bid.buyer_id, "unknown")
            stage_bids.setdefault(stage, []).append(bid.bid_yen)
            if bid.buyer_id in winning_buyers:
                stage_wins[stage] = stage_wins.get(stage, 0) + 1

        segments: list[SegmentSummary] = []
        for stage, bid_yens in sorted(stage_bids.items()):
            n_unique = len(
                {b.buyer_id for b in self._all_bids
                 if self._buyer_stages.get(b.buyer_id) == stage}
            )
            wins = stage_wins.get(stage, 0)
            segments.append(
                SegmentSummary(
                    life_stage=stage,
                    count=n_unique,
                    avg_bid_yen=int(statistics.mean(bid_yens)) if bid_yens else 0,
                    median_bid_yen=int(statistics.median(bid_yens)) if bid_yens else 0,
                    win_rate=wins / max(n_unique, 1),
                )
            )
        return segments

    def _compute_histogram(self, n_buckets: int = 10) -> list[BidBucket]:
        """Build a histogram of all bid prices."""
        if not self._all_bids:
            return []
        bid_yens = [b.bid_yen for b in self._all_bids]
        lo = min(bid_yens)
        hi = max(bid_yens)
        if lo == hi:
            return [BidBucket(low_yen=lo, high_yen=hi, count=len(bid_yens))]

        step = (hi - lo) / n_buckets
        buckets: list[BidBucket] = []
        for i in range(n_buckets):
            bucket_lo = int(lo + step * i)
            bucket_hi = int(lo + step * (i + 1))
            count = sum(1 for y in bid_yens if bucket_lo <= y < bucket_hi)
            # last bucket includes upper bound
            if i == n_buckets - 1:
                count = sum(1 for y in bid_yens if bucket_lo <= y <= bucket_hi)
            buckets.append(BidBucket(low_yen=bucket_lo, high_yen=bucket_hi, count=count))
        return buckets
