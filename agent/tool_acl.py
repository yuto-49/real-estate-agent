"""Tool Access Control List — enforces which tools each agent role can invoke.

This is a security boundary: the ACL is checked BEFORE tool definitions
are sent to Claude and AFTER tool calls are received, providing defense in depth.
"""

from enum import Enum
from types import MappingProxyType


class AgentRole(str, Enum):
    BUYER = "buyer"
    SELLER = "seller"
    BROKER = "broker"
    ASSISTANT = "assistant"


# Frozen permission map — immutable at runtime
TOOL_PERMISSIONS: MappingProxyType[AgentRole, frozenset[str]] = MappingProxyType({
    AgentRole.BUYER: frozenset({
        "search_properties",
        "analyze_neighborhood",
        "place_offer",
        "get_comps",
        "counter_offer",
        "get_intelligence_report",
    }),
    AgentRole.SELLER: frozenset({
        "list_property",
        "evaluate_offer",
        "set_asking_price",
        "accept_offer",
        "counter_offer",
        "get_intelligence_report",
    }),
    AgentRole.BROKER: frozenset({
        "mediate_negotiation",
        "market_analysis",
        "generate_contract",
        "schedule_inspection",
        "get_comps",
        "analyze_neighborhood",
        "get_intelligence_report",
    }),
    AgentRole.ASSISTANT: frozenset({
        "search_properties",
        "analyze_neighborhood",
        "place_offer",
        "get_comps",
        "counter_offer",
        "get_intelligence_report",
    }),
})


def validate_tool_access(role: AgentRole, tool_name: str) -> bool:
    """Check if a role is permitted to use a specific tool."""
    allowed = TOOL_PERMISSIONS.get(role, frozenset())
    return tool_name in allowed


def filter_tools_for_role(role: AgentRole, tools: list[dict]) -> list[dict]:
    """Filter tool definitions to only those permitted for the role.
    Called BEFORE sending tools to Claude API.
    """
    allowed = TOOL_PERMISSIONS.get(role, frozenset())
    return [t for t in tools if t.get("name") in allowed]
