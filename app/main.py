import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.config import settings
from app.database import Base, engine, SessionLocal

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


def _migrate_svj_import_mappings():
    """Add owner_import_mapping and contact_import_mapping columns to svj_info table."""
    with engine.connect() as conn:
        columns = [
            row[1] for row in
            conn.execute(text("PRAGMA table_info(svj_info)")).fetchall()
        ]
        for col_name in ("owner_import_mapping", "contact_import_mapping"):
            if col_name not in columns:
                # safe: col_name from hardcoded tuple above
                conn.execute(text(
                    f"ALTER TABLE svj_info ADD COLUMN {col_name} TEXT"
                ))
                logger.info("Added %s column to svj_info", col_name)
        conn.commit()


def _migrate_email_log_name_normalized():
    """Add name_normalized column to email_logs and backfill from recipient_name."""
    with engine.connect() as conn:
        columns = [
            row[1] for row in
            conn.execute(text("PRAGMA table_info(email_logs)")).fetchall()
        ]
        if "name_normalized" not in columns:
            conn.execute(text(
                "ALTER TABLE email_logs ADD COLUMN name_normalized VARCHAR(300)"
            ))
            logger.info("Added name_normalized column to email_logs")
            # Backfill — SQLite doesn't have strip_diacritics, do in Python
            from app.utils import strip_diacritics
            rows = conn.execute(text(
                "SELECT id, recipient_name FROM email_logs WHERE recipient_name IS NOT NULL"
            )).fetchall()
            for row_id, name in rows:
                conn.execute(text(
                    "UPDATE email_logs SET name_normalized = :norm WHERE id = :id"
                ), {"norm": strip_diacritics(name), "id": row_id})
            if rows:
                logger.info("Backfilled name_normalized for %d email_logs", len(rows))
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
        ("ix_email_logs_name_normalized", "email_logs", "name_normalized"),
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
        # payment.py
        ("ix_variable_symbol_mappings_unit_id", "variable_symbol_mappings", "unit_id"),
        ("ix_variable_symbol_mappings_source", "variable_symbol_mappings", "source"),
        ("ix_unit_balances_unit_id", "unit_balances", "unit_id"),
        ("ix_unit_balances_year", "unit_balances", "year"),
        ("ix_unit_balances_owner_id", "unit_balances", "owner_id"),
        ("ix_prescription_years_year", "prescription_years", "year"),
        ("ix_prescriptions_prescription_year_id", "prescriptions", "prescription_year_id"),
        ("ix_prescriptions_unit_id", "prescriptions", "unit_id"),
        ("ix_prescriptions_variable_symbol", "prescriptions", "variable_symbol"),
        ("ix_prescription_items_prescription_id", "prescription_items", "prescription_id"),
        ("ix_bank_statements_import_status", "bank_statements", "import_status"),
        ("ix_payments_statement_id", "payments", "statement_id"),
        ("ix_payments_date", "payments", "date"),
        ("ix_payments_vs", "payments", "vs"),
        ("ix_payments_match_status", "payments", "match_status"),
        ("ix_payments_unit_id", "payments", "unit_id"),
        ("ix_payments_owner_id", "payments", "owner_id"),
        ("ix_payments_prescription_id", "payments", "prescription_id"),
        # payment_allocations
        ("ix_payment_allocations_payment_id", "payment_allocations", "payment_id"),
        ("ix_payment_allocations_unit_id", "payment_allocations", "unit_id"),
        ("ix_payment_allocations_owner_id", "payment_allocations", "owner_id"),
        ("ix_payment_allocations_prescription_id", "payment_allocations", "prescription_id"),
        ("ix_settlements_year", "settlements", "year"),
        ("ix_settlements_unit_id", "settlements", "unit_id"),
        ("ix_settlements_status", "settlements", "status"),
        ("ix_settlement_items_settlement_id", "settlement_items", "settlement_id"),
        # space.py
        ("ix_spaces_section", "spaces", "section"),
        ("ix_spaces_status", "spaces", "status"),
        ("ix_tenants_owner_id", "tenants", "owner_id"),
        ("ix_tenants_is_active", "tenants", "is_active"),
        ("ix_tenants_name_normalized", "tenants", "name_normalized"),
        ("ix_space_tenants_space_id", "space_tenants", "space_id"),
        ("ix_space_tenants_tenant_id", "space_tenants", "tenant_id"),
        ("ix_space_tenants_is_active", "space_tenants", "is_active"),
        ("ix_space_tenants_variable_symbol", "space_tenants", "variable_symbol"),
        # space_id on payment tables
        ("ix_variable_symbol_mappings_space_id", "variable_symbol_mappings", "space_id"),
        ("ix_prescriptions_space_id", "prescriptions", "space_id"),
        ("ix_payments_space_id", "payments", "space_id"),
        ("ix_payment_allocations_space_id", "payment_allocations", "space_id"),
        ("ix_unit_balances_space_id", "unit_balances", "space_id"),
    ]
    import re
    _SAFE_IDENT = re.compile(r'^"?[a-z_][a-z0-9_]*"?$')
    with engine.connect() as conn:
        for idx_name, table, column in _INDEXES:
            if not all(_SAFE_IDENT.match(p) for p in (idx_name, table, column)):
                logger.warning("Skipping index %s — invalid identifier", idx_name)
                continue
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


