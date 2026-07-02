"""Generate BuyerSimReport comparing GNN valuation with satei and price-probability.

Pure domain layer -- no I/O. Produces Japanese-language narrative summaries.
"""

from __future__ import annotations

import statistics

from domain.buyer_sim.models import (
    BidBucket,
    BuyerSimReport,
    BuyerSimResult,
    SegmentSummary,
)


def generate_report(
    property_id: str,
    sim_result: BuyerSimResult,
    satei_price_yen: int | None = None,
    price_prob_sweet_spot_yen: int | None = None,
) -> BuyerSimReport:
    """Generate a comprehensive report for a single property.

    Args:
        property_id: Target property to report on.
        sim_result: Full simulation result from BuyerSimEnvironment.
        satei_price_yen: Hedonic satei valuation (optional).
        price_prob_sweet_spot_yen: Price-probability sweet spot (optional).

    Returns:
        BuyerSimReport with GNN valuation, confidence interval,
        hazard impact, segments, histogram, and JP narrative.
    """
    # --- GNN valuation ---
    gnn_val = sim_result.property_valuations.get(property_id, 0)

    # --- bid distribution for this property ---
    prop_bids: list[int] = []
    for rnd in sim_result.rounds:
        for bid in rnd.bids:
            if bid.property_id == property_id:
                prop_bids.append(bid.bid_yen)

    if prop_bids:
        mean_bid = int(statistics.mean(prop_bids))
        median_bid = int(statistics.median(prop_bids))
        std_bid = int(statistics.stdev(prop_bids)) if len(prop_bids) >= 2 else 0
    else:
        mean_bid = gnn_val
        median_bid = gnn_val
        std_bid = 0

    # confidence interval: +/- 1 std from GNN valuation
    conf_low = max(gnn_val - std_bid, 0)
    conf_high = gnn_val + std_bid

    # --- hazard impact ---
    # Compare average bid on this property vs overall average bid
    all_bids: list[int] = []
    for rnd in sim_result.rounds:
        for bid in rnd.bids:
            all_bids.append(bid.bid_yen)

    overall_avg = int(statistics.mean(all_bids)) if all_bids else 0
    if overall_avg > 0 and mean_bid > 0:
        hazard_impact_pct = round(
            (mean_bid - overall_avg) / overall_avg * 100, 2
        )
    else:
        hazard_impact_pct = 0.0

    # --- rounds to converge ---
    rounds_to_converge = (
        sim_result.converged_at_round
        if sim_result.converged_at_round is not None
        else len(sim_result.rounds)
    )

    # --- bid histogram for this property ---
    histogram = _build_property_histogram(prop_bids)

    # --- narrative ---
    narrative = _build_narrative(
        property_id=property_id,
        gnn_val=gnn_val,
        n_buyers=sim_result.config.n_buyers,
        n_rounds=len(sim_result.rounds),
        satei_price_yen=satei_price_yen,
        price_prob_sweet_spot_yen=price_prob_sweet_spot_yen,
        mean_bid=mean_bid,
        median_bid=median_bid,
        hazard_impact_pct=hazard_impact_pct,
        converged=sim_result.converged,
    )

    return BuyerSimReport(
        property_id=property_id,
        gnn_valuation_yen=gnn_val,
        gnn_confidence_low_yen=conf_low,
        gnn_confidence_high_yen=conf_high,
        satei_price_yen=satei_price_yen,
        price_probability_sweet_spot_yen=price_prob_sweet_spot_yen,
        buyer_segments=sim_result.buyer_segments,
        bid_histogram=tuple(histogram),
        median_bid_yen=median_bid,
        mean_bid_yen=mean_bid,
        hazard_impact_pct=hazard_impact_pct,
        rounds_to_converge=rounds_to_converge,
        narrative_jp=narrative,
    )


# ---------------------------------------------------------------------------
# private helpers
# ---------------------------------------------------------------------------


def _build_property_histogram(
    bid_yens: list[int], n_buckets: int = 8
) -> list[BidBucket]:
    """Build a histogram of bid prices for a single property."""
    if not bid_yens:
        return []
    lo = min(bid_yens)
    hi = max(bid_yens)
    if lo == hi:
        return [BidBucket(low_yen=lo, high_yen=hi, count=len(bid_yens))]

    step = (hi - lo) / n_buckets
    buckets: list[BidBucket] = []
    for i in range(n_buckets):
        bucket_lo = int(lo + step * i)
        bucket_hi = int(lo + step * (i + 1))
        if i == n_buckets - 1:
            count = sum(1 for y in bid_yens if bucket_lo <= y <= bucket_hi)
        else:
            count = sum(1 for y in bid_yens if bucket_lo <= y < bucket_hi)
        buckets.append(
            BidBucket(low_yen=bucket_lo, high_yen=bucket_hi, count=count)
        )
    return buckets


def _to_man_yen(yen: int) -> str:
    """Convert yen to 万円 display string."""
    man = yen / 10_000
    if man >= 10_000:
        # use 億円 for >= 1 oku
        oku = man / 10_000
        return f"{oku:.2f}億円"
    return f"{man:,.0f}万円"


def _build_narrative(
    *,
    property_id: str,
    gnn_val: int,
    n_buyers: int,
    n_rounds: int,
    satei_price_yen: int | None,
    price_prob_sweet_spot_yen: int | None,
    mean_bid: int,
    median_bid: int,
    hazard_impact_pct: float,
    converged: bool,
) -> str:
    """Build Japanese narrative summarising simulation findings."""
    lines: list[str] = []

    gnn_str = _to_man_yen(gnn_val)
    convergence_note = "収束しました" if converged else "最大ラウンド数に達しました"

    lines.append(
        f"GNNバイヤーシミュレーション結果: "
        f"{n_buyers}名の買い手エージェントによる{n_rounds}ラウンドの"
        f"シミュレーションで、本物件の市場合意価格は{gnn_str}と推定されました。"
        f"({convergence_note})"
    )

    # comparison with satei
    if satei_price_yen is not None and satei_price_yen > 0:
        diff_pct = round((gnn_val - satei_price_yen) / satei_price_yen * 100, 1)
        direction = "上方" if diff_pct >= 0 else "下方"
        satei_str = _to_man_yen(satei_price_yen)
        lines.append(
            f"査定価格{satei_str}と比較して{abs(diff_pct)}%の{direction}乖離があります。"
        )

    # comparison with price-probability sweet spot
    if price_prob_sweet_spot_yen is not None and price_prob_sweet_spot_yen > 0:
        diff_pct = round(
            (gnn_val - price_prob_sweet_spot_yen)
            / price_prob_sweet_spot_yen
            * 100,
            1,
        )
        direction = "上方" if diff_pct >= 0 else "下方"
        pp_str = _to_man_yen(price_prob_sweet_spot_yen)
        lines.append(
            f"成約確率最適価格{pp_str}と比較して{abs(diff_pct)}%の{direction}乖離があります。"
        )

    # hazard impact note
    if abs(hazard_impact_pct) > 3.0:
        if hazard_impact_pct < 0:
            lines.append(
                f"ハザードリスクにより、平均入札額が全体平均より"
                f"{abs(hazard_impact_pct):.1f}%低くなっています。"
            )
        else:
            lines.append(
                f"本物件の入札額は全体平均より{hazard_impact_pct:.1f}%高く、"
                f"立地優位性が示唆されます。"
            )

    # bid statistics
    median_str = _to_man_yen(median_bid)
    mean_str = _to_man_yen(mean_bid)
    lines.append(f"入札中央値: {median_str}、入札平均値: {mean_str}。")

    return "\n".join(lines)
