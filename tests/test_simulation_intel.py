"""Tests for simulation-intelligence integration.

Covers: derive_config_from_report, intelligence briefings,
get_negotiation_intel tool, SimulationState, and tool ACL additions.
"""

import pytest
from agent.tool_acl import AgentRole, validate_tool_access
from agent.simulation_tools import SimulationState, create_simulation_tools


# ── Fixtures ──

@pytest.fixture
def sample_report():
    """A realistic MiroFish report data dict."""
    return {
        "market_outlook": {
            "trend": "cautiously_optimistic",
            "confidence": 0.72,
            "projected_appreciation_pct": 3.2,
            "market_health_score": 75,
        },
        "decision_anchors": {
            "max_recommended_price": 520000,
            "walk_away_price": 480000,
        },
        "strategy_comparison": [
            {
                "name": "Aggressive",
                "recommended_offer_pct": 90,
                "success_probability": 0.35,
                "risk_level": "high",
            },
            {
                "name": "Balanced",
                "recommended_offer_pct": 95,
                "success_probability": 0.65,
                "risk_level": "medium",
            },
            {
                "name": "Conservative",
                "recommended_offer_pct": 98,
                "success_probability": 0.85,
                "risk_level": "low",
            },
        ],
        "risk_assessment": [
            {"factor": "market_volatility", "severity": "medium", "probability": 0.25},
            {"factor": "interest_rate_risk", "severity": "high", "probability": 0.15},
            {"factor": "structural_issues", "severity": "low", "probability": 0.05},
        ],
        "monte_carlo_results": {
            "probability_of_loss": 0.12,
            "mean_irr": 7.3,
            "hold_years": 10,
            "irr_distribution": {"p10": 2.1, "p25": 4.5, "p50": 7.3, "p75": 10.1, "p90": 13.8},
        },
        "comparable_sales_analysis": {
            "value_indicator": "above_market",
            "median_price_per_sqft": 185,
            "subject_price_per_sqft": 210,
            "comparables_count": 8,
            "comparables": [
                {"address": "123 Oak St", "sale_price": 490000, "price_per_sqft": 178, "days_on_market": 32},
                {"address": "456 Elm Ave", "sale_price": 510000, "price_per_sqft": 192, "days_on_market": 18},
            ],
        },
        "timing_recommendation": {
            "action": "buy_now",
            "reasoning": "Interest rates expected to rise in Q2, current market offers favorable conditions",
        },
        "financial_analysis": {
            "cash_flow": {"net_cash_flow": -450},
        },
        "neighborhood_scoring": {
            "overall_score": 82,
            "schools": 88,
            "transit": 75,
            "safety": 90,
            "walkability": 65,
        },
    }


@pytest.fixture
def high_risk_report(sample_report):
    """Report with high risk indicators."""
    report = dict(sample_report)
    report["monte_carlo_results"] = {
        "probability_of_loss": 0.4,
        "mean_irr": 2.1,
        "hold_years": 10,
        "irr_distribution": {"p10": -5.0, "p25": -1.0, "p50": 2.1, "p75": 5.0, "p90": 8.0},
    }
    report["market_outlook"] = {
        "trend": "bearish",
        "confidence": 0.6,
        "market_health_score": 45,
    }
    report["risk_assessment"] = [
        {"factor": "market_crash_risk", "severity": "high", "probability": 0.45},
        {"factor": "liquidity_risk", "severity": "high", "probability": 0.35},
    ]
    return report


@pytest.fixture
def sim_state():
    return SimulationState(
        negotiation_id="sim-test",
        property_id="prop-123",
        asking_price=500000,
        buyer_maximum=520000,
        seller_minimum=470000,
        buyer_latest_price=465000,
        seller_latest_price=500000,
    )


# ── derive_config_from_report tests ──

