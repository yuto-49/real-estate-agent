"""FastAPI entry point for the Real Estate Agentic System.

Scope (post-pivot): Tokyo workforce-housing investor analytics. The buyer/
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
    description="Tokyo workforce-housing investor analytics platform",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(CorrelationIdMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
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


@app.get("/health")
async def health():
    return {"status": "ok", "version": "0.2.0"}


@app.get("/metrics")
async def get_metrics():
    from services.metrics import metrics
    return metrics.export()
