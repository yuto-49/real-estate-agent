"""Test script: Build and inspect a seed document without running MiroFish."""

import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from intelligence.seed_assembly import SeedAssemblyService
from services.maps import MapsService
from services.market_data import MarketDataService


class MockDB:
    class User:
        budget_min = 300000
        budget_max = 500000
        life_stage = "relocating"
        investment_goals = {"primary": "residence"}
        risk_tolerance = "moderate"
        timeline_days = 90
        zip_code = "60614"
        search_radius = 10
        latitude = 41.8781
        longitude = -87.6298
        preferred_types = ["sfr", "condo"]

    async def get_user_profile(self, user_id):
        return self.User()


async def main():
    service = SeedAssemblyService(
        maps=MapsService(),
        market=MarketDataService(),
        db=MockDB(),
    )
    seed = await service.build_seed("test-user")
    print("=" * 60)
    print("ASSEMBLED SEED DOCUMENT")
    print("=" * 60)
    print(seed)
    print(f"\nSeed hash: {service.seed_hash(seed)}")
    print(f"Seed length: {len(seed)} chars")


if __name__ == "__main__":
    asyncio.run(main())
