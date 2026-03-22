"""Služba pro párování plateb na jednotky přes variabilní symboly.

Logika:
1. VS z platby → lookup v VariableSymbolMapping → unit_id (AUTO_MATCHED)
2. Fallback: jméno odesílatele + částka → SUGGESTED
3. Nenapárované: match_status=UNMATCHED
"""

from __future__ import annotations

import logging
import re
from typing import Optional

from sqlalchemy.orm import Session

from app.models import (
    VariableSymbolMapping, Prescription, Payment, PaymentAllocation,
    PaymentDirection, PaymentMatchStatus, Unit, OwnerUnit,
    PrescriptionYear, Owner,
)
from app.utils import strip_diacritics

logger = logging.getLogger(__name__)


def _clean_name_words(text: str) -> set[str]:
    """Vyčistit jméno — strip diakritiky, interpunkce, vrátit slova > 3 znaky."""
    clean = re.sub(r'[^\w\s]', ' ', strip_diacritics(text))
    return {w for w in clean.split() if len(w) > 3}


def compute_candidates(db: Session, payments: list, year: int,
                        statement_id: int | None = None) -> dict[int, list[dict]]:
    """Pro UNMATCHED příjmové platby spočítat kandidátní jednotky.

    Kandidát = jednotka kde jméno vlastníka sedí s odesílatelem (2+ společná slova).
    Jednotky s již napárovanou platbou v tomto výpisu se vynechají.
    Vrací dict payment_id → list[{unit_number, monthly, score, reasons}],
    max 3 kandidáti seřazení dle skóre.
    """
    unmatched = [
        p for p in payments
        if p.match_status == PaymentMatchStatus.UNMATCHED
        and p.direction == PaymentDirection.INCOME
    ]
    if not unmatched:
        return {}

    # Načti předpisy
    py = db.query(PrescriptionYear).filter_by(year=year).first()
    if not py:
        return {}

    # Pre-load jednotky a vlastníky (předejít N+1)
    all_units = {u.id: u for u in db.query(Unit).all()}
    all_owners = {o.id: o for o in db.query(Owner).all()}

    prescriptions = db.query(Prescription).filter_by(prescription_year_id=py.id).all()
    unit_info: dict[int, dict] = {}  # unit_number → {unit_id, monthly, vs, ...}
    for p in prescriptions:
        if p.unit_id:
            unit = all_units.get(p.unit_id)
            if unit:
                unit_info[unit.unit_number] = {
                    "unit_id": p.unit_id,
                    "monthly": p.monthly_total or 0,
                    "vs": p.variable_symbol or "",
                }

    # Jednotky již napárované v tomto výpisu → vyloučit z kandidátů
    matched_statuses = {PaymentMatchStatus.AUTO_MATCHED, PaymentMatchStatus.MANUAL,
                        PaymentMatchStatus.SUGGESTED}
    already_matched_units: set[int] = set()
    if statement_id:
        matched_allocs = (
            db.query(PaymentAllocation.unit_id)
            .join(Payment)
            .filter(
                Payment.statement_id == statement_id,
                Payment.match_status.in_(matched_statuses),
            )
            .all()
        )
        already_matched_units = {r[0] for r in matched_allocs}

    # Owner jména per unit (vyčištěná slova + příjmení)
    active_ous = db.query(OwnerUnit).filter(OwnerUnit.valid_to.is_(None)).all()
    unit_owner_words: dict[int, list[set]] = {}  # unit_number → [set of words]
    unit_owner_surnames: dict[int, set] = {}     # unit_number → {příjmení}
    for ou in active_ous:
        owner = all_owners.get(ou.owner_id)
        if owner and owner.name_normalized:
            unit = all_units.get(ou.unit_id)
            if unit:
                words = _clean_name_words(owner.name_normalized)
                if words:
                    unit_owner_words.setdefault(unit.unit_number, []).append(words)
                # Příjmení = první slovo v name_normalized (formát příjmení-first)
                surname = _clean_name_words(owner.name_normalized.split()[0])
                if surname:
                    unit_owner_surnames.setdefault(unit.unit_number, set()).update(surname)

    result = {}
    for payment in unmatched:
        sender_words = _clean_name_words(payment.counter_account_name or "")
        if not sender_words:
            continue

        candidates = []
        for un, info in unit_info.items():
            # Přeskočit jednotky s již napárovanou platbou
            if info["unit_id"] in already_matched_units:
                continue

            monthly = info["monthly"]

            # Jméno match — 2+ společná slova NEBO shoda na příjmení vlastníka
            name_match = False
            for word_set in unit_owner_words.get(un, []):
                common = sender_words & word_set
                if len(common) >= 2:
                    name_match = True
                    break
            if not name_match:
                # Fallback: shoda na příjmení (první slovo jména vlastníka)
                surnames = unit_owner_surnames.get(un, set())
                if sender_words & surnames:
                    name_match = True

            if not name_match:
                continue

            # Přeskočit nesmyslné kandidáty (předpis > 10× platba)
            if monthly and monthly > payment.amount * 10:
                continue

            score = 2  # base za jmennou shodu
            reasons = []
            amount_match = False

            # Bonus za přesnou shodu částky
            if monthly > 0:
                for n in range(1, 13):
                    if abs(payment.amount - monthly * n) < 0.01:
                        reasons.append(f"{n}×{monthly:.0f}")
                        score += 3
                        amount_match = True
                        break

            candidates.append({
                "unit_number": un,
                "monthly": monthly,
                "vs": info["vs"],
                "score": score,
                "reasons": reasons,
                "amount_match": amount_match,
            })

        # Seřadit dle skóre, vzít top 3
        candidates.sort(key=lambda x: (-x["score"], x["unit_number"]))
        if candidates:
            result[payment.id] = candidates[:3]

    return result


