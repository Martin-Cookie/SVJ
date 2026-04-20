"""Tests for app.utils — flash_from_params and other utility functions."""
import time
from pathlib import Path
from types import SimpleNamespace

from app.utils import (
    flash_from_params, strip_diacritics, fmt_num, is_valid_email,
    compute_eta, build_wizard_steps, build_import_wizard,
    build_name_with_titles, render_email_template, is_safe_path,
    encode_smtp_password, decode_smtp_password,
)


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


# ---------------------------------------------------------------------------
# compute_eta
# ---------------------------------------------------------------------------

class TestComputeEta:
    def test_zero_total(self):
        result = compute_eta(0, 0, time.monotonic())
        assert result["pct"] == 0

    def test_half_done(self):
        started = time.monotonic() - 10  # 10s ago
        result = compute_eta(50, 100, started)
        assert result["pct"] == 50

    def test_complete(self):
        started = time.monotonic() - 5
        result = compute_eta(100, 100, started)
        assert result["pct"] == 100

    def test_eta_text(self):
        started = time.monotonic() - 10
        result = compute_eta(50, 100, started)
        # ETA should be ~10s
        assert result["eta"] != ""


# ---------------------------------------------------------------------------
# build_wizard_steps
# ---------------------------------------------------------------------------

class TestBuildWizardSteps:
    def test_first_step_active(self):
        defs = [{"label": "A"}, {"label": "B"}, {"label": "C"}]
        steps = build_wizard_steps(defs, current_step=1, max_done=0)
        assert steps[0]["status"] == "active"
        assert steps[1]["status"] == "pending"
        assert steps[2]["status"] == "pending"

    def test_second_step_active(self):
        defs = [{"label": "A"}, {"label": "B"}, {"label": "C"}]
        steps = build_wizard_steps(defs, current_step=2, max_done=1)
        assert steps[0]["status"] == "done"
        assert steps[1]["status"] == "active"
        assert steps[2]["status"] == "pending"

    def test_all_done(self):
        defs = [{"label": "A"}, {"label": "B"}]
        steps = build_wizard_steps(defs, current_step=2, max_done=2)
        assert steps[0]["status"] == "done"
        assert steps[1]["status"] == "done"

    def test_sending_step(self):
        defs = [{"label": "A"}, {"label": "B"}]
        steps = build_wizard_steps(defs, current_step=2, max_done=1, sending_step=2)
        assert steps[1]["status"] == "sending"

    def test_labels_preserved(self):
        defs = [{"label": "Upload"}, {"label": "Preview"}]
        steps = build_wizard_steps(defs, current_step=1, max_done=0)
        assert steps[0]["label"] == "Upload"
        assert steps[1]["label"] == "Preview"


# ---------------------------------------------------------------------------
# build_import_wizard
# ---------------------------------------------------------------------------

class TestBuildImportWizard:
    def test_step_1(self):
        result = build_import_wizard(1)
        assert result["wizard_current"] == 1
        assert result["wizard_total"] == 4
        assert len(result["wizard_steps"]) == 4
        assert result["wizard_steps"][0]["status"] == "active"

    def test_step_4(self):
        result = build_import_wizard(4)
        assert result["wizard_current"] == 4
        # First 3 should be done
        for i in range(3):
            assert result["wizard_steps"][i]["status"] == "done"


# ---------------------------------------------------------------------------
# build_name_with_titles
# ---------------------------------------------------------------------------

class TestBuildNameWithTitles:
    def test_full(self):
        assert build_name_with_titles("Ing.", "Jan", "Novák") == "Ing. Novák Jan"

    def test_no_title(self):
        assert build_name_with_titles(None, "Jan", "Novák") == "Novák Jan"

    def test_no_last_name(self):
        assert build_name_with_titles(None, "Jan", None) == "Jan"

    def test_all_parts(self):
        assert build_name_with_titles("MUDr.", "Marie", "Svobodová") == "MUDr. Svobodová Marie"

    def test_empty_title(self):
        assert build_name_with_titles("", "Jan", "Novák") == "Novák Jan"


# ---------------------------------------------------------------------------
# render_email_template
# ---------------------------------------------------------------------------

class TestRenderEmailTemplate:
    def test_simple(self):
        result = render_email_template("Ahoj {{ jmeno }}!", {"jmeno": "Jan"})
        assert result == "Ahoj Jan!"

    def test_unknown_variable(self):
        result = render_email_template("{{ unknown }}", {})
        assert result == ""

    def test_multiple_vars(self):
        result = render_email_template(
            "{{ jmeno }} - {{ rok }}",
            {"jmeno": "Jan", "rok": "2026"},
        )
        assert result == "Jan - 2026"

    def test_fmt_num_filter(self):
        result = render_email_template(
            "{{ castka|fmt_num }}",
            {"castka": 12345},
        )
        assert "12 345" in result


# ---------------------------------------------------------------------------
# is_safe_path
# ---------------------------------------------------------------------------

class TestIsSafePath:
    def test_valid_path(self, tmp_path):
        allowed = tmp_path / "uploads"
        allowed.mkdir()
        f = allowed / "test.txt"
        f.touch()
        assert is_safe_path(f, allowed) is True

    def test_traversal(self, tmp_path):
        allowed = tmp_path / "uploads"
        allowed.mkdir()
        evil = tmp_path / "secret.txt"
        evil.touch()
        assert is_safe_path(evil, allowed) is False

    def test_dotdot(self, tmp_path):
        allowed = tmp_path / "uploads"
        allowed.mkdir()
        traversal = allowed / ".." / "secret.txt"
        assert is_safe_path(traversal, allowed) is False

    def test_multiple_allowed(self, tmp_path):
        dir1 = tmp_path / "dir1"
        dir2 = tmp_path / "dir2"
        dir1.mkdir()
        dir2.mkdir()
        f = dir2 / "test.txt"
        f.touch()
        assert is_safe_path(f, dir1, dir2) is True


# ---------------------------------------------------------------------------
# encode/decode_smtp_password
# ---------------------------------------------------------------------------

class TestSmtpPassword:
    def test_roundtrip(self):
        password = "tajné heslo 123!"
        encoded = encode_smtp_password(password)
        assert encoded != password
        decoded = decode_smtp_password(encoded)
        assert decoded == password

    def test_empty(self):
        assert decode_smtp_password(encode_smtp_password("")) == ""

    def test_unicode(self):
        password = "čeština ěšč"
        assert decode_smtp_password(encode_smtp_password(password)) == password
