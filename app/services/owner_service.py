"""
Owner service — shared owner operations (merge, duplicate detection).
"""
from __future__ import annotations

from datetime import date

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.models import Owner, OwnerUnit
from app.utils import utcnow


def merge_owners(target: Owner, duplicates: list[Owner], db: Session) -> None:
    """Merge duplicate owners into target.

    - Transfers OwnerUnit records to target (soft-deletes if duplicate unit)
    - Copies missing contact info (email, phone, addresses)
    - Deactivates duplicates (is_active = False)
    """
    existing_unit_ids = {ou.unit_id for ou in target.current_units}

    for dup in duplicates:
        if dup.id == target.id:
            continue

        # Transfer unit assignments
        for ou in list(dup.units):
            if ou.unit_id not in existing_unit_ids or ou.valid_to is not None:
                ou.owner_id = target.id
                existing_unit_ids.add(ou.unit_id)
            else:
                # Duplicate unit assignment — deactivate the duplicate's
                ou.valid_to = date.today()

        # Smart contact merge — don't lose different values
        # Each group: values from dup fill first empty slot in target
        for fields in [("email", "email_secondary"), ("phone", "phone_secondary", "phone_landline")]:
            target_vals = {getattr(target, f) for f in fields} - {None, ""}
            for dup_field in fields:
                val = getattr(dup, dup_field)
                if not val or val in target_vals:
                    continue
                # New value — place into first empty slot
                for tgt_field in fields:
                    if not getattr(target, tgt_field):
                        setattr(target, tgt_field, val)
                        break
                target_vals.add(val)

        # Copy addresses if target is missing
        for prefix in ("perm", "corr"):
            if not getattr(target, f"{prefix}_street") and getattr(dup, f"{prefix}_street"):
                for suffix in ("street", "district", "city", "zip", "country"):
                    setattr(target, f"{prefix}_{suffix}", getattr(dup, f"{prefix}_{suffix}"))

        # Deactivate the duplicate
        dup.is_active = False
        dup.updated_at = utcnow()

    target.updated_at = utcnow()


def find_duplicate_groups(db: Session) -> list[dict]:
    """Find groups of active owners with the same name_normalized.

    Returns list of dicts:
        {
            "name_normalized": str,
            "owners": [Owner, ...],
            "recommended_id": int,  # ID of the recommended merge target
        }
    Sorted by name_normalized.
    """
    # Find name_normalized values with more than one active owner
    dupes = (
        db.query(Owner.name_normalized, func.count(Owner.id).label("cnt"))
        .filter(Owner.is_active == True, Owner.name_normalized != "")
        .group_by(Owner.name_normalized)
        .having(func.count(Owner.id) > 1)
        .order_by(Owner.name_normalized)
        .all()
    )

    groups = []
    for name_norm, _cnt in dupes:
        owners = (
            db.query(Owner)
            .options(joinedload(Owner.units).joinedload(OwnerUnit.unit))
            .filter(Owner.name_normalized == name_norm, Owner.is_active == True)
            .order_by(Owner.created_at)
            .all()
        )
        if len(owners) < 2:
            continue

        # Recommend: prefer excel source with most units, then oldest
        def _score(o):
            source_priority = 0 if o.data_source == "excel" else (1 if o.data_source == "manual" else 2)
            unit_count = len(o.current_units)
            return (source_priority, -unit_count, o.created_at or datetime.min)

        recommended = min(owners, key=_score)

        groups.append({
            "name_normalized": name_norm,
            "owners": owners,
            "recommended_id": recommended.id,
        })

    return groups