def _find_name_matches(sender_words: set, name_lookup: list[dict]) -> list[dict]:
    """Najdi všechny shody jména odesílatele proti lookup tabulce.

    Shoda = alespoň jedno slovo delší než 3 znaky se shoduje.
    Vrací seznam všech matchů seřazený podle skóre (víc shodných slov = lepší).
    """
    significant_sender = {w for w in sender_words if len(w) > 3}
    if not significant_sender:
        return []

    matches = []
    for entry in name_lookup:
        significant_entry = {w for w in entry["words"] if len(w) > 3}
        if not significant_entry:
            continue

        common = significant_sender & significant_entry
        if not common:
            continue

        matches.append((len(common), entry))

    # Seřadit podle skóre (nejvíc shodných slov první)
    matches.sort(key=lambda x: x[0], reverse=True)
    return [entry for _, entry in matches]


def _check_amount_match(amount: float, monthly_total: Optional[float]) -> bool:
    """True pokud amount je přesný násobek monthly_total (1-12×)."""
    if not monthly_total or monthly_total <= 0:
        return False

    for n in range(1, 13):
        expected = monthly_total * n
        if abs(amount - expected) < 0.01:
            return True
    return False


def _find_multi_unit_match(amount: float, candidates: list[dict]) -> Optional[list[dict]]:
    """Zkusit najít kombinaci jednotek jednoho vlastníka kde součet předpisů = amount.

    Seskupí kandidáty podle owner_id, pro každého vlastníka s 2+ jednotkami
    zkouší kombinace (2-4) kde sum(monthly * n) = amount (přesná shoda).
    """
    from itertools import combinations

    # Seskupit podle owner_id
    by_owner: dict[int, list[dict]] = {}
    for c in candidates:
        oid = c.get("owner_id")
        if not oid or not c.get("monthly") or c["monthly"] <= 0:
            continue
        by_owner.setdefault(oid, []).append(c)

    for owner_id, entries in by_owner.items():
        if len(entries) < 2:
            continue

        # Zkusit kombinace 2-4 jednotek
        for size in range(2, min(len(entries) + 1, 5)):
            for combo in combinations(entries, size):
                combo_sum = sum(e["monthly"] for e in combo)
                # Zkusit n-násobek (1-12 měsíců)
                for n in range(1, 13):
                    expected = combo_sum * n
                    if abs(amount - expected) < 0.01:
                        return list(combo)
    return None


