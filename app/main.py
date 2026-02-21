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

    # Ensure data directories exist
    for d in [settings.upload_dir, settings.generated_dir, settings.temp_dir]:
        d.mkdir(parents=True, exist_ok=True)
    for sub in ["excel", "word_templates", "scanned_ballots", "tax_pdfs", "csv"]:
        (settings.upload_dir / sub).mkdir(exist_ok=True)
    for sub in ["ballots", "exports"]:
        (settings.generated_dir / sub).mkdir(exist_ok=True)

    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)

# Static files
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")

# Register routers
from app.routers import dashboard, owners, units, voting, tax, sync, settings_page  # noqa: E402

app.include_router(dashboard.router)
app.include_router(owners.router, prefix="/vlastnici", tags=["Vlastníci"])
app.include_router(units.router, prefix="/jednotky", tags=["Jednotky"])
app.include_router(voting.router, prefix="/hlasovani", tags=["Hlasování"])
app.include_router(tax.router, prefix="/dane", tags=["Daně"])
app.include_router(sync.router, prefix="/synchronizace", tags=["Synchronizace"])
app.include_router(settings_page.router, prefix="/nastaveni", tags=["Nastavení"])
