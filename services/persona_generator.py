"""Persona generation services for negotiation and market-investor simulations."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

import anthropic

from config import settings
from services.logging import get_logger

logger = get_logger(__name__)


@dataclass
class AgentPersona:
    """Rich persona for a negotiation agent."""

    role: str  # "buyer" or "seller"
    name: str
    personality_type: str  # MBTI-style, e.g. "INTJ"
    negotiation_style: str  # aggressive / analytical / collaborative / avoidant
    risk_tolerance: str  # high / medium / low
    experience_level: str  # first_time / experienced / professional
    motivations: list[str] = field(default_factory=list)
    background: str = ""
    pressure_points: list[str] = field(default_factory=list)
    strengths: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "name": self.name,
            "personality_type": self.personality_type,
            "negotiation_style": self.negotiation_style,
            "risk_tolerance": self.risk_tolerance,
            "experience_level": self.experience_level,
            "motivations": self.motivations,
            "background": self.background,
            "pressure_points": self.pressure_points,
            "strengths": self.strengths,
        }


@dataclass
class InvestorPersona:
    """Run-scoped investor persona for the market simulation."""

    display_name: str
    archetype: str
    budget: float
    risk_posture: str
    hold_horizon: str
    target_yield: str
    preferred_property_types: list[str] = field(default_factory=list)
    preferred_price_band: str = ""
    neighborhood_preferences: list[str] = field(default_factory=list)
    avoidance_triggers: list[str] = field(default_factory=list)
    competition_style: str = ""
    exit_style: str = ""
    investment_thesis: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "display_name": self.display_name,
            "archetype": self.archetype,
            "budget": self.budget,
            "risk_posture": self.risk_posture,
            "hold_horizon": self.hold_horizon,
            "target_yield": self.target_yield,
            "preferred_property_types": list(self.preferred_property_types),
            "preferred_price_band": self.preferred_price_band,
            "neighborhood_preferences": list(self.neighborhood_preferences),
            "avoidance_triggers": list(self.avoidance_triggers),
            "competition_style": self.competition_style,
            "exit_style": self.exit_style,
            "investment_thesis": self.investment_thesis,
        }


# ── Fallback personas when Claude API is unavailable ──

_FALLBACK_BUYER = AgentPersona(
    role="buyer",
    name="Alex Chen",
    personality_type="INTJ",
    negotiation_style="analytical",
    risk_tolerance="medium",
    experience_level="experienced",
    motivations=["investment returns", "portfolio diversification"],
    background="An experienced real-estate investor looking for rental income properties in the Chicago metro area.",
    pressure_points=["rising interest rates", "competing buyers in the area"],
    strengths=["data-driven decision making", "patient negotiator", "strong market knowledge"],
)

_FALLBACK_SELLER = AgentPersona(
    role="seller",
    name="Maria Rodriguez",
    personality_type="ESFJ",
    negotiation_style="collaborative",
    risk_tolerance="medium",
    experience_level="experienced",
    motivations=["maximize sale price", "quick close for relocation"],
    background="A homeowner relocating for work, motivated to sell within 60 days but wants a fair price.",
    pressure_points=["relocation deadline", "carrying costs on two properties"],
    strengths=["property well-maintained", "desirable neighbourhood", "flexible on closing date"],
)

_NEGOTIATION_GENERATION_PROMPT = """\
Generate two negotiation personas for a real-estate transaction. Return valid JSON only (no markdown).

Buyer profile data:
{buyer_context}

Property / market context:
{property_context}

