"""AI Investment Assistant — MiroFish-powered property similarity & guidance.

This agent helps users select a reference property, runs MiroFish analysis,
finds similar properties, and compares them with deep financial data.
"""

from agent.base_agent import BaseAgent
from agent.prompts_assistant import INVESTMENT_ASSISTANT_PROMPT
from agent.tool_acl import AgentRole
from agent.tools.search import search_properties
from agent.tools.neighborhood import analyze_neighborhood
from agent.tools.offers import place_offer
from agent.tools.comps import get_comps
from agent.tools.counter import counter_offer
from agent.tools.intelligence import get_intelligence_report


class AssistantAgent(BaseAgent):
    def __init__(self, client, **kwargs):
        super().__init__(client, role=AgentRole.ASSISTANT, **kwargs)
        self.tool_registry.register("search_properties", search_properties)
        self.tool_registry.register("analyze_neighborhood", analyze_neighborhood)
        self.tool_registry.register("place_offer", place_offer)
        self.tool_registry.register("get_comps", get_comps)
        self.tool_registry.register("counter_offer", counter_offer)
        self.tool_registry.register("get_intelligence_report", get_intelligence_report)

    def system_prompt(self) -> str:
        return INVESTMENT_ASSISTANT_PROMPT

    def tools(self) -> list[dict]:
        return [
            {
                "name": "search_properties",
                "description": "Search listings matching criteria (location, price range, bedrooms, property type). Use this to find properties similar to the user's reference property.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "location": {"type": "string", "description": "City, neighborhood, zip code, or address"},
                        "min_price": {"type": "number", "description": "Minimum price filter"},
                        "max_price": {"type": "number", "description": "Maximum price filter"},
                        "bedrooms": {"type": "integer", "description": "Minimum bedrooms"},
                        "property_type": {"type": "string", "enum": ["sfr", "condo", "duplex", "triplex"]},
                    },
                    "required": ["location"],
                },
            },
            {
                "name": "analyze_neighborhood",
                "description": "Analyze a neighborhood using TomTom Maps — returns nearby schools, transit, restaurants, parks, and walkability score. Use on both the reference property and candidates for comparison.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "address": {"type": "string", "description": "Full street address to analyze"},
                        "radius_meters": {"type": "integer", "default": 1500},
                    },
                    "required": ["address"],
                },
            },
            {
                "name": "get_comps",
                "description": "Get comparable recent sales near an address. Use this to check if a property is priced fairly and to discover similar properties that recently sold.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "address": {"type": "string", "description": "Address to find comparables for"},
                        "radius_miles": {"type": "number", "default": 1.0},
                    },
                    "required": ["address"],
                },
            },
            {
                "name": "get_intelligence_report",
                "description": "Retrieve the user's MiroFish deep intelligence report. THIS IS YOUR MOST IMPORTANT TOOL. It contains financial analysis (mortgage, cash flow), Monte Carlo simulations (IRR/NPV distributions), rent-vs-buy analysis, tax benefits, comparable sales, neighborhood scores, market outlook, risk assessment, and investment strategy recommendations. Always use this before giving investment advice.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "user_id": {"type": "string", "description": "The user ID to fetch the report for"},
                        "report_id": {"type": "string", "description": "Optional specific report ID. If omitted, fetches the most recent completed report."},
                    },
                    "required": ["user_id"],
                },
            },
            {
                "name": "place_offer",
                "description": "Submit a purchase offer on a property when the user is ready to act",
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
        ]
