"""FastAPI entry point for the Real Estate Agentic System."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.properties import router as properties_router
from api.offers import router as offers_router
from api.search import router as search_router
from api.deals import router as deals_router
from api.reports import router as reports_router
from api.users import router as users_router
from api.negotiations import router as negotiations_router
from api.ws import router as ws_router
from api.webhooks import router as webhooks_router
from api.agent import router as agent_router
from api.simulation import router as simulation_router
from api.batch_simulation import router as batch_simulation_router
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
    """Startup/shutdown lifecycle."""
    setup_logging(settings.log_level)
    # Auto-create any new tables (e.g. simulation_results)
    from db.models import Base as DBBase
    async with engine.begin() as conn:
        await conn.run_sync(DBBase.metadata.create_all)
    yield
    await maps_service.close()
    await engine.dispose()
    await close_redis()


app = FastAPI(
    title="Real Estate Agentic System",
    description="Full-stack real estate transaction platform with MiroFish intelligence",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(CorrelationIdMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routers
app.include_router(properties_router, prefix="/api/properties", tags=["properties"])
app.include_router(offers_router, prefix="/api/offers", tags=["offers"])
app.include_router(search_router, prefix="/api/search", tags=["search"])
app.include_router(deals_router, prefix="/api/deals", tags=["deals"])
app.include_router(reports_router, prefix="/api/reports", tags=["reports"])
app.include_router(users_router, prefix="/api/users", tags=["users"])
app.include_router(negotiations_router, prefix="/api/negotiations", tags=["negotiations"])
app.include_router(ws_router, prefix="/ws", tags=["websocket"])
app.include_router(webhooks_router, prefix="/api/webhooks", tags=["webhooks"])
app.include_router(agent_router, prefix="/api/agent", tags=["agent"])
app.include_router(simulation_router, prefix="/api/simulation", tags=["simulation"])
app.include_router(batch_simulation_router, prefix="/api/simulation", tags=["batch-simulation"])


@app.get("/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}


@app.get("/metrics")
async def get_metrics():
    from services.metrics import metrics
    return metrics.export()
