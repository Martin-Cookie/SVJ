import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from sqlalchemy import inspect, text

from app.config import settings
from app.database import Base, engine

logger = logging.getLogger(__name__)


def _migrate_units_table():
    """Ensure units table has correct schema with INTEGER PRIMARY KEY.

    SQLite only auto-generates rowid for 'INTEGER PRIMARY KEY' (exact syntax).
    If the table was created with bare 'INT' or missing PK, ids will be NULL.
    Fixes this by recreating the table and re-linking owner_units via unit_number.
    """
    with engine.connect() as conn:
        result = conn.execute(text(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='units'"
        )).scalar()
        if not result:
            return
        if "PRIMARY KEY" in result.upper():
            return
        logger.info("Migrating units table: fixing INTEGER PRIMARY KEY")
        conn.execute(text("PRAGMA foreign_keys = OFF"))
        # Create new table with proper PK
        conn.execute(text("""
            CREATE TABLE units_new (
                id INTEGER NOT NULL PRIMARY KEY,
                unit_number INTEGER NOT NULL,
                building_number VARCHAR(20),
                podil_scd INTEGER,
                floor_area FLOAT,
                room_count VARCHAR(20),
                space_type VARCHAR(50),
                section VARCHAR(10),
                orientation_number INTEGER,
                address VARCHAR(200),
                lv_number INTEGER,
                created_at DATETIME
            )
        """))
        # Copy data (new ids will be auto-generated)
        conn.execute(text("""
            INSERT INTO units_new (
                unit_number, building_number, podil_scd, floor_area,
                room_count, space_type, section, orientation_number,
                address, lv_number, created_at
            )
            SELECT CAST(unit_number AS INTEGER), building_number, podil_scd,
                   floor_area, room_count, space_type, section,
                   orientation_number, address, lv_number, created_at
            FROM units
        """))
        # Re-link owner_units: old unit_id was rowid, map via unit_number
        conn.execute(text("""
            UPDATE owner_units SET unit_id = (
                SELECT un.id FROM units_new un
                WHERE un.unit_number = (
                    SELECT CAST(u.unit_number AS INTEGER) FROM units u
                    WHERE u.rowid = owner_units.unit_id
                )
            )
        """))
        conn.execute(text("DROP TABLE units"))
        conn.execute(text("ALTER TABLE units_new RENAME TO units"))
        conn.execute(text("CREATE UNIQUE INDEX ix_units_unit_number ON units (unit_number)"))
        conn.execute(text("CREATE INDEX ix_units_building_number ON units (building_number)"))
        conn.execute(text("CREATE INDEX ix_units_space_type ON units (space_type)"))
        conn.execute(text("CREATE INDEX ix_units_section ON units (section)"))
        conn.execute(text("CREATE INDEX ix_units_lv_number ON units (lv_number)"))
        conn.execute(text("PRAGMA foreign_keys = ON"))
        conn.commit()
        logger.info("Units table migration complete")


def _migrate_owner_units_history():
    """Add valid_from / valid_to columns to owner_units for ownership history."""
    with engine.connect() as conn:
        columns = [
            row[1] for row in
            conn.execute(text("PRAGMA table_info(owner_units)")).fetchall()
        ]
        if "valid_from" not in columns:
            conn.execute(text("ALTER TABLE owner_units ADD COLUMN valid_from DATE"))
            logger.info("Added valid_from column to owner_units")
        if "valid_to" not in columns:
            conn.execute(text("ALTER TABLE owner_units ADD COLUMN valid_to DATE"))
            logger.info("Added valid_to column to owner_units")
        conn.commit()


