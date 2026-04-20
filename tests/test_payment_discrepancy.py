"""Tests for app.services.payment_discrepancy — pure functions."""

from unittest.mock import MagicMock

from app.services.payment_discrepancy import (
    Discrepancy,
    _match_owner_by_sender,
    build_email_context,
    _fmt,
)


def _mock_owner(display_name: str, name_normalized: str, email: str = "") -> MagicMock:
    """Create a mock Owner with required attributes."""
    owner = MagicMock()
    owner.display_name = display_name
    owner.name_normalized = name_normalized
    owner.email = email
    owner.id = id(owner)
    return owner


# ---------------------------------------------------------------------------
# _fmt
# ---------------------------------------------------------------------------

class TestFmt:
    def test_zero(self):
        assert _fmt(0) == "0"

    def test_small(self):
        assert _fmt(42) == "42"

    def test_thousands(self):
        assert _fmt(1234) == "1 234"

    def test_large(self):
        assert _fmt(1234567) == "1 234 567"

    def test_none_like(self):
        assert _fmt(0.0) == "0"

    def test_negative(self):
        result = _fmt(-5000)
        assert "5" in result  # Should format the number


# ---------------------------------------------------------------------------
# _match_owner_by_sender
# ---------------------------------------------------------------------------

class TestMatchOwnerBySender:
    def test_empty_list(self):
        assert _match_owner_by_sender([], "Novák Jan") is None

    def test_single_owner(self):
        o = _mock_owner("Jan Novák", "novak jan")
        assert _match_owner_by_sender([o], "Novák Jan") is o

    def test_single_owner_ignores_sender(self):
        o = _mock_owner("Jan Novák", "novak jan")
        assert _match_owner_by_sender([o], "Svoboda Petr") is o

    def test_no_sender(self):
        o1 = _mock_owner("Jan Novák", "novak jan")
        o2 = _mock_owner("Marie Nováková", "novakova marie")
        assert _match_owner_by_sender([o1, o2], None) is o1

    def test_empty_sender(self):
        o1 = _mock_owner("Jan Novák", "novak jan")
        o2 = _mock_owner("Marie Nováková", "novakova marie")
        assert _match_owner_by_sender([o1, o2], "") is o1

    def test_two_word_match(self):
        o1 = _mock_owner("Jan Novák", "novak jan")
        o2 = _mock_owner("Marie Nováková", "novakova marie")
        result = _match_owner_by_sender([o1, o2], "Jan Novák")
        assert result is o1

    def test_surname_fallback(self):
        o1 = _mock_owner("Jan Novák", "novak jan")
        o2 = _mock_owner("Marie Nováková", "novakova marie")
        result = _match_owner_by_sender([o1, o2], "Nováková")
        assert result is o2

    def test_no_match_returns_first(self):
        o1 = _mock_owner("Jan Novák", "novak jan")
        o2 = _mock_owner("Marie Nováková", "novakova marie")
        result = _match_owner_by_sender([o1, o2], "Úplně Jiný Člověk")
        assert result is o1

    def test_owner_without_normalized(self):
        o1 = _mock_owner("Jan Novák", None)
        o2 = _mock_owner("Marie Nováková", "novakova marie")
        result = _match_owner_by_sender([o1, o2], "Nováková Marie")
        assert result is o2


# ---------------------------------------------------------------------------
# build_email_context
# ---------------------------------------------------------------------------

def _make_disc(**kwargs) -> Discrepancy:
    """Create a Discrepancy with defaults."""
    defaults = {
        "payment_id": 1,
        "payment_date": "05.01.2026",
        "payment_amount": 5000,
        "payment_vs": "1234567",
        "sender_name": "Novák Jan",
        "types": [],
        "entity_type": "unit",
        "entity_label": "Jednotka č. 5",
        "entity_vs": "7654321",
        "expected_amount": 4500,
        "recipient_name": "Jan Novák",
        "recipient_email": "novak@example.com",
    }
    defaults.update(kwargs)
    return Discrepancy(**defaults)


class TestBuildEmailContext:
    def test_basic_context(self):
        disc = _make_disc(types=["wrong_vs"])
        ctx = build_email_context(disc, "SVJ Test", "leden", 2026)
        assert ctx["jmeno"] == "Jan Novák"
        assert ctx["mesic_nazev"] == "leden"
        assert ctx["rok"] == "2026"
        assert ctx["svj_nazev"] == "SVJ Test"
        assert ctx["entita"] == "Jednotka č. 5"

    def test_wrong_vs_chyba(self):
        disc = _make_disc(types=["wrong_vs"])
        ctx = build_email_context(disc, "SVJ", "leden", 2026)
        assert len(ctx["chyby"]) == 1
        assert "Špatný variabilní symbol" in ctx["chyby"][0]
        assert "1234567" in ctx["chyby"][0]
        assert "7654321" in ctx["chyby"][0]

    def test_wrong_amount_chyba(self):
        disc = _make_disc(types=["wrong_amount"])
        ctx = build_email_context(disc, "SVJ", "leden", 2026)
        assert len(ctx["chyby"]) == 1
        assert "Nesprávná výše platby" in ctx["chyby"][0]
        assert "5 000" in ctx["chyby"][0]
        assert "4 500" in ctx["chyby"][0]

    def test_combined_chyba(self):
        disc = _make_disc(
            types=["combined"],
            allocations=[
                {"entity_label": "Jednotka č. 5", "amount": 3000, "expected": 2500},
                {"entity_label": "Prostor č. 1", "amount": 2000, "expected": 1500},
            ],
        )
        ctx = build_email_context(disc, "SVJ", "únor", 2026)
        assert len(ctx["chyby"]) == 1
        assert "Sloučená platba" in ctx["chyby"][0]
        assert "Jednotka č. 5" in ctx["chyby"][0]
        assert "Prostor č. 1" in ctx["chyby"][0]

    def test_multiple_types(self):
        disc = _make_disc(types=["wrong_vs", "wrong_amount"])
        ctx = build_email_context(disc, "SVJ", "leden", 2026)
        assert len(ctx["chyby"]) == 2

    def test_empty_vs(self):
        disc = _make_disc(types=["wrong_vs"], payment_vs="", entity_vs="")
        ctx = build_email_context(disc, "SVJ", "leden", 2026)
        assert "(prázdný)" in ctx["chyby"][0]
        assert "(neznámý)" in ctx["vs_predpisu"]

    def test_no_svj_name(self):
        disc = _make_disc(types=[])
        ctx = build_email_context(disc, "", "leden", 2026)
        assert ctx["svj_nazev"] == "SVJ"  # Fallback

    def test_formatted_amounts(self):
        disc = _make_disc(types=[], payment_amount=12345, expected_amount=11000)
        ctx = build_email_context(disc, "SVJ", "leden", 2026)
        assert ctx["castka_zaplaceno"] == "12 345"
        assert ctx["castka_predpis"] == "11 000"
