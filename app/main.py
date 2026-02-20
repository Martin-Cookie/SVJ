from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import Base, engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Import models so they register with Base
    import app.models  # noqa: F401

    Base.metadata.create_all(bind=engine)

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
from app.routers import dashboard, owners, voting, tax, sync, settings_page  # noqa: E402

app.include_router(dashboard.router)
app.include_router(owners.router, prefix="/vlastnici", tags=["Vlastníci"])
app.include_router(voting.router, prefix="/hlasovani", tags=["Hlasování"])
app.include_router(tax.router, prefix="/dane", tags=["Daně"])
app.include_router(sync.router, prefix="/synchronizace", tags=["Synchronizace"])
app.include_router(settings_page.router, prefix="/nastaveni", tags=["Nastavení"])
