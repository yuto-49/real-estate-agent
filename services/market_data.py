"""Market data service — thin wrapper delegating to the configured provider."""

from services.market_data_provider import MarketDataFactory, MarketDataProvider


class MarketDataService:
    def __init__(self, provider: MarketDataProvider | None = None):
        self._provider = provider or MarketDataFactory.create()

    async def get_local_stats(self, zip_code: str, radius_miles: int = 10) -> dict:
        return await self._provider.get_local_stats(zip_code, radius_miles)

    async def get_active_listings(
        self,
        latitude: float,
        longitude: float,
        min_price: float | None = None,
        max_price: float | None = None,
        property_types: list[str] | None = None,
    ) -> list[dict]:
        return await self._provider.get_active_listings(
            latitude, longitude, min_price, max_price, property_types
        )

    async def get_comps(self, address: str, radius_miles: float = 1.0) -> list[dict]:
        return await self._provider.get_comps(address, radius_miles)
