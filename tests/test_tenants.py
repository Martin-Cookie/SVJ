"""Testy pro Tenant model + dedup helper + create endpoint."""
from datetime import datetime

from app.models import Owner, OwnerType, Space, SpaceStatus, SpaceTenant, Tenant
from app.routers.tenants._helpers import find_existing_tenant


def _mk_tenant(db, **kw):
    defaults = dict(
        tenant_type=OwnerType.PHYSICAL,
        is_active=True,
        data_source="manual",
        created_at=datetime(2026, 1, 1),
    )
    defaults.update(kw)
    t = Tenant(**defaults)
    db.add(t)
    db.flush()
    return t


def _mk_space(db, number, designation="Byt"):
    s = Space(
        space_number=number, designation=designation,
        status=SpaceStatus.RENTED, created_at=datetime(2026, 1, 1),
    )
    db.add(s)
    db.flush()
    return s


def _mk_rel(db, space, tenant, rent=0.0):
    st = SpaceTenant(
        space_id=space.id, tenant_id=tenant.id,
        monthly_rent=rent, is_active=True, created_at=datetime(2026, 1, 1),
    )
    db.add(st)
    db.flush()
    return st


# ── resolved properties ────────────────────────────────────────────────


def test_resolved_birth_number_standalone(db_session):
    t = _mk_tenant(db_session, first_name="Jan", last_name="Novak",
                   name_normalized="novak jan", birth_number="800101/1234")
    assert t.resolved_birth_number == "800101/1234"
    assert t.resolved_company_id == ""


def test_resolved_fields_linked_from_owner(db_session):
    owner = Owner(
        first_name="Jana", last_name="Svobodova",
        name_with_titles="Svobodova Jana", name_normalized="svobodova jana",
        owner_type=OwnerType.PHYSICAL, birth_number="755050/0000",
        phone="777", email="jana@example.com", is_active=True,
    )
    db_session.add(owner)
    db_session.flush()
    t = _mk_tenant(db_session, owner_id=owner.id)
    assert t.resolved_birth_number == "755050/0000"
    assert t.resolved_phone == "777"
    assert t.resolved_email == "jana@example.com"
    assert t.resolved_type == OwnerType.PHYSICAL
    assert t.is_linked is True


def test_resolved_birth_number_linked_empty_falls_through(db_session):
    """Pokud linked Owner nemá RČ, vrací se prázdný string (ne None)."""
    owner = Owner(
        first_name="Karel", last_name="Dvorak",
        name_with_titles="Dvorak Karel", name_normalized="dvorak karel",
        owner_type=OwnerType.PHYSICAL, is_active=True,
    )
    db_session.add(owner)
    db_session.flush()
    t = _mk_tenant(db_session, owner_id=owner.id, birth_number="IGNORED")
    # Linked: fallback na Owner.birth_number, ne na vlastní
    assert t.resolved_birth_number == ""


# ── active_space_rels sorting ─────────────────────────────────────────


def test_active_space_rels_sorted_by_number(db_session):
    t = _mk_tenant(db_session, first_name="Petr", last_name="Chvostik",
                   name_normalized="chvostik petr")
    s8 = _mk_space(db_session, 8, "Byt velky")
    s5 = _mk_space(db_session, 5, "Byt maly")
    _mk_rel(db_session, s8, t, rent=8000)
    _mk_rel(db_session, s5, t, rent=5000)
    rels = t.active_space_rels
    assert [r.space.space_number for r in rels] == [5, 8]
    assert t.active_space_rel.space.space_number == 5


def test_active_space_rels_ignores_inactive(db_session):
    t = _mk_tenant(db_session, first_name="X", last_name="Y", name_normalized="y x")
    s1 = _mk_space(db_session, 1)
    rel = _mk_rel(db_session, s1, t)
    rel.is_active = False
    db_session.flush()
    assert t.active_space_rels == []
    assert t.active_space_rel is None


# ── find_existing_tenant — priority chain ────────────────────────────


def test_find_existing_by_birth_number(db_session):
    _mk_tenant(db_session, first_name="A", last_name="B",
               name_normalized="b a", birth_number="111/11")
    found = find_existing_tenant(db_session, birth_number="111/11")
    assert found is not None
    assert found.birth_number == "111/11"


def test_find_existing_by_company_id(db_session):
    _mk_tenant(db_session, tenant_type=OwnerType.LEGAL_ENTITY,
               first_name="Firma", last_name="", name_normalized="firma",
               company_id="12345678")
    found = find_existing_tenant(db_session, company_id="12345678")
    assert found is not None


def test_find_existing_by_name_and_type(db_session):
    _mk_tenant(db_session, first_name="Jan", last_name="Novak",
               name_normalized="novak jan", tenant_type=OwnerType.PHYSICAL)
    # Stejné jméno, stejný typ → match
    found = find_existing_tenant(
        db_session, first_name="Jan", last_name="Novak",
        tenant_type=OwnerType.PHYSICAL,
    )
    assert found is not None
    # Stejné jméno, jiný typ → ne
    none_found = find_existing_tenant(
        db_session, first_name="Jan", last_name="Novak",
        tenant_type=OwnerType.LEGAL_ENTITY,
    )
    assert none_found is None


def test_find_existing_none_for_unknown(db_session):
    assert find_existing_tenant(db_session, birth_number="999/99") is None


# ── tenant_create endpoint — duplicate handling ──────────────────────


def test_tenant_create_shows_duplicates_warning(client, db_session):
    _mk_tenant(db_session, first_name="Jan", last_name="Novak",
               name_normalized="novak jan", tenant_type=OwnerType.PHYSICAL)
    db_session.commit()
    resp = client.post("/najemci/novy", data={
        "first_name": "Jan", "last_name": "Novak", "tenant_type": "physical",
    })
    assert resp.status_code == 200
    assert "duplicit" in resp.text.lower() or "již existuje" in resp.text.lower() or "force_create" in resp.text
    # Druhý Tenant se nevytvořil
    assert db_session.query(Tenant).filter(Tenant.name_normalized == "novak jan").count() == 1


def test_tenant_create_force_create_bypasses(client, db_session):
    _mk_tenant(db_session, first_name="Jan", last_name="Novak",
               name_normalized="novak jan", tenant_type=OwnerType.PHYSICAL)
    db_session.commit()
    resp = client.post(
        "/najemci/novy",
        data={
            "first_name": "Jan", "last_name": "Novak",
            "tenant_type": "physical", "force_create": "1",
        },
        follow_redirects=False,
    )
    assert resp.status_code in (200, 302)
    assert db_session.query(Tenant).filter(Tenant.name_normalized == "novak jan").count() == 2


def test_tenant_create_no_xss_in_duplicate_warning(client, db_session):
    """Regresní test: HTMX response nesmí obsahovat nevalidované HTML ve jménu."""
    _mk_tenant(
        db_session,
        first_name="<script>alert(1)</script>", last_name="Hacker",
        name_normalized="hacker <script>alert(1)</script>",
        tenant_type=OwnerType.PHYSICAL,
    )
    db_session.commit()
    resp = client.post(
        "/najemci/novy",
        data={"first_name": "<script>alert(1)</script>", "last_name": "Hacker",
              "tenant_type": "physical"},
        headers={"HX-Request": "true"},
    )
    # Jinja2 autoescape musí escapovat
    assert "<script>alert(1)</script>" not in resp.text
    assert "&lt;script&gt;" in resp.text or "duplicit" in resp.text.lower()
