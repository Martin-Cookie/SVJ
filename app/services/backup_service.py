from __future__ import annotations

import json
import logging
import os
import shutil
import sqlite3
import time
import zipfile
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# ---- File-based restore lock ----

_LOCK_FILENAME = ".restore_lock"
_LOCK_STALE_SECONDS = 600  # 10 minutes


def acquire_restore_lock(backup_dir: str) -> bool:
    """Try to acquire file-based restore lock. Returns True if acquired."""
    lock_path = Path(backup_dir) / _LOCK_FILENAME
    os.makedirs(backup_dir, exist_ok=True)

    if lock_path.is_file():
        # Check for stale lock
        try:
            data = json.loads(lock_path.read_text())
            lock_time = data.get("timestamp", 0)
            if time.time() - lock_time < _LOCK_STALE_SECONDS:
                return False  # lock is active
            logger.warning("Stale restore lock found (age %.0fs), removing", time.time() - lock_time)
        except (json.JSONDecodeError, OSError):
            logger.warning("Corrupted restore lock, removing")

    lock_path.write_text(json.dumps({
        "pid": os.getpid(),
        "timestamp": time.time(),
    }))
    return True


def release_restore_lock(backup_dir: str) -> None:
    """Release file-based restore lock."""
    lock_path = Path(backup_dir) / _LOCK_FILENAME
    try:
        lock_path.unlink(missing_ok=True)
    except OSError:
        pass


# ---- Backup creation ----


SAFETY_BACKUP_PREFIX = "_safety_"


def create_backup(
    db_path: str,
    uploads_dir: str,
    generated_dir: str,
    backup_dir: str,
    custom_name: str = None,
    is_safety: bool = False,
) -> tuple[Path, str | None]:
    """Create a ZIP backup of database + uploads + generated files + .env.

    Returns (zip_path, wal_warning) where wal_warning is None if WAL
    checkpoint succeeded without issues.
    """
    os.makedirs(backup_dir, exist_ok=True)

    # Disk space check
    _check_disk_space(db_path, uploads_dir, generated_dir, backup_dir)

    if custom_name:
        # Sanitize: keep only safe chars, ensure .zip
        safe = "".join(c for c in custom_name if c.isalnum() or c in "-_.")
        safe = safe.strip().rstrip(".")
        if not safe:
            safe = f"svj_backup_{datetime.now().strftime('%Y-%m-%d_%H%M%S')}"
        zip_name = safe if safe.endswith(".zip") else f"{safe}.zip"
    else:
        timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        prefix = SAFETY_BACKUP_PREFIX if is_safety else ""
        zip_name = f"{prefix}svj_backup_{timestamp}.zip"
    zip_path = Path(backup_dir) / zip_name

    # WAL checkpoint — flush pending writes into main DB file before backup
    wal_warning = None
    if os.path.isfile(db_path):
        try:
            conn = sqlite3.connect(db_path)
            result = conn.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
            conn.close()
            # result = (blocked, wal_pages, checkpointed_pages)
            # blocked != 0 means checkpoint was blocked by another connection
            if result and result[0] != 0:
                wal_warning = (
                    f"WAL checkpoint byl blokován (stav={result[0]}, "
                    f"stránky={result[1]}, checkpointováno={result[2]}). "
                    f"Záloha může být neúplná."
                )
                logger.warning("WAL checkpoint blokován: %s", result)
        except Exception as exc:
            wal_warning = f"WAL checkpoint selhal: {exc}. Záloha může být neúplná."
            logger.warning("WAL checkpoint selhal: %s", exc)

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        # Database
        if os.path.isfile(db_path):
            zf.write(db_path, "svj.db")

        # Uploads directory
        _add_directory_to_zip(zf, uploads_dir, "uploads")

        # Generated directory
        _add_directory_to_zip(zf, generated_dir, "generated")

        # .env file (if exists)
        env_path = Path(db_path).parent.parent / ".env"
        if env_path.is_file():
            zf.write(str(env_path), ".env")

        # manifest.json with metadata
        db_size = os.path.getsize(db_path) if os.path.isfile(db_path) else 0
        table_counts = _get_table_counts(db_path) if os.path.isfile(db_path) else {}
        manifest = {
            "created_at": datetime.now().isoformat(),
            "app_version": "1.0",
            "db_file": "svj.db",
            "db_size_bytes": db_size,
            "table_counts": table_counts,
        }
        zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))

    # Auto-cleanup old backups
    cleanup_old_backups(backup_dir)

    return zip_path, wal_warning


