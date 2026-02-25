"""
Owner exchange service — replace owners on a unit during sync.

Handles the case where the number or identity of owners changes
(e.g. 1 owner → 5 owners, or 2 → 1).
"""
from __future__ import annotations

import re
from datetime import date, datetime
from difflib import SequenceMatcher

from sqlalchemy.orm import Session

from app.models import (
    ImportLog, Owner, OwnerUnit, OwnerType, SyncRecord, SyncResolution,
    SyncSession, SyncStatus, Unit,
)
from app.services.owner_matcher import match_name, normalize_for_matching


def recalculate_unit_votes(unit, db: Session):
    """Přepočítá hlasy všech aktivních vlastníků jednotky dle podíl_scd * share.

    Zajistí, že sum(votes) == unit.podil_scd (zbytky se rozmístí).
    """
    ous = db.query(OwnerUnit).filter_by(unit_id=unit.id).filter(OwnerUnit.valid_to.is_(None)).all()
    total = unit.podil_scd or 0
    if not ous or not total:
        for ou in ous:
            ou.votes = 0
        return
    raw = [(ou, total * ou.share) for ou in ous]
    for ou, r in raw:
        ou.votes = int(r)
    remainder = total - sum(ou.votes for ou in ous)
    raw.sort(key=lambda x: -(x[1] - int(x[1])))
    for i in range(remainder):
        raw[i][0].votes += 1


def _split_votes(total_votes: int, num_owners: int) -> list[int]:
    """Split votes evenly; remainder goes to the first N owners."""
    if num_owners <= 0:
        return []
    base = total_votes // num_owners
    remainder = total_votes % num_owners
    return [base + (1 if i < remainder else 0) for i in range(num_owners)]


def _parse_csv_name(csv_name: str) -> tuple[str, str | None]:
    """Parse a single CSV name 'příjmení jméno' → (first_name, last_name).

    For legal entities (containing s.r.o., a.s., etc.) return the whole
    string as first_name with no last_name.
    """
    name = csv_name.strip()
    if not name:
        return ("", None)
    # Legal entity markers
    if re.search(r'\b(s\.r\.o\.|a\.s\.|spol\.|z\.s\.|v\.o\.s\.)\b', name, re.IGNORECASE):
        return (name, None)
    parts = name.split(None, 1)
    if len(parts) == 2:
        # CSV format: "příjmení jméno" → first word = last_name, rest = first_name
        return (parts[1], parts[0])
    return (parts[0], None)


def _split_csv_names(csv_owner_name: str) -> list[str]:
    """Split a CSV owner name field into individual names."""
    names = re.split(r'\s*[;,]\s*', csv_owner_name.strip())
    return [n.strip() for n in names if n.strip()]


def _find_existing_owner(
    db: Session,
    csv_name: str,
    active_owners: list[dict],
) -> tuple[str, Owner | None, float]:
    """Find an existing owner matching csv_name.

    Returns (match_type, owner_or_none, confidence).
    match_type: "reuse" | "possible" | "new"
    """
    norm = normalize_for_matching(csv_name)

    # 1. Exact normalized match among active owners
    exact = (
        db.query(Owner)
        .filter(Owner.name_normalized == norm, Owner.is_active == True)
        .first()
    )
    if exact:
        return ("reuse", exact, 1.0)

    # 2. Fuzzy match via match_name with threshold 0.90
    matches = match_name(csv_name, active_owners, threshold=0.90)
    if matches:
        best = matches[0]
        owner = db.query(Owner).get(best["owner_id"])
        if owner:
            return ("possible", owner, best["confidence"])

    # 3. Not found
    return ("new", None, 0.0)