Return a JSON object with this exact structure:
{{
  "buyer": {{
    "name": "<realistic full name>",
    "personality_type": "<4-letter MBTI, e.g. INTJ>",
    "negotiation_style": "<aggressive|analytical|collaborative|avoidant>",
    "risk_tolerance": "<high|medium|low>",
    "experience_level": "<first_time|experienced|professional>",
    "motivations": ["<motivation 1>", "<motivation 2>"],
    "background": "<2-3 sentence bio>",
    "pressure_points": ["<what makes them concede 1>", "<what makes them concede 2>"],
    "strengths": ["<advantage 1>", "<advantage 2>"]
  }},
  "seller": {{
    "name": "<realistic full name>",
    "personality_type": "<4-letter MBTI>",
    "negotiation_style": "<aggressive|analytical|collaborative|avoidant>",
    "risk_tolerance": "<high|medium|low>",
    "experience_level": "<first_time|experienced|professional>",
    "motivations": ["<motivation 1>", "<motivation 2>"],
    "background": "<2-3 sentence bio>",
    "pressure_points": ["<what makes them concede 1>", "<what makes them concede 2>"],
    "strengths": ["<advantage 1>", "<advantage 2>"]
  }}
}}
"""

_MARKET_NAME_POOLS: dict[str, list[str]] = {
    "value": ["Jordan Pike", "Priya Dalton", "Evan Mercer", "Naomi Graves"],
    "yield": ["Lucas Hale", "Mina Foster", "Andre Sutton", "Claire Benton"],
    "momentum": ["Theo Mercer", "Riley Shaw", "Camden Holt", "Sofia Lane"],
    "contrarian": ["Avery Sloan", "Mara Quinn", "Julian Frost", "Tessa Rowe"],
}

_MARKET_ARCHETYPE_TEMPLATES: dict[str, dict[str, Any]] = {
    "value": {
        "risk_posture": "measured",
        "hold_horizon": "6-8 ticks",
        "target_yield": "5-7% gross yield",
        "preferred_property_types": ["condo", "sfr", "multifamily"],
        "neighborhood_preferences": ["walkable transit-rich corridors", "stable pricing pockets"],
        "avoidance_triggers": ["headline hazard flags", "price overextension"],
        "competition_style": "patient but willing to raise once conviction is high",
        "exit_style": "walk away when the valuation edge disappears",
        "investment_thesis": "Acquire mispriced urban assets where signal support still outweighs crowd pressure.",
    },
    "yield": {
        "risk_posture": "income-focused",
        "hold_horizon": "8-10 ticks",
        "target_yield": "6-8% stabilized yield",
        "preferred_property_types": ["multifamily", "duplex", "condo"],
        "neighborhood_preferences": ["dense renter demand", "reliable school and safety signals"],
        "avoidance_triggers": ["weak rent comps", "high recurring carrying costs"],
        "competition_style": "measured and selective",
        "exit_style": "hold unless yield support deteriorates materially",
        "investment_thesis": "Favor durable rental economics over short-lived momentum spikes.",
    },
    "momentum": {
        "risk_posture": "assertive",
        "hold_horizon": "4-6 ticks",
        "target_yield": "accept lower yield for faster appreciation",
        "preferred_property_types": ["condo", "sfr", "multifamily"],
        "neighborhood_preferences": ["high-velocity submarkets", "areas with rising peer attention"],
        "avoidance_triggers": ["stalled bid activity", "softening demand signals"],
        "competition_style": "aggressive when peers converge",
        "exit_style": "rotate out when momentum stalls",
        "investment_thesis": "Lean into assets where market attention is compounding and upside is confirming itself.",
    },
    "contrarian": {
        "risk_posture": "disciplined",
        "hold_horizon": "6-7 ticks",
        "target_yield": "seek upside from underappreciated pricing",
        "preferred_property_types": ["sfr", "condo", "multifamily"],
        "neighborhood_preferences": ["stable but overlooked pockets", "areas with room for rerating"],
        "avoidance_triggers": ["crowded bidding wars", "structural hazard concentration"],
        "competition_style": "avoid crowds and wait for conviction",
        "exit_style": "leave when competition overwhelms the edge",
        "investment_thesis": "Find pricing inefficiencies before the rest of the market reprices the opportunity.",
    },
}

_MARKET_GENERATION_PROMPT = """\
Generate realistic investor personas for a real-estate market simulation. Return valid JSON only (no markdown).

Market inventory context:
{inventory_context}

Investors to generate:
{investor_context}

