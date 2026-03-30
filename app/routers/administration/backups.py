"""Zálohy — vytvoření, stažení, smazání, přejmenování, obnovení."""

import logging
import os
import re
import shutil
import sqlite3
import tempfile
from datetime import datetime
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.database import SessionLocal, engine, get_db
from app.models import (
    Owner, Unit, Voting, TaxSession, SyncSession,
    EmailLog, ImportLog, BoardMember,
    ActivityAction, log_activity,
)
from app.services.backup_service import (
    _rollback_from_safety,
    create_backup, restore_backup, restore_from_directory,
    log_restore, read_restore_log,
    acquire_restore_lock, release_restore_lock,
    get_backups_total_size,
)
from app.utils import UPLOAD_LIMITS, is_safe_path, templates, validate_upload

from ._helpers import BACKUP_DIR, DB_PATH, GENERATED_DIR, UPLOADS_DIR

logger = logging.getLogger(__name__)

router = APIRouter()


def _safety_backup() -> str:
    """Create a safety backup and return its filename."""
    zip_path, _ = create_backup(str(DB_PATH), str(UPLOADS_DIR), str(GENERATED_DIR), str(BACKUP_DIR))
    return zip_path.name


@router.get("/zalohy")
async def backups_page(
    request: Request,
    chyba: str = Query(""),
    zprava: str = Query(""),
    wal_warning: str = Query(""),
    db: Session = Depends(get_db),
):
    """Stránka správy záloh s historií obnovení."""
    backups = []
    if BACKUP_DIR.is_dir():
        for f in sorted(BACKUP_DIR.iterdir(), reverse=True):
            if f.suffix == ".zip":
                stat = f.stat()
                backups.append({
                    "filename": f.name,
                    "size": stat.st_size,
                    "created": datetime.fromtimestamp(stat.st_mtime),
                })

    default_backup_name = f"svj_backup_{datetime.now().strftime('%Y-%m-%d_%H%M%S')}"
    restore_log = read_restore_log(str(BACKUP_DIR))
    backups_total_size = get_backups_total_size(str(BACKUP_DIR))

    # Flash messages
    flash_message = ""
    flash_type = ""
    if zprava == "vytvoreno" and wal_warning:
        flash_message = "Záloha vytvořena, ale WAL checkpoint hlásí problém. Záloha může být neúplná."
        flash_type = "warning"
    elif zprava == "vytvoreno":
        flash_message = "Záloha úspěšně vytvořena."

    return templates.TemplateResponse("administration/backups.html", {
        "request": request,
        "active_nav": "administration",
        "backups": backups,
        "restore_log": restore_log,
        "default_backup_name": default_backup_name,
        "backups_total_size": backups_total_size,
        "chyba": chyba,
        "zprava": zprava,
        "flash_message": flash_message,
        "flash_type": flash_type,
    })


@router.post("/zaloha/vytvorit")
async def backup_create(filename: str = Form(""), db: Session = Depends(get_db)):
    """Vytvoření nové zálohy databáze a souborů."""
    # Check if there is any data to backup
    total = sum(
        db.query(m).count()
        for m in (Owner, Unit, Voting, TaxSession, SyncSession, EmailLog, ImportLog, BoardMember)
    )
    if total == 0:
        return RedirectResponse("/sprava/zalohy?chyba=prazdna", status_code=302)

    name = filename.strip() or None
    _, wal_warning = create_backup(str(DB_PATH), str(UPLOADS_DIR), str(GENERATED_DIR), str(BACKUP_DIR), custom_name=name)

    # Log activity — backup is file-based, use separate session
    _db = SessionLocal()
    try:
        log_activity(_db, ActivityAction.CREATED, "backup", "sprava",
                     entity_name=name or "Automatická záloha")
        _db.commit()
    finally:
        _db.close()

    if wal_warning:
        return RedirectResponse(f"/sprava/zalohy?zprava=vytvoreno&wal_warning=1", status_code=302)
    return RedirectResponse("/sprava/zalohy?zprava=vytvoreno", status_code=302)


