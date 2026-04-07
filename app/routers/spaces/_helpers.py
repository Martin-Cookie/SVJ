from __future__ import annotations

import json
import logging

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.models import Space, SpaceStatus, SpaceTenant, SvjInfo, Tenant
from app.utils import strip_diacritics, templates

logger = logging.getLogger(__name__)


SORT_COLUMNS = {
    "space_number": Space.space_number,
    "designation": Space.designation,
    "section": Space.section,
    "floor": Space.floor,
    "area": Space.area,
    "status": Space.status,
    "rent": None,  # Python-side — z SpaceTenant
    "tenant": None,  # Python-side — jméno nájemce
}


def _filter_spaces(db: Session, q="", stav="", sekce="", najemce="", sort="space_number", order="asc"):
    """Filter and sort spaces. Returns list[Space] with eager-loaded tenants."""
    query = db.query(Space).options(
        joinedload(Space.tenants).joinedload(SpaceTenant.tenant).joinedload(Tenant.owner)
    )

    if q:
        search_ascii = f"%{strip_diacritics(q)}%"
        search = f"%{q}%"
        query = query.filter(
            Space.designation.ilike(search)
            | Space.section.ilike(search)
            | Space.note.ilike(search)
            | Space.tenants.any(
                SpaceTenant.is_active
                & SpaceTenant.tenant.has(Tenant.name_normalized.like(search_ascii))
            )
        )
    if stav:
        query = query.filter(Space.status == stav)
    if sekce:
        query = query.filter(Space.section == sekce)
    if najemce == "with":
        query = query.filter(Space.tenants.any(SpaceTenant.is_active == True))  # noqa: E712
    elif najemce == "without":
        query = query.filter(~Space.tenants.any(SpaceTenant.is_active == True))  # noqa: E712

    # SQL sort
    sort_col = SORT_COLUMNS.get(sort)
    if sort_col is not None:
        if order == "desc":
            query = query.order_by(sort_col.desc().nulls_last())
        else:
            query = query.order_by(sort_col.asc().nulls_last())
        spaces = query.all()
    else:
        spaces = query.order_by(Space.space_number).all()

    # Python-side sort
    if sort == "rent":
        def _rent(s):
            at = s.active_tenant_rel
            return at.monthly_rent if at else 0
        spaces.sort(key=_rent, reverse=(order == "desc"))
    elif sort == "tenant":
        def _tenant_name(s):
            at = s.active_tenant_rel
            return at.tenant.resolved_name_normalized if at else ""
        spaces.sort(key=_tenant_name, reverse=(order == "desc"))

    return spaces


def _space_stats(db: Session):
    """Compute stats for space list page."""
    total = db.query(Space).count()
    status_counts = dict(
        db.query(Space.status, func.count(Space.id))
        .group_by(Space.status).all()
    )
    sections = [
        r[0] for r in
        db.query(Space.section).filter(Space.section.isnot(None))
        .distinct().order_by(Space.section).all()
    ]
    total_rent = db.query(func.sum(SpaceTenant.monthly_rent)).filter(
        SpaceTenant.is_active
    ).scalar() or 0
    with_tenant = db.query(Space).filter(
        Space.tenants.any(SpaceTenant.is_active == True)  # noqa: E712
    ).count()

    return {
        "total": total,
        "rented": status_counts.get(SpaceStatus.RENTED, 0),
        "vacant": status_counts.get(SpaceStatus.VACANT, 0),
        "blocked": status_counts.get(SpaceStatus.BLOCKED, 0),
        "sections": sections,
        "total_rent": total_rent,
        "with_tenant": with_tenant,
        "without_tenant": total - with_tenant,
    }


def _load_space_mapping(db: Session):
    """Load saved space import mapping from SvjInfo."""
    info = db.query(SvjInfo).first()
    if info and info.space_import_mapping:
        try:
            return json.loads(info.space_import_mapping)
        except (json.JSONDecodeError, TypeError):
            pass
    return None


def _save_space_mapping(db: Session, mapping: dict):
    """Save space import mapping to SvjInfo."""
    info = db.query(SvjInfo).first()
    if info:
        info.space_import_mapping = json.dumps(mapping, ensure_ascii=False)
        db.commit()
