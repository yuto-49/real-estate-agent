"""FastAPI entry point for the Real Estate Agentic System.

Scope (post-pivot): Tokyo brokerage satei-to-close platform. The buyer/
seller negotiation chat, social-sentiment NIMBY simulator, and synthetic
market tick engine have been removed — see migration ``f9a1b2c3d4e5``.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.properties import router as properties_router
from api.search import router as search_router
from api.users import router as users_router
from api.portfolio import router as portfolio_router
from api.underwrite import underwrite_router, listing_router
from api.decisions import router as decisions_router
from api.strategy import router as strategy_router
from api.onboarding import router as onboarding_router
from api.investor_profile import router as investor_profile_router
from api.public_config import router as public_config_router
from api.listing_analysis import router as listing_analysis_router
from api.rent_comps import router as rent_comps_router
from api.simulation_unified import router as simulation_router
from api.market_simulation import router as market_sim_router
from api.signals import router as signals_router
from api.stubs import (
    agent_stub,
    negotiations_stub,
    reports_stub,
    social_sim_stub,
    visualization_stub,
)
from api.satei import router as satei_router
from api.price_probability import router as price_probability_router
from api.negotiation_coach import router as negotiation_coach_router
from api.buyer_simulation import router as buyer_simulation_router
from db.database import engine
from middleware.correlation import CorrelationIdMiddleware
from services.logging import setup_logging
from services.maps import MapsService
from services.redis import close_redis
from config import settings

# Shared Maps service instance (closed on shutdown)
maps_service = MapsService()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle. Schema is owned by Alembic only."""
    setup_logging(settings.log_level)
    yield
    await maps_service.close()
    await engine.dispose()
    await close_redis()


app = FastAPI(
    title="Real Estate Agentic System",
    description="AI-powered satei-to-close platform for Tokyo brokerages",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(CorrelationIdMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routers
app.include_router(properties_router, prefix="/api/properties", tags=["properties"])
app.include_router(search_router, prefix="/api/search", tags=["search"])
app.include_router(users_router, prefix="/api/users", tags=["users"])
app.include_router(portfolio_router, prefix="/api/portfolio", tags=["portfolio"])
app.include_router(underwrite_router, prefix="/api/underwrite", tags=["underwrite"])
app.include_router(listing_router, prefix="/api/listing", tags=["listing"])
app.include_router(decisions_router, prefix="/api/decisions", tags=["decisions"])
app.include_router(strategy_router, prefix="/api/strategy", tags=["strategy"])
app.include_router(onboarding_router, prefix="/api/onboarding", tags=["onboarding"])
app.include_router(investor_profile_router, prefix="/api/investor-profile", tags=["investor-profile"])
app.include_router(public_config_router, prefix="/api/config", tags=["public-config"])
app.include_router(listing_analysis_router, prefix="/api/listings", tags=["listing-analysis"])
app.include_router(rent_comps_router, prefix="/api/properties", tags=["rent-comps"])

# Stub routers — return 501 for features removed in Tokyo pivot
app.include_router(negotiations_stub, prefix="/api/negotiations", tags=["negotiations-stub"])
app.include_router(reports_stub, prefix="/api/reports", tags=["reports-stub"])
app.include_router(social_sim_stub, prefix="/api/social-sim", tags=["social-sim-stub"])
app.include_router(simulation_router, prefix="/api/simulation", tags=["simulation"])
app.include_router(market_sim_router, prefix="/api/simulation", tags=["market-simulation"])
app.include_router(signals_router, prefix="/api/signals", tags=["signals"])
app.include_router(visualization_stub, prefix="/api/visualization", tags=["visualization-stub"])
app.include_router(agent_stub, prefix="/api/agent", tags=["agent-stub"])
app.include_router(satei_router, prefix="/api/satei", tags=["satei"])
app.include_router(price_probability_router, prefix="/api/price-probability", tags=["price-probability"])
app.include_router(negotiation_coach_router, prefix="/api/negotiation-coach", tags=["negotiation-coach"])
app.include_router(buyer_simulation_router, prefix="/api/buyer-simulation", tags=["buyer-simulation"])


# WebSocket stubs — accept then close with error message
@app.websocket("/ws/negotiations/{negotiation_id}")
async def ws_negotiation_stub(websocket, negotiation_id: str):
    await websocket.accept()
    await websocket.send_json({"type": "error", "detail": "WebSocket not yet reimplemented"})
    await websocket.close()


@app.websocket("/ws/strategy/{run_id}")
async def ws_strategy_stub(websocket, run_id: str):
    await websocket.accept()
    await websocket.send_json({"type": "error", "detail": "WebSocket not yet reimplemented"})
    await websocket.close()


@app.get("/health")
async def health():
    return {"status": "ok", "version": "0.2.0"}


@app.get("/metrics")
async def get_metrics():
    from services.metrics import metrics
    return metrics.export()