@router.get("/zaloha/{filename}/stahnout")
async def backup_download(filename: str):
    """Stažení záložního souboru."""
    file_path = BACKUP_DIR / filename
    if not file_path.is_file() or not filename.endswith(".zip") or not is_safe_path(file_path, BACKUP_DIR):
        return RedirectResponse("/sprava/zalohy", status_code=302)
    return FileResponse(
        path=str(file_path),
        filename=filename,
        media_type="application/octet-stream",
    )


@router.post("/zaloha/{filename}/smazat")
async def backup_delete(filename: str):
    """Smazání záložního souboru."""
    file_path = BACKUP_DIR / filename
    if file_path.is_file() and filename.endswith(".zip") and is_safe_path(file_path, BACKUP_DIR):
        file_path.unlink()
    return RedirectResponse("/sprava/zalohy", status_code=302)


@router.post("/zaloha/{filename}/prejmenovat")
async def backup_rename(filename: str, new_name: str = Form(...)):
    """Rename an existing backup ZIP file."""
    file_path = BACKUP_DIR / filename
    if not file_path.is_file() or not filename.endswith(".zip") or not is_safe_path(file_path, BACKUP_DIR):
        return RedirectResponse("/sprava/zalohy", status_code=302)

    # Sanitize new_name: keep only safe chars
    safe = re.sub(r"[^\w\-.]", "_", new_name.strip())
    safe = safe.strip("._")
    if not safe:
        return RedirectResponse("/sprava/zalohy?chyba=nazev", status_code=302)
    if not safe.endswith(".zip"):
        safe += ".zip"

    new_path = BACKUP_DIR / safe
    if new_path.exists() and new_path != file_path:
        return RedirectResponse("/sprava/zalohy?chyba=duplicita", status_code=302)

    file_path.rename(new_path)
    return RedirectResponse("/sprava/zalohy", status_code=302)


@router.post("/zaloha/{filename}/obnovit")
async def backup_restore_existing(filename: str):
    """Restore from an existing backup in the backups directory."""
    file_path = BACKUP_DIR / filename
    if not file_path.is_file() or not filename.endswith(".zip") or not is_safe_path(file_path, BACKUP_DIR):
        return RedirectResponse("/sprava/zalohy", status_code=302)

    if not acquire_restore_lock(str(BACKUP_DIR)):
        return RedirectResponse("/sprava/zalohy?chyba=probihajici", status_code=302)

    try:
        # Track existing backups to find safety backup name
        existing = set(p.name for p in BACKUP_DIR.glob("*.zip")) if BACKUP_DIR.is_dir() else set()

        engine.dispose()
        restore_backup(
            str(file_path), str(DB_PATH), str(UPLOADS_DIR),
            str(GENERATED_DIR), str(BACKUP_DIR),
        )
        new_backups = set(p.name for p in BACKUP_DIR.glob("*.zip")) - existing
        safety = next(iter(new_backups), "")
        log_restore(str(BACKUP_DIR), filename, "Existující záloha", safety_backup=safety)
        from app.main import run_post_restore_migrations
        warnings = run_post_restore_migrations()

        _db = SessionLocal()
        try:
            log_activity(_db, ActivityAction.RESTORED, "backup", "sprava",
                         entity_name=filename, description="Obnova z existující zálohy")
            _db.commit()
        finally:
            _db.close()

        zprava = "obnoveno_varovani" if warnings else "obnoveno"
        return RedirectResponse(f"/sprava/zalohy?zprava={zprava}", status_code=302)
    except ValueError:
        logger.exception("Validační chyba při obnově ze zálohy %s", filename)
        return RedirectResponse("/sprava/zalohy?chyba=neplatny", status_code=302)
    except Exception:
        logger.exception("Selhání obnovy ze zálohy %s", filename)
        return RedirectResponse("/sprava/zalohy?chyba=selhani", status_code=302)
    finally:
        release_restore_lock(str(BACKUP_DIR))