class TestDeriveConfigFromReport:
    """Test NegotiationSimulator.derive_config_from_report static method."""

    def _derive(self, report, asking_price=500000):
        from services.negotiation_simulator import NegotiationSimulator
        return NegotiationSimulator.derive_config_from_report(report, asking_price)

    def test_extracts_buyer_maximum(self, sample_report):
        config = self._derive(sample_report)
        assert config["buyer_maximum"] == 520000

    def test_extracts_walk_away(self, sample_report):
        config = self._derive(sample_report)
        assert config["buyer_walk_away"] == 480000

    def test_aggressive_strategy_for_optimistic_low_risk(self, sample_report):
        """Cautiously optimistic market with 12% loss probability → aggressive (low risk + positive trend)."""
        config = self._derive(sample_report)
        assert config["strategy"] == "aggressive"

    def test_aggressive_strategy_for_strong_market(self, sample_report):
        """Bullish market with low risk → aggressive."""
        report = dict(sample_report)
        report["market_outlook"] = {
            "trend": "bullish",
            "confidence": 0.9,
            "market_health_score": 90,
        }
        report["monte_carlo_results"]["probability_of_loss"] = 0.08
        config = self._derive(report)
        assert config["strategy"] == "aggressive"

    def test_conservative_strategy_for_high_risk(self, high_risk_report):
        config = self._derive(high_risk_report)
        assert config["strategy"] == "conservative"

    def test_initial_offer_from_strategy(self, sample_report):
        config = self._derive(sample_report)
        # Aggressive strategy at 90% of 500000 = 450000
        assert config["initial_offer"] == 450000

    def test_above_market_lowers_offer(self):
        """When comps show above_market and no strategy override, offer at 90%."""
        report = {
            "comparable_sales_analysis": {
                "value_indicator": "above_market",
                "median_price_per_sqft": 185,
            },
        }
        config = self._derive(report)
        assert config.get("initial_offer") == 450000  # 90% of 500k

    def test_below_market_conservative_offer(self):
        """Below market → don't lowball, offer at 97%."""
        report = {
            "comparable_sales_analysis": {
                "value_indicator": "below_market",
                "median_price_per_sqft": 220,
            },
        }
        config = self._derive(report)
        assert config.get("initial_offer") == 485000  # 97% of 500k

    def test_buy_now_sets_high_urgency(self, sample_report):
        config = self._derive(sample_report)
        assert config.get("scenario_constraints", {}).get("buyer_urgency") == "high"

    def test_wait_sets_low_urgency(self, sample_report):
        report = dict(sample_report)
        report["timing_recommendation"] = {"action": "wait_3_months"}
        config = self._derive(report)
        assert config.get("scenario_constraints", {}).get("buyer_urgency") == "low"

    def test_high_risk_caps_max_rounds(self, high_risk_report):
        config = self._derive(high_risk_report)
        assert config.get("max_rounds") <= 8

    def test_empty_report_returns_empty(self):
        config = self._derive({})
        assert config == {}


# ── SimulationState tests ──

class TestSimulationState:
    def test_initial_state(self, sim_state):
        assert sim_state.status == "active"
        assert sim_state.current_round == 0
        assert sim_state.offers == []

    def test_defaults(self):
        state = SimulationState()
        assert state.negotiation_id == "sim-negotiation"
        assert state.asking_price == 0
        assert state.price_path == []


# ── Simulation tools tests ──

class TestSimulationTools:
    @pytest.fixture
    def tools(self, sim_state):
        return create_simulation_tools(sim_state)

    async def test_place_offer(self, tools, sim_state):
        result = await tools["place_offer"](property_id="p1", offer_price=480000)
        assert result["status"] == "submitted"
        assert result["offer_price"] == 480000
        assert sim_state.buyer_latest_price == 480000
        assert len(sim_state.offers) == 1
        assert sim_state.offers[0]["type"] == "offer"

    async def test_counter_offer_buyer(self, tools, sim_state):
        result = await tools["counter_offer"](
            negotiation_id="sim-test", counter_price=475000, _from_role="buyer"
        )
        assert result["status"] == "counter_submitted"
        assert sim_state.buyer_latest_price == 475000

    async def test_counter_offer_seller(self, tools, sim_state):
        result = await tools["counter_offer"](
            negotiation_id="sim-test", counter_price=495000, _from_role="seller"
        )
        assert result["status"] == "counter_submitted"
        assert sim_state.seller_latest_price == 495000

    async def test_accept_offer(self, tools, sim_state):
        sim_state.buyer_latest_price = 490000
        result = await tools["accept_offer"](offer_id="o1", _from_role="seller")
        assert result["status"] == "accepted"
        assert result["final_price"] == 490000
        assert sim_state.status == "accepted"

    async def test_evaluate_offer_recommends_accept(self, tools, sim_state):
        sim_state.buyer_latest_price = 495000  # 1% below asking
        result = await tools["evaluate_offer"](offer_id="o1")
        assert result["recommendation"] == "accept"

    async def test_evaluate_offer_recommends_counter(self, tools, sim_state):
        sim_state.buyer_latest_price = 450000  # 10% below asking
        result = await tools["evaluate_offer"](offer_id="o1")
        assert result["recommendation"] == "counter_higher"

    async def test_mediate_negotiation(self, tools, sim_state):
        result = await tools["mediate_negotiation"](negotiation_id="sim-test")
        assert result["buyer_position"] == sim_state.buyer_latest_price
        assert result["seller_position"] == sim_state.seller_latest_price
        assert "midpoint" in result
        assert "spread_pct" in result

    async def test_price_path_tracking(self, tools, sim_state):
        await tools["place_offer"](property_id="p1", offer_price=470000)
        await tools["counter_offer"](negotiation_id="n1", counter_price=495000, _from_role="seller")
        assert len(sim_state.price_path) == 2
        assert sim_state.price_path[0]["role"] == "buyer"
        assert sim_state.price_path[1]["role"] == "seller"

    async def test_noop_tools_return_not_available(self, tools):
        result = await tools["search_properties"]()
        assert result["status"] == "not_available_in_simulation"

    async def test_intelligence_report_passthrough(self, tools):
        report = {"market_outlook": {"trend": "bullish"}}
        result = await tools["get_intelligence_report"](user_id="u1", _report_data=report)
        assert result["market_outlook"]["trend"] == "bullish"

    async def test_intelligence_report_no_data(self, tools):
        result = await tools["get_intelligence_report"](user_id="u1")
        assert result["status"] == "no_report_available"


