"""Tests for app.services.bank_import — Fio CSV parsing functions."""

from datetime import date

from app.services.bank_import import (
    _parse_date,
    _parse_amount,
    _extract_metadata,
    parse_fio_csv,
)


# ---------------------------------------------------------------------------
# _parse_date
# ---------------------------------------------------------------------------

class TestParseDate:
    def test_valid(self):
        assert _parse_date("15.03.2026") == date(2026, 3, 15)

    def test_with_spaces(self):
        assert _parse_date("  01.01.2025  ") == date(2025, 1, 1)

    def test_invalid(self):
        assert _parse_date("not-a-date") is None

    def test_empty(self):
        assert _parse_date("") is None

    def test_wrong_format(self):
        assert _parse_date("2026-03-15") is None


# ---------------------------------------------------------------------------
# _parse_amount
# ---------------------------------------------------------------------------

class TestParseAmount:
    def test_integer(self):
        assert _parse_amount("1234") == 1234.0

    def test_decimal_comma(self):
        assert _parse_amount("1234,56") == 1234.56

    def test_negative(self):
        assert _parse_amount("-5000") == -5000.0

    def test_negative_decimal(self):
        assert _parse_amount("-1507224") == -1507224.0

    def test_nbsp(self):
        assert _parse_amount("919\xa0732,3") == 919732.3

    def test_spaces(self):
        assert _parse_amount("847 255,31") == 847255.31

    def test_empty(self):
        assert _parse_amount("") == 0.0

    def test_invalid(self):
        assert _parse_amount("abc") == 0.0

    def test_positive_sign(self):
        assert _parse_amount("+919732,3") == 919732.3


# ---------------------------------------------------------------------------
# _extract_metadata
# ---------------------------------------------------------------------------

class TestExtractMetadata:
    def test_full_header(self):
        lines = [
            '"Výpis č. 1/2026 z účtu ""2900708337/2010"""',
            '"Období: 01.01.2026 - 31.01.2026"',
            '"Počáteční stav účtu k 01.01.2026: 847255,31 CZK"',
            '"Koncový stav účtu k 31.01.2026: 259763,61 CZK"',
            '"Suma příjmů: +919732,3 CZK"',
            '"Suma výdajů: -1507224 CZK"',
            "",
            "",
            "",
        ]
        meta = _extract_metadata(lines)
        assert meta["bank_account"] == "2900708337/2010"
        assert meta["period_from"] == date(2026, 1, 1)
        assert meta["period_to"] == date(2026, 1, 31)
        assert meta["opening_balance"] == 847255.31
        assert meta["closing_balance"] == 259763.61
        assert meta["total_income"] == 919732.3
        assert meta["total_expense"] == 1507224.0

    def test_empty_lines(self):
        meta = _extract_metadata([])
        assert meta["bank_account"] is None
        assert meta["period_from"] is None

    def test_partial_header(self):
        lines = [
            '"Období: 01.06.2025 - 30.06.2025"',
        ]
        meta = _extract_metadata(lines)
        assert meta["period_from"] == date(2025, 6, 1)
        assert meta["period_to"] == date(2025, 6, 30)
        assert meta["bank_account"] is None


# ---------------------------------------------------------------------------
# parse_fio_csv (full pipeline)
# ---------------------------------------------------------------------------

def _make_fio_csv(transactions_csv: str = "", account: str = "2900708337/2010") -> bytes:
    """Build a minimal Fio CSV file as bytes."""
    header = f'''"Výpis č. 1/2026 z účtu ""{account}"""
"Období: 01.01.2026 - 31.01.2026"
"Počáteční stav účtu k 01.01.2026: 100000,00 CZK"
"Koncový stav účtu k 31.01.2026: 110000,00 CZK"
"Suma příjmů: +15000,00 CZK"
"Suma výdajů: -5000,00 CZK"
""
""
""'''.strip()
    columns = '"ID operace";"Datum";"Objem";"Měna";"Protiúčet";"Název protiúčtu";"Kód banky";"Název banky";"KS";"VS";"SS";"Poznámka";"Zpráva pro příjemce";"Typ";"Provedl";"Upřesnění";"Poznámka";"BIC";"ID pokynu"'
    lines = [header, "", columns]
    if transactions_csv:
        lines.append(transactions_csv)
    return ("\n".join(lines)).encode("utf-8-sig")


class TestParseFioCsv:
    def test_basic_income(self):
        tx = '"12345";"05.01.2026";"5000,00";"CZK";"123456/0100";"Novák Jan";"0100";"KB";"0308";"1234567";"";"";"Platba za leden";"Bezhotovostní příjem";"";"";"";"";"999"'
        result = parse_fio_csv(_make_fio_csv(tx), "test.csv")
        assert len(result["errors"]) == 0
        assert len(result["transactions"]) == 1
        t = result["transactions"][0]
        assert t["operation_id"] == "12345"
        assert t["date"] == date(2026, 1, 5)
        assert t["amount"] == 5000.0
        assert t["direction"] == "income"
        assert t["vs"] == "1234567"
        assert t["counter_account_name"] == "Novák Jan"

    def test_expense(self):
        tx = '"99999";"10.01.2026";"-3000,00";"CZK";"9999/0800";"ČEZ";"0800";"ČSOB";"";"";"";"";"Faktura";"Bezhotovostní platba";"";"";"";"";"888"'
        result = parse_fio_csv(_make_fio_csv(tx), "test.csv")
        assert len(result["transactions"]) == 1
        t = result["transactions"][0]
        assert t["direction"] == "expense"
        assert t["amount"] == 3000.0
        assert t["vs"] is None

    def test_zero_vs_becomes_none(self):
        tx = '"11111";"01.01.2026";"1000,00";"CZK";"";"";"";"";"";"";"";"";"";"";"";"";"";"";"111"'
        result = parse_fio_csv(_make_fio_csv(tx), "test.csv")
        assert result["transactions"][0]["vs"] is None

    def test_empty_vs_becomes_none(self):
        tx = '"11111";"01.01.2026";"1000,00";"CZK";"";"";"";"";"";"";"";"";"";"";"";"";"";"";"111"'
        result = parse_fio_csv(_make_fio_csv(tx), "test.csv")
        assert result["transactions"][0]["vs"] is None

    def test_too_short_file(self):
        result = parse_fio_csv(b"too short", "bad.csv")
        assert len(result["errors"]) > 0
        assert len(result["transactions"]) == 0

    def test_metadata_parsed(self):
        result = parse_fio_csv(_make_fio_csv(), "test.csv")
        meta = result["metadata"]
        assert meta["bank_account"] == "2900708337/2010"
        assert meta["period_from"] == date(2026, 1, 1)

    def test_multiple_transactions(self):
        tx1 = '"10001";"01.01.2026";"5000,00";"CZK";"";"";"";"";"";"";"";"";"";"";"";"";"";"";"1"'
        tx2 = '"10002";"02.01.2026";"3000,00";"CZK";"";"";"";"";"";"";"";"";"";"";"";"";"";"";"2"'
        result = parse_fio_csv(_make_fio_csv(f"{tx1}\n{tx2}"), "test.csv")
        assert len(result["transactions"]) == 2

    def test_bom_handling(self):
        content = _make_fio_csv()
        assert content[:3] == b"\xef\xbb\xbf"  # UTF-8 BOM
        result = parse_fio_csv(content, "test.csv")
        assert "errors" in result