def _migrate_tax_tables():
    """Add new columns to tax_sessions and tax_distributions for send workflow."""
    with engine.connect() as conn:
        # tax_sessions
        columns = [
            row[1] for row in
            conn.execute(text("PRAGMA table_info(tax_sessions)")).fetchall()
        ]
        for col, ddl in [
            ("send_batch_size", "ALTER TABLE tax_sessions ADD COLUMN send_batch_size INTEGER DEFAULT 10"),
            ("send_batch_interval", "ALTER TABLE tax_sessions ADD COLUMN send_batch_interval INTEGER DEFAULT 5"),
            ("send_scheduled_at", "ALTER TABLE tax_sessions ADD COLUMN send_scheduled_at DATETIME"),
            ("send_status", "ALTER TABLE tax_sessions ADD COLUMN send_status VARCHAR(20) DEFAULT 'DRAFT'"),
            ("test_email_passed", "ALTER TABLE tax_sessions ADD COLUMN test_email_passed BOOLEAN DEFAULT 0"),
            ("test_email_address", "ALTER TABLE tax_sessions ADD COLUMN test_email_address VARCHAR"),
            ("send_confirm_each_batch", "ALTER TABLE tax_sessions ADD COLUMN send_confirm_each_batch BOOLEAN DEFAULT 0"),
        ]:
            if col not in columns:
                conn.execute(text(ddl))
                logger.info("Added %s column to tax_sessions", col)

        # Fix lowercase enum values from earlier migration
        conn.execute(text(
            "UPDATE tax_sessions SET send_status = 'DRAFT' WHERE send_status = 'draft'"
        ))

        # tax_distributions
        columns = [
            row[1] for row in
            conn.execute(text("PRAGMA table_info(tax_distributions)")).fetchall()
        ]
        for col, ddl in [
            ("email_status", "ALTER TABLE tax_distributions ADD COLUMN email_status VARCHAR(20) DEFAULT 'PENDING'"),
            ("email_address_used", "ALTER TABLE tax_distributions ADD COLUMN email_address_used VARCHAR(200)"),
            ("email_error", "ALTER TABLE tax_distributions ADD COLUMN email_error TEXT"),
            ("ad_hoc_name", "ALTER TABLE tax_distributions ADD COLUMN ad_hoc_name VARCHAR(300)"),
            ("ad_hoc_email", "ALTER TABLE tax_distributions ADD COLUMN ad_hoc_email VARCHAR(200)"),
        ]:
            if col not in columns:
                conn.execute(text(ddl))
                logger.info("Added %s column to tax_distributions", col)

        # Fix lowercase enum values from earlier migration
        conn.execute(text(
            "UPDATE tax_distributions SET email_status = 'PENDING' WHERE email_status = 'pending'"
        ))

        conn.commit()


def _migrate_owners_phone_secondary():
    """Add phone_secondary column to owners table."""
    with engine.connect() as conn:
        columns = [
            row[1] for row in
            conn.execute(text("PRAGMA table_info(owners)")).fetchall()
        ]
        if "phone_secondary" not in columns:
            conn.execute(text(
                "ALTER TABLE owners ADD COLUMN phone_secondary VARCHAR(50)"
            ))
            logger.info("Added phone_secondary column to owners")
        conn.commit()


def _migrate_ballots_shared_owners():
    """Add shared_owners_text column to ballots table."""
    with engine.connect() as conn:
        columns = [
            row[1] for row in
            conn.execute(text("PRAGMA table_info(ballots)")).fetchall()
        ]
        if "shared_owners_text" not in columns:
            conn.execute(text(
                "ALTER TABLE ballots ADD COLUMN shared_owners_text VARCHAR(500)"
            ))
            logger.info("Added shared_owners_text column to ballots")
        conn.commit()


def _migrate_svj_info_voting_mapping():
    """Add voting_import_mapping column to svj_info table."""
    with engine.connect() as conn:
        columns = [
            row[1] for row in
            conn.execute(text("PRAGMA table_info(svj_info)")).fetchall()
        ]
        if "voting_import_mapping" not in columns:
            conn.execute(text(
                "ALTER TABLE svj_info ADD COLUMN voting_import_mapping TEXT"
            ))
            logger.info("Added voting_import_mapping column to svj_info")
        conn.commit()


def _ensure_indexes():
    """Create indexes defined in models that may be missing on existing tables."""
    _INDEXES = [
        # voting.py
        ("ix_votings_status", "votings", "status"),
        ("ix_voting_items_voting_id", "voting_items", "voting_id"),
        ("ix_ballots_voting_id", "ballots", "voting_id"),
        ("ix_ballots_owner_id", "ballots", "owner_id"),
        ("ix_ballots_status", "ballots", "status"),
        ("ix_ballot_votes_ballot_id", "ballot_votes", "ballot_id"),
        ("ix_ballot_votes_voting_item_id", "ballot_votes", "voting_item_id"),
        # administration.py
        ("ix_svj_addresses_svj_info_id", "svj_addresses", "svj_info_id"),
        ("ix_board_members_group", "board_members", "\"group\""),
        # tax.py
        ("ix_tax_documents_session_id", "tax_documents", "session_id"),
        ("ix_tax_distributions_document_id", "tax_distributions", "document_id"),
        ("ix_tax_distributions_owner_id", "tax_distributions", "owner_id"),
        ("ix_tax_distributions_match_status", "tax_distributions", "match_status"),
        ("ix_tax_sessions_send_status", "tax_sessions", "send_status"),
        ("ix_tax_distributions_email_status", "tax_distributions", "email_status"),
        # sync.py
        ("ix_sync_records_session_id", "sync_records", "session_id"),
        ("ix_sync_records_status", "sync_records", "status"),
        ("ix_sync_records_resolution", "sync_records", "resolution"),
        # common.py
        ("ix_email_logs_status", "email_logs", "status"),
        ("ix_email_logs_module", "email_logs", "module"),
        ("ix_email_logs_reference_id", "email_logs", "reference_id"),
        ("ix_import_logs_import_type", "import_logs", "import_type"),
        # owner_units history
        ("ix_owner_units_valid_from", "owner_units", "valid_from"),
        ("ix_owner_units_valid_to", "owner_units", "valid_to"),
        # share_check.py
        ("ix_share_check_records_session_id", "share_check_records", "session_id"),
        ("ix_share_check_records_status", "share_check_records", "status"),
        ("ix_share_check_records_resolution", "share_check_records", "resolution"),
        # administration.py — code lists
        ("ix_code_list_items_category", "code_list_items", "category"),
        # activity_logs
        ("ix_activity_logs_action", "activity_logs", "action"),
        ("ix_activity_logs_entity_type", "activity_logs", "entity_type"),
        ("ix_activity_logs_module", "activity_logs", "module"),
        ("ix_activity_logs_created_at", "activity_logs", "created_at"),
    ]
    with engine.connect() as conn:
        for idx_name, table, column in _INDEXES:
            try:
                conn.execute(text(
                    f"CREATE INDEX IF NOT EXISTS {idx_name} ON {table} ({column})"
                ))
            except Exception as e:
                logger.warning("Index %s creation failed: %s", idx_name, e)
        conn.commit()
    logger.info("Database indexes ensured")


def _seed_code_lists():
    """Populate code_list_items from existing unique values if table is empty."""
    from sqlalchemy.orm import Session as _Session
    from app.models.administration import CodeListItem
    from app.models.owner import Unit, OwnerUnit

    with _Session(engine) as session:
        if session.query(CodeListItem).first() is not None:
            return  # already seeded

        _SEED_SOURCES = [
            ("space_type", Unit, "space_type"),
            ("section", Unit, "section"),
            ("room_count", Unit, "room_count"),
            ("ownership_type", OwnerUnit, "ownership_type"),
        ]
        for category, model, column in _SEED_SOURCES:
            col = getattr(model, column)
            values = (
                session.query(col)
                .filter(col.isnot(None), col != "")
                .distinct()
                .order_by(col)
                .all()
            )
            for idx, (val,) in enumerate(values):
                session.add(CodeListItem(
                    category=category,
                    value=val,
                    order=idx,
                ))
        session.commit()
        logger.info("Code lists seeded from existing data")


def _seed_email_templates():
    """Seed default email template if table is empty."""
    from sqlalchemy.orm import Session as _Session
    from app.models.administration import EmailTemplate

    with _Session(engine) as session:
        if session.query(EmailTemplate).first() is not None:
            return
        session.add(EmailTemplate(
            name="Rozúčtování příjmů",
            subject_template="Rozúčtování příjmů za rok {rok}",
            body_template="Dobrý den,\n\nv příloze zasíláme rozúčtování příjmů za rok {rok}.\n\nS pozdravem,\nSVJ",
            order=0,
        ))
        session.commit()
        logger.info("Default email template seeded")