def prepare_exchange_preview(
    db: Session,
    record_ids: list[int],
) -> list[dict]:
    """Build preview data for owner exchange.

    Returns a list of dicts, one per record, containing all info
    needed to render the preview template.
    """
    # Pre-load active owners for fuzzy matching
    active_owners_raw = (
        db.query(Owner)
        .filter(Owner.is_active == True)
        .all()
    )
    active_owners = [
        {"id": o.id, "name": o.name_with_titles, "name_normalized": o.name_normalized}
        for o in active_owners_raw
    ]

    results = []
    for rid in record_ids:
        record = db.query(SyncRecord).get(rid)
        if not record or record.status != SyncStatus.DIFFERENCE:
            continue

        # Parse CSV names
        csv_names = _split_csv_names(record.csv_owner_name or "")
        if not csv_names:
            continue

        # Find unit
        unit = (
            db.query(Unit)
            .filter(Unit.unit_number == int(record.unit_number))
            .first()
        ) if record.unit_number else None
        if not unit:
            continue

        # Current owner_units (only active — valid_to IS NULL)
        current_ous = db.query(OwnerUnit).filter_by(unit_id=unit.id).filter(OwnerUnit.valid_to.is_(None)).all()
        current_owners = []
        for ou in current_ous:
            owner = db.query(Owner).get(ou.owner_id)
            if owner:
                current_owners.append({
                    "id": owner.id,
                    "name": owner.name_with_titles,
                    "votes": ou.votes,
                    "ownership_type": ou.ownership_type,
                })

        # Match each CSV name
        new_owners_preview = []
        for csv_name in csv_names:
            match_type, owner, confidence = _find_existing_owner(db, csv_name, active_owners)
            first_name, last_name = _parse_csv_name(csv_name)
            entry = {
                "csv_name": csv_name,
                "first_name": first_name,
                "last_name": last_name,
                "match_type": match_type,  # reuse / possible / new
                "confidence": confidence,
                "existing_owner_id": owner.id if owner else None,
                "existing_owner_name": owner.name_with_titles if owner else None,
            }
            new_owners_preview.append(entry)

        # Calculate vote split
        total_votes = unit.podil_scd or 0
        votes_split = _split_votes(total_votes, len(csv_names))
        for i, entry in enumerate(new_owners_preview):
            entry["votes"] = votes_split[i] if i < len(votes_split) else 0

        # Check for space_type / ownership_type changes
        space_type_changed = (
            record.csv_space_type and record.excel_space_type
            and record.csv_space_type != record.excel_space_type
        )
        ownership_type_changed = (
            record.csv_ownership_type and record.excel_ownership_type
            and record.csv_ownership_type != record.excel_ownership_type
        )

        results.append({
            "record": record,
            "unit": unit,
            "current_owners": current_owners,
            "new_owners": new_owners_preview,
            "total_votes": total_votes,
            "votes_evenly_split": len(csv_names) > 1,
            "space_type_changed": space_type_changed,
            "ownership_type_changed": ownership_type_changed,
            "csv_space_type": record.csv_space_type,
            "excel_space_type": record.excel_space_type,
            "csv_ownership_type": record.csv_ownership_type,
            "excel_ownership_type": record.excel_ownership_type,
        })

    return results


