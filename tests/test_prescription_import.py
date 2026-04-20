"""Tests for app.services.prescription_import — pure parsing functions."""

from datetime import date

from app.models.payment import PrescriptionCategory
from app.services.prescription_import import (
    _categorize_item,
    _parse_amount,
    _extract_vs,
    _extract_space_number,
    _extract_section_and_unit,
    _extract_space_type,
    _extract_owner_name,
    _extract_valid_from,
)


# ---------------------------------------------------------------------------
# _categorize_item
# ---------------------------------------------------------------------------

class TestCategorizeItem:
    def test_fond_oprav(self):
        assert _categorize_item("Fond oprav") == PrescriptionCategory.FOND_OPRAV

    def test_fond_oprav_case(self):
        assert _categorize_item("FOND OPRAV") == PrescriptionCategory.FOND_OPRAV

    def test_vodne(self):
        assert _categorize_item("Vodné a stočné") == PrescriptionCategory.SLUZBY

    def test_vytah(self):
        assert _categorize_item("Výtah - servis") == PrescriptionCategory.SLUZBY

    def test_uklid(self):
        assert _categorize_item("Úklid společných prostor") == PrescriptionCategory.SLUZBY

    def test_komin(self):
        assert _categorize_item("Komín - revize") == PrescriptionCategory.SLUZBY

    def test_elektrina(self):
        assert _categorize_item("Elektřina společná") == PrescriptionCategory.SLUZBY

    def test_odpad(self):
        assert _categorize_item("Odpad komunální") == PrescriptionCategory.SLUZBY

    def test_provozni_default(self):
        assert _categorize_item("Pojištění domu") == PrescriptionCategory.PROVOZNI

    def test_provozni_unknown(self):
        assert _categorize_item("Správa domu") == PrescriptionCategory.PROVOZNI

    def test_empty(self):
        assert _categorize_item("") == PrescriptionCategory.PROVOZNI


# ---------------------------------------------------------------------------
# _parse_amount
# ---------------------------------------------------------------------------

class TestParseAmount:
    def test_simple(self):
        assert _parse_amount("264") == 264.0

    def test_with_spaces(self):
        assert _parse_amount("1 438") == 1438.0

    def test_nbsp(self):
        assert _parse_amount("1\xa0438") == 1438.0

    def test_zero(self):
        assert _parse_amount("0") == 0.0

    def test_empty(self):
        assert _parse_amount("") == 0.0

    def test_whitespace(self):
        assert _parse_amount("  ") == 0.0

    def test_invalid(self):
        assert _parse_amount("abc") == 0.0

    def test_large(self):
        assert _parse_amount("12 345") == 12345.0

    def test_decimal(self):
        assert _parse_amount("1234.5") == 1234.5


# ---------------------------------------------------------------------------
# _extract_vs
# ---------------------------------------------------------------------------

class TestExtractVs:
    def test_found(self):
        assert _extract_vs("Variabilní symbol: 1234567") == "1234567"

    def test_with_context(self):
        text = "Nějaký text\nVariabilní symbol: 9876\nDalší text"
        assert _extract_vs(text) == "9876"

    def test_not_found(self):
        assert _extract_vs("Žádný symbol tady") is None

    def test_empty(self):
        assert _extract_vs("") is None


# ---------------------------------------------------------------------------
# _extract_space_number
# ---------------------------------------------------------------------------

class TestExtractSpaceNumber:
    def test_found(self):
        assert _extract_space_number("Číslo prostoru: 42") == 42

    def test_not_found(self):
        assert _extract_space_number("Žádné číslo") is None

    def test_empty(self):
        assert _extract_space_number("") is None


# ---------------------------------------------------------------------------
# _extract_section_and_unit
# ---------------------------------------------------------------------------

class TestExtractSectionAndUnit:
    def test_found(self):
        assert _extract_section_and_unit("Ulice 123\nA 111") == ("A", "111")

    def test_section_b(self):
        assert _extract_section_and_unit("B 205") == ("B", "205")

    def test_not_found(self):
        assert _extract_section_and_unit("Žádná sekce") == (None, None)

    def test_empty(self):
        assert _extract_section_and_unit("") == (None, None)

    def test_multiline(self):
        text = "Adresa domu\nUlice 1098\nC 301"
        assert _extract_section_and_unit(text) == ("C", "301")


# ---------------------------------------------------------------------------
# _extract_space_type
# ---------------------------------------------------------------------------

class TestExtractSpaceType:
    def test_found(self):
        assert _extract_space_type("Druh jednotky: byt") == "byt"

    def test_with_newline(self):
        assert _extract_space_type("Druh jednotky: nebytový prostor\nDalší") == "nebytový prostor"

    def test_not_found(self):
        assert _extract_space_type("Něco jiného") is None

    def test_empty(self):
        assert _extract_space_type("") is None


# ---------------------------------------------------------------------------
# _extract_owner_name
# ---------------------------------------------------------------------------

class TestExtractOwnerName:
    def test_single(self):
        text = "Údaje o vlastníkovi:\nNovák Jan"
        assert _extract_owner_name(text) == "Novák Jan"

    def test_multiple(self):
        text = "Údaje o vlastníkovi:\nNovák Jan\nNováková Marie"
        assert _extract_owner_name(text) == "Novák Jan, Nováková Marie"

    def test_not_found(self):
        assert _extract_owner_name("Něco jiného") is None

    def test_empty_value(self):
        assert _extract_owner_name("Údaje o vlastníkovi:\n") is None

    def test_with_context(self):
        text = "Typ: SJM\nÚdaje o vlastníkovi:\nSvoboda Petr"
        assert _extract_owner_name(text) == "Svoboda Petr"


# ---------------------------------------------------------------------------
# _extract_valid_from
# ---------------------------------------------------------------------------

class TestExtractValidFrom:
    def test_january(self):
        text = "EVIDENČNÍ LIST platný od 1. ledna 2026"
        assert _extract_valid_from(text) == date(2026, 1, 1)

    def test_september(self):
        text = "EVIDENČNÍ LIST platný od 15. září 2025"
        assert _extract_valid_from(text) == date(2025, 9, 15)

    def test_december(self):
        text = "EVIDENČNÍ LIST platný od 1. prosince 2024"
        assert _extract_valid_from(text) == date(2024, 12, 1)

    def test_all_months(self):
        months = [
            ("ledna", 1), ("února", 2), ("března", 3), ("dubna", 4),
            ("května", 5), ("června", 6), ("července", 7), ("srpna", 8),
            ("září", 9), ("října", 10), ("listopadu", 11), ("prosince", 12),
        ]
        for name, num in months:
            text = f"EVIDENČNÍ LIST platný od 1. {name} 2026"
            result = _extract_valid_from(text)
            assert result is not None, f"Failed for {name}"
            assert result.month == num, f"Expected month {num} for {name}, got {result.month}"

    def test_not_found(self):
        assert _extract_valid_from("Něco jiného") is None

    def test_empty(self):
        assert _extract_valid_from("") is None

    def test_invalid_month(self):
        text = "EVIDENČNÍ LIST platný od 1. foobar 2026"
        assert _extract_valid_from(text) is None