def run_post_restore_migrations():
    """Re-connect to the (possibly replaced) database and run all migrations.

    Called after every backup restore so the server keeps running even when
    the restored DB is missing new columns or tables.
    """
    engine.dispose()  # drop stale connections to the old file

    # Create any missing tables (e.g. share_check_* from newer code)
    import app.models  # noqa: F401
    Base.metadata.create_all(bind=engine)

    try:
        _migrate_units_table()
    except Exception:
        logger.warning("post-restore: units table migration skipped")
    try:
        _migrate_owner_units_history()
    except Exception:
        logger.warning("post-restore: owner_units history migration skipped")
    try:
        _migrate_tax_tables()
    except Exception:
        logger.warning("post-restore: tax tables migration skipped")
    try:
        _migrate_owners_phone_secondary()
    except Exception:
        logger.warning("post-restore: owners phone_secondary migration skipped")
    try:
        _migrate_ballots_shared_owners()
    except Exception:
        logger.warning("post-restore: ballots shared_owners migration skipped")
    try:
        _migrate_svj_info_voting_mapping()
    except Exception:
        logger.warning("post-restore: svj_info voting_import_mapping migration skipped")
    try:
        _ensure_indexes()
    except Exception:
        logger.warning("post-restore: index creation skipped")
    try:
        _seed_code_lists()
    except Exception:
        logger.warning("post-restore: code list seeding skipped")
    try:
        _seed_email_templates()
    except Exception:
        logger.warning("post-restore: email template seeding skipped")
    try:
        from app.routers.tax import recover_stuck_sending_sessions
        recover_stuck_sending_sessions()
    except Exception:
        logger.warning("post-restore: sending session recovery skipped")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Import models so they register with Base
    import app.models  # noqa: F401

    Base.metadata.create_all(bind=engine)

    # One-time migrations
    try:
        _migrate_units_table()
    except Exception:
        logger.warning("units migration skipped (table may not exist yet)")

    # Add valid_from / valid_to to owner_units
    try:
        _migrate_owner_units_history()
    except Exception:
        logger.warning("owner_units history migration skipped")

    # Add send workflow columns to tax tables
    try:
        _migrate_tax_tables()
    except Exception:
        logger.warning("tax tables migration skipped")

    # Add phone_secondary to owners
    try:
        _migrate_owners_phone_secondary()
    except Exception:
        logger.warning("owners phone_secondary migration skipped")

    # Add shared_owners_text to ballots
    try:
        _migrate_ballots_shared_owners()
    except Exception:
        logger.warning("ballots shared_owners migration skipped")

    # Add voting_import_mapping to svj_info
    try:
        _migrate_svj_info_voting_mapping()
    except Exception:
        logger.warning("svj_info voting_import_mapping migration skipped")

    # Ensure indexes on existing tables
    try:
        _ensure_indexes()
    except Exception:
        logger.warning("index creation skipped")

    # Seed code lists from existing data
    try:
        _seed_code_lists()
    except Exception:
        logger.warning("code list seeding skipped")

    # Seed default email templates
    try:
        _seed_email_templates()
    except Exception:
        logger.warning("email template seeding skipped")

    # Recover stuck SENDING sessions (server restart recovery)
    try:
        from app.routers.tax import recover_stuck_sending_sessions
        recover_stuck_sending_sessions()
    except Exception:
        logger.warning("sending session recovery skipped")

    # Ensure data directories exist
    for d in [settings.upload_dir, settings.generated_dir, settings.temp_dir]:
        d.mkdir(parents=True, exist_ok=True)
    for sub in ["excel", "word_templates", "scanned_ballots", "tax_pdfs", "csv", "share_check"]:
        (settings.upload_dir / sub).mkdir(exist_ok=True)
    for sub in ["ballots", "exports"]:
        (settings.generated_dir / sub).mkdir(exist_ok=True)

    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)


# Custom error pages
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

_error_templates = Jinja2Templates(directory="app/templates")


@app.exception_handler(404)
async def not_found_handler(request, exc):
    return _error_templates.TemplateResponse("error.html", {
        "request": request,
        "status_code": 404,
        "title": "Stránka nenalezena",
        "message": "Požadovaná stránka neexistuje nebo byla přesunuta.",
    }, status_code=404)


@app.exception_handler(500)
async def server_error_handler(request, exc):
    return _error_templates.TemplateResponse("error.html", {
        "request": request,
        "status_code": 500,
        "title": "Chyba serveru",
        "message": "Nastala neočekávaná chyba. Zkuste to prosím znovu.",
    }, status_code=500)

# Security headers middleware
@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response

# Raise default Starlette multipart limits (default max_files=1000 is too low
# for large PDF directories uploaded via webkitdirectory)
from starlette.requests import Request as _StarletteRequest
for _method in (_StarletteRequest._get_form, _StarletteRequest.form):
    _method.__kwdefaults__["max_files"] = 5000
    _method.__kwdefaults__["max_fields"] = 5000

# Static files
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")

# Register routers
from app.routers import dashboard, owners, units, voting, tax, sync, share_check, settings_page, administration  # noqa: E402

app.include_router(dashboard.router)
app.include_router(owners.router, prefix="/vlastnici", tags=["Vlastníci"])
app.include_router(units.router, prefix="/jednotky", tags=["Jednotky"])
app.include_router(voting.router, prefix="/hlasovani", tags=["Hlasování"])
app.include_router(tax.router, prefix="/dane", tags=["Daně"])
app.include_router(sync.router, prefix="/synchronizace", tags=["Synchronizace"])
app.include_router(share_check.router, prefix="/kontrola-podilu", tags=["Kontrola podílu"])
app.include_router(administration.router, prefix="/sprava", tags=["Administrace"])
app.include_router(settings_page.router, prefix="/nastaveni", tags=["Nastavení"])
