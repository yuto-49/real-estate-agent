"""MLIT reinfolib (不動産情報ライブラリ) provider — mock reads CSV fixtures."""

from __future__ import annotations

import csv
import re
from pathlib import Path
from statistics import median
from typing import Protocol, runtime_checkable

_FIXTURES_DIR = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "tokyo" / "mlit_transactions"

# 建築年 patterns: "平成15年" → 2003, "昭和53年" → 1978, "令和2年" → 2020
_ERA_MAP = {"明治": 1868, "大正": 1912, "昭和": 1926, "平成": 1989, "令和": 2019}
_ERA_RE = re.compile(r"^(明治|大正|昭和|平成|令和)(\d+)年$")


def _parse_era_year(text: str) -> int | None:
    m = _ERA_RE.match(text.strip())
    if not m:
        return None
    era, offset = m.group(1), int(m.group(2))
    return _ERA_MAP[era] + offset - 1


def _safe_int(v: str) -> int | None:
    v = v.strip().replace(",", "")
    return int(v) if v else None


def _safe_float(v: str) -> float | None:
    v = v.strip().replace(",", "")
    return float(v) if v else None


@runtime_checkable
class ReinfolibProvider(Protocol):
    """Protocol for MLIT transaction data access."""

    async def get_transactions(
        self,
        city_code: str | None = None,
        from_year: int | None = None,
        to_year: int | None = None,
    ) -> list[dict]: ...

    async def get_price_index(self, city_code: str) -> dict: ...


class MockReinfolibProvider:
    """Reads MLIT CSV fixture, parses numeric fields, caches on first load."""

    def __init__(self, fixtures_dir: Path = _FIXTURES_DIR) -> None:
        self._fixtures_dir = fixtures_dir
        self._cache: list[dict] | None = None

    def _load(self) -> list[dict]:
        if self._cache is not None:
            return self._cache
        rows: list[dict] = []
        for fp in sorted(self._fixtures_dir.glob("*.csv")):
            with fp.open(encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    parsed = dict(row)
                    parsed["取引価格_int"] = _safe_int(row.get("取引価格(総額)", ""))
                    parsed["面積_float"] = _safe_float(row.get("面積(㎡)", ""))
                    parsed["最寄駅距離_int"] = _safe_int(row.get("最寄駅:距離(分)", ""))
                    parsed["建築年_seireki"] = _parse_era_year(row.get("建築年", ""))
                    rows.append(parsed)
        self._cache = rows
        return rows

    async def get_transactions(
        self,
        city_code: str | None = None,
        from_year: int | None = None,
        to_year: int | None = None,
    ) -> list[dict]:
        results = self._load()
        if city_code is not None:
            results = [r for r in results if r.get("市区町村コード") == city_code]
        if from_year is not None:
            results = [r for r in results if (r.get("建築年_seireki") or 0) >= from_year]
        if to_year is not None:
            results = [r for r in results if (r.get("建築年_seireki") or 9999) <= to_year]
        return results

    async def get_price_index(self, city_code: str) -> dict:
        txns = [r for r in self._load() if r.get("市区町村コード") == city_code]
        prices = [r["取引価格_int"] for r in txns if r.get("取引価格_int") is not None]
        if not prices:
            return {"city_code": city_code, "median_price": None, "count": 0, "yoy_change": None}
        return {
            "city_code": city_code,
            "median_price": int(median(prices)),
            "count": len(prices),
            "yoy_change": None,  # placeholder — requires multi-year data
        }