def _migrate_payment_allocations():
    """Vytvořit PaymentAllocation záznamy pro existující napárované platby."""
    from sqlalchemy.orm import Session as _Session
    from app.models.payment import Payment, PaymentAllocation, PaymentMatchStatus

    with _Session(engine) as session:
        # Zjistit zda tabulka existuje a má data
        existing_count = session.query(PaymentAllocation).count()
        if existing_count > 0:
            return  # Už migrováno

        # Pro každou napárovanou platbu s unit_id vytvořit alokaci
        payments = (
            session.query(Payment)
            .filter(Payment.unit_id.isnot(None))
            .filter(Payment.match_status != PaymentMatchStatus.UNMATCHED)
            .all()
        )
        if not payments:
            return

        for p in payments:
            session.add(PaymentAllocation(
                payment_id=p.id,
                unit_id=p.unit_id,
                owner_id=p.owner_id,
                prescription_id=p.prescription_id,
                amount=p.amount,
            ))
        session.commit()
        logger.info("Migrated %d payments → payment_allocations", len(payments))


def _migrate_bank_statement_locked():
    """Přidat sloupec locked_at do bank_statements."""
    with engine.connect() as conn:
        cols = [r[1] for r in conn.execute(text("PRAGMA table_info('bank_statements')")).fetchall()]
        if "locked_at" not in cols:
            conn.execute(text("ALTER TABLE bank_statements ADD COLUMN locked_at DATETIME"))
            conn.commit()
            logger.info("Added locked_at column to bank_statements")


def _migrate_unit_balances_owner():
    """Přidat sloupce owner_id a owner_name do unit_balances + balance_import_mapping do svj_info."""
    with engine.connect() as conn:
        cols = [r[1] for r in conn.execute(text("PRAGMA table_info('unit_balances')")).fetchall()]
        if "owner_id" not in cols:
            conn.execute(text("ALTER TABLE unit_balances ADD COLUMN owner_id INTEGER REFERENCES owners(id)"))
            conn.execute(text("ALTER TABLE unit_balances ADD COLUMN owner_name VARCHAR(300)"))
            conn.commit()
            logger.info("Added owner_id, owner_name columns to unit_balances")
        svj_cols = [r[1] for r in conn.execute(text("PRAGMA table_info('svj_info')")).fetchall()]
        if "balance_import_mapping" not in svj_cols:
            conn.execute(text("ALTER TABLE svj_info ADD COLUMN balance_import_mapping TEXT"))
            conn.commit()
            logger.info("Added balance_import_mapping column to svj_info")