# ── get_negotiation_intel tool tests ──

class TestNegotiationIntel:
    @pytest.fixture
    def tools(self, sim_state, sample_report):
        tools = create_simulation_tools(sim_state)
        # Bind report data as the simulator would
        self._report = sample_report
        return tools

    async def _call(self, tools, aspect):
        return await tools["get_negotiation_intel"](aspect=aspect, _report_data=self._report)

    async def test_pricing_aspect(self, tools):
        result = await self._call(tools, "pricing")
        assert "pricing" in result
        assert result["pricing"]["max_recommended_price"] == 520000
        assert result["pricing"]["value_indicator"] == "above_market"

    async def test_risk_aspect(self, tools):
        result = await self._call(tools, "risk")
        assert "risk" in result
        assert result["risk"]["probability_of_loss"] == 0.12
        assert len(result["risk"]["key_risks"]) > 0

    async def test_strategy_aspect(self, tools):
        result = await self._call(tools, "strategy")
        assert "strategy" in result
        names = [s["name"] for s in result["strategy"]["options"]]
        assert "Aggressive" in names
        assert "Balanced" in names
        assert "Conservative" in names

    async def test_market_aspect(self, tools):
        result = await self._call(tools, "market")
        assert "market" in result
        assert result["market"]["trend"] == "cautiously_optimistic"
        assert result["market"]["timing_action"] == "buy_now"

    async def test_comps_aspect(self, tools):
        result = await self._call(tools, "comps")
        assert "comps" in result
        assert result["comps"]["median_price_per_sqft"] == 185
        assert len(result["comps"]["recent_sales"]) == 2

    async def test_all_aspect(self, tools):
        result = await self._call(tools, "all")
        assert "pricing" in result
        assert "risk" in result
        assert "strategy" in result
        assert "market" in result
        assert "comps" in result

    async def test_no_report_returns_status(self, tools):
        result = await tools["get_negotiation_intel"](aspect="pricing")
        assert result["status"] == "no_report_available"


# ── Tool ACL additions ──

class TestToolACLAdditions:
    def test_buyer_can_accept_offer(self):
        assert validate_tool_access(AgentRole.BUYER, "accept_offer") is True

    def test_buyer_can_get_negotiation_intel(self):
        assert validate_tool_access(AgentRole.BUYER, "get_negotiation_intel") is True

    def test_seller_can_get_negotiation_intel(self):
        assert validate_tool_access(AgentRole.SELLER, "get_negotiation_intel") is True

    def test_broker_can_get_negotiation_intel(self):
        assert validate_tool_access(AgentRole.BROKER, "get_negotiation_intel") is True

    def test_buyer_can_get_intelligence_report(self):
        assert validate_tool_access(AgentRole.BUYER, "get_intelligence_report") is True

    def test_seller_can_get_intelligence_report(self):
        assert validate_tool_access(AgentRole.SELLER, "get_intelligence_report") is True

    def test_broker_can_get_intelligence_report(self):
        assert validate_tool_access(AgentRole.BROKER, "get_intelligence_report") is True