def execute_exchange(
    db: Session,
    record_ids: list[int],
    session_id: int,
    exchange_date: date | None = None,
) -> dict:
    """Execute the owner exchange for given records.

    Returns a summary dict with counts.
    """
    if exchange_date is None:
        exchange_date = date.today()
    now = datetime.now().strftime("%d.%m.%Y %H:%M")
    session = db.query(SyncSession).get(session_id)

    # Pre-load active owners for matching
    active_owners_raw = (
        db.query(Owner)
        .filter(Owner.is_active == True)
        .all()
    )
    active_owners = [
        {"id": o.id, "name": o.name_with_titles, "name_normalized": o.name_normalized}
        for o in active_owners_raw
    ]

    success_count = 0
    new_owners_count = 0
    reused_count = 0
    deactivated_count = 0
    change_details = []

    for rid in record_ids:
        record = db.query(SyncRecord).get(rid)
        if not record or record.status != SyncStatus.DIFFERENCE:
            continue

        csv_names = _split_csv_names(record.csv_owner_name or "")
        if not csv_names:
            continue

        unit = (
            db.query(Unit)
            .filter(Unit.unit_number == int(record.unit_number))
            .first()
        ) if record.unit_number else None
        if not unit:
            continue

        # Collect old OwnerUnits
        old_ous = db.query(OwnerUnit).filter_by(unit_id=unit.id).filter(OwnerUnit.valid_to.is_(None)).all()
        old_owner_names = []
        ou_by_owner_id = {}
        for ou in old_ous:
            o = db.query(Owner).get(ou.owner_id)
            if o:
                old_owner_names.append(o.name_with_titles)
                ou_by_owner_id[o.id] = ou

        # Match each CSV name to existing owners on this unit
        matched_owner_ids = set()  # DB owner IDs that match a CSV name
        new_owner_names = []
        unmatched_csv_names = []

        for csv_name in csv_names:
            match_type, existing_owner, confidence = _find_existing_owner(
                db, csv_name, active_owners,
            )

            if match_type in ("reuse", "possible") and existing_owner:
                if existing_owner.id in ou_by_owner_id:
                    # Owner already on this unit — keep existing OwnerUnit
                    matched_owner_ids.add(existing_owner.id)
                    new_owner_names.append(existing_owner.name_with_titles)
                    # Update ownership_type if CSV has a different value
                    if record.csv_ownership_type:
                        ou_by_owner_id[existing_owner.id].ownership_type = record.csv_ownership_type
                    reused_count += 1
                else:
                    # Owner exists but not on this unit — need new OwnerUnit
                    unmatched_csv_names.append((csv_name, existing_owner))
                    reused_count += 1
            else:
                unmatched_csv_names.append((csv_name, None))

        # Soft-delete only OwnerUnits for owners NOT matched to any CSV name
        removed_owner_ids = []
        for ou in old_ous:
            if ou.owner_id not in matched_owner_ids:
                ou.valid_to = exchange_date
                removed_owner_ids.append(ou.owner_id)
        db.flush()

        # Create new OwnerUnit records only for unmatched CSV names
        for csv_name, existing_owner in unmatched_csv_names:
            if existing_owner:
                owner = existing_owner
            else:
                # Create new owner
                first_name, last_name = _parse_csv_name(csv_name)
                is_legal = last_name is None and first_name and re.search(
                    r'\b(s\.r\.o\.|a\.s\.|spol\.|z\.s\.|v\.o\.s\.)\b',
                    first_name, re.IGNORECASE,
                )
                owner = Owner(
                    first_name=first_name or csv_name,
                    last_name=last_name,
                    name_with_titles=csv_name,
                    name_normalized=normalize_for_matching(csv_name),
                    owner_type=OwnerType.LEGAL_ENTITY if is_legal else OwnerType.PHYSICAL,
                    data_source="csv_sync",
                    is_active=True,
                )
                db.add(owner)
                db.flush()
                active_owners.append({
                    "id": owner.id,
                    "name": owner.name_with_titles,
                    "name_normalized": owner.name_normalized,
                })
                new_owners_count += 1

            ou = OwnerUnit(
                owner_id=owner.id,
                unit_id=unit.id,
                ownership_type=record.csv_ownership_type or "",
                share=1.0 / len(csv_names) if len(csv_names) > 1 else 1.0,
                votes=0,  # will be recalculated below
                valid_from=exchange_date,
            )
            db.add(ou)
            new_owner_names.append(owner.name_with_titles)

        # Flush new OwnerUnits so the deactivation check sees them
        # (session has autoflush=False)
        db.flush()

        # Recalculate votes for all current OwnerUnits on this unit
        current_ous = db.query(OwnerUnit).filter_by(unit_id=unit.id).filter(OwnerUnit.valid_to.is_(None)).all()
        votes_split = _split_votes(unit.podil_scd or 0, len(current_ous))
        for i, cou in enumerate(current_ous):
            cou.votes = votes_split[i] if i < len(votes_split) else 0
            cou.share = 1.0 / len(current_ous) if len(current_ous) > 1 else 1.0

        # Count removed owners that have no remaining active units
        for oid in removed_owner_ids:
            remaining = db.query(OwnerUnit).filter_by(owner_id=oid).filter(OwnerUnit.valid_to.is_(None)).count()
            if remaining == 0:
                deactivated_count += 1

        # Update unit space_type and ownership_type if CSV differs
        if record.csv_space_type and record.csv_space_type != (unit.space_type or ""):
            unit.space_type = record.csv_space_type
        # ownership_type is on OwnerUnit, already set above

        # Update SyncRecord
        record.status = SyncStatus.MATCH
        record.resolution = SyncResolution.EXCHANGED
        record.excel_owner_name = record.csv_owner_name
        record.excel_space_type = record.csv_space_type or record.excel_space_type
        record.excel_ownership_type = record.csv_ownership_type or record.excel_ownership_type

        # Admin note
        note_parts = [
            f"Výměna vlastníků ({now}):",
            f"  Staří: {'; '.join(old_owner_names) or '—'}",
            f"  Noví: {'; '.join(new_owner_names)}",
        ]
        if len(csv_names) > 1:
            note_parts.append(f"  Hlasy: {'/'.join(str(v) for v in votes_split)} — nutno zkontrolovat na LV")
        else:
            note_parts.append("  Nutno zkontrolovat na LV")
        note = "\n".join(note_parts)
        record.admin_note = (record.admin_note + "\n" if record.admin_note else "") + note

        success_count += 1
        change_details.append(
            f"J. {record.unit_number}: {'; '.join(old_owner_names)} → {'; '.join(new_owner_names)}"
        )

    # Recalculate session totals
    if session:
        all_records = db.query(SyncRecord).filter_by(session_id=session_id).all()
        session.total_matches = sum(1 for r in all_records if r.status == SyncStatus.MATCH)
        session.total_name_order = sum(1 for r in all_records if r.status == SyncStatus.NAME_ORDER)
        session.total_differences = sum(1 for r in all_records if r.status == SyncStatus.DIFFERENCE)
        session.total_missing = sum(
            1 for r in all_records
            if r.status in (SyncStatus.MISSING_CSV, SyncStatus.MISSING_EXCEL)
        )

    # Log
    if change_details:
        log = ImportLog(
            filename=f"sync_session_{session_id}",
            file_path=f"sync_exchange/{session_id}",
            import_type="sync_exchange",
            rows_total=len(record_ids),
            rows_imported=success_count,
            rows_skipped=len(record_ids) - success_count,
            errors="\n".join(change_details),
        )
        db.add(log)

    db.commit()

    return {
        "success": success_count,
        "new_owners": new_owners_count,
        "reused": reused_count,
        "deactivated": deactivated_count,
        "details": change_details,
    }
