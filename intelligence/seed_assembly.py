"""Seed Assembly Service — the bridge between the transaction platform and MiroFish.

Integrates GeohashCache for Maps caching and MarketDataProvider pattern.
"""

import hashlib
import json
from typing import Any

from services.geocache import GeohashCache
from services.maps import MapsService
from services.market_data import MarketDataService


class SeedAssemblyService:
    """Compiles a personalized seed document for MiroFish."""

    def __init__(
        self,
        maps: MapsService,
        market: MarketDataService,
        db: Any,
        geocache: GeohashCache | None = None,
    ):
        self.maps = maps
        self.market = market
        self.db = db
        self.geocache = geocache
        # If geocache is available and maps doesn't have one, inject it
        if geocache and not maps.geocache:
            maps.geocache = geocache

    async def build_seed(
        self,
        user_id: str,
        location_overrides: dict | None = None,
    ) -> str:
        """Assemble a 5-section seed document from live data sources.

        Args:
            user_id: The user profile to base the seed on.
            location_overrides: Optional dict with keys like zip_code, latitude,
                longitude, min_price, max_price, property_types to override
                the user profile values (e.g. when analyzing a specific location
                from the search page).
        """
        user = await self._get_user(user_id)

        # Apply location overrides from search context
        overrides = location_overrides or {}
        if overrides.get("zip_code"):
            user["zip_code"] = overrides["zip_code"]
        if overrides.get("latitude") is not None:
            user["latitude"] = overrides["latitude"]
        if overrides.get("longitude") is not None:
            user["longitude"] = overrides["longitude"]
        if overrides.get("min_price") is not None:
            user["budget_min"] = overrides["min_price"]
        if overrides.get("max_price") is not None:
            user["budget_max"] = overrides["max_price"]
        if overrides.get("property_types"):
            user["preferred_types"] = overrides["property_types"]

        # Section 1: Investor Profile
        profile_section = self._format_profile(user)

        # Section 2: Local Market Context (uses provider pattern)
        market_data = await self.market.get_local_stats(
            zip_code=user.get("zip_code", "60601"),
            radius_miles=user.get("search_radius", 10),
        )
        market_section = self._format_market(market_data)

        # Section 3: Investment Decision Framework
        framework_section = self._load_template("decision_framework.md")

        # Section 4: Active Listings (with cached neighborhood data)
        listings = await self.market.get_active_listings(
            latitude=user.get("latitude", 0),
            longitude=user.get("longitude", 0),
            min_price=user.get("budget_min"),
            max_price=(user.get("budget_max") or 0) * 1.15 if user.get("budget_max") else None,
            property_types=user.get("preferred_types"),
        )

        # Enrich with neighborhood data (uses geocache if available)
        for listing in listings[:15]:  # Cap enrichment to 15 listings
            try:
                listing["neighborhood"] = await self.maps.analyze_neighborhood(
                    listing["address"],
                    radius=1500,
                    categories=["school", "transit_station", "restaurant", "park"],
                )
            except Exception:
                listing["neighborhood"] = {"error": "enrichment_failed"}
        listings_section = self._format_listings(listings)

        # Section 5: Platform Rules
        rules_section = self._load_template("platform_rules.md")

        seed = "\n\n".join([
            profile_section,
            market_section,
            framework_section,
            listings_section,
            rules_section,
        ])

        return seed

    async def _get_user(self, user_id: str) -> dict:
        """Get user profile — supports both ORM objects and dict-like DB access."""
        if hasattr(self.db, "get_user_profile"):
            user = await self.db.get_user_profile(user_id)
            return {
                "budget_min": user.budget_min,
                "budget_max": user.budget_max,
                "life_stage": str(user.life_stage) if user.life_stage else "unknown",
                "investment_goals": user.investment_goals or {},
                "risk_tolerance": str(user.risk_tolerance) if user.risk_tolerance else "moderate",
                "timeline_days": user.timeline_days or 90,
                "zip_code": user.zip_code or "60601",
                "search_radius": user.search_radius or 10,
                "latitude": user.latitude or 0,
                "longitude": user.longitude or 0,
                "preferred_types": user.preferred_types or [],
            }
        elif hasattr(self.db, "execute"):
            from sqlalchemy import select
            from db.models import UserProfile
            result = await self.db.execute(
                select(UserProfile).where(UserProfile.id == user_id)
            )
            user = result.scalar_one_or_none()
            if not user:
                raise ValueError(f"User {user_id} not found")
            return {
                "budget_min": user.budget_min,
                "budget_max": user.budget_max,
                "life_stage": user.life_stage.value if user.life_stage else "unknown",
                "investment_goals": user.investment_goals or {},
                "risk_tolerance": user.risk_tolerance.value if user.risk_tolerance else "moderate",
                "timeline_days": user.timeline_days or 90,
                "zip_code": user.zip_code or "60601",
                "search_radius": user.search_radius or 10,
                "latitude": user.latitude or 0,
                "longitude": user.longitude or 0,
                "preferred_types": user.preferred_types or [],
            }
        raise ValueError("No valid DB accessor provided")

    def seed_hash(self, seed_text: str) -> str:
        return hashlib.sha256(seed_text.encode()).hexdigest()[:16]

    def _format_profile(self, user: dict) -> str:
        budget_min = user.get("budget_min", 0) or 0
        budget_max = user.get("budget_max", 0) or 0
        return f"""# Investor Profile
- Budget: ${budget_min:,.0f} – ${budget_max:,.0f}
- Life Stage: {user.get('life_stage', 'unknown')}
- Investment Goals: {json.dumps(user.get('investment_goals', {}))}
- Risk Tolerance: {user.get('risk_tolerance', 'moderate')}
- Timeline: {user.get('timeline_days', 90)} days
- Location: {user.get('zip_code', '')} (radius: {user.get('search_radius', 10)} mi)
- Preferred Types: {', '.join(user.get('preferred_types', []) or ['any'])}"""

    def _format_market(self, data: dict) -> str:
        return f"""# Local Market Context
- Median Home Price: ${data.get('median_price', 0):,.0f}
- 30-Year Fixed Rate: {data.get('mortgage_rate', 0):.1f}%
- Inventory: {data.get('months_inventory', 0):.1f} months
- Median Days on Market: {data.get('days_on_market', 0)}
- Rent-vs-Buy Ratio: {data.get('rent_vs_buy', 0):.2f}
- YoY Price Change: {data.get('yoy_change', 0):.1f}%"""

    def _format_listings(self, listings: list) -> str:
        sections = ["# Active Listings"]
        for i, listing in enumerate(listings[:30], 1):
            sections.append(
                f"## Listing {i}: {listing['address']}\n"
                f"- Price: ${listing.get('price', 0):,.0f}\n"
                f"- Beds/Baths: {listing.get('bedrooms', '?')}/{listing.get('bathrooms', '?')}\n"
                f"- Sqft: {listing.get('sqft', '?')}\n"
                f"- Type: {listing.get('property_type', '?')}\n"
                f"- Neighborhood: {json.dumps(listing.get('neighborhood', {}), indent=2)}"
            )
        return "\n\n".join(sections)

    def _load_template(self, filename: str) -> str:
        import os
        path = os.path.join(os.path.dirname(__file__), "templates", filename)
        try:
            with open(path) as f:
                return f.read()
        except FileNotFoundError:
            return f"# {filename}\n[Template not yet created]"
