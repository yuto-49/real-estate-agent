"""Neighborhood analysis tool handler (TomTom Nearby Search)."""

from services.maps import MapsService


async def analyze_neighborhood(
    maps: MapsService,
    address: str,
    radius_meters: int = 1500,
    **_kwargs,
) -> dict:
    """Analyze a neighborhood via TomTom Nearby Search API."""
    return await maps.analyze_neighborhood(
        address=address,
        radius=radius_meters,
        categories=["school", "transit_station", "restaurant", "park"],
    )
