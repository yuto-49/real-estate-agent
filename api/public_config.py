"""Public runtime configuration for the frontend."""

from fastapi import APIRouter

from api.schemas import PublicRuntimeConfigResponse
from config import settings

router = APIRouter()


@router.get("/public", response_model=PublicRuntimeConfigResponse)
async def get_public_runtime_config() -> PublicRuntimeConfigResponse:
    """Expose only browser-safe runtime configuration."""
    return PublicRuntimeConfigResponse(**settings.public_runtime_config())
