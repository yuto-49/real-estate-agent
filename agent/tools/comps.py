"""Comparable sales tool handler."""

from services.market_data import MarketDataService


async def get_comps(
    market_data: MarketDataService,
    address: str,
    radius_miles: float = 1.0,
    **_kwargs,
) -> dict:
    """Get comparable recent sales near an address."""
    comps = await market_data.get_comps(address, radius_miles)
    return {
        "address": address,
        "radius_miles": radius_miles,
        "comps": comps,
        "count": len(comps),
    }
