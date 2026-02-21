import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from sqlalchemy import inspect, text

from app.config import settings
from app.database import Base, engine

logger = logging.getLogger(__name__)


def _migrate_unit_number_to_integer():
    """One-time migration: convert units.unit_number from TEXT to INTEGER.

    SQLite doesn't support ALTER COLUMN, so we recreate the table preserving
    all constraints and foreign key references.
    """
    with engine.connect() as conn:
        cols = {c["name"]: c for c in inspect(engine).get_columns("units")}
        col_type = str(cols["unit_number"]["type"]).upper()
        if col_type in ("INTEGER", "BIGINT"):
            return  # already migrated
        logger.info("Migrating units.unit_number TEXT → INTEGER")
        conn.execute(text("PRAGMA foreign_keys = OFF"))
        conn.execute(text("""
            CREATE TABLE units_new (
                id INTEGER PRIMARY KEY,
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
        conn.execute(text("""
            INSERT INTO units_new
            SELECT id, CAST(unit_number AS INTEGER), building_number,
                   podil_scd, floor_area, room_count, space_type, section,
                   orientation_number, address, lv_number, created_at
            FROM units
        """))
        conn.execute(text("DROP TABLE units"))
        conn.execute(text("ALTER TABLE units_new RENAME TO units"))
        conn.execute(text(
            "CREATE UNIQUE INDEX ix_units_unit_number ON units (unit_number)"
        ))
        conn.execute(text(
            "CREATE INDEX ix_units_building_number ON units (building_number)"
        ))
        conn.execute(text(
            "CREATE INDEX ix_units_space_type ON units (space_type)"
        ))
        conn.execute(text(
            "CREATE INDEX ix_units_section ON units (section)"
        ))
        conn.execute(text(
            "CREATE INDEX ix_units_lv_number ON units (lv_number)"
        ))
        conn.execute(text("PRAGMA foreign_keys = ON"))
        conn.commit()
        logger.info("Migration complete")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Import models so they register with Base
    import app.models  # noqa: F401

    Base.metadata.create_all(bind=engine)

    # One-time migrations
    try:
        _migrate_unit_number_to_integer()
    except Exception:
        logger.warning("units.unit_number migration skipped (table may not exist yet)")

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