@router.post("/zaloha/obnovit")
async def backup_restore(file: UploadFile = File(...)):
    """Obnovení dat z nahraného ZIP záložního souboru."""
    err = await validate_upload(file, **UPLOAD_LIMITS["backup"])
    if err:
        return RedirectResponse("/sprava/zalohy?chyba=upload", status_code=302)

    if not acquire_restore_lock(str(BACKUP_DIR)):
        return RedirectResponse("/sprava/zalohy?chyba=probihajici", status_code=302)

    # Save uploaded file to temp location
    temp_path = BACKUP_DIR / "upload_temp.zip"
    os.makedirs(BACKUP_DIR, exist_ok=True)
    with open(temp_path, "wb") as f:
        f.write(await file.read())

    try:
        # Track which backups exist before restore (to find the safety backup name)
        existing = set(p.name for p in BACKUP_DIR.glob("*.zip")) if BACKUP_DIR.is_dir() else set()

        engine.dispose()
        restore_backup(
            str(temp_path), str(DB_PATH), str(UPLOADS_DIR),
            str(GENERATED_DIR), str(BACKUP_DIR),
        )
        # Find safety backup created by restore_backup
        new_backups = set(p.name for p in BACKUP_DIR.glob("*.zip")) - existing
        safety = next(iter(new_backups), "")
        log_restore(str(BACKUP_DIR), file.filename or "upload.zip", "ZIP soubor", safety_backup=safety)

        from app.main import run_post_restore_migrations
        warnings = run_post_restore_migrations()

        _db = SessionLocal()
        try:
            log_activity(_db, ActivityAction.RESTORED, "backup", "sprava",
                         entity_name=file.filename or "upload.zip", description="Obnova z nahraného ZIP souboru")
            _db.commit()
        finally:
            _db.close()

        zprava = "obnoveno_varovani" if warnings else "obnoveno"
        return RedirectResponse(f"/sprava/zalohy?zprava={zprava}", status_code=302)
    except ValueError:
        logger.exception("Validační chyba při obnově z nahraného ZIP")
        return RedirectResponse("/sprava/zalohy?chyba=neplatny", status_code=302)
    except Exception:
        logger.exception("Selhání obnovy z nahraného ZIP")
        return RedirectResponse("/sprava/zalohy?chyba=selhani", status_code=302)
    finally:
        if temp_path.is_file():
            temp_path.unlink()
        release_restore_lock(str(BACKUP_DIR))


@router.post("/zaloha/obnovit-soubor")
async def backup_restore_db_file(file: UploadFile = File(...)):
    """Restore from an uploaded svj.db file (from an unzipped backup)."""
    err = await validate_upload(file, **UPLOAD_LIMITS["db"])
    if err:
        return RedirectResponse("/sprava/zalohy?chyba=upload", status_code=302)

    if not acquire_restore_lock(str(BACKUP_DIR)):
        return RedirectResponse("/sprava/zalohy?chyba=probihajici", status_code=302)

    try:
        safety = _safety_backup()

        # Dispose existing DB connections before overwriting
        engine.dispose()

        # Overwrite database
        db_content = await file.read()
        with open(str(DB_PATH), "wb") as f:
            f.write(db_content)

        # Validate SQLite integrity before proceeding
        try:
            conn = sqlite3.connect(str(DB_PATH))
            result = conn.execute("PRAGMA integrity_check").fetchone()
            conn.close()
            if result[0] != "ok":
                raise ValueError(f"SQLite integrity check failed: {result[0]}")
        except (sqlite3.DatabaseError, ValueError) as e:
            logger.error("Neplatný SQLite soubor: %s", e)
            _rollback_from_safety(
                str(Path(BACKUP_DIR) / safety), str(DB_PATH),
                str(UPLOADS_DIR), str(GENERATED_DIR),
            )
            return RedirectResponse("/sprava/zalohy?chyba=neplatny_db", status_code=302)

        log_restore(str(BACKUP_DIR), file.filename or "svj.db", "DB soubor", safety_backup=safety)
        from app.main import run_post_restore_migrations
        warnings = run_post_restore_migrations()

        _db = SessionLocal()
        try:
            log_activity(_db, ActivityAction.RESTORED, "backup", "sprava",
                         entity_name=file.filename or "svj.db", description="Obnova z DB souboru")
            _db.commit()
        finally:
            _db.close()

        zprava = "obnoveno_varovani" if warnings else "obnoveno"
        return RedirectResponse(f"/sprava/zalohy?zprava={zprava}", status_code=302)
    except Exception:
        logger.exception("Selhání obnovy z DB souboru")
        _rollback_from_safety(
            str(Path(BACKUP_DIR) / safety), str(DB_PATH),
            str(UPLOADS_DIR), str(GENERATED_DIR),
        )
        return RedirectResponse("/sprava/zalohy?chyba=selhani", status_code=302)
    finally:
        release_restore_lock(str(BACKUP_DIR))


