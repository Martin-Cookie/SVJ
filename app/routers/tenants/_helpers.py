from __future__ import annotations

import logging

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.models import Owner, OwnerType, Space, SpaceTenant, Tenant
from app.utils import strip_diacritics, templates

logger = logging.getLogger(__name__)


SORT_COLUMNS = {
    "name": None,  # Python-side — resolved from owner or own fields
    "type": None,  # Python-side — resolved type
    "phone": None,  # Python-side — resolved phone
    "email": None,  # Python-side — resolved email
    "space": None,  # Python-side — active space number
    "rent": None,  # Python-side — active rent
}


def _filter_tenants(db: Session, q="", typ="", stav="", sort="name", order="asc"):
    """Filter and sort tenants. Returns list[Tenant] with eager-loaded relations."""
    query = db.query(Tenant).options(
        joinedload(Tenant.owner),
        joinedload(Tenant.spaces).joinedload(SpaceTenant.space),
    )

    if stav == "active":
        query = query.filter(Tenant.is_active == True)  # noqa: E712
    elif stav == "inactive":
        query = query.filter(Tenant.is_active == False)  # noqa: E712

    if typ == "physical":
        query = query.filter(
            ((Tenant.owner_id.isnot(None)) & Tenant.owner.has(Owner.owner_type == OwnerType.PHYSICAL))
            | ((Tenant.owner_id.is_(None)) & (Tenant.tenant_type == OwnerType.PHYSICAL))
        )
    elif typ == "legal":
        query = query.filter(
            ((Tenant.owner_id.isnot(None)) & Tenant.owner.has(Owner.owner_type == OwnerType.LEGAL_ENTITY))
            | ((Tenant.owner_id.is_(None)) & (Tenant.tenant_type == OwnerType.LEGAL_ENTITY))
        )
    elif typ == "linked":
        query = query.filter(Tenant.owner_id.isnot(None))
    elif typ == "standalone":
        query = query.filter(Tenant.owner_id.is_(None))

    tenants = query.all()

    # Text search (Python-side for resolved fields)
    if q:
        search_ascii = strip_diacritics(q)
        filtered = []
        for t in tenants:
            if (search_ascii in (t.resolved_name_normalized or "")
                    or q.lower() in (t.resolved_email or "").lower()
                    or q in (t.resolved_phone or "")
                    or q in (t.birth_number or "")
                    or q in (t.company_id or "")):
                filtered.append(t)
            else:
                # Search in space designation
                asr = t.active_space_rel
                if asr and q.lower() in (asr.space.designation or "").lower():
                    filtered.append(t)
        tenants = filtered

    # Python-side sort
    sort_fns = {
        "name": lambda t: t.resolved_name_normalized or "",
        "type": lambda t: (t.resolved_type or OwnerType.PHYSICAL).value,
        "phone": lambda t: t.resolved_phone or "",
        "email": lambda t: t.resolved_email or "",
        "space": lambda t: (t.active_space_rel.space.space_number if t.active_space_rel else 0),
        "rent": lambda t: (t.active_space_rel.monthly_rent if t.active_space_rel else 0),
    }
    fn = sort_fns.get(sort, sort_fns["name"])
    tenants.sort(key=fn, reverse=(order == "desc"))

    return tenants


def _tenant_stats(db: Session):
    """Compute stats for tenant list page."""
    total = db.query(Tenant).count()
    active = db.query(Tenant).filter(Tenant.is_active == True).count()  # noqa: E712
    linked = db.query(Tenant).filter(Tenant.owner_id.isnot(None)).count()
    standalone = total - linked

    # FO/PO — musíme brát resolved type (z Owner pokud propojený, jinak tenant_type)
    physical = db.query(Tenant).filter(
        ((Tenant.owner_id.isnot(None)) & Tenant.owner.has(Owner.owner_type == OwnerType.PHYSICAL))
        | ((Tenant.owner_id.is_(None)) & (Tenant.tenant_type == OwnerType.PHYSICAL))
    ).count()
    legal = db.query(Tenant).filter(
        ((Tenant.owner_id.isnot(None)) & Tenant.owner.has(Owner.owner_type == OwnerType.LEGAL_ENTITY))
        | ((Tenant.owner_id.is_(None)) & (Tenant.tenant_type == OwnerType.LEGAL_ENTITY))
    ).count()

    return {
        "total": total,
        "active": active,
        "inactive": total - active,
        "linked": linked,
        "standalone": standalone,
        "physical": physical,
        "legal": legal,
    }
