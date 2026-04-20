from __future__ import annotations

import json
import logging

from markupsafe import escape
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.models import Owner, OwnerType, OwnerUnit, SvjInfo, Unit, WaterMeter
from app.services.code_list_service import get_all_code_lists
from app.utils import strip_diacritics, templates

logger = logging.getLogger(__name__)


SORT_COLUMNS = {
    "name": Owner.name_normalized,
    "type": Owner.owner_type,
    "email": Owner.email,
    "phone": Owner.phone,
    "podil": None,  # handled in Python — needs sum across units
    "jednotky": None,  # handled in Python
    "sekce": None,  # handled in Python
    "vodometry": None,  # handled in Python — count of water meters
}


def _filter_owners(db: Session, q="", owner_type="", vlastnictvi="", kontakt="", stav="", sekce="", sort="name", order="asc"):
    """Filter and sort owners. Returns list[Owner] with eager-loaded units."""
    from sqlalchemy import cast, or_, String

    query = db.query(Owner).filter_by(is_active=True).options(
        joinedload(Owner.units).joinedload(OwnerUnit.unit)
    )
    if q:
        search = f"%{q}%"
        search_ascii = f"%{strip_diacritics(q)}%"
        query = query.filter(
            Owner.name_normalized.like(search_ascii)
            | Owner.name_with_titles.ilike(search)
            | Owner.first_name.ilike(search)
            | Owner.last_name.ilike(search)
            | Owner.email.ilike(search)
            | Owner.phone.ilike(search)
            | Owner.birth_number.ilike(search)
            | Owner.company_id.ilike(search)
            | Owner.units.any((OwnerUnit.valid_to.is_(None)) & OwnerUnit.unit.has(cast(Unit.unit_number, String).ilike(search)))
        )
    if owner_type:
        query = query.filter(Owner.owner_type == owner_type)
    if vlastnictvi == "_empty":
        query = query.filter(
            Owner.units.any(
                (OwnerUnit.valid_to.is_(None)) & ((OwnerUnit.ownership_type.is_(None)) | (OwnerUnit.ownership_type == ""))
            )
        )
    elif vlastnictvi:
        query = query.filter(
            Owner.units.any((OwnerUnit.valid_to.is_(None)) & (OwnerUnit.ownership_type == vlastnictvi))
        )
    if kontakt == "s_emailem":
        query = query.filter(or_(
            (Owner.email.isnot(None)) & (Owner.email != ""),
            (Owner.email_secondary.isnot(None)) & (Owner.email_secondary != ""),
        ))
    elif kontakt == "bez_emailu":
        query = query.filter(
            (Owner.email.is_(None)) | (Owner.email == ""),
            (Owner.email_secondary.is_(None)) | (Owner.email_secondary == ""),
        )
    elif kontakt == "s_telefonem":
        query = query.filter(Owner.phone.isnot(None), Owner.phone != "")
    elif kontakt == "bez_telefonu":
        query = query.filter((Owner.phone.is_(None)) | (Owner.phone == ""))
    if stav == "bez_jednotky":
        query = query.filter(~Owner.units.any(OwnerUnit.valid_to.is_(None)))
    if sekce:
        query = query.filter(
            Owner.units.any((OwnerUnit.valid_to.is_(None)) & OwnerUnit.unit.has(Unit.section == sekce))
        )

    # Sorting
    sort_col = SORT_COLUMNS.get(sort)
    if sort == "podil":
        # SQL subquery: sum of votes across current owner-unit assignments
        podil_sub = (
            db.query(OwnerUnit.owner_id, func.coalesce(func.sum(OwnerUnit.votes), 0).label("total_votes"))
            .filter(OwnerUnit.valid_to.is_(None))
            .group_by(OwnerUnit.owner_id)
            .subquery()
        )
        query = query.outerjoin(podil_sub, Owner.id == podil_sub.c.owner_id)
        col = podil_sub.c.total_votes
        query = query.order_by(col.desc().nulls_last() if order == "desc" else col.asc().nulls_last())
        owners = query.all()
    elif sort == "jednotky":
        # SQL subquery: min unit_number per owner
        unit_sub = (
            db.query(OwnerUnit.owner_id, func.min(Unit.unit_number).label("min_unit"))
            .join(Unit, OwnerUnit.unit_id == Unit.id)
            .filter(OwnerUnit.valid_to.is_(None))
            .group_by(OwnerUnit.owner_id)
            .subquery()
        )
        query = query.outerjoin(unit_sub, Owner.id == unit_sub.c.owner_id)
        col = unit_sub.c.min_unit
        query = query.order_by(col.desc().nulls_last() if order == "desc" else col.asc().nulls_last())
        owners = query.all()
    elif sort == "sekce":
        # SQL subquery: min section per owner
        sec_sub = (
            db.query(OwnerUnit.owner_id, func.min(Unit.section).label("min_section"))
            .join(Unit, OwnerUnit.unit_id == Unit.id)
            .filter(OwnerUnit.valid_to.is_(None))
            .group_by(OwnerUnit.owner_id)
            .subquery()
        )
        query = query.outerjoin(sec_sub, Owner.id == sec_sub.c.owner_id)
        col = sec_sub.c.min_section
        query = query.order_by(col.desc().nulls_last() if order == "desc" else col.asc().nulls_last())
        owners = query.all()
    elif sort == "vodometry":
        # SQL subquery: count of water meters per owner (via units)
        meter_sub = (
            db.query(OwnerUnit.owner_id, func.count(WaterMeter.id).label("meter_count"))
            .join(Unit, OwnerUnit.unit_id == Unit.id)
            .outerjoin(WaterMeter, WaterMeter.unit_id == Unit.id)
            .filter(OwnerUnit.valid_to.is_(None))
            .group_by(OwnerUnit.owner_id)
            .subquery()
        )
        query = query.outerjoin(meter_sub, Owner.id == meter_sub.c.owner_id)
        col = meter_sub.c.meter_count
        query = query.order_by(col.desc().nulls_last() if order == "desc" else col.asc().nulls_last())
        owners = query.all()
    elif sort_col is not None:
        if order == "desc":
            query = query.order_by(sort_col.desc().nulls_last())
        else:
            query = query.order_by(sort_col.asc().nulls_last())
        owners = query.all()
    else:
        owners = query.order_by(Owner.name_normalized).all()

    return owners


