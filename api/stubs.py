"""Stub routers for features removed in the Tokyo pivot (migration f9a1b2c3d4e5).

The frontend still has pages that call these endpoints. Instead of 404,
return 501 with a clear message pointing to the roadmap.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

_MSG = (
    "Feature removed in pivot. "
    "New brokerage features: POST /api/satei/compute (査定コンプグリッド), "
    "POST /api/price-probability/compute (成約確率カーブ), "
    "POST /api/negotiation-coach/session (交渉戦略コーチ). "
    "See doc/TIER1_IMPLEMENTATION_PLAN.md"
)


async def _stub(request: Request) -> None:
    raise HTTPException(status_code=501, detail=_MSG)


# ── Negotiations ────────────────────────────────────────────────────────

negotiations_stub = APIRouter()
negotiations_stub.add_api_route("/", _stub, methods=["POST"])
negotiations_stub.add_api_route("/{id}", _stub, methods=["GET"])
negotiations_stub.add_api_route("/{id}/offer", _stub, methods=["POST"])
negotiations_stub.add_api_route("/{id}/accept", _stub, methods=["POST"])
negotiations_stub.add_api_route("/{id}/transition", _stub, methods=["POST"])

# ── Reports ─────────────────────────────────────────────────────────────

reports_stub = APIRouter()
reports_stub.add_api_route("/generate", _stub, methods=["POST"])
reports_stub.add_api_route("/status/{id}", _stub, methods=["GET"])
reports_stub.add_api_route("/{id}", _stub, methods=["GET"])
reports_stub.add_api_route("/user/{user_id}", _stub, methods=["GET"])

# ── Social Simulation ──────────────────────────────────────────────────

social_sim_stub = APIRouter()
social_sim_stub.add_api_route("/start", _stub, methods=["POST"])
social_sim_stub.add_api_route("/{run_id}/status", _stub, methods=["GET"])
social_sim_stub.add_api_route("/{run_id}/result", _stub, methods=["GET"])
social_sim_stub.add_api_route("/{run_id}/actions", _stub, methods=["GET"])
social_sim_stub.add_api_route("/{run_id}/timeline", _stub, methods=["GET"])
social_sim_stub.add_api_route("/{run_id}/generate-report", _stub, methods=["POST"])

# ── Simulation ────────────────────────────────────────────────────────
# Replaced by api/simulation_unified.py — unified simulation router.

# ── Visualization ──────────────────────────────────────────────────────

visualization_stub = APIRouter()
visualization_stub.add_api_route("/property/{property_id}", _stub, methods=["GET"])
visualization_stub.add_api_route("/replay/{simulation_id}", _stub, methods=["GET"])
visualization_stub.add_api_route("/replay/batch/{batch_id}", _stub, methods=["GET"])
visualization_stub.add_api_route("/replay/by-property/{property_id}", _stub, methods=["GET"])

# ── Agent ──────────────────────────────────────────────────────────────

agent_stub = APIRouter()
agent_stub.add_api_route("/message", _stub, methods=["POST"])


__all__ = [
    "negotiations_stub",
    "reports_stub",
    "social_sim_stub",
    "visualization_stub",
    "agent_stub",
]