@router.post("/zaloha/obnovit-slozku")
async def backup_restore_folder(files: List[UploadFile] = File(...)):
    """Restore from an uploaded backup folder (webkitdirectory).

    The browser sends all files from the selected folder. We look for svj.db
    and optionally uploads/ and generated/ subdirectories.
    """
    # Total size check (500 MB limit for folder uploads)
    total_size = 0
    for f in files:
        content = await f.read()
        total_size += len(content)
        await f.seek(0)
    if total_size > UPLOAD_LIMITS["folder"]["max_size_mb"] * 1024 * 1024:
        return RedirectResponse("/sprava/zalohy?chyba=upload", status_code=302)

    if not acquire_restore_lock(str(BACKUP_DIR)):
        return RedirectResponse("/sprava/zalohy?chyba=probihajici", status_code=302)

    # Create a temp directory to receive the folder contents
    tmp = tempfile.mkdtemp(prefix="svj_restore_")
    folder_name = ""
    try:
        db_found = False
        for f in files:
            if not f.filename:
                continue
            # webkitRelativePath gives e.g. "folder_name/svj.db" or "folder_name/uploads/doc.pdf"
            # The first path component is the folder name — strip it
            parts = f.filename.replace("\\", "/").split("/")
            if len(parts) > 1:
                if not folder_name:
                    folder_name = parts[0]
                rel = "/".join(parts[1:])  # strip top-level folder name
            else:
                rel = parts[0]

            target = Path(tmp) / rel
            # Path traversal protection: ensure target stays within tmp dir
            resolved = os.path.realpath(str(target))
            if not resolved.startswith(os.path.realpath(tmp) + os.sep) and resolved != os.path.realpath(tmp):
                logger.warning("Path traversal attempt blocked: %s", rel)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with open(str(target), "wb") as dst:
                dst.write(await f.read())

            if rel == "svj.db":
                db_found = True

        if not db_found:
            return RedirectResponse("/sprava/zalohy?chyba=neplatny", status_code=302)

        # Use service function with safety backup + rollback on failure
        engine.dispose()
        restore_from_directory(
            tmp, str(DB_PATH), str(UPLOADS_DIR), str(GENERATED_DIR), str(BACKUP_DIR),
        )

        log_restore(str(BACKUP_DIR), folder_name or "složka", "Složka (Finder)")

        from app.main import run_post_restore_migrations
        warnings = run_post_restore_migrations()

        _db = SessionLocal()
        try:
            log_activity(_db, ActivityAction.RESTORED, "backup", "sprava",
                         entity_name=folder_name or "složka", description="Obnova ze složky (Finder)")
            _db.commit()
        finally:
            _db.close()

        zprava = "obnoveno_varovani" if warnings else "obnoveno"
        return RedirectResponse(f"/sprava/zalohy?zprava={zprava}", status_code=302)
    except Exception:
        logger.exception("Selhání obnovy ze složky")
        return RedirectResponse("/sprava/zalohy?chyba=selhani", status_code=302)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        release_restore_lock(str(BACKUP_DIR))
