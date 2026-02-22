import json
import os
import shutil
import zipfile
from datetime import datetime
from pathlib import Path


def create_backup(
    db_path: str,
    uploads_dir: str,
    generated_dir: str,
    backup_dir: str,
    custom_name: str = None,
) -> Path:
    """Create a ZIP backup of database + uploads + generated files."""
    os.makedirs(backup_dir, exist_ok=True)

    if custom_name:
        # Sanitize: keep only safe chars, ensure .zip
        safe = "".join(c for c in custom_name if c.isalnum() or c in "-_.")
        safe = safe.strip().rstrip(".")
        if not safe:
            safe = f"svj_backup_{datetime.now().strftime('%Y-%m-%d_%H%M%S')}"
        zip_name = safe if safe.endswith(".zip") else f"{safe}.zip"
    else:
        timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        zip_name = f"svj_backup_{timestamp}.zip"
    zip_path = Path(backup_dir) / zip_name

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        # Database
        if os.path.isfile(db_path):
            zf.write(db_path, "svj.db")

        # Uploads directory
        _add_directory_to_zip(zf, uploads_dir, "uploads")

        # Generated directory
        _add_directory_to_zip(zf, generated_dir, "generated")

    return zip_path


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

    # Safety backup before restore
    create_backup(db_path, uploads_dir, generated_dir, backup_dir)

    # Restore
    with zipfile.ZipFile(zip_path, "r") as zf:
        # Restore database
        with zf.open("svj.db") as src, open(db_path, "wb") as dst:
            dst.write(src.read())

        # Restore uploads
        _restore_directory_from_zip(zf, "uploads", uploads_dir)

        # Restore generated
        _restore_directory_from_zip(zf, "generated", generated_dir)


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
    create_backup(db_path, uploads_dir, generated_dir, backup_dir)

    # Restore database
    shutil.copy2(str(db_file), db_path)

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

    for name in zf.namelist():
        if name.startswith(zip_prefix + "/") and not name.endswith("/"):
            rel_path = os.path.relpath(name, zip_prefix)
            target_path = os.path.join(target_dir, rel_path)
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            with zf.open(name) as src, open(target_path, "wb") as dst:
                dst.write(src.read())


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