def _migrate_spaces_tables():
    """Add space_id columns to payment tables + space_import_mapping to svj_info."""
    _SPACE_COLUMNS = [
        ("variable_symbol_mappings", "space_id", "INTEGER REFERENCES spaces(id)"),
        ("prescriptions", "space_id", "INTEGER REFERENCES spaces(id)"),
        ("payments", "space_id", "INTEGER REFERENCES spaces(id)"),
        ("payment_allocations", "space_id", "INTEGER REFERENCES spaces(id)"),
        ("unit_balances", "space_id", "INTEGER REFERENCES spaces(id)"),
    ]
    with engine.connect() as conn:
        for table, col, col_type in _SPACE_COLUMNS:
            cols = [r[1] for r in conn.execute(text(f"PRAGMA table_info('{table}')")).fetchall()]
            if col not in cols:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}"))
                logger.info("Added %s column to %s", col, table)
        # space_import_mapping on svj_info
        svj_cols = [r[1] for r in conn.execute(text("PRAGMA table_info('svj_info')")).fetchall()]
        if "space_import_mapping" not in svj_cols:
            conn.execute(text("ALTER TABLE svj_info ADD COLUMN space_import_mapping TEXT"))
            logger.info("Added space_import_mapping column to svj_info")
        # Fix unit_id NOT NULL → nullable on variable_symbol_mappings (needed for space-only VS)
        vsm_cols = conn.execute(text("PRAGMA table_info('variable_symbol_mappings')")).fetchall()
        unit_id_col = next((c for c in vsm_cols if c[1] == "unit_id"), None)
        if unit_id_col and unit_id_col[3] == 1:  # notnull=1 → needs fix
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS _vsm_new (
                    id INTEGER PRIMARY KEY,
                    variable_symbol VARCHAR(20) NOT NULL UNIQUE,
                    unit_id INTEGER REFERENCES units(id),
                    space_id INTEGER REFERENCES spaces(id),
                    source VARCHAR(6),
                    description TEXT,
                    is_active BOOLEAN DEFAULT 1,
                    created_at DATETIME,
                    updated_at DATETIME
                )
            """))
            conn.execute(text("INSERT INTO _vsm_new SELECT id, variable_symbol, unit_id, space_id, source, description, is_active, created_at, updated_at FROM variable_symbol_mappings"))
            conn.execute(text("DROP TABLE variable_symbol_mappings"))
            conn.execute(text("ALTER TABLE _vsm_new RENAME TO variable_symbol_mappings"))
            conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_vsm_variable_symbol ON variable_symbol_mappings(variable_symbol)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_vsm_unit_id ON variable_symbol_mappings(unit_id)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_vsm_space_id ON variable_symbol_mappings(space_id)"))
            logger.info("Recreated variable_symbol_mappings with nullable unit_id")
        # Fix unit_id NOT NULL → nullable on payment_allocations (needed for space-only allocations)
        pa_cols = conn.execute(text("PRAGMA table_info('payment_allocations')")).fetchall()
        pa_unit_col = next((c for c in pa_cols if c[1] == "unit_id"), None)
        if pa_unit_col and pa_unit_col[3] == 1:  # notnull=1 → needs fix
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS _pa_new (
                    id INTEGER PRIMARY KEY,
                    payment_id INTEGER NOT NULL REFERENCES payments(id) ON DELETE CASCADE,
                    unit_id INTEGER REFERENCES units(id),
                    space_id INTEGER REFERENCES spaces(id),
                    owner_id INTEGER REFERENCES owners(id),
                    prescription_id INTEGER REFERENCES prescriptions(id),
                    amount FLOAT NOT NULL
                )
            """))
            conn.execute(text("INSERT INTO _pa_new SELECT id, payment_id, unit_id, space_id, owner_id, prescription_id, amount FROM payment_allocations"))
            conn.execute(text("DROP TABLE payment_allocations"))
            conn.execute(text("ALTER TABLE _pa_new RENAME TO payment_allocations"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_pa_payment_id ON payment_allocations(payment_id)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_pa_unit_id ON payment_allocations(unit_id)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_pa_space_id ON payment_allocations(space_id)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_pa_owner_id ON payment_allocations(owner_id)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_pa_prescription_id ON payment_allocations(prescription_id)"))
            logger.info("Recreated payment_allocations with nullable unit_id")
        conn.commit()


_ALL_MIGRATIONS = [
    ("units table", _migrate_units_table),
    ("owner_units history", _migrate_owner_units_history),
    ("tax tables", _migrate_tax_tables),
    ("owners phone_secondary", _migrate_owners_phone_secondary),
    ("ballots shared_owners", _migrate_ballots_shared_owners),
    ("svj_info voting_import_mapping", _migrate_svj_info_voting_mapping),
    ("svj_info import_mappings", _migrate_svj_import_mappings),
    ("email_logs name_normalized", _migrate_email_log_name_normalized),
    ("payment_allocations migration", _migrate_payment_allocations),
    ("bank_statement locked_at", _migrate_bank_statement_locked),
    ("unit_balances owner columns", _migrate_unit_balances_owner),
    ("spaces tables migration", _migrate_spaces_tables),
    ("index creation", _ensure_indexes),
    ("code list seeding", _seed_code_lists),
    ("email template seeding", _seed_email_templates),
]


def run_post_restore_migrations() -> list[str]:
    """Re-connect to the (possibly replaced) database and run all migrations.

    Called after every backup restore so the server keeps running even when
    the restored DB is missing new columns or tables.

    Returns list of warning messages (empty if all migrations succeeded).
    """
    warnings = []
    engine.dispose()  # drop stale connections to the old file

    # Create any missing tables (e.g. share_check_* from newer code)
    import app.models  # noqa: F401
    Base.metadata.create_all(bind=engine)

    for name, func in _ALL_MIGRATIONS:
        try:
            func()
        except Exception:
            msg = f"post-restore: {name} migration skipped"
            logger.warning(msg)
            warnings.append(msg)

    try:
        from app.routers.tax import recover_stuck_sending_sessions
        recover_stuck_sending_sessions()
    except Exception:
        msg = "post-restore: sending session recovery skipped"
        logger.warning(msg)
        warnings.append(msg)

    return warnings


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.debug:
        logger.warning("DEBUG mode je zapnutý — SQL echo aktivní. Pro produkci nastavte DEBUG=false v .env")

    # Import models so they register with Base
    import app.models  # noqa: F401

    Base.metadata.create_all(bind=engine)

    # Run all migrations (shared list with post-restore)
    for name, func in _ALL_MIGRATIONS:
        try:
            func()
        except Exception:
            logger.warning("%s migration skipped", name)

    # Recover stuck SENDING sessions (server restart recovery)
    try:
        from app.routers.tax import recover_stuck_sending_sessions
        recover_stuck_sending_sessions()
    except Exception:
        logger.warning("sending session recovery skipped")

    # Ensure data directories exist
    for d in [settings.upload_dir, settings.generated_dir, settings.temp_dir]:
        d.mkdir(parents=True, exist_ok=True)
    for sub in ["excel", "word_templates", "scanned_ballots", "tax_pdfs", "csv", "share_check", "contracts"]:
        (settings.upload_dir / sub).mkdir(exist_ok=True)
    for sub in ["ballots", "exports"]:
        (settings.generated_dir / sub).mkdir(exist_ok=True)

    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)


# Custom error pages
from fastapi.templating import Jinja2Templates

_error_templates = Jinja2Templates(directory="app/templates")


from sqlalchemy.exc import IntegrityError, OperationalError  # noqa: E402


@app.exception_handler(IntegrityError)
async def integrity_error_handler(request, exc):
    logger.warning("DB IntegrityError: %s", exc.orig)
    return _error_templates.TemplateResponse("error.html", {
        "request": request,
        "status_code": 409,
        "title": "Konflikt dat",
        "message": "Operace nemohla být dokončena — data kolidují s existujícím záznamem.",
    }, status_code=409)


@app.exception_handler(OperationalError)
async def operational_error_handler(request, exc):
    logger.error("DB OperationalError: %s", exc.orig)
    return _error_templates.TemplateResponse("error.html", {
        "request": request,
        "status_code": 500,
        "title": "Chyba databáze",
        "message": "Nastala chyba při práci s databází. Zkuste to prosím znovu.",
    }, status_code=500)


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


# Global debtor count for sidebar badge — runs on full-page HTML requests only
@app.middleware("http")
async def inject_debtor_count(request, call_next):
    path = request.url.path
    is_htmx_partial = (
        request.headers.get("hx-request") == "true"
        and request.headers.get("hx-boosted") != "true"
    )
    # Skip static files, HTMX partials, and non-page requests (exports, API)
    if path.startswith("/static") or is_htmx_partial:
        return await call_next(request)
    # Compute debtor count
    try:
        from app.routers.payments._helpers import _count_debtors_fast
        from app.models import PrescriptionYear
        db = SessionLocal()
        try:
            py = db.query(PrescriptionYear).order_by(PrescriptionYear.year.desc()).first()
            request.state.nav_debtor_count = _count_debtors_fast(db, py.year) if py else 0
        finally:
            db.close()
    except Exception:
        request.state.nav_debtor_count = 0
    return await call_next(request)

# Raise default Starlette multipart limits (default max_files=1000 is too low
# for large PDF directories uploaded via webkitdirectory)
try:
    from starlette.requests import Request as _StarletteRequest
    _StarletteRequest.form.__kwdefaults__["max_files"] = 5000
    _StarletteRequest.form.__kwdefaults__["max_fields"] = 5000
except (AttributeError, KeyError, TypeError):
    logging.getLogger(__name__).warning("Cannot override Starlette max_files limit")

# Static files
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")

# Register routers
from app.routers import dashboard, owners, units, voting, tax, sync, share_check, settings_page, administration, payments, spaces, tenants  # noqa: E402

app.include_router(dashboard.router)
app.include_router(owners.router, prefix="/vlastnici", tags=["Vlastníci"])
app.include_router(units.router, prefix="/jednotky", tags=["Jednotky"])
app.include_router(voting.router, prefix="/hlasovani", tags=["Hlasování"])
app.include_router(tax.router, prefix="/dane", tags=["Daně"])
app.include_router(sync.router, prefix="/synchronizace", tags=["Synchronizace"])
app.include_router(share_check.router, prefix="/kontrola-podilu", tags=["Kontrola podílu"])
app.include_router(administration.router, prefix="/sprava", tags=["Administrace"])
app.include_router(settings_page.router, prefix="/nastaveni", tags=["Nastavení"])
app.include_router(payments.router, prefix="/platby", tags=["Platby"])
app.include_router(spaces.router, prefix="/prostory", tags=["Prostory"])
app.include_router(tenants.router, prefix="/najemci", tags=["Nájemci"])
