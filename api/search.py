from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def search_properties(q: str = "", location: str = ""):
    """Natural language property search — routed through Buyer Agent."""
    return {"query": q, "location": location, "results": []}
