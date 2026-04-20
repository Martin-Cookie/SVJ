"""Tests for app.utils — flash_from_params and other utility functions."""
from types import SimpleNamespace

from app.utils import flash_from_params, strip_diacritics, fmt_num, is_valid_email


# ---------------------------------------------------------------------------
# flash_from_params
# ---------------------------------------------------------------------------

def _make_request(params: dict):
    """Create a minimal request-like object with query_params."""
    return SimpleNamespace(query_params=params)


class TestFlashFromParams:
    def test_no_flash_param(self):
        request = _make_request({})
        msg, typ = flash_from_params(request, {"ok": ("Done.", "success")})
        assert msg == ""
        assert typ == ""

    def test_unknown_code(self):
        request = _make_request({"flash": "unknown"})
        msg, typ = flash_from_params(request, {"ok": ("Done.", "success")})
        assert msg == ""
        assert typ == ""

    def test_simple_match(self):
        request = _make_request({"flash": "ok"})
        msg, typ = flash_from_params(request, {"ok": ("Operace úspěšná.", "success")})
        assert msg == "Operace úspěšná."
        assert typ == "success"

    def test_placeholder_from_query(self):
        request = _make_request({"flash": "sent", "count": "5"})
        msg, typ = flash_from_params(request, {
            "sent": ("Odesláno {count} emailů.", "success"),
        })
        assert msg == "Odesláno 5 emailů."
        assert typ == "success"

    def test_placeholder_from_extra_ctx(self):
        request = _make_request({"flash": "ok"})
        msg, typ = flash_from_params(request, {
            "ok": ("Hotovo: {detail}.", "success"),
        }, detail="vše v pořádku")
        assert msg == "Hotovo: vše v pořádku."
        assert typ == "success"

    def test_query_param_overrides_default(self):
        request = _make_request({"flash": "ok", "msg": "Custom message"})
        msg, typ = flash_from_params(request, {
            "ok": ("{msg}", "success"),
        }, msg="Default message")
        assert msg == "Custom message"

    def test_empty_query_param_uses_default(self):
        request = _make_request({"flash": "ok", "msg": ""})
        msg, typ = flash_from_params(request, {
            "ok": ("{msg}", "success"),
        }, msg="Default message")
        assert msg == "Default message"

    def test_missing_placeholder_keeps_template(self):
        request = _make_request({"flash": "ok"})
        msg, typ = flash_from_params(request, {
            "ok": ("Missing: {nonexistent}.", "success"),
        })
        assert msg == "Missing: {nonexistent}."


# ---------------------------------------------------------------------------
# strip_diacritics
# ---------------------------------------------------------------------------

class TestStripDiacritics:
    def test_czech(self):
        assert strip_diacritics("Příliš žluťoučký") == "prilis zlutoucky"

    def test_empty(self):
        assert strip_diacritics("") == ""

    def test_no_diacritics(self):
        assert strip_diacritics("Hello World") == "hello world"


# ---------------------------------------------------------------------------
# fmt_num
# ---------------------------------------------------------------------------

class TestFmtNum:
    def test_integer(self):
        assert fmt_num(12345) == "12 345"

    def test_float(self):
        result = fmt_num(12345.67)
        assert "12 345" in result

    def test_zero(self):
        assert fmt_num(0) == "0"

    def test_none(self):
        assert fmt_num(None) == "—"


# ---------------------------------------------------------------------------
# is_valid_email
# ---------------------------------------------------------------------------

class TestIsValidEmail:
    def test_valid(self):
        assert is_valid_email("user@example.com") is True

    def test_invalid(self):
        assert is_valid_email("not-an-email") is False

    def test_empty(self):
        assert is_valid_email("") is False
