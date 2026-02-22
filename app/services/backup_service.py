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
) -> Path:
    """Create a ZIP backup of database + uploads + generated files."""
    os.makedirs(backup_dir, exist_ok=True)

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
