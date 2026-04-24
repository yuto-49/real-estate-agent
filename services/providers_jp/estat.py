"""e-Stat demographics provider — mock reads from JSON fixture."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol, runtime_checkable

_FIXTURES_DIR = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "tokyo" / "estat_demographics"


@runtime_checkable
class EstatProvider(Protocol):
    """Protocol for e-Stat census/demographics data."""

    async def get_population(self, area_code: str | None = None) -> list[dict]: ...


class MockEstatProvider:
    """Reads chome_population.json fixture, filters by area_code prefix."""

    def __init__(self, fixtures_dir: Path = _FIXTURES_DIR) -> None:
        self._fixtures_dir = fixtures_dir
        self._cache: list[dict] | None = None

    def _load(self) -> list[dict]:
        if self._cache is not None:
            return self._cache
        fp = self._fixtures_dir / "chome_population.json"
        data = json.loads(fp.read_text(encoding="utf-8"))
        self._cache = data.get("records", [])
        return self._cache

    async def get_population(self, area_code: str | None = None) -> list[dict]:
        records = self._load()
        if area_code is not None:
            records = [r for r in records if r.get("kcode", "").startswith(area_code)]
        return records
