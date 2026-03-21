"""Tool ACL tests."""

from agent.tool_acl import (
    AgentRole,
    TOOL_PERMISSIONS,
    validate_tool_access,
    filter_tools_for_role,
)


def test_buyer_can_search():
    assert validate_tool_access(AgentRole.BUYER, "search_properties") is True


def test_buyer_cannot_mediate():
    assert validate_tool_access(AgentRole.BUYER, "mediate_negotiation") is False


def test_seller_can_list():
    assert validate_tool_access(AgentRole.SELLER, "list_property") is True


def test_seller_cannot_search():
    assert validate_tool_access(AgentRole.SELLER, "search_properties") is False


def test_broker_can_mediate():
    assert validate_tool_access(AgentRole.BROKER, "mediate_negotiation") is True


def test_broker_cannot_place_offer():
    assert validate_tool_access(AgentRole.BROKER, "place_offer") is False


def test_filter_tools_buyer():
    tools = [
        {"name": "search_properties", "description": "Search"},
        {"name": "mediate_negotiation", "description": "Mediate"},
        {"name": "place_offer", "description": "Offer"},
    ]
    filtered = filter_tools_for_role(AgentRole.BUYER, tools)
    names = {t["name"] for t in filtered}
    assert "search_properties" in names
    assert "place_offer" in names
    assert "mediate_negotiation" not in names


def test_permissions_are_frozen():
    # Verify permissions map is immutable
    try:
        TOOL_PERMISSIONS[AgentRole.BUYER] = frozenset({"hacked"})
        assert False, "Should not be able to modify frozen map"
    except TypeError:
        pass


def test_counter_offer_shared():
    """Both buyer and seller can counter-offer."""
    assert validate_tool_access(AgentRole.BUYER, "counter_offer") is True
    assert validate_tool_access(AgentRole.SELLER, "counter_offer") is True
