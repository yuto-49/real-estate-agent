"""Buyer Agent — searches properties, evaluates neighborhoods, negotiates price down."""

from agent.base_agent import BaseAgent
from agent.prompts import BUYER_AGENT_PROMPT
from agent.tool_acl import AgentRole
from agent.tools.search import search_properties
from agent.tools.neighborhood import analyze_neighborhood
from agent.tools.offers import place_offer, accept_offer
from agent.tools.comps import get_comps
from agent.tools.counter import counter_offer
from agent.tools.intelligence import get_intelligence_report


class BuyerAgent(BaseAgent):
    def __init__(self, client, **kwargs):
        super().__init__(client, role=AgentRole.BUYER, **kwargs)
        self.tool_registry.register("search_properties", search_properties)
        self.tool_registry.register("analyze_neighborhood", analyze_neighborhood)
        self.tool_registry.register("place_offer", place_offer)
        self.tool_registry.register("accept_offer", accept_offer)
        self.tool_registry.register("get_comps", get_comps)
        self.tool_registry.register("counter_offer", counter_offer)
        self.tool_registry.register("get_intelligence_report", get_intelligence_report)

    def system_prompt(self) -> str:
        return BUYER_AGENT_PROMPT

    def tools(self) -> list[dict]:
        return [
            {
                "name": "search_properties",
                "description": "Search listings matching buyer criteria",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "location": {"type": "string", "description": "City, zip code, or address"},
                        "min_price": {"type": "number"},
                        "max_price": {"type": "number"},
                        "bedrooms": {"type": "integer"},
                        "property_type": {"type": "string", "enum": ["sfr", "condo", "duplex", "triplex"]},
                    },
                    "required": ["location"],
                },
            },
            {
                "name": "analyze_neighborhood",
                "description": "Analyze a neighborhood via TomTom Maps (schools, transit, walkability)",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "address": {"type": "string"},
                        "radius_meters": {"type": "integer", "default": 1500},
                    },
                    "required": ["address"],
                },
            },
            {
                "name": "place_offer",
                "description": "Submit a purchase offer on a property",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "property_id": {"type": "string"},
                        "offer_price": {"type": "number"},
                        "contingencies": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "e.g. ['inspection', 'financing', 'appraisal']",
                        },
                    },
                    "required": ["property_id", "offer_price"],
                },
            },
            {
                "name": "get_comps",
                "description": "Get comparable recent sales near an address",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "address": {"type": "string"},
                        "radius_miles": {"type": "number", "default": 1.0},
                    },
                    "required": ["address"],
                },
            },
            {
                "name": "counter_offer",
                "description": "Submit a counter-offer in an active negotiation",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "negotiation_id": {"type": "string"},
                        "counter_price": {"type": "number"},
                        "message": {"type": "string"},
                    },
                    "required": ["negotiation_id", "counter_price"],
                },
            },
            {
                "name": "accept_offer",
                "description": "Accept the current offer and close the negotiation",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "offer_id": {"type": "string"},
                    },
                    "required": ["offer_id"],
                },
            },
            {
                "name": "get_intelligence_report",
                "description": "Retrieve the user's MiroFish intelligence report (market outlook, strategy comparison, risk assessment, property recommendations) to inform negotiation strategy",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "user_id": {"type": "string", "description": "The user ID to fetch the report for"},
                        "report_id": {"type": "string", "description": "Optional specific report ID"},
                    },
                    "required": ["user_id"],
                },
            },
        ]
