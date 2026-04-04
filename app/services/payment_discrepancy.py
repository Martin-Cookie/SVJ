"""Služba pro detekci nesrovnalostí v platbách a generování upozornění.

Typy nesrovnalostí:
- wrong_vs: platba má jiný VS než předpis přiřazené jednotky/prostoru
- wrong_amount: zaplacená částka neodpovídá měsíčnímu předpisu
- combined: jedna platba rozdělena na více jednotek/prostorů
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

from sqlalchemy.orm import Session, joinedload

from app.models import (
    BankStatement, Payment, PaymentAllocation, PaymentDirection,
    PaymentMatchStatus, Prescription, PrescriptionYear,
    Unit, Owner, OwnerUnit, Space, SpaceTenant, Tenant,
)

logger = logging.getLogger(__name__)


@dataclass
class Discrepancy:
    """Jedna nesrovnalost v platbě."""
    payment_id: int
    payment_date: str  # DD.MM.YYYY
    payment_amount: float
    payment_vs: str  # VS z platby
    sender_name: str  # protiúčet
    types: list[str] = field(default_factory=list)  # ["wrong_vs", "wrong_amount", "combined"]
    # Cílová entita
    entity_type: str = ""  # "unit" nebo "space"
    entity_label: str = ""  # "Jednotka č. 5" nebo "Prostor č. 3 — Sklep"
    entity_vs: str = ""  # VS z předpisu
    expected_amount: float = 0.0  # měsíční předpis
    # Příjemce upozornění
    recipient_name: str = ""
    recipient_email: str = ""
    recipient_type: str = ""  # "owner" nebo "tenant"
    owner_id: int | None = None
    tenant_id: int | None = None
    # Detaily pro sloučenou platbu
    allocations: list[dict] = field(default_factory=list)  # [{entity_label, amount, expected}]


def _match_owner_by_sender(owners: list[Owner], sender_name: str | None) -> Owner | None:
    """Vybrat vlastníka, jehož jméno odpovídá odesílateli platby.

    Při SJM (více vlastníků na jednotce) preferovat toho, kdo platbu poslal.
    Porovnání: příjmení odesílatele se vyskytuje v name_normalized vlastníka.
    Fallback: první vlastník v seznamu.
    """
    if not owners:
        return None
    if len(owners) == 1:
        return owners[0]
    if not sender_name:
        return owners[0]

    # Normalizovat jméno odesílatele a rozdělit na slova
    from app.utils import strip_diacritics
    sender_words = set(strip_diacritics(sender_name).split())

    for owner in owners:
        if not owner.name_normalized:
            continue
        owner_words = set(owner.name_normalized.split())
        # Shoda = alespoň 2 slova se shodují (příjmení + jméno)
        # nebo celé příjmení odesílatele je v owner_words
        common = sender_words & owner_words
        if len(common) >= 2:
            return owner

    # Fallback: hledat alespoň příjmení (první slovo odesílatele)
    for owner in owners:
        if not owner.name_normalized:
            continue
        owner_words = set(owner.name_normalized.split())
        if sender_words & owner_words:
            return owner

    return owners[0]


def detect_discrepancies(
    db: Session,
    statement_id: int,
) -> list[Discrepancy]:
    """Detekovat nesrovnalosti v platbách výpisu.

    Kontroluje:
    1. MANUAL a SUGGESTED platby — špatný VS, špatná částka
    2. AUTO_MATCHED platby — špatná částka (VS sedí, ale zaplaceno jinak)
    3. Sloučené platby — více alokací na jednu platbu
    """
    statement = db.query(BankStatement).get(statement_id)
    if not statement:
        return []

    # Rok pro předpisy
    pf = statement.period_from
    year = pf.year if pf else None
    if not year:
        return []

    # Načíst předpisy pro rok
    py = db.query(PrescriptionYear).filter_by(year=year).first()
    unit_prescriptions: dict[int, Prescription] = {}  # unit_id → Prescription
    space_prescriptions: dict[int, Prescription] = {}  # space_id → (není v Prescription, ale v SpaceTenant)
    if py:
        for presc in db.query(Prescription).filter_by(prescription_year_id=py.id).all():
            if presc.unit_id:
                unit_prescriptions[presc.unit_id] = presc

    # SpaceTenant — měsíční nájmy a VS
    active_sts = db.query(SpaceTenant).filter_by(is_active=True).options(
        joinedload(SpaceTenant.tenant).joinedload(Tenant.owner),
        joinedload(SpaceTenant.space),
    ).all()
    space_rent: dict[int, float] = {}  # space_id → monthly_rent
    space_vs_map: dict[int, str] = {}  # space_id → VS
    space_tenant_map: dict[int, SpaceTenant] = {}  # space_id → SpaceTenant
    for st in active_sts:
        if st.monthly_rent:
            space_rent[st.space_id] = st.monthly_rent
        if st.variable_symbol:
            space_vs_map[st.space_id] = st.variable_symbol
        space_tenant_map[st.space_id] = st

    # Vlastníci jednotek — více vlastníků (SJM) na jednu jednotku
    active_ous = db.query(OwnerUnit).filter(
        OwnerUnit.valid_to.is_(None)
    ).options(joinedload(OwnerUnit.owner)).all()
    unit_owners_list: dict[int, list[Owner]] = {}  # unit_id → [Owner, ...]
    for ou in active_ous:
        if ou.owner:
            unit_owners_list.setdefault(ou.unit_id, []).append(ou.owner)

    # Načíst platby výpisu (jen příjmy, napárované)
    payments = (
        db.query(Payment)
        .filter_by(statement_id=statement_id)
        .filter(Payment.direction == PaymentDirection.INCOME)
        .filter(Payment.match_status.in_([
            PaymentMatchStatus.AUTO_MATCHED,
            PaymentMatchStatus.SUGGESTED,
            PaymentMatchStatus.MANUAL,
        ]))
        .options(
            joinedload(Payment.unit),
            joinedload(Payment.space),
            joinedload(Payment.allocations).joinedload(PaymentAllocation.unit),
            joinedload(Payment.allocations).joinedload(PaymentAllocation.space),
        )
        .all()
    )

    discrepancies: list[Discrepancy] = []

    for payment in payments:
        allocs = payment.allocations or []

        # Sloučená platba = více alokací
        is_combined = len(allocs) > 1

        # Pro každou alokaci (nebo přímo z payment pokud není alokace)
        targets = []
        if allocs:
            for a in allocs:
                targets.append({
                    "unit": a.unit,
                    "space": a.space,
                    "amount": a.amount or payment.amount,
                })
        elif payment.unit_id or payment.space_id:
            targets.append({
                "unit": payment.unit,
                "space": payment.space,
                "amount": payment.amount,
            })

        if not targets:
            continue

        # Detekce pro každý target
        disc_types = []
        alloc_details = []

        for t in targets:
            unit = t["unit"]
            space = t["space"]
            alloc_amount = t["amount"]

            if unit:
                presc = unit_prescriptions.get(unit.id)
                expected = presc.monthly_total if presc else 0
                expected_vs = presc.variable_symbol if presc else ""
                entity_label = f"Jednotka č. {unit.unit_number}"
                entity_type = "unit"
                entity_vs = expected_vs or ""

                # Špatný VS
                if payment.match_status in (PaymentMatchStatus.MANUAL, PaymentMatchStatus.SUGGESTED):
                    if expected_vs and payment.vs and payment.vs != expected_vs:
                        if "wrong_vs" not in disc_types:
                            disc_types.append("wrong_vs")

                # Špatná částka
                if expected and alloc_amount and abs(alloc_amount - expected) > 0.50:
                    # Tolerovat násobky (1-12 měsíců)
                    is_multiple = False
                    if expected > 0:
                        ratio = alloc_amount / expected
                        if abs(ratio - round(ratio)) < 0.01 and 1 <= round(ratio) <= 12:
                            is_multiple = True
                    if not is_multiple and "wrong_amount" not in disc_types:
                        disc_types.append("wrong_amount")

                alloc_details.append({
                    "entity_label": entity_label,
                    "amount": alloc_amount,
                    "expected": expected,
                })

            elif space:
                expected = space_rent.get(space.id, 0)
                expected_vs = space_vs_map.get(space.id, "")
                entity_label = f"Prostor č. {space.space_number} — {space.designation or ''}"
                entity_type = "space"
                entity_vs = expected_vs or ""

                # Špatný VS
                if payment.match_status in (PaymentMatchStatus.MANUAL, PaymentMatchStatus.SUGGESTED):
                    if expected_vs and payment.vs and payment.vs != expected_vs:
                        if "wrong_vs" not in disc_types:
                            disc_types.append("wrong_vs")

                # Špatná částka
                if expected and alloc_amount and abs(alloc_amount - expected) > 0.50:
                    is_multiple = False
                    if expected > 0:
                        ratio = alloc_amount / expected
                        if abs(ratio - round(ratio)) < 0.01 and 1 <= round(ratio) <= 12:
                            is_multiple = True
                    if not is_multiple and "wrong_amount" not in disc_types:
                        disc_types.append("wrong_amount")

                alloc_details.append({
                    "entity_label": entity_label,
                    "amount": alloc_amount,
                    "expected": expected,
                })

        if is_combined:
            disc_types.append("combined")

        if not disc_types:
            continue

        # Určit příjemce
        recipient_name = ""
        recipient_email = ""
        recipient_type = ""
        owner_id = None
        tenant_id = None

        # Preferovat první alokaci pro určení příjemce
        first_unit = targets[0].get("unit") if targets else None
        first_space = targets[0].get("space") if targets else None

        if first_unit:
            owners = unit_owners_list.get(first_unit.id, [])
            owner = _match_owner_by_sender(owners, payment.counter_account_name)
            if owner:
                recipient_name = owner.display_name
                recipient_email = owner.email or ""
                recipient_type = "owner"
                owner_id = owner.id
        elif first_space:
            st = space_tenant_map.get(first_space.id)
            if st and st.tenant:
                tenant = st.tenant
                recipient_name = tenant.display_name
                recipient_email = tenant.email or ""
                recipient_type = "tenant"
                tenant_id = tenant.id
                # Pokud je nájemce propojený s vlastníkem, použít i jeho email
                if not recipient_email and tenant.owner:
                    recipient_email = tenant.owner.email or ""

        # Entita label — pro sloučenou platbu spojit
        if is_combined:
            entity_label = " + ".join(a["entity_label"] for a in alloc_details)
            entity_type = "combined"
            entity_vs = ""
            expected_amount = sum(a["expected"] for a in alloc_details)
        else:
            entity_label = alloc_details[0]["entity_label"] if alloc_details else ""
            entity_type = targets[0].get("unit") and "unit" or "space"
            entity_vs = ""
            expected_amount = alloc_details[0]["expected"] if alloc_details else 0
            # VS z předpisu
            if targets[0].get("unit"):
                presc = unit_prescriptions.get(targets[0]["unit"].id)
                entity_vs = presc.variable_symbol if presc else ""
            elif targets[0].get("space"):
                entity_vs = space_vs_map.get(targets[0]["space"].id, "")

        disc = Discrepancy(
            payment_id=payment.id,
            payment_date=payment.date.strftime("%d.%m.%Y") if payment.date else "",
            payment_amount=payment.amount,
            payment_vs=payment.vs or "",
            sender_name=payment.counter_account_name or "",
            types=disc_types,
            entity_type=entity_type,
            entity_label=entity_label,
            entity_vs=entity_vs,
            expected_amount=expected_amount,
            recipient_name=recipient_name,
            recipient_email=recipient_email,
            recipient_type=recipient_type,
            owner_id=owner_id,
            tenant_id=tenant_id,
            allocations=alloc_details if is_combined else [],
        )
        discrepancies.append(disc)

    return discrepancies


# Label mapování pro šablony
DISCREPANCY_LABELS = {
    "wrong_vs": "Špatný variabilní symbol",
    "wrong_amount": "Nesprávná výše platby",
    "combined": "Sloučená platba za více jednotek/prostorů",
}


def build_email_context(disc: Discrepancy, svj_name: str, month_name: str, year: int) -> dict:
    """Sestavit kontext pro rendering emailové šablony z nesrovnalosti."""
    # Popisy chyb v přirozeném jazyce
    chyby = []
    for t in disc.types:
        if t == "wrong_vs":
            chyby.append(
                f"Špatný variabilní symbol — platba má VS {disc.payment_vs or '(prázdný)'}, "
                f"správný VS je {disc.entity_vs or '(neznámý)'}"
            )
        elif t == "wrong_amount":
            chyby.append(
                f"Nesprávná výše platby — zaplaceno {_fmt(disc.payment_amount)} Kč, "
                f"předpis je {_fmt(disc.expected_amount)} Kč"
            )
        elif t == "combined":
            parts = ", ".join(
                f"{a['entity_label']} ({_fmt(a['expected'])} Kč)"
                for a in disc.allocations
            )
            chyby.append(
                f"Sloučená platba za více jednotek/prostorů: {parts}"
            )

    return {
        "jmeno": disc.recipient_name,
        "mesic_nazev": month_name,
        "rok": str(year),
        "datum_platby": disc.payment_date,
        "castka_zaplaceno": _fmt(disc.payment_amount),
        "vs_platby": disc.payment_vs or "(prázdný)",
        "entita": disc.entity_label,
        "castka_predpis": _fmt(disc.expected_amount),
        "vs_predpisu": disc.entity_vs or "(neznámý)",
        "chyby": chyby,
        "svj_nazev": svj_name or "SVJ",
    }


def _fmt(val: float) -> str:
    """Formátovat číslo s mezerovým oddělovačem tisíců."""
    if not val:
        return "0"
    return f"{val:,.0f}".replace(",", " ")
