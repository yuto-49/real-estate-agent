"""Chat-based portfolio extraction service (onboarding wizard P3).

Calls Claude with a structured `record_portfolio_holdings` tool whose schema
mirrors :class:`api.schemas.PortfolioHoldingCreate`. The tool input is the
list of holdings Claude inferred from the user's free-text description.

We deliberately do **not** commit anything here — the caller surfaces the
extracted rows to the user for confirmation/edits, then re-posts the final
list to the confirm endpoint which reuses the same idempotent insert path as
the CSV import.

Design choices:

* The Anthropic client is injected so tests can pass a fake. In production
  the FastAPI router constructs one from settings.
* If Claude returns no ``tool_use`` block, we return an empty list with a
  warning string in ``narration`` — never raise.
* Holdings are coerced through Pydantic on the way out so the API surface
  is consistent with the CSV path.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from api.schemas import HoldingFinancialsCreate, PortfolioHoldingCreate


TOOL_NAME = "record_portfolio_holdings"

TOOL_SCHEMA: dict[str, Any] = {
    "name": TOOL_NAME,
    "description": (
        "Record one or more real estate holdings the user has described. "
        "Only invoke this when the user has provided enough detail to "
        "populate at least an address. Omit any unknown fields."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "holdings": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "address": {"type": "string"},
                        "asset_class": {
                            "type": "string",
                            "description": (
                                "One of: sfr, condo, multi_family, "
                                "commercial, land. Default sfr."
                            ),
                        },
                        "zip_code": {"type": "string"},
                        "cost_basis": {"type": "number"},
                        "current_value_estimate": {"type": "number"},
                        "loan_balance": {"type": "number"},
                        "interest_rate": {
                            "type": "number",
                            "description": "Annual rate as a decimal (e.g. 0.065).",
                        },
                        "monthly_rent": {"type": "number"},
                        "monthly_piti": {"type": "number"},
                    },
                    "required": ["address"],
                },
            }
        },
        "required": ["holdings"],
    },
}

SYSTEM_PROMPT = (
    "You help an investor enumerate their real estate holdings. Each turn, "
    "ask clarifying questions if needed, then call the "
    f"`{TOOL_NAME}` tool with whatever structured data you have so far. "
    "If you don't have enough information, ask a follow-up question in plain "
    "text instead of calling the tool. Never invent values you weren't told."
)


class ChatLike(Protocol):
    """Subset of the Anthropic client we use — easier to fake in tests."""

    class _Messages(Protocol):
        async def create(self, **kwargs: Any) -> Any: ...

    @property
    def messages(self) -> _Messages: ...


@dataclass(frozen=True, slots=True)
class ChatExtractionResult:
    """What the extractor returns each turn."""

    narration: str
    holdings: list[PortfolioHoldingCreate]


_FIN_FIELDS = {
    "cost_basis",
    "current_value_estimate",
    "loan_balance",
    "interest_rate",
    "monthly_rent",
    "monthly_piti",
}


def _coerce_holding(raw: dict[str, Any]) -> PortfolioHoldingCreate | None:
    """Turn the LLM's free-form dict into a typed holding, lenient on errors."""
    address = (raw.get("address") or "").strip()
    if not address:
        return None

    fin_data = {k: raw[k] for k in _FIN_FIELDS if raw.get(k) is not None}
    fin = HoldingFinancialsCreate(**fin_data) if fin_data else None

    try:
        return PortfolioHoldingCreate(
            address=address,
            asset_class=str(raw.get("asset_class") or "sfr"),
            zip_code=(raw.get("zip_code") or None),
            financials=fin,
        )
    except Exception:
        return None


async def extract_holdings_from_chat(
    client: ChatLike,
    *,
    messages: list[dict[str, Any]],
    model: str = "claude-haiku-4-5-20251001",
) -> ChatExtractionResult:
    """Run a single Claude turn and pull holdings out of the tool call.

    The caller owns conversation history (``messages``) — this function does
    not persist anything. Returns both the narration (text Claude wrote, if
    any) and the structured holdings (possibly empty).
    """
    response = await client.messages.create(
        model=model,
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        tools=[TOOL_SCHEMA],
        messages=messages,
    )

    text_parts: list[str] = []
    holdings: list[PortfolioHoldingCreate] = []

    for block in getattr(response, "content", []) or []:
        block_type = getattr(block, "type", None)
        if block_type == "text":
            text_parts.append(getattr(block, "text", ""))
        elif block_type == "tool_use" and getattr(block, "name", None) == TOOL_NAME:
            raw_holdings = (getattr(block, "input", {}) or {}).get("holdings", [])
            for entry in raw_holdings:
                if not isinstance(entry, dict):
                    continue
                coerced = _coerce_holding(entry)
                if coerced is not None:
                    holdings.append(coerced)

    return ChatExtractionResult(
        narration="\n".join(p for p in text_parts if p).strip(),
        holdings=holdings,
    )


__all__ = [
    "ChatExtractionResult",
    "ChatLike",
    "SYSTEM_PROMPT",
    "TOOL_NAME",
    "TOOL_SCHEMA",
    "extract_holdings_from_chat",
]