def _owner_meter_counts(db: Session) -> dict[int, int]:
    """Return {owner_id: water_meter_count} for all active owners."""
    rows = (
        db.query(OwnerUnit.owner_id, func.count(WaterMeter.id))
        .join(Unit, OwnerUnit.unit_id == Unit.id)
        .outerjoin(WaterMeter, WaterMeter.unit_id == Unit.id)
        .filter(OwnerUnit.valid_to.is_(None))
        .group_by(OwnerUnit.owner_id)
        .all()
    )
    return {owner_id: cnt for owner_id, cnt in rows}


def _format_address(owner, prefix):
    """Format address fields into a single string."""
    parts = []
    street = getattr(owner, f"{prefix}_street")
    district = getattr(owner, f"{prefix}_district")
    city = getattr(owner, f"{prefix}_city")
    zip_code = getattr(owner, f"{prefix}_zip")
    country = getattr(owner, f"{prefix}_country")
    if street:
        parts.append(street)
    if district:
        parts.append(district)
    if city and zip_code:
        parts.append(f"{zip_code} {city}")
    elif city:
        parts.append(city)
    elif zip_code:
        parts.append(zip_code)
    if country:
        parts.append(country)
    return ", ".join(parts)


def _rebuild_owner_name(owner: Owner) -> None:
    """Rebuild name_with_titles and name_normalized from identity fields."""
    parts_wt = []
    if owner.title:
        parts_wt.append(owner.title)
    if owner.last_name:
        parts_wt.append(owner.last_name)
    if owner.first_name:
        parts_wt.append(owner.first_name)
    owner.name_with_titles = " ".join(parts_wt)

    parts_norm = []
    if owner.last_name:
        parts_norm.append(owner.last_name)
    if owner.first_name:
        parts_norm.append(owner.first_name)
    owner.name_normalized = strip_diacritics(" ".join(parts_norm))


