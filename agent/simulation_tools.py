"""In-memory mock tools for negotiation simulation.

These replace the real DB-backed tools during simulation so agents
can negotiate without writing to the database. State is tracked
in a shared SimulationState object.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SimulationState:
    """Tracks all in-memory state for one simulation run."""
    negotiation_id: str = "sim-negotiation"
    property_id: str = ""
    asking_price: float = 0
    buyer_maximum: float = 0
    seller_minimum: float = 0
    current_round: int = 0
    buyer_latest_price: float = 0
    seller_latest_price: float = 0
    offers: list[dict] = field(default_factory=list)
    status: str = "active"  # active, accepted, rejected
    price_path: list[dict] = field(default_factory=list)


def create_simulation_tools(state: SimulationState) -> dict[str, Any]:
    """Create a set of in-memory tool handlers bound to the given state.

    Returns a dict of {tool_name: async_handler} that can be registered
    on an agent's tool_registry temporarily.
    """

    async def sim_place_offer(
        property_id: str = "",
        offer_price: float = 0,
        contingencies: list[str] | None = None,
        **kwargs,
    ) -> dict:
        """Simulated place_offer — records in state, no DB."""
        state.buyer_latest_price = offer_price
        entry = {
            "type": "offer",
            "from": "buyer",
            "price": offer_price,
            "round": state.current_round,
            "contingencies": contingencies or [],
        }
        state.offers.append(entry)
        state.price_path.append({"round": state.current_round, "role": "buyer", "price": offer_price})
        return {
            "status": "submitted",
            "offer_price": offer_price,
            "negotiation_id": state.negotiation_id,
            "message": f"Offer of ${offer_price:,.0f} submitted.",
        }

    async def sim_counter_offer(
        negotiation_id: str = "",
        counter_price: float = 0,
        message: str = "",
        **kwargs,
    ) -> dict:
        """Simulated counter_offer — records in state, no DB."""
        # Determine who is countering based on context
        # The simulator sets the 'from_role' before calling
        from_role = kwargs.get("_from_role", "unknown")
        if from_role == "buyer":
            state.buyer_latest_price = counter_price
        elif from_role == "seller":
            state.seller_latest_price = counter_price

        entry = {
            "type": "counter_offer",
            "from": from_role,
            "price": counter_price,
            "round": state.current_round,
            "message": message,
        }
        state.offers.append(entry)
        state.price_path.append({"round": state.current_round, "role": from_role, "price": counter_price})

        spread = abs(state.seller_latest_price - state.buyer_latest_price)
        spread_pct = (spread / state.asking_price * 100) if state.asking_price > 0 else 0

        return {
            "status": "counter_submitted",
            "counter_price": counter_price,
            "spread": round(spread, 2),
            "spread_pct": round(spread_pct, 1),
            "message": f"Counter-offer of ${counter_price:,.0f} submitted. Current spread: {spread_pct:.1f}%",
        }

    async def sim_accept_offer(offer_id: str = "", **kwargs) -> dict:
        """Simulated accept_offer — marks deal as accepted in state."""
        # Use the latest offer price as the accepted price
        accepted_price = state.buyer_latest_price or state.seller_latest_price
        state.status = "accepted"
        entry = {
            "type": "accept",
            "from": kwargs.get("_from_role", "unknown"),
            "price": accepted_price,
            "round": state.current_round,
        }
        state.offers.append(entry)
        state.price_path.append({"round": state.current_round, "role": "accepted", "price": accepted_price})
        return {
            "status": "accepted",
            "final_price": accepted_price,
            "message": f"Offer accepted at ${accepted_price:,.0f}!",
        }

    async def sim_evaluate_offer(offer_id: str = "", **kwargs) -> dict:
        """Simulated evaluate_offer — provides analysis based on state."""
        latest_offer = state.buyer_latest_price
        spread = state.asking_price - latest_offer
        spread_pct = (spread / state.asking_price * 100) if state.asking_price > 0 else 0

        if spread_pct <= 3:
            recommendation = "accept"
        elif spread_pct <= 8:
            recommendation = "counter_split"
        else:
            recommendation = "counter_higher"

        return {
            "offer_price": latest_offer,
            "asking_price": state.asking_price,
            "spread": round(spread, 2),
            "spread_pct": round(spread_pct, 1),
            "recommendation": recommendation,
            "market_position": "fair" if spread_pct < 10 else "below_market",
        }

    async def sim_mediate_negotiation(negotiation_id: str = "", **kwargs) -> dict:
        """Simulated mediate — broker gets full view of both positions."""
        spread = abs(state.seller_latest_price - state.buyer_latest_price)
        spread_pct = (spread / state.asking_price * 100) if state.asking_price > 0 else 0
        midpoint = (state.seller_latest_price + state.buyer_latest_price) / 2

        return {
            "buyer_position": state.buyer_latest_price,
            "seller_position": state.seller_latest_price,
            "spread": round(spread, 2),
            "spread_pct": round(spread_pct, 1),
            "midpoint": round(midpoint, 2),
            "round": state.current_round,
            "recommendation": (
                "suggest_split" if spread_pct < 5
                else "continue_negotiation" if spread_pct < 10
                else "consider_stopping"
            ),
        }

    async def sim_get_intelligence_report(user_id: str = "", **kwargs) -> dict:
        """Pass-through — returns report data from kwargs if provided."""
        return kwargs.get("_report_data", {"status": "no_report_available"})

    return {
        "place_offer": sim_place_offer,
        "counter_offer": sim_counter_offer,
        "accept_offer": sim_accept_offer,
        "evaluate_offer": sim_evaluate_offer,
        "mediate_negotiation": sim_mediate_negotiation,
        "get_intelligence_report": sim_get_intelligence_report,
        # Pass-through tools that don't need simulation
        "search_properties": _noop_tool("search_properties"),
        "analyze_neighborhood": _noop_tool("analyze_neighborhood"),
        "get_comps": _noop_tool("get_comps"),
        "list_property": _noop_tool("list_property"),
        "set_asking_price": _noop_tool("set_asking_price"),
        "market_analysis": _noop_tool("market_analysis"),
        "generate_contract": _noop_tool("generate_contract"),
        "schedule_inspection": _noop_tool("schedule_inspection"),
    }


def _noop_tool(name: str):
    """Create a no-op async handler for tools not used during simulation."""
    async def handler(**kwargs):
        return {"status": "not_available_in_simulation", "tool": name}
    return handler
