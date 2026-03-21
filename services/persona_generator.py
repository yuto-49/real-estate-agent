"""Agent persona generator — creates rich buyer/seller personas using Claude.

Inspired by MiroFish's persona architecture: MBTI-style personality types,
negotiation styles, risk profiles, and backstory generation.
"""

import json
from dataclasses import dataclass, field

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

    def to_dict(self) -> dict:
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


_GENERATION_PROMPT = """\
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
        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        response = await client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            messages=[
                {
                    "role": "user",
                    "content": _GENERATION_PROMPT.format(
                        buyer_context=buyer_ctx,
                        property_context=prop_ctx,
                    ),
                }
            ],
        )

        raw = response.content[0].text
        # Strip possible markdown fences
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1]
            if raw.endswith("```"):
                raw = raw[: raw.rfind("```")]
        data = json.loads(raw)

        buyer = AgentPersona(role="buyer", **data["buyer"])
        seller = AgentPersona(role="seller", **data["seller"])

        return {"buyer": buyer, "seller": seller}

    except Exception as e:
        logger.warning("persona_generation.fallback", error=str(e))
        # Return deterministic fallback personas, customised with buyer profile data
        buyer = AgentPersona(**{**_FALLBACK_BUYER.__dict__})
        seller = AgentPersona(**{**_FALLBACK_SELLER.__dict__})

        if buyer_profile:
            if buyer_profile.get("risk_tolerance"):
                buyer.risk_tolerance = buyer_profile["risk_tolerance"]
            if buyer_profile.get("life_stage"):
                stage = buyer_profile["life_stage"]
                if stage in ("first_time_buyer", "student"):
                    buyer.experience_level = "first_time"
                elif stage in ("investor", "professional"):
                    buyer.experience_level = "professional"

        return {"buyer": buyer, "seller": seller}
