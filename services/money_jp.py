"""Money values in Japanese yen.

Tokyo buyers read prices as 万円 / 億円, never as raw 円. Backend storage is
always integer yen (JPY has no minor unit) — Float is banned because it loses
precision past 2^24. Use this value object everywhere money crosses an API or
LLM boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

_MAN: Final[int] = 10_000
_OKU: Final[int] = 100_000_000


@dataclass(frozen=True, slots=True)
class MoneyJPY:
    amount: int  # integer yen

    def __post_init__(self) -> None:
        if not isinstance(self.amount, int) or isinstance(self.amount, bool):
            raise TypeError(f"MoneyJPY requires int yen, got {type(self.amount).__name__}")
        if self.amount < 0:
            raise ValueError("MoneyJPY does not support negative values")

    # --- arithmetic (returns new instances; immutable) ---------------------
    def __add__(self, other: "MoneyJPY") -> "MoneyJPY":
        if not isinstance(other, MoneyJPY):
            return NotImplemented
        return MoneyJPY(self.amount + other.amount)

    def __sub__(self, other: "MoneyJPY") -> "MoneyJPY":
        if not isinstance(other, MoneyJPY):
            return NotImplemented
        return MoneyJPY(self.amount - other.amount)

    def scaled(self, ratio: float) -> "MoneyJPY":
        """Multiply by a ratio and round to the nearest yen."""
        return MoneyJPY(int(round(self.amount * ratio)))

    # --- unit conversions --------------------------------------------------
    def as_man(self) -> float:
        return self.amount / _MAN

    def as_oku(self) -> float:
        return self.amount / _OKU

    # --- formatting --------------------------------------------------------
    def format_ja(self) -> str:
        """Human-friendly JP string:
            ¥12,000        -> "12,000円"
            ¥1,980,000     -> "198万円"
            ¥198,000,000   -> "1億9,800万円"
            ¥1,000,000,000 -> "10億円"
        """
        yen = self.amount
        if yen < _MAN:
            return f"{yen:,}円"
        if yen < _OKU:
            man = yen // _MAN
            remainder = yen % _MAN
            if remainder:
                return f"{man:,}万{remainder:,}円"
            return f"{man:,}万円"
        oku = yen // _OKU
        remainder = yen % _OKU
        if remainder == 0:
            return f"{oku:,}億円"
        man_part = remainder // _MAN
        yen_part = remainder % _MAN
        if yen_part == 0 and man_part:
            return f"{oku:,}億{man_part:,}万円"
        if yen_part:
            return f"{oku:,}億{man_part:,}万{yen_part:,}円"
        return f"{oku:,}億円"

    def __str__(self) -> str:
        return self.format_ja()

    # --- factories ---------------------------------------------------------
    @classmethod
    def from_man(cls, man: int | float) -> "MoneyJPY":
        return cls(int(round(man * _MAN)))

    @classmethod
    def from_oku(cls, oku: int | float) -> "MoneyJPY":
        return cls(int(round(oku * _OKU)))