def _create_allocation(db: Session, payment: Payment, unit_id: int,
                       owner_id: Optional[int], prescription_id: Optional[int],
                       amount: float) -> None:
    """Vytvořit PaymentAllocation záznam (dual-write)."""
    db.add(PaymentAllocation(
        payment_id=payment.id,
        unit_id=unit_id,
        owner_id=owner_id,
        prescription_id=prescription_id,
        amount=amount,
    ))


def _extract_unit_from_vs(vs: str, known_vs_map: dict[str, int],
                          unit_ids: set[int]) -> Optional[int]:
    """Zkusit dekódovat číslo jednotky z VS přes podobnost s předpisovými VS.

    Formát předpisových VS: prefix(5) + unit_number(3 zero-padded) + suffix(2)
    Příklad: 1109800501 → 11098 + 005 + 01 → jednotka 5

    Zkouší několik variant extrakce za prefixem '1098'.
    """
    vs_stripped = vs.lstrip("0")
    idx = vs_stripped.find("1098")
    if idx < 0:
        return None

    # Za '1098' extrahovat zbytek
    remainder = vs_stripped[idx + 4:]
    if len(remainder) < 2:
        return None

    # Zkusit více variant (od nejdelšího po nejkratší):
    # 1. remainder bez posledních 2 znaků (suffix): "01038" → "010" → 10
    # 2. celý remainder: "503" → 503
    # 3. první 3 znaky: "01038" → "010" → 10
    # 4. první 2 znaky: "01038" → "01" → 1
    candidates = []
    if len(remainder) > 2:
        part = remainder[:-2]
        if part.isdigit():
            candidates.append(int(part))
    if remainder.isdigit():
        candidates.append(int(remainder))
    for width in (3, 2):
        if len(remainder) >= width:
            part = remainder[:width]
            if part.isdigit():
                candidates.append(int(part))

    # Vrátit první existující jednotku
    for unit_num in candidates:
        if unit_num in unit_ids:
            return unit_num
    return None


