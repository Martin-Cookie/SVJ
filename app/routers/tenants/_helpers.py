from __future__ import annotations

import logging

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.models import Owner, OwnerType, Space, SpaceTenant, Tenant
from app.utils import strip_diacritics, templates

logger = logging.getLogger(__name__)


def find_existing_tenant(
    db: Session,
    *,
    owner_id: int | None = None,
    birth_number: str | None = None,
    company_id: str | None = None,
    first_name: str | None = None,
    last_name: str | None = None,
    tenant_type: OwnerType | None = None,
) -> Tenant | None:
    """Najít existujícího nájemce podle (v pořadí priority):
    owner_id → birth_number → company_id → jméno+typ.
    Vrací None pokud nic nevyhovuje.
    """
    if owner_id:
        t = db.query(Tenant).filter(Tenant.owner_id == owner_id).first()
        if t:
            return t
    if birth_number and birth_number.strip():
        t = db.query(Tenant).filter(Tenant.birth_number == birth_number.strip()).first()
        if t:
            return t
    if company_id and company_id.strip():
        t = db.query(Tenant).filter(Tenant.company_id == company_id.strip()).first()
        if t:
            return t
    ln = (last_name or "").strip()
    fn = (first_name or "").strip()
    if ln or fn:
        ln_norm = strip_diacritics(ln) if ln and ln != "*" else ""
        fn_norm = strip_diacritics(fn) if fn and fn != "*" else ""
        name_norm = f"{ln_norm} {fn_norm}".strip()
        if name_norm:
            q = db.query(Tenant).filter(
                Tenant.owner_id.is_(None),
                Tenant.name_normalized == name_norm,
            )
            if tenant_type:
                q = q.filter(Tenant.tenant_type == tenant_type)
            t = q.first()
            if t:
                return t
    return None


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

    # Deduplikace — joinedload na spaces může vrátit duplicity
    seen_ids = set()
    unique_tenants = []
    for t in tenants:
        if t.id not in seen_ids:
            seen_ids.add(t.id)
            unique_tenants.append(t)
    tenants = unique_tenants

    # Text search (Python-side for resolved fields)
    if q:
        search_ascii = strip_diacritics(q)
        filtered = []
        for t in tenants:
            if (search_ascii in (t.resolved_name_normalized or "")
                    or q.lower() in (t.resolved_email or "").lower()
                    or q in (t.resolved_phone or "")
                    or q in (t.resolved_birth_number or "")
                    or q in (t.resolved_company_id or "")):
                filtered.append(t)
            else:
                # Search in designation of any active space
                for sr in t.active_space_rels:
                    if sr.space and q.lower() in (sr.space.designation or "").lower():
                        filtered.append(t)
                        break
        tenants = filtered

    # Python-side sort — cache active rels per tenant (property je neindexovaná)
    rels_cache = {t.id: t.active_space_rels for t in tenants}
    sort_fns = {
        "name": lambda t: t.resolved_name_normalized or "",
        "type": lambda t: (t.resolved_type or OwnerType.PHYSICAL).value,
        "phone": lambda t: t.resolved_phone or "",
        "email": lambda t: t.resolved_email or "",
        "space": lambda t: (rels_cache[t.id][0].space.space_number if rels_cache[t.id] else 0),
        "rent": lambda t: sum((sr.monthly_rent or 0) for sr in rels_cache[t.id]),
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
