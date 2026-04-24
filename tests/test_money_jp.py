"""Unit tests for services.money_jp.MoneyJPY."""

from __future__ import annotations

import pytest

from services.money_jp import MoneyJPY


@pytest.mark.unit
class TestMoneyJPYConstruction:
    def test_accepts_nonneg_int(self):
        assert MoneyJPY(0).amount == 0
        assert MoneyJPY(198_000_000).amount == 198_000_000

    def test_rejects_float(self):
        with pytest.raises(TypeError):
            MoneyJPY(1.5)  # type: ignore[arg-type]

    def test_rejects_bool(self):
        with pytest.raises(TypeError):
            MoneyJPY(True)  # type: ignore[arg-type]

    def test_rejects_negative(self):
        with pytest.raises(ValueError):
            MoneyJPY(-1)

    def test_is_frozen(self):
        m = MoneyJPY(1000)
        with pytest.raises(AttributeError):
            m.amount = 2000  # type: ignore[misc]


@pytest.mark.unit
class TestMoneyJPYArithmetic:
    def test_add(self):
        assert (MoneyJPY(100) + MoneyJPY(250)).amount == 350

    def test_sub(self):
        assert (MoneyJPY(1000) - MoneyJPY(300)).amount == 700

    def test_scaled_rounds_to_nearest_yen(self):
        assert MoneyJPY(1000).scaled(0.333).amount == 333

    def test_add_with_non_money_returns_notimplemented(self):
        with pytest.raises(TypeError):
            MoneyJPY(100) + 50  # type: ignore[operator]


@pytest.mark.unit
class TestMoneyJPYFormatting:
    @pytest.mark.parametrize(
        "yen,expected",
        [
            (0, "0円"),
            (999, "999円"),
            (1_000, "1,000円"),
            (9_999, "9,999円"),
            (10_000, "1万円"),
            (12_000, "1万2,000円"),
            (1_980_000, "198万円"),
            (1_985_000, "198万5,000円"),
            (100_000_000, "1億円"),
            (198_000_000, "1億9,800万円"),
            (198_005_000, "1億9,800万5,000円"),
            (1_000_000_000, "10億円"),
        ],
    )
    def test_format_ja_examples(self, yen, expected):
        assert MoneyJPY(yen).format_ja() == expected

    def test_str_delegates_to_format_ja(self):
        assert str(MoneyJPY(198_000_000)) == "1億9,800万円"


@pytest.mark.unit
class TestMoneyJPYFactories:
    def test_from_man(self):
        assert MoneyJPY.from_man(198).amount == 1_980_000

    def test_from_oku(self):
        assert MoneyJPY.from_oku(1.98).amount == 198_000_000

    def test_roundtrip_via_man(self):
        m = MoneyJPY(1_980_000)
        assert MoneyJPY.from_man(m.as_man()).amount == 1_980_000

    def test_roundtrip_via_oku(self):
        m = MoneyJPY(198_000_000)
        assert MoneyJPY.from_oku(m.as_oku()).amount == 198_000_000


@pytest.mark.unit
def test_precision_past_float_exact_range():
    """The whole point of integer yen: preserve values Float cannot.

    float64 is exact for integers up to 2^53 (9,007,199,254,740,992). Past
    that, consecutive integers collide. Storing yen as int preserves them.
    """
    big = 2**53 + 1
    assert MoneyJPY(big).amount == big
    assert float(big) == float(big - 1)  # float collapses the two values