def match_payments(db: Session, statement_id: int, year: int) -> dict:
    """Napáruj platby z výpisu na jednotky přes VS + fallback jméno+částka.

    Args:
        db: databázová session
        statement_id: ID bankovního výpisu
        year: rok pro vyhledání předpisů

    Returns:
        dict s počty: matched, suggested, unmatched, total
    """
    # Načti VS mapování (aktivní)
    vs_map = {}
    for m in db.query(VariableSymbolMapping).filter_by(is_active=True).all():
        vs_map[m.variable_symbol] = m.unit_id

    # Načti předpisy pro rok
    prescriptions_by_vs = {}
    prescriptions_by_unit = {}
    all_prescriptions = []
    py = db.query(PrescriptionYear).filter_by(year=year).first()
    if py:
        for p in db.query(Prescription).filter_by(prescription_year_id=py.id).all():
            if p.variable_symbol:
                prescriptions_by_vs[p.variable_symbol] = p
            if p.unit_id:
                prescriptions_by_unit[p.unit_id] = p
            all_prescriptions.append(p)

    # Načti jednotky (pro VS-prefix matching)
    all_units = db.query(Unit).all()
    unit_by_number = {u.unit_number: u.id for u in all_units}
    unit_number_by_id = {u.id: u.unit_number for u in all_units}

    # Načti aktuální vlastníky jednotek
    all_owners = {o.id: o for o in db.query(Owner).all()}
    owner_by_unit = {}
    active_owner_units = db.query(OwnerUnit).filter(OwnerUnit.valid_to.is_(None)).all()
    for ou in active_owner_units:
        owner_by_unit[ou.unit_id] = ou.owner_id

    # 1. fáze: VS párování
    payments = (
        db.query(Payment)
        .filter_by(statement_id=statement_id, match_status=PaymentMatchStatus.UNMATCHED)
        .filter(Payment.direction == PaymentDirection.INCOME)
        .all()
    )

    matched = 0
    suggested = 0
    unmatched = 0

    for payment in payments:
        if not payment.vs:
            continue

        unit_id = vs_map.get(payment.vs)
        if not unit_id:
            continue

        payment.unit_id = unit_id
        payment.owner_id = owner_by_unit.get(unit_id)
        payment.match_status = PaymentMatchStatus.AUTO_MATCHED

        prescription = prescriptions_by_vs.get(payment.vs)
        if prescription:
            payment.prescription_id = prescription.id

        payment.assigned_month = payment.date.month if payment.date else None

        # Dual-write: vytvořit alokaci
        _create_allocation(
            db, payment, unit_id, payment.owner_id,
            payment.prescription_id, payment.amount,
        )
        matched += 1

    db.flush()

    # Sbírej unit_ids napárované ve fázi 1 — vyloučit z fází 2 a 3
    auto_matched_unit_ids = set()
    for p in payments:
        if p.match_status == PaymentMatchStatus.AUTO_MATCHED and p.unit_id:
            auto_matched_unit_ids.add(p.unit_id)

    # 2. fáze: Fallback — jméno odesílatele + částka
    still_unmatched = [
        p for p in payments
        if p.match_status == PaymentMatchStatus.UNMATCHED and p.counter_account_name
    ]

    if still_unmatched:
        # Připravit name lookup z předpisů + vlastníků (bez auto-matched jednotek)
        name_lookup = []
        seen_keys = set()  # deduplikace

        for presc in all_prescriptions:
            if presc.owner_name and presc.unit_id:
                if presc.unit_id in auto_matched_unit_ids:
                    continue  # Vyloučit auto-matched jednotky
                norm = strip_diacritics(presc.owner_name)
                key = (norm, presc.unit_id)
                if key not in seen_keys:
                    seen_keys.add(key)
                    name_lookup.append({
                        "name_norm": norm,
                        "words": set(norm.split()),
                        "unit_id": presc.unit_id,
                        "owner_id": owner_by_unit.get(presc.unit_id),
                        "monthly": presc.monthly_total,
                        "prescription_id": presc.id,
                    })

        for ou in active_owner_units:
            if ou.unit_id in auto_matched_unit_ids:
                continue  # Vyloučit auto-matched jednotky
            owner = all_owners.get(ou.owner_id)
            if not owner or not owner.name_normalized:
                continue
            key = (owner.name_normalized, ou.unit_id)
            if key not in seen_keys:
                seen_keys.add(key)
                presc = prescriptions_by_unit.get(ou.unit_id)
                name_lookup.append({
                    "name_norm": owner.name_normalized,
                    "words": set(owner.name_normalized.split()),
                    "unit_id": ou.unit_id,
                    "owner_id": ou.owner_id,
                    "monthly": presc.monthly_total if presc else None,
                    "prescription_id": presc.id if presc else None,
                })

        for payment in still_unmatched:
            sender_norm = strip_diacritics(payment.counter_account_name)
            sender_words = set(sender_norm.split())

            candidates = _find_name_matches(sender_words, name_lookup)
            if not candidates:
                continue

            # Najít kandidáta kde částka odpovídá předpisu
            best = None
            for c in candidates:
                if _check_amount_match(payment.amount, c["monthly"]):
                    best = c
                    break

            if best:
                # Single-unit match
                payment.unit_id = best["unit_id"]
                payment.owner_id = owner_by_unit.get(best["unit_id"])
                payment.match_status = PaymentMatchStatus.SUGGESTED
                payment.assigned_month = payment.date.month if payment.date else None

                presc = prescriptions_by_unit.get(best["unit_id"])
                if presc:
                    payment.prescription_id = presc.id

                _create_allocation(
                    db, payment, best["unit_id"], payment.owner_id,
                    payment.prescription_id, payment.amount,
                )
                suggested += 1
            else:
                # Zkusit multi-unit match (součet předpisů více jednotek)
                multi = _find_multi_unit_match(payment.amount, candidates)
                if multi:
                    # Multi-unit → Payment.unit_id = None, N alokací
                    payment.unit_id = None
                    payment.owner_id = multi[0].get("owner_id")
                    payment.match_status = PaymentMatchStatus.SUGGESTED
                    payment.assigned_month = payment.date.month if payment.date else None

                    for entry in multi:
                        _create_allocation(
                            db, payment, entry["unit_id"],
                            entry.get("owner_id"),
                            entry.get("prescription_id"),
                            entry["monthly"],
                        )
                    suggested += 1
                elif len(candidates) == 1:
                    # Pokud jen 1 jmenný kandidát a částka nesedí, přesto navrhnout
                    best = candidates[0]
                    payment.unit_id = best["unit_id"]
                    payment.owner_id = owner_by_unit.get(best["unit_id"])
                    payment.match_status = PaymentMatchStatus.SUGGESTED
                    payment.assigned_month = payment.date.month if payment.date else None

                    presc = prescriptions_by_unit.get(best["unit_id"])
                    if presc:
                        payment.prescription_id = presc.id

                    _create_allocation(
                        db, payment, best["unit_id"], payment.owner_id,
                        payment.prescription_id, payment.amount,
                    )
                    suggested += 1

        db.flush()

    # 3. fáze: VS-prefix matching + skórovací systém
    still_unmatched2 = [
        p for p in payments
        if p.match_status == PaymentMatchStatus.UNMATCHED and p.vs
    ]

    if still_unmatched2:
        # Připrav name lookup pro skóring (owner names per unit_id)
        unit_owner_words: dict[int, list[set]] = {}
        for ou in active_owner_units:
            owner = all_owners.get(ou.owner_id)
            if owner and owner.name_normalized:
                unit_owner_words.setdefault(ou.unit_id, []).append(
                    {w for w in owner.name_normalized.split() if len(w) > 3}
                )
        for presc in all_prescriptions:
            if presc.owner_name and presc.unit_id:
                norm = strip_diacritics(presc.owner_name)
                unit_owner_words.setdefault(presc.unit_id, []).append(
                    {w for w in norm.split() if len(w) > 3}
                )

        # Předpisové VS → set pro prefix matching
        known_vs_map = {p.variable_symbol: p.unit_id for p in all_prescriptions if p.variable_symbol}

        for payment in still_unmatched2:
            # Zkusit dekódovat unit z VS
            decoded_un = _extract_unit_from_vs(payment.vs, known_vs_map, set(unit_by_number.keys()))
            if not decoded_un:
                continue

            decoded_uid = unit_by_number[decoded_un]

            # Přeskočit auto-matched jednotky
            if decoded_uid in auto_matched_unit_ids:
                continue

            presc = prescriptions_by_unit.get(decoded_uid)

            # Spočítat skóre: VS dekódování (+3) + jméno (+2) + částka (+3)
            score = 3  # VS dekódování base

            # Jméno odesílatele vs vlastník jednotky
            if payment.counter_account_name:
                sender_words = {
                    w for w in strip_diacritics(payment.counter_account_name).split()
                    if len(w) > 3
                }
                for word_set in unit_owner_words.get(decoded_uid, []):
                    if sender_words & word_set:
                        score += 2
                        break

            # Částka vs předpis
            if presc and _check_amount_match(payment.amount, presc.monthly_total):
                score += 3

            if score >= 5:
                # Dostatečná jistota → SUGGESTED
                payment.unit_id = decoded_uid
                payment.owner_id = owner_by_unit.get(decoded_uid)
                payment.match_status = PaymentMatchStatus.SUGGESTED
                payment.assigned_month = payment.date.month if payment.date else None
                if presc:
                    payment.prescription_id = presc.id

                _create_allocation(
                    db, payment, decoded_uid, payment.owner_id,
                    payment.prescription_id, payment.amount,
                )
                suggested += 1

        db.flush()

    # Spočítat zbylé unmatched
    unmatched = sum(
        1 for p in payments if p.match_status == PaymentMatchStatus.UNMATCHED
    )

    logger.info(
        "Matching statement %d: %d matched, %d suggested, %d unmatched",
        statement_id, matched, suggested, unmatched,
    )

    return {
        "matched": matched,
        "suggested": suggested,
        "unmatched": unmatched,
        "total": len(payments),
    }
