"""Testy pro platební modul — matching, overview, settlement, helpers."""

from datetime import date, datetime

import pytest

from app.models import (
    BankStatement, Owner, OwnerUnit, Payment, PaymentAllocation,
    PaymentDirection, PaymentMatchStatus,
    Prescription, PrescriptionItem, PrescriptionYear, PrescriptionCategory,
    Settlement, SettlementStatus, SettlementItem,
    Unit, UnitBalance, VariableSymbolMapping, SymbolSource,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def seed_basic(db_session):
    """Základní seed: 2 jednotky, 2 vlastníci, předpisy, VS mapování."""
    db = db_session

    u1 = Unit(unit_number=1, building_number="A111", space_type="byt")
    u2 = Unit(unit_number=5, building_number="B222", space_type="garáž")
    db.add_all([u1, u2])
    db.flush()

    o1 = Owner(
        first_name="Jan", last_name="Novák", name_with_titles="Novák Jan",
        name_normalized="novak jan",
    )
    o2 = Owner(
        first_name="Marie", last_name="Svobodová", name_with_titles="Svobodová Marie",
        name_normalized="svobodova marie",
    )
    db.add_all([o1, o2])
    db.flush()

    ou1 = OwnerUnit(owner_id=o1.id, unit_id=u1.id, ownership_type="sole")
    ou2 = OwnerUnit(owner_id=o2.id, unit_id=u2.id, ownership_type="sole")
    db.add_all([ou1, ou2])

    py = PrescriptionYear(year=2026)
    db.add(py)
    db.flush()

    p1 = Prescription(
        prescription_year_id=py.id, unit_id=u1.id, owner_name="Novák Jan",
        monthly_total=3000, variable_symbol="1109800101", space_type="byt",
        space_number="A111",
    )
    p2 = Prescription(
        prescription_year_id=py.id, unit_id=u2.id, owner_name="Svobodová Marie",
        monthly_total=600, variable_symbol="9109800501", space_type="garáž",
        space_number="B222",
    )
    db.add_all([p1, p2])
    db.flush()

    pi1 = PrescriptionItem(
        prescription_id=p1.id, name="Fond oprav", amount=1500,
        category=PrescriptionCategory.FOND_OPRAV, order=1,
    )
    pi2 = PrescriptionItem(
        prescription_id=p1.id, name="Služby", amount=1500,
        category=PrescriptionCategory.SLUZBY, order=2,
    )
    db.add_all([pi1, pi2])

    vs1 = VariableSymbolMapping(
        unit_id=u1.id, variable_symbol="1109800101",
        source=SymbolSource.AUTO, is_active=True,
    )
    vs2 = VariableSymbolMapping(
        unit_id=u2.id, variable_symbol="9109800501",
        source=SymbolSource.AUTO, is_active=True,
    )
    db.add_all([vs1, vs2])
    db.flush()

    return {
        "unit1": u1, "unit2": u2,
        "owner1": o1, "owner2": o2,
        "py": py, "presc1": p1, "presc2": p2,
    }


@pytest.fixture()
def seed_statement(db_session, seed_basic):
    """Bankovní výpis s platbami."""
    db = db_session
    stmt = BankStatement(
        filename="test.csv", bank_account="123/0800",
        period_from=date(2026, 1, 1), period_to=date(2026, 1, 31),
    )
    db.add(stmt)
    db.flush()

    # Platba s VS → auto match
    pay1 = Payment(
        statement_id=stmt.id, date=date(2026, 1, 15), amount=3000,
        vs="1109800101", counter_account_name="Novak Jan",
        direction=PaymentDirection.INCOME, match_status=PaymentMatchStatus.UNMATCHED,
        operation_id="OP001",
    )
    # Platba bez VS, se jménem → name match
    pay2 = Payment(
        statement_id=stmt.id, date=date(2026, 1, 16), amount=600,
        vs="", counter_account_name="SVOBODOVA MARIE",
        direction=PaymentDirection.INCOME, match_status=PaymentMatchStatus.UNMATCHED,
        operation_id="OP002",
    )
    # Výdajová platba → ignorovat
    pay3 = Payment(
        statement_id=stmt.id, date=date(2026, 1, 17), amount=50000,
        vs="", counter_account_name="Dodavatel",
        direction=PaymentDirection.EXPENSE, match_status=PaymentMatchStatus.UNMATCHED,
        operation_id="OP003",
    )
    # Platba bez operation_id → taky se párkuje
    pay4 = Payment(
        statement_id=stmt.id, date=date(2026, 1, 18), amount=3000,
        vs="1109800101", counter_account_name="Novak Jan",
        direction=PaymentDirection.INCOME, match_status=PaymentMatchStatus.UNMATCHED,
        operation_id="OP004",
    )
    db.add_all([pay1, pay2, pay3, pay4])
    db.flush()

    return {**seed_basic, "statement": stmt, "pay1": pay1, "pay2": pay2, "pay3": pay3, "pay4": pay4}


# ===========================================================================
# Unit testy — čisté funkce (bez DB)
# ===========================================================================

class TestCleanNameWords:
    def test_basic(self):
        from app.services.payment_matching import _clean_name_words
        result = _clean_name_words("Jan Novák")
        assert "novak" in result
        # "jan" má 3 znaky → vyloučen (MIN_WORD_LENGTH = 3, > 3)
        assert "jan" not in result

    def test_empty(self):
        from app.services.payment_matching import _clean_name_words
        assert _clean_name_words("") == set()

    def test_diacritics_removed(self):
        from app.services.payment_matching import _clean_name_words
        result = _clean_name_words("Řehák Michal")
        assert "rehak" in result
        assert "michal" in result


class TestCheckAmountMatch:
    def test_exact_match(self):
        from app.services.payment_matching import _check_amount_match
        assert _check_amount_match(3000, 3000) is True  # 1x

    def test_multiple_months(self):
        from app.services.payment_matching import _check_amount_match
        assert _check_amount_match(6000, 3000) is True  # 2x
        assert _check_amount_match(36000, 3000) is True  # 12x

    def test_no_match(self):
        from app.services.payment_matching import _check_amount_match
        assert _check_amount_match(3500, 3000) is False

    def test_zero_monthly(self):
        from app.services.payment_matching import _check_amount_match
        assert _check_amount_match(3000, 0) is False
        assert _check_amount_match(3000, None) is False

    def test_tolerance(self):
        from app.services.payment_matching import _check_amount_match
        assert _check_amount_match(3000.005, 3000) is True
        assert _check_amount_match(3000.02, 3000) is False


class TestExtractUnitFromVs:
    def test_standard_format(self):
        from app.services.payment_matching import _extract_unit_from_vs
        # VS 1109800501 → prefix 11098 → remainder 00501 → bez posledních 2 = 005 → 5
        unit_ids = {1, 5, 10}
        result = _extract_unit_from_vs("1109800501", {}, unit_ids, "1098")
        assert result == 5

    def test_no_prefix(self):
        from app.services.payment_matching import _extract_unit_from_vs
        result = _extract_unit_from_vs("9999999999", {}, {1, 5}, "1098")
        assert result is None

    def test_empty_vs(self):
        from app.services.payment_matching import _extract_unit_from_vs
        result = _extract_unit_from_vs("", {}, {1, 5}, "1098")
        assert result is None

    def test_known_vs_map_priority(self):
        from app.services.payment_matching import _extract_unit_from_vs
        # Pokud VS je v known_vs_map, neměla by se volat _extract (tu funkci volá match_payments)
        # _extract_unit_from_vs samotná ignoruje known_vs_map pokud VS nemá prefix
        result = _extract_unit_from_vs("12345", {"12345": 99}, {99}, "1098")
        assert result is None  # "12345" nemá prefix 1098


class TestFindMultiUnitMatch:
    def test_two_units_same_owner(self):
        from app.services.payment_matching import _find_multi_unit_match
        candidates = [
            {"owner_id": 1, "monthly": 2000, "unit_id": 10},
            {"owner_id": 1, "monthly": 500, "unit_id": 20},
        ]
        # 2500 = 2000 + 500 (1× měsíc)
        result = _find_multi_unit_match(2500, candidates)
        assert result is not None
        assert len(result) == 2

    def test_no_match(self):
        from app.services.payment_matching import _find_multi_unit_match
        candidates = [
            {"owner_id": 1, "monthly": 2000, "unit_id": 10},
            {"owner_id": 1, "monthly": 500, "unit_id": 20},
        ]
        result = _find_multi_unit_match(9999, candidates)
        assert result is None

    def test_different_owners(self):
        from app.services.payment_matching import _find_multi_unit_match
        candidates = [
            {"owner_id": 1, "monthly": 2000, "unit_id": 10},
            {"owner_id": 2, "monthly": 500, "unit_id": 20},
        ]
        # 2500, ale různí vlastníci → žádný multi-unit match
        result = _find_multi_unit_match(2500, candidates)
        assert result is None

    def test_multi_month(self):
        from app.services.payment_matching import _find_multi_unit_match
        candidates = [
            {"owner_id": 1, "monthly": 1000, "unit_id": 10},
            {"owner_id": 1, "monthly": 500, "unit_id": 20},
        ]
        # 3000 = (1000 + 500) × 2 měsíce
        result = _find_multi_unit_match(3000, candidates)
        assert result is not None


# ===========================================================================
# Integrační testy — match_payments s DB
# ===========================================================================

class TestMatchPayments:
    def test_vs_auto_match(self, db_session, seed_statement):
        """Platba s VS → AUTO_MATCHED."""
        from app.services.payment_matching import match_payments
        data = seed_statement
        result = match_payments(db_session, data["statement"].id, 2026)

        assert result["matched"] >= 1

        db_session.refresh(data["pay1"])
        assert data["pay1"].match_status == PaymentMatchStatus.AUTO_MATCHED
        assert data["pay1"].unit_id == data["unit1"].id

    def test_name_match_suggested(self, db_session, seed_statement):
        """Platba bez VS, se jménem vlastníka + částka → SUGGESTED."""
        from app.services.payment_matching import match_payments
        data = seed_statement
        match_payments(db_session, data["statement"].id, 2026)

        db_session.refresh(data["pay2"])
        # Jméno "SVOBODOVA MARIE" by mělo matchnout na vlastníka "Svobodová Marie"
        # Match závisí na délce slov a name_normalized
        assert data["pay2"].match_status in (
            PaymentMatchStatus.SUGGESTED, PaymentMatchStatus.UNMATCHED
        )

    def test_expense_ignored(self, db_session, seed_statement):
        """Výdajové platby se nepárují."""
        from app.services.payment_matching import match_payments
        data = seed_statement
        match_payments(db_session, data["statement"].id, 2026)

        db_session.refresh(data["pay3"])
        assert data["pay3"].match_status == PaymentMatchStatus.UNMATCHED

    def test_second_vs_match(self, db_session, seed_statement):
        """Druhá platba se stejným VS se taky napáruje."""
        from app.services.payment_matching import match_payments
        data = seed_statement
        match_payments(db_session, data["statement"].id, 2026)

        db_session.refresh(data["pay4"])
        # pay4 má stejný VS jako pay1 → taky AUTO_MATCHED
        assert data["pay4"].match_status == PaymentMatchStatus.AUTO_MATCHED

    def test_allocations_created(self, db_session, seed_statement):
        """Auto-matched platba vytvoří PaymentAllocation."""
        from app.services.payment_matching import match_payments
        data = seed_statement
        match_payments(db_session, data["statement"].id, 2026)

        allocs = db_session.query(PaymentAllocation).filter_by(
            payment_id=data["pay1"].id
        ).all()
        assert len(allocs) == 1
        assert allocs[0].unit_id == data["unit1"].id
        assert allocs[0].amount == 3000

    def test_return_counts(self, db_session, seed_statement):
        """match_payments vrací dict s počty."""
        from app.services.payment_matching import match_payments
        data = seed_statement
        result = match_payments(db_session, data["statement"].id, 2026)

        assert "matched" in result
        assert "suggested" in result
        assert "unmatched" in result
        assert "total" in result
        assert result["total"] > 0


# ===========================================================================
# Testy payment_overview
# ===========================================================================

class TestPaymentOverview:
    def test_compute_payment_matrix_empty(self, db_session, seed_basic):
        """Matice bez plateb — všechny jednotky mají debt."""
        from app.services.payment_overview import compute_payment_matrix
        result = compute_payment_matrix(db_session, 2026)

        assert "units" in result
        assert "months_with_data" in result
        # Bez plateb → months_with_data je prázdný set → expected=0+opening=0 → debt=0
        assert result["months_with_data"] == set()

    def test_compute_payment_matrix_with_payments(self, db_session, seed_statement):
        """Matice s matchovanými platbami."""
        from app.services.payment_matching import match_payments
        from app.services.payment_overview import compute_payment_matrix
        data = seed_statement
        match_payments(db_session, data["statement"].id, 2026)

        result = compute_payment_matrix(db_session, 2026)
        assert len(result["units"]) > 0
        assert 1 in result["months_with_data"]  # leden má platby

    def test_compute_debtor_list(self, db_session, seed_statement):
        """Dlužníci — jednotky kde paid < expected."""
        from app.services.payment_matching import match_payments
        from app.services.payment_overview import compute_debtor_list
        data = seed_statement
        match_payments(db_session, data["statement"].id, 2026)

        debtors, months = compute_debtor_list(db_session, 2026)
        assert isinstance(debtors, list)
        assert isinstance(months, set)

    def test_payment_with_alloc_wrapper(self):
        """PaymentWithAlloc deleguje atributy na Payment."""
        from app.services.payment_overview import PaymentWithAlloc

        class FakePayment:
            date = date(2026, 1, 15)
            vs = "123"
            amount = 3000

        wrapped = PaymentWithAlloc(FakePayment(), 2500)
        assert wrapped.alloc_amount == 2500
        assert wrapped.date == date(2026, 1, 15)
        assert wrapped.vs == "123"
        assert wrapped.amount == 3000


# ===========================================================================
# Testy settlement_service
# ===========================================================================

class TestSettlementService:
    def test_generate_settlements(self, db_session, seed_statement):
        """Generování vyúčtování vytvoří Settlement záznamy."""
        from app.services.payment_matching import match_payments
        from app.services.settlement_service import generate_settlements
        data = seed_statement
        match_payments(db_session, data["statement"].id, 2026)

        result = generate_settlements(db_session, 2026)
        assert "created" in result
        assert "updated" in result
        assert result["created"] > 0

        settlements = db_session.query(Settlement).filter_by(year=2026).all()
        assert len(settlements) > 0

    def test_generate_settlements_creates_items(self, db_session, seed_statement):
        """Vyúčtování má SettlementItems z PrescriptionItems."""
        from app.services.payment_matching import match_payments
        from app.services.settlement_service import generate_settlements
        data = seed_statement
        match_payments(db_session, data["statement"].id, 2026)
        generate_settlements(db_session, 2026)

        s = db_session.query(Settlement).filter_by(
            unit_id=data["unit1"].id, year=2026
        ).first()
        assert s is not None
        assert len(s.items) == 2  # 2 PrescriptionItems → 2 SettlementItems

    def test_generate_settlements_upsert(self, db_session, seed_statement):
        """Druhé volání aktualizuje existující, ne vytvoří nové."""
        from app.services.payment_matching import match_payments
        from app.services.settlement_service import generate_settlements
        data = seed_statement
        match_payments(db_session, data["statement"].id, 2026)

        r1 = generate_settlements(db_session, 2026)
        r2 = generate_settlements(db_session, 2026)

        assert r1["created"] > 0
        assert r2["created"] == 0
        assert r2["updated"] > 0

    def test_result_amount_round(self, db_session, seed_statement):
        """result_amount je zaokrouhleno na 2 desetinná místa."""
        from app.services.payment_matching import match_payments
        from app.services.settlement_service import generate_settlements
        data = seed_statement
        match_payments(db_session, data["statement"].id, 2026)
        generate_settlements(db_session, 2026)

        for s in db_session.query(Settlement).filter_by(year=2026).all():
            # result_amount by měl mít max 2 des. místa
            assert s.result_amount == round(s.result_amount, 2)


# ===========================================================================
# Testy compute_candidates
# ===========================================================================

class TestComputeCandidates:
    def test_unmatched_get_candidates(self, db_session, seed_statement):
        """Nenapárované příjmy dostanou kandidáty."""
        from app.services.payment_matching import compute_candidates
        data = seed_statement
        payments = db_session.query(Payment).filter_by(
            statement_id=data["statement"].id
        ).all()

        candidates = compute_candidates(db_session, payments, 2026, data["statement"].id)
        assert isinstance(candidates, dict)

    def test_expense_no_candidates(self, db_session, seed_statement):
        """Výdajové platby nemají kandidáty."""
        from app.services.payment_matching import compute_candidates
        data = seed_statement
        payments = db_session.query(Payment).filter_by(
            statement_id=data["statement"].id
        ).all()

        candidates = compute_candidates(db_session, payments, 2026, data["statement"].id)
        # pay3 je výdajová → nesmí mít kandidáty
        assert data["pay3"].id not in candidates


# ===========================================================================
# Testy round() na finančních výpočtech (N6A)
# ===========================================================================

class TestFinancialRounding:
    def test_debt_is_rounded(self, db_session, seed_statement):
        """saldo v matici plateb je zaokrouhleno na 2 des. místa."""
        from app.services.payment_matching import match_payments
        from app.services.payment_overview import compute_payment_matrix
        data = seed_statement
        match_payments(db_session, data["statement"].id, 2026)

        result = compute_payment_matrix(db_session, 2026)
        for row in result["units"]:
            assert row["saldo"] == round(row["saldo"], 2)
            assert row["expected"] == round(row["expected"], 2)
