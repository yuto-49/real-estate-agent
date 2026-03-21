"""Broker Agent — mediates negotiations, ensures compliance, manages closing."""

from agent.base_agent import BaseAgent
from agent.prompts import BROKER_AGENT_PROMPT
from agent.tool_acl import AgentRole
from agent.tools.broker_tools import (
    mediate_negotiation, market_analysis, generate_contract, schedule_inspection,
)
from agent.tools.comps import get_comps
from agent.tools.neighborhood import analyze_neighborhood
from agent.tools.intelligence import get_intelligence_report


class BrokerAgent(BaseAgent):
    def __init__(self, client, **kwargs):
        super().__init__(client, role=AgentRole.BROKER, **kwargs)
        self.tool_registry.register("mediate_negotiation", mediate_negotiation)
        self.tool_registry.register("market_analysis", market_analysis)
        self.tool_registry.register("generate_contract", generate_contract)
        self.tool_registry.register("schedule_inspection", schedule_inspection)
        self.tool_registry.register("get_comps", get_comps)
        self.tool_registry.register("analyze_neighborhood", analyze_neighborhood)
        self.tool_registry.register("get_intelligence_report", get_intelligence_report)

    def system_prompt(self) -> str:
        return BROKER_AGENT_PROMPT

    def tools(self) -> list[dict]:
        return [
            {
                "name": "mediate_negotiation",
                "description": "Facilitate a round of negotiation between buyer and seller",
                "input_schema": {
                    "type": "object",
                    "properties": {"negotiation_id": {"type": "string"}},
                    "required": ["negotiation_id"],
                },
            },
            {
                "name": "market_analysis",
                "description": "Provide comprehensive market analysis for a location",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "location": {"type": "string"},
                        "radius_miles": {"type": "number", "default": 5.0},
                    },
                    "required": ["location"],
                },
            },
            {
                "name": "generate_contract",
                "description": "Draft a purchase agreement for an accepted deal",
                "input_schema": {
                    "type": "object",
                    "properties": {"deal_id": {"type": "string"}},
                    "required": ["deal_id"],
                },
            },
            {
                "name": "schedule_inspection",
                "description": "Schedule a property inspection",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "property_id": {"type": "string"},
                        "inspection_type": {
                            "type": "string",
                            "enum": ["general", "structural", "pest", "environmental"],
                        },
                    },
                    "required": ["property_id", "inspection_type"],
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
                "name": "analyze_neighborhood",
                "description": "Analyze a neighborhood via TomTom Maps",
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
                "name": "get_intelligence_report",
                "description": "Retrieve a user's MiroFish intelligence report (market outlook, strategy comparison, risk assessment, property recommendations) to inform mediation strategy",
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