Return a JSON object with this exact structure:
{{
  "personas": [
    {{
      "display_name": "<realistic full name>",
      "archetype": "<must match requested archetype>",
      "budget": <must match requested budget exactly>,
      "risk_posture": "<short phrase>",
      "hold_horizon": "<short phrase>",
      "target_yield": "<short phrase>",
      "preferred_property_types": ["<type 1>", "<type 2>"],
      "preferred_price_band": "<human-readable price band>",
      "neighborhood_preferences": ["<preference 1>", "<preference 2>"],
      "avoidance_triggers": ["<risk 1>", "<risk 2>"],
      "competition_style": "<short phrase>",
      "exit_style": "<short phrase>",
      "investment_thesis": "<1-2 sentence thesis that explains why this investor buys or exits>"
    }}
  ]
}}
"""


def _safe_parse_json(raw: str) -> dict[str, Any]:
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1]
        if text.endswith("```"):
            text = text[: text.rfind("```")]
    return json.loads(text)


async def _call_claude(prompt: str) -> dict[str, Any]:
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    response = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )
    return _safe_parse_json(response.content[0].text)


def _price_band(budget: float) -> str:
    lower = max(100_000, int((budget * 0.78) // 5_000 * 5_000))
    upper = int((budget * 1.02) // 5_000 * 5_000)
    return f"${lower // 1000}k-${upper // 1000}k"


def _fallback_market_persona(archetype: str, budget: float, index: int, inventory_context: dict[str, Any] | None = None) -> InvestorPersona:
    template = dict(_MARKET_ARCHETYPE_TEMPLATES.get(archetype, _MARKET_ARCHETYPE_TEMPLATES["value"]))
    name_pool = _MARKET_NAME_POOLS.get(archetype, _MARKET_NAME_POOLS["value"])
    property_types = list(template["preferred_property_types"])
    context_types = list((inventory_context or {}).get("property_types") or [])
    if context_types:
        property_types = [ptype for ptype in property_types if ptype in context_types] or property_types

    zip_codes = list((inventory_context or {}).get("zip_codes") or [])
    neighborhood_preferences = list(template["neighborhood_preferences"])
    if zip_codes:
        neighborhood_preferences = neighborhood_preferences + [f"target ZIPs like {', '.join(zip_codes[:2])}"]

    return InvestorPersona(
        display_name=name_pool[index % len(name_pool)],
        archetype=archetype,
        budget=round(budget, 2),
        risk_posture=str(template["risk_posture"]),
        hold_horizon=str(template["hold_horizon"]),
        target_yield=str(template["target_yield"]),
        preferred_property_types=property_types,
        preferred_price_band=_price_band(budget),
        neighborhood_preferences=neighborhood_preferences,
        avoidance_triggers=list(template["avoidance_triggers"]),
        competition_style=str(template["competition_style"]),
        exit_style=str(template["exit_style"]),
        investment_thesis=str(template["investment_thesis"]),
    )


def fallback_market_personas(
    archetypes: list[str],
    budgets: list[float],
    inventory_context: dict[str, Any] | None = None,
) -> list[InvestorPersona]:
    return [
        _fallback_market_persona(archetype, budget, index, inventory_context)
        for index, (archetype, budget) in enumerate(zip(archetypes, budgets, strict=False))
    ]


async def generate_personas(
    buyer_profile: dict | None = None,
    property_context: dict | None = None,
) -> dict[str, AgentPersona]:
    """Generate buyer + seller personas via Claude API.

    Falls back to deterministic defaults if the API call fails.
    """
    buyer_ctx = json.dumps(buyer_profile or {}, indent=2)
    prop_ctx = json.dumps(property_context or {}, indent=2)

    try:
        if not settings.anthropic_api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not configured")

        data = await _call_claude(
            _NEGOTIATION_GENERATION_PROMPT.format(
                buyer_context=buyer_ctx,
                property_context=prop_ctx,
            )
        )
        buyer = AgentPersona(role="buyer", **data["buyer"])
        seller = AgentPersona(role="seller", **data["seller"])
        return {"buyer": buyer, "seller": seller}

    except Exception as exc:
        logger.warning("persona_generation.fallback", error=str(exc))
        buyer = AgentPersona(**{**_FALLBACK_BUYER.__dict__})
        seller = AgentPersona(**{**_FALLBACK_SELLER.__dict__})

        if buyer_profile:
            if buyer_profile.get("risk_tolerance"):
                buyer.risk_tolerance = str(buyer_profile["risk_tolerance"])
            if buyer_profile.get("life_stage"):
                stage = buyer_profile["life_stage"]
                if stage in ("first_time_buyer", "student"):
                    buyer.experience_level = "first_time"
                elif stage in ("investor", "professional"):
                    buyer.experience_level = "professional"

        return {"buyer": buyer, "seller": seller}


async def generate_market_investor_personas(
    archetypes: list[str],
    budgets: list[float],
    inventory_context: dict[str, Any] | None = None,
) -> list[InvestorPersona]:
    """Generate run-scoped investor personas for market simulation runs."""
    if len(archetypes) != len(budgets):
        raise ValueError("archetypes and budgets must have the same length")

    inventory_context = inventory_context or {}
    fallback = fallback_market_personas(archetypes, budgets, inventory_context)

    try:
        if not settings.anthropic_api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not configured")

        investor_context = [
            {
                "slot": index + 1,
                "archetype": archetype,
                "budget": round(budget, 2),
                "preferred_property_types": fallback[index].preferred_property_types,
                "suggested_price_band": fallback[index].preferred_price_band,
            }
            for index, (archetype, budget) in enumerate(zip(archetypes, budgets, strict=False))
        ]
        data = await _call_claude(
            _MARKET_GENERATION_PROMPT.format(
                inventory_context=json.dumps(inventory_context, indent=2),
                investor_context=json.dumps(investor_context, indent=2),
            )
        )
        raw_personas = list(data.get("personas") or [])
        if len(raw_personas) != len(archetypes):
            raise ValueError("LLM returned the wrong number of investor personas")

        personas: list[InvestorPersona] = []
        for index, raw_persona in enumerate(raw_personas):
            normalized = dict(raw_persona)
            normalized["archetype"] = archetypes[index]
            normalized["budget"] = round(float(budgets[index]), 2)
            personas.append(InvestorPersona(**normalized))
        return personas

    except Exception as exc:
        logger.warning("market_persona_generation.fallback", error=str(exc))
        return fallback
