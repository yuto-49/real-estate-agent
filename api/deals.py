from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def list_deals():
    """List active and completed deals."""
    return {"deals": []}
