"""Seller Agent — lists properties, evaluates offers, negotiates price up."""

from agent.base_agent import BaseAgent
from agent.prompts import SELLER_AGENT_PROMPT
from agent.tool_acl import AgentRole
from agent.tools.listings import list_property, set_asking_price
from agent.tools.offers import evaluate_offer, accept_offer
from agent.tools.counter import counter_offer
from agent.tools.intelligence import get_intelligence_report


class SellerAgent(BaseAgent):
    def __init__(self, client, **kwargs):
        super().__init__(client, role=AgentRole.SELLER, **kwargs)
        self.tool_registry.register("list_property", list_property)
        self.tool_registry.register("evaluate_offer", evaluate_offer)
        self.tool_registry.register("set_asking_price", set_asking_price)
        self.tool_registry.register("accept_offer", accept_offer)
        self.tool_registry.register("counter_offer", counter_offer)
        self.tool_registry.register("get_intelligence_report", get_intelligence_report)

    def system_prompt(self) -> str:
        return SELLER_AGENT_PROMPT

    def tools(self) -> list[dict]:
        return [
            {
                "name": "list_property",
                "description": "List a property for sale",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "address": {"type": "string"},
                        "asking_price": {"type": "number"},
                        "bedrooms": {"type": "integer"},
                        "bathrooms": {"type": "number"},
                        "sqft": {"type": "integer"},
                    },
                    "required": ["address", "asking_price", "bedrooms", "bathrooms", "sqft"],
                },
            },
            {
                "name": "evaluate_offer",
                "description": "Analyze an incoming offer against market data",
                "input_schema": {
                    "type": "object",
                    "properties": {"offer_id": {"type": "string"}},
                    "required": ["offer_id"],
                },
            },
            {
                "name": "set_asking_price",
                "description": "Update asking price for a listed property",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "property_id": {"type": "string"},
                        "new_price": {"type": "number"},
                    },
                    "required": ["property_id", "new_price"],
                },
            },
            {
                "name": "accept_offer",
                "description": "Accept an offer and move to contract phase",
                "input_schema": {
                    "type": "object",
                    "properties": {"offer_id": {"type": "string"}},
                    "required": ["offer_id"],
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
            {
                "name": "get_negotiation_intel",
                "description": "Get curated negotiation intelligence from the MiroFish analysis. Returns pricing anchors, market outlook, or comparable sales — distilled for negotiation decisions.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "aspect": {
                            "type": "string",
                            "enum": ["pricing", "risk", "strategy", "market", "comps", "all"],
                            "description": "Which aspect of the intelligence report to retrieve.",
                        },
                    },
                    "required": ["aspect"],
                },
            },
        ]
