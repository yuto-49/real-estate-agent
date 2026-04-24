"""Offline Japanese address normalization.

Collapses variant inputs to a single canonical form so lookups and vector-
search metadata filters hit one key. Pure Python, no network, no external
data files — enough for the 東京都23区 flow in Phase 0/1.

Swap point for Phase 3: replace `OfflineTokyoNormalizer` with a Geolonia- or
Google-backed impl via the `AddressNormalizer` Protocol. Callers depend on
the Protocol.

Limitations (documented so they don't get forgotten):
  - Ward code table is 東京都23区 only; non-Tokyo inputs return
    shichouson_code=None.
  - Does not resolve lat/lng (geocoding concern).
  - Does not handle 大字/字, 丁目なし streets, or historical address
    changes — those need real Geolonia tables.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Final, Protocol

# ---------------------------------------------------------------------------
# Kanji numeral helpers. Applied ONLY to chome ordinal tokens — never to the
# whole string (otherwise 六本木 silently becomes "6本木").
# ---------------------------------------------------------------------------

_KANJI_ORDINAL_CHARS: Final = "一二三四五六七八九十"
_KANJI_TO_INT: Final = {ch: i + 1 for i, ch in enumerate("一二三四五六七八九")}
_KANJI_TO_INT["十"] = 10
_INT_TO_KANJI: Final = "〇一二三四五六七八九"


def _kanji_ordinal_to_int(token: str) -> int | None:
    if not token or not all(ch in _KANJI_ORDINAL_CHARS for ch in token):
        return None
    if len(token) == 1:
        return _KANJI_TO_INT[token]
    if token == "十":
        return 10
    if token.startswith("十") and len(token) == 2:
        return 10 + _KANJI_TO_INT[token[1]]
    if token.endswith("十") and len(token) == 2:
        return _KANJI_TO_INT[token[0]] * 10
    if "十" in token and len(token) == 3:
        a, _, b = token
        return _KANJI_TO_INT[a] * 10 + _KANJI_TO_INT[b]
    return None


def _int_to_kanji_ordinal(n: int) -> str:
    if n < 0:
        raise ValueError("negative ordinal")
    if n < 10:
        return _INT_TO_KANJI[n]
    if n == 10:
        return "十"
    if n < 20:
        return "十" + _INT_TO_KANJI[n - 10]
    tens, ones = divmod(n, 10)
    tens_part = _INT_TO_KANJI[tens] + "十"
    return tens_part + (_INT_TO_KANJI[ones] if ones else "")


# ---------------------------------------------------------------------------
# Prefecture + ward tables.
# ---------------------------------------------------------------------------

_PREFECTURES: Final[tuple[str, ...]] = (
    # Longest-first so "東京都" matches before any "東京" prefix variant.
    "北海道", "東京都", "京都府", "大阪府",
    "青森県", "岩手県", "宮城県", "秋田県", "山形県", "福島県",
    "茨城県", "栃木県", "群馬県", "埼玉県", "千葉県", "神奈川県",
    "新潟県", "富山県", "石川県", "福井県", "山梨県", "長野県", "岐阜県",
    "静岡県", "愛知県", "三重県", "滋賀県", "兵庫県", "奈良県", "和歌山県",
    "鳥取県", "島根県", "岡山県", "広島県", "山口県",
    "徳島県", "香川県", "愛媛県", "高知県",
    "福岡県", "佐賀県", "長崎県", "熊本県", "大分県", "宮崎県", "鹿児島県", "沖縄県",
)

TOKYO23_WARD_CODES: Final[dict[str, str]] = {
    "千代田区": "13101", "中央区": "13102", "港区": "13103", "新宿区": "13104",
    "文京区": "13105", "台東区": "13106", "墨田区": "13107", "江東区": "13108",
    "品川区": "13109", "目黒区": "13110", "大田区": "13111", "世田谷区": "13112",
    "渋谷区": "13113", "中野区": "13114", "杉並区": "13115", "豊島区": "13116",
    "北区": "13117", "荒川区": "13118", "板橋区": "13119", "練馬区": "13120",
    "足立区": "13121", "葛飾区": "13122", "江戸川区": "13123",
}
# Longest-first to avoid "北区" partial-matching inside e.g. "江北区" (none
# exist in reality, but the principle keeps us honest).
_WARDS_SORTED: Final = tuple(sorted(TOKYO23_WARD_CODES, key=len, reverse=True))


# ---------------------------------------------------------------------------
# Result type + Protocol
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class NormalizedAddress:
    todoufuken: str | None
    shikuchouson: str | None
    chome: str | None             # canonical: "六本木六丁目" (area + 漢数字 + 丁目)
    banchi: str | None
    go: str | None
    building: str | None
    todoufuken_code: str | None   # "13" for 東京都
    shichouson_code: str | None   # "13103" for 港区

    def canonical(self) -> str:
        parts = [p for p in (self.todoufuken, self.shikuchouson, self.chome) if p]
        tail = [t for t in (self.banchi, self.go) if t]
        if tail:
            parts.append("-".join(tail))
        if self.building:
            parts.append(self.building)
        return " ".join(parts)


class AddressNormalizer(Protocol):
    def normalize(self, raw: str) -> NormalizedAddress: ...


# ---------------------------------------------------------------------------
# Offline rule-based impl
# ---------------------------------------------------------------------------


_CHOME_SUFFIX = re.compile(
    r"^(?P<area>[^\s0-9]+?)"
    rf"(?P<num>\d+|[{_KANJI_ORDINAL_CHARS}]+)丁目"
)
_CHOME_DASHED = re.compile(
    r"^(?P<area>[^\s0-9]+?)"
    r"(?P<num>\d+)"
    r"-(?P<banchi>\d+)"
    r"(?:-(?P<go>\d+))?"
    r"(?:\s+(?P<building>.+))?\s*$"
)
_BAN_GO = re.compile(
    r"(?P<banchi>\d+)(?:番地?|-)?(?P<go>\d+)?(?:号)?"
)


class OfflineTokyoNormalizer:
    """Rule-based normalizer covering 東京都23区. Non-Tokyo inputs degrade to
    (prefecture, None, None, ...) without raising — callers decide what to do.
    """

    def normalize(self, raw: str) -> NormalizedAddress:
        s = unicodedata.normalize("NFKC", raw).strip()

        prefecture = self._take_prefecture(s)
        if prefecture is not None:
            s = s[len(prefecture):]

        if prefecture and prefecture != "東京都":
            return NormalizedAddress(
                todoufuken=prefecture,
                shikuchouson=None,
                chome=None,
                banchi=None,
                go=None,
                building=s.strip() or None,
                todoufuken_code=None,
                shichouson_code=None,
            )

        ward = self._take_ward(s)
        if ward is not None:
            s = s[len(ward):]

        todoufuken = "東京都" if (prefecture == "東京都" or ward) else None
        chome, banchi, go, building = self._extract_chome_and_tail(s)

        return NormalizedAddress(
            todoufuken=todoufuken,
            shikuchouson=ward,
            chome=chome,
            banchi=banchi,
            go=go,
            building=building,
            todoufuken_code="13" if todoufuken == "東京都" else None,
            shichouson_code=TOKYO23_WARD_CODES.get(ward or "") if ward else None,
        )

    @staticmethod
    def _take_prefecture(s: str) -> str | None:
        for p in _PREFECTURES:
            if s.startswith(p):
                return p
        return None

    @staticmethod
    def _take_ward(s: str) -> str | None:
        for w in _WARDS_SORTED:
            if s.startswith(w):
                return w
        return None

    def _extract_chome_and_tail(
        self, tail: str
    ) -> tuple[str | None, str | None, str | None, str | None]:
        tail = tail.strip()
        if not tail:
            return None, None, None, None

        # Pass 1: explicit 丁目 suffix.
        m = _CHOME_SUFFIX.match(tail)
        if m:
            area = m.group("area")
            num_raw = m.group("num")
            n = int(num_raw) if num_raw.isdigit() else _kanji_ordinal_to_int(num_raw)
            if n is None:
                n = 0
            chome = f"{area}{_int_to_kanji_ordinal(n)}丁目"
            banchi, go, building = self._parse_ban_go(tail[m.end():].strip())
            return chome, banchi, go, building

        # Pass 2: area + N-M(-K) with optional trailing building.
        m = _CHOME_DASHED.match(tail)
        if m:
            area = m.group("area")
            n = int(m.group("num"))
            chome = f"{area}{_int_to_kanji_ordinal(n)}丁目"
            return chome, m.group("banchi"), m.group("go"), m.group("building")

        # Nothing matched — treat the whole remainder as building.
        return None, None, None, tail or None

    @staticmethod
    def _parse_ban_go(tail: str) -> tuple[str | None, str | None, str | None]:
        if not tail:
            return None, None, None
        m = _BAN_GO.search(tail)
        if not m:
            return None, None, tail or None
        banchi = m.group("banchi")
        go = m.group("go")
        rest = (tail[: m.start()] + tail[m.end():]).strip()
        return banchi, go, (rest or None)


_default_normalizer = OfflineTokyoNormalizer()


def normalize(raw: str) -> NormalizedAddress:
    return _default_normalizer.normalize(raw)