def _check_disk_space(db_path: str, uploads_dir: str, generated_dir: str, backup_dir: str) -> None:
    """Check if there is enough disk space for backup creation."""
    estimated_size = 0
    if os.path.isfile(db_path):
        estimated_size += os.path.getsize(db_path)
    for d in (uploads_dir, generated_dir):
        if os.path.isdir(d):
            for root, _dirs, files in os.walk(d):
                for f in files:
                    try:
                        estimated_size += os.path.getsize(os.path.join(root, f))
                    except OSError:
                        pass

    usage = shutil.disk_usage(backup_dir)
    # Need at least 2x estimated size free
    if usage.free < estimated_size * 2:
        raise OSError(
            f"Nedostatek místa na disku. Potřeba: {estimated_size * 2 // 1048576} MB, "
            f"volno: {usage.free // 1048576} MB"
        )


def cleanup_old_backups(backup_dir: str, keep_count: int = 10) -> int:
    """Delete oldest backups beyond keep_count. Returns number of deleted backups.

    Safety backups (prefixed with ``_safety_``) are excluded from cleanup
    to prevent accidental deletion of restore rollback points.
    """
    backup_path = Path(backup_dir)
    if not backup_path.is_dir():
        return 0

    # Exclude safety backups from cleanup — they are restore rollback points
    zips = sorted(
        (p for p in backup_path.glob("*.zip") if not p.name.startswith(SAFETY_BACKUP_PREFIX)),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    deleted = 0
    for old_zip in zips[keep_count:]:
        try:
            old_zip.unlink()
            deleted += 1
            logger.info("Auto-cleanup: smazána stará záloha %s", old_zip.name)
        except OSError as e:
            logger.warning("Auto-cleanup: nelze smazat %s: %s", old_zip.name, e)
    return deleted


def get_backups_total_size(backup_dir: str) -> int:
    """Return total size of all backup ZIP files in bytes."""
    backup_path = Path(backup_dir)
    if not backup_path.is_dir():
        return 0
    return sum(f.stat().st_size for f in backup_path.glob("*.zip"))


# ---- Restore from ZIP ----


def restore_backup(
    zip_path: str,
    db_path: str,
    uploads_dir: str,
    generated_dir: str,
    backup_dir: str,
) -> None:
    """Restore data from a ZIP backup. Creates a safety backup first."""
    zip_path = Path(zip_path)

    # Validate ZIP
    if not zipfile.is_zipfile(zip_path):
        raise ValueError("Nahraný soubor není platný ZIP archiv.")

    with zipfile.ZipFile(zip_path, "r") as zf:
        names = zf.namelist()
        if "svj.db" not in names:
            raise ValueError("ZIP archiv neobsahuje soubor svj.db.")

        # CRC integrity check (before creating safety backup)
        bad_file = zf.testzip()
        if bad_file is not None:
            raise ValueError(f"ZIP archiv je poškozený — chyba v souboru: {bad_file}")

    # Safety backup before restore
    safety_path, _ = create_backup(db_path, uploads_dir, generated_dir, backup_dir, is_safety=True)

    # Restore with rollback on failure
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            # Restore database
            with zf.open("svj.db") as src, open(db_path, "wb") as dst:
                shutil.copyfileobj(src, dst)

            # SQLite integrity check after restore
            _verify_db_integrity(db_path)

            # Restore uploads
            _restore_directory_from_zip(zf, "uploads", uploads_dir)

            # Restore generated
            _restore_directory_from_zip(zf, "generated", generated_dir)

            # Restore .env if present in ZIP
            if ".env" in zf.namelist():
                env_path = Path(db_path).parent.parent / ".env"
                with zf.open(".env") as src, open(str(env_path), "wb") as dst:
                    shutil.copyfileobj(src, dst)
    except Exception:
        logger.exception("Restore ze ZIP selhalo, provádím rollback ze safety backup")
        _rollback_from_safety(str(safety_path), db_path, uploads_dir, generated_dir)
        raise


# ---- Restore from directory ----


def restore_from_directory(
    src_dir: str,
    db_path: str,
    uploads_dir: str,
    generated_dir: str,
    backup_dir: str,
) -> None:
    """Restore data from an unzipped backup directory. Creates a safety backup first."""
    src = Path(src_dir)

    # Find svj.db — either directly in src or one level deeper
    db_file = src / "svj.db"
    if not db_file.is_file():
        # Try one level deeper (e.g. Safari unzips into a subfolder)
        for child in src.iterdir():
            if child.is_dir() and (child / "svj.db").is_file():
                src = child
                db_file = child / "svj.db"
                break
    if not db_file.is_file():
        raise ValueError("Adresář neobsahuje soubor svj.db.")

    # Safety backup before restore
    safety_path, _ = create_backup(db_path, uploads_dir, generated_dir, backup_dir, is_safety=True)

    try:
        # Restore database
        shutil.copy2(str(db_file), db_path)

        # SQLite integrity check after restore
        _verify_db_integrity(db_path)

        # Restore uploads
        src_uploads = src / "uploads"
        if src_uploads.is_dir():
            if os.path.isdir(uploads_dir):
                shutil.rmtree(uploads_dir)
            shutil.copytree(str(src_uploads), uploads_dir)
        else:
            os.makedirs(uploads_dir, exist_ok=True)

        # Restore generated
        src_generated = src / "generated"
        if src_generated.is_dir():
            if os.path.isdir(generated_dir):
                shutil.rmtree(generated_dir)
            shutil.copytree(str(src_generated), generated_dir)
        else:
            os.makedirs(generated_dir, exist_ok=True)

        # Restore .env if present
        src_env = src / ".env"
        if src_env.is_file():
            env_path = Path(db_path).parent.parent / ".env"
            shutil.copy2(str(src_env), str(env_path))
    except Exception:
        logger.exception("Restore z adresáře selhalo, provádím rollback ze safety backup")
        _rollback_from_safety(str(safety_path), db_path, uploads_dir, generated_dir)
        raise


# ---- Rollback helper ----


def _rollback_from_safety(safety_zip: str, db_path: str, uploads_dir: str, generated_dir: str) -> None:
    """Restore from safety backup after a failed restore attempt."""
    try:
        with zipfile.ZipFile(safety_zip, "r") as zf:
            if "svj.db" in zf.namelist():
                with zf.open("svj.db") as src, open(db_path, "wb") as dst:
                    shutil.copyfileobj(src, dst)
            _restore_directory_from_zip(zf, "uploads", uploads_dir)
            _restore_directory_from_zip(zf, "generated", generated_dir)
        logger.info("Rollback ze safety backup úspěšný: %s", safety_zip)
    except Exception:
        logger.exception("KRITICKÁ CHYBA: rollback ze safety backup selhal: %s", safety_zip)


# ---- Internal helpers ----


def _verify_db_integrity(db_path: str) -> None:
    """Run SQLite integrity check on restored database. Raises ValueError on failure."""
    try:
        conn = sqlite3.connect(db_path)
        result = conn.execute("PRAGMA integrity_check").fetchone()
        conn.close()
        if result[0] != "ok":
            raise ValueError(f"SQLite integrity check selhal: {result[0]}")
    except sqlite3.DatabaseError as e:
        raise ValueError(f"Obnovený soubor není platná SQLite databáze: {e}")


def _get_table_counts(db_path: str) -> dict:
    """Get row counts for key tables (for manifest metadata)."""
    tables = [
        # Vlastníci a jednotky
        "owners", "units", "owner_units", "proxies",
        # Prostory a nájemci
        "spaces", "tenants", "space_tenants",
        # Hlasování
        "votings", "voting_items", "ballots", "ballot_votes",
        # Daňové podklady
        "tax_sessions", "tax_documents", "tax_distributions",
        # Synchronizace a kontroly
        "sync_sessions", "sync_records",
        "share_check_sessions", "share_check_records", "share_check_column_mappings",
        # Platby
        "prescription_years", "prescriptions", "prescription_items",
        "variable_symbol_mappings", "bank_statements", "payments",
        "payment_allocations", "bank_statement_column_mappings",
        "unit_balances", "settlements", "settlement_items",
        # Logy
        "email_logs", "import_logs", "activity_logs",
        # Administrace
        "svj_info", "svj_addresses", "board_members",
        "code_list_items", "email_templates",
    ]
    counts = {}
    try:
        conn = sqlite3.connect(db_path)
        for table in tables:
            assert table.replace("_", "").isalnum(), f"invalid table name: {table}"
            try:
                row = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()  # safe: hardcoded list + assert
                counts[table] = row[0]
            except sqlite3.OperationalError:
                pass  # table doesn't exist yet
        conn.close()
    except sqlite3.DatabaseError:
        pass
    return counts


def _add_directory_to_zip(
    zf: zipfile.ZipFile, dir_path: str, archive_prefix: str
) -> None:
    """Recursively add directory contents to ZIP under given prefix."""
    if not os.path.isdir(dir_path):
        return
    for root, _dirs, files in os.walk(dir_path):
        for file in files:
            file_path = os.path.join(root, file)
            arcname = os.path.join(
                archive_prefix, os.path.relpath(file_path, dir_path)
            )
            zf.write(file_path, arcname)


def _restore_directory_from_zip(
    zf: zipfile.ZipFile, zip_prefix: str, target_dir: str
) -> None:
    """Extract directory from ZIP, replacing existing contents."""
    # Clear existing directory
    if os.path.isdir(target_dir):
        shutil.rmtree(target_dir)
    os.makedirs(target_dir, exist_ok=True)

    resolved_target = os.path.realpath(target_dir)
    for name in zf.namelist():
        if name.startswith(zip_prefix + "/") and not name.endswith("/"):
            rel_path = os.path.relpath(name, zip_prefix)
            target_path = os.path.realpath(os.path.join(target_dir, rel_path))
            # Zip Slip protection: ensure extracted path stays within target
            if not target_path.startswith(resolved_target + os.sep):
                continue
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            with zf.open(name) as src, open(target_path, "wb") as dst:
                shutil.copyfileobj(src, dst)


# ---- Restore log (JSON file, survives DB restores) ----

_RESTORE_LOG = "restore_log.json"


def log_restore(backup_dir: str, source: str, method: str, safety_backup: str = "") -> None:
    """Append an entry to the restore log."""
    log_path = Path(backup_dir) / _RESTORE_LOG
    entries = read_restore_log(backup_dir)
    entry = {
        "timestamp": datetime.now().isoformat(),
        "source": source,
        "method": method,
    }
    if safety_backup:
        entry["safety_backup"] = safety_backup
    entries.insert(0, entry)
    os.makedirs(backup_dir, exist_ok=True)
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)


def read_restore_log(backup_dir: str) -> list:
    """Read restore log entries (newest first)."""
    log_path = Path(backup_dir) / _RESTORE_LOG
    if not log_path.is_file():
        return []
    try:
        with open(log_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []
