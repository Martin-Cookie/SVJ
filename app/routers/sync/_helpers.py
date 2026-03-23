import logging
import re

from difflib import SequenceMatcher

from sqlalchemy import cast, Integer
from sqlalchemy.orm import Session

from app.models import (
    Owner, OwnerType, OwnerUnit, SyncRecord, SyncResolution, SyncStatus, Unit,
)
from app.services.owner_exchange import recalculate_unit_votes
from app.services.owner_matcher import normalize_for_matching
from app.utils import strip_diacritics

logger = logging.getLogger(__name__)


SYNC_SORT_COLUMNS = {
    "unit": cast(SyncRecord.unit_number, Integer),
    "owner": SyncRecord.excel_owner_name,
    "space_type": SyncRecord.excel_space_type,
    "ownership": SyncRecord.excel_ownership_type,
    "podil": SyncRecord.excel_podil_scd,
    "match": SyncRecord.match_details,
    "action": SyncRecord.resolution,
}


ALLOWED_UPDATE_FIELDS = {"ownership_type", "space_type", "podil_scd", "owner_name"}


def _apply_owner_name_update(db, unit, record, new_value):
    """Apply owner name changes from CSV to DB. Returns list of change descriptions."""

    changes = []
    csv_names = [n.strip() for n in re.split(r'\s*[;,]\s*', new_value.strip()) if n.strip()]

    all_owner_units = db.query(OwnerUnit).filter_by(unit_id=unit.id).filter(OwnerUnit.valid_to.is_(None)).all()
    all_owners = []
    ou_by_owner = {}
    for aou in all_owner_units:
        o = db.query(Owner).get(aou.owner_id)
        if o:
            all_owners.append(o)
            ou_by_owner[o.id] = aou

    # Match CSV names to existing owners by fuzzy similarity
    used_db = set()
    matched_pairs = []
    unmatched_csv = []
    for cn in csv_names:
        csv_norm = normalize_for_matching(cn)
        best_owner, best_ratio = None, -1
        for o in all_owners:
            if o.id in used_db:
                continue
            r = SequenceMatcher(None, csv_norm, o.name_normalized or "").ratio()
            if r > best_ratio:
                best_ratio = r
                best_owner = o
        if best_owner and best_ratio >= 0.75:
            used_db.add(best_owner.id)
            matched_pairs.append((best_owner, cn, best_ratio))
        else:
            unmatched_csv.append(cn)

    unmatched_db = [o for o in all_owners if o.id not in used_db]

    # Rename matched owners
    for owner, matched_name, _ratio in matched_pairs:
        old_val = owner.name_with_titles
        if old_val != matched_name:
            name_parts = matched_name.split(None, 1)
            if len(name_parts) == 2:
                owner.last_name = name_parts[0]
                owner.first_name = name_parts[1]
            else:
                owner.first_name = name_parts[0]
                owner.last_name = None
            owner.name_with_titles = matched_name
            owner.name_normalized = normalize_for_matching(matched_name)
            changes.append(f"jméno: {old_val} → {matched_name}")

    # Hard-delete OwnerUnits for unmatched DB owners
    for o in unmatched_db:
        aou = ou_by_owner.get(o.id)
        if aou:
            db.delete(aou)
            changes.append(f"odebrán: {o.name_with_titles}")
    db.flush()

    # Create new Owner + OwnerUnit for unmatched CSV names
    total_votes = int(unit.podil_scd or 0)
    new_count = len(matched_pairs) + len(unmatched_csv)
    votes_each = total_votes // new_count if new_count > 0 else 0
    for cn in unmatched_csv:
        cn_simple = strip_diacritics(cn.strip())
        existing_global = db.query(Owner).filter(
            Owner.name_normalized == cn_simple, Owner.is_active == True,
        ).first()
        if not existing_global:
            cn_stemmed = normalize_for_matching(cn)
            existing_global = db.query(Owner).filter(
                Owner.name_normalized == cn_stemmed, Owner.is_active == True,
            ).first()
        if existing_global:
            owner = existing_global
            changes.append(f"přidán (existující): {cn}")
        else:
            name_parts = cn.split(None, 1)
            is_legal = re.search(
                r'\b(s\.r\.o\.|a\.s\.|spol\.|z\.s\.|v\.o\.s\.)\b', cn, re.IGNORECASE,
            )
            owner = Owner(
                first_name=name_parts[1] if len(name_parts) == 2 else name_parts[0],
                last_name=name_parts[0] if len(name_parts) == 2 else None,
                name_with_titles=cn,
                name_normalized=strip_diacritics(cn.strip()),
                owner_type=OwnerType.LEGAL_ENTITY if is_legal else OwnerType.PHYSICAL,
                data_source="csv_sync", is_active=True,
            )
            db.add(owner)
            db.flush()
            changes.append(f"přidán: {cn}")
        db.add(OwnerUnit(
            owner_id=owner.id, unit_id=unit.id,
            ownership_type=record.csv_ownership_type or "",
            share=1.0 / new_count if new_count > 1 else 1.0,
            votes=votes_each,
        ))

    # Recalculate votes if ownership changed
    if unmatched_db or unmatched_csv:
        db.flush()
        active_ous = db.query(OwnerUnit).filter_by(unit_id=unit.id).filter(OwnerUnit.valid_to.is_(None)).all()
        if active_ous:
            base = total_votes // len(active_ous)
            remainder = total_votes % len(active_ous)
            for idx, aou in enumerate(active_ous):
                aou.votes = base + (1 if idx < remainder else 0)
                aou.share = 1.0 / len(active_ous)

    record.excel_owner_name = new_value.strip()
    return changes


def _build_contact_preview(session_id: int, db: Session) -> list[dict]:
    """Build preview of contact transfers from CSV to owners."""
    records = (
        db.query(SyncRecord)
        .filter_by(session_id=session_id)
        .filter(SyncRecord.status == SyncStatus.MATCH)
        .all()
    )

    preview = []
    seen_owners: set[int] = set()
    for record in records:
        if not record.unit_number:
            continue
        if not record.csv_email and not record.csv_phone:
            continue

        short_num = record.unit_number
        owner_units = (
            db.query(OwnerUnit)
            .join(OwnerUnit.unit)
            .filter(Unit.unit_number.endswith(f"/{short_num}") | (Unit.unit_number == short_num))
            .filter(OwnerUnit.valid_to.is_(None))
            .all()
        )
        if not owner_units:
            continue

        for ou in owner_units:
            if ou.owner_id in seen_owners:
                continue
            seen_owners.add(ou.owner_id)

            owner = db.query(Owner).get(ou.owner_id)
            if not owner:
                continue

            will_email = bool(record.csv_email and not owner.email)
            will_phone = bool(record.csv_phone and not owner.phone)

            if not will_email and not will_phone:
                continue

            preview.append({
                "owner_id": owner.id,
                "owner_name": owner.display_name,
                "unit_number": record.unit_number,
                "current_email": owner.email or "",
                "csv_email": record.csv_email or "",
                "will_email": will_email,
                "current_phone": owner.phone or "",
                "csv_phone": record.csv_phone or "",
                "will_phone": will_phone,
            })

    preview.sort(key=lambda x: x["owner_name"])
    return preview


def _exchange_stats(previews: list[dict]) -> dict:
    """Compute summary statistics for exchange preview."""
    total_units = len(previews)
    total_new = sum(
        1 for p in previews for o in p["new_owners"] if o["match_type"] == "new"
    )
    total_reused = sum(
        1 for p in previews for o in p["new_owners"] if o["match_type"] == "reuse"
    )
    total_possible = sum(
        1 for p in previews for o in p["new_owners"] if o["match_type"] == "possible"
    )
    return {
        "total_units": total_units,
        "total_new": total_new,
        "total_reused": total_reused,
        "total_possible": total_possible,
    }