def _find_duplicate_owners(db: Session, owner: Owner) -> list[Owner]:
    """Find other active owners with the same name_normalized (potential duplicates)."""
    if not owner.name_normalized:
        return []
    return (
        db.query(Owner)
        .filter(
            Owner.id != owner.id,
            Owner.is_active == True,
            Owner.name_normalized == owner.name_normalized,
        )
        .options(joinedload(Owner.units).joinedload(OwnerUnit.unit))
        .all()
    )


def _header_oob_html(owner: Owner) -> str:
    """Build OOB swap HTML for owner display name + badges in page header."""
    name_html = (
        f'<h1 id="owner-display-name" hx-swap-oob="true"'
        f' class="text-2xl font-bold text-gray-800">{escape(owner.display_name)}</h1>'
    )
    type_badge = (
        '<span class="px-2 py-1 text-xs font-medium bg-blue-100 text-blue-800 rounded-full">Právnická osoba</span>'
        if owner.owner_type == OwnerType.LEGAL_ENTITY
        else '<span class="px-2 py-1 text-xs font-medium bg-gray-100 text-gray-800 rounded-full">Fyzická osoba</span>'
    )
    extra_badges = ""
    if owner.birth_number:
        extra_badges += f'<span class="px-2 py-1 text-xs font-medium bg-gray-50 text-gray-700 rounded border border-gray-200">RČ: {escape(owner.birth_number)}</span>'
    if owner.company_id:
        extra_badges += f'<span class="px-2 py-1 text-xs font-medium bg-gray-50 text-gray-700 rounded border border-gray-200">IČ: {escape(owner.company_id)}</span>'
    badges_html = f'<div id="owner-badges" hx-swap-oob="true" class="mt-1 flex items-center gap-2">{type_badge}{extra_badges}</div>'
    return name_html + badges_html


def _address_context(owner, prefix):
    """Extract address fields for a given prefix (perm/corr)."""
    return {
        "prefix": prefix,
        "address_label": "Trvalá adresa" if prefix == "perm" else "Korespondenční adresa",
        "street": getattr(owner, f"{prefix}_street"),
        "district": getattr(owner, f"{prefix}_district"),
        "city": getattr(owner, f"{prefix}_city"),
        "zip": getattr(owner, f"{prefix}_zip"),
        "country": getattr(owner, f"{prefix}_country"),
    }


def _owner_units_context(owner, db):
    """Helper to build context for owner_units_section partial."""
    assigned_unit_ids = [ou.unit_id for ou in owner.current_units]
    if assigned_unit_ids:
        available_units = db.query(Unit).filter(
            Unit.id.notin_(assigned_unit_ids)
        ).order_by(Unit.unit_number).all()
    else:
        available_units = db.query(Unit).order_by(Unit.unit_number).all()
    svj_info = db.query(SvjInfo).first()
    declared_shares = svj_info.total_shares if svj_info and svj_info.total_shares else 0
    return available_units, declared_shares


def _load_owner_mapping(db: Session) -> dict | None:
    """Load saved owner import mapping from SvjInfo."""
    info = db.query(SvjInfo).first()
    if info and info.owner_import_mapping:
        try:
            return json.loads(info.owner_import_mapping)
        except (json.JSONDecodeError, TypeError):
            logger.debug("Failed to parse saved owner import mapping", exc_info=True)
    return None


def _save_owner_mapping(db: Session, mapping: dict):
    """Save owner import mapping to SvjInfo."""
    info = db.query(SvjInfo).first()
    if info:
        info.owner_import_mapping = json.dumps(mapping, ensure_ascii=False)
        db.commit()


def _load_contact_mapping(db: Session) -> dict | None:
    """Load saved contact import mapping from SvjInfo."""
    info = db.query(SvjInfo).first()
    if info and info.contact_import_mapping:
        try:
            return json.loads(info.contact_import_mapping)
        except (json.JSONDecodeError, TypeError):
            logger.debug("Failed to parse saved contact import mapping", exc_info=True)
    return None


def _save_contact_mapping(db: Session, mapping: dict):
    """Save contact import mapping to SvjInfo."""
    info = db.query(SvjInfo).first()
    if info:
        info.contact_import_mapping = json.dumps(mapping, ensure_ascii=False)
        db.commit()
