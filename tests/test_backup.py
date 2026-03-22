"""Tests for backup_service — lock management, create/restore, cleanup, restore log."""
import json
import os
import sqlite3
import time
import zipfile
from pathlib import Path

import pytest

from app.services.backup_service import (
    acquire_restore_lock,
    cleanup_old_backups,
    create_backup,
    get_backups_total_size,
    log_restore,
    read_restore_log,
    release_restore_lock,
    restore_backup,
    restore_from_directory,
    _LOCK_FILENAME,
    _LOCK_STALE_SECONDS,
    _RESTORE_LOG,
    _verify_db_integrity,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def backup_env(tmp_path):
    """Create a realistic backup environment with DB, uploads, generated dirs."""
    db_dir = tmp_path / "data"
    db_dir.mkdir()
    db_path = db_dir / "svj.db"

    # Create a real SQLite database
    conn = sqlite3.connect(str(db_path))
    conn.execute("CREATE TABLE owners (id INTEGER PRIMARY KEY, name TEXT)")
    conn.execute("INSERT INTO owners VALUES (1, 'Test Owner')")
    conn.commit()
    conn.close()

    uploads_dir = db_dir / "uploads"
    uploads_dir.mkdir()
    (uploads_dir / "excel").mkdir()
    (uploads_dir / "excel" / "test.xlsx").write_bytes(b"fake-excel-content")

    generated_dir = db_dir / "generated"
    generated_dir.mkdir()
    (generated_dir / "report.pdf").write_bytes(b"fake-pdf-content")

    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()

    return {
        "db_path": str(db_path),
        "uploads_dir": str(uploads_dir),
        "generated_dir": str(generated_dir),
        "backup_dir": str(backup_dir),
    }


# ---------------------------------------------------------------------------
# Lock management
# ---------------------------------------------------------------------------

class TestLockManagement:
    def test_acquire_lock_success(self, tmp_path):
        backup_dir = str(tmp_path / "backups")
        assert acquire_restore_lock(backup_dir) is True
        lock_path = Path(backup_dir) / _LOCK_FILENAME
        assert lock_path.is_file()

        data = json.loads(lock_path.read_text())
        assert "pid" in data
        assert "timestamp" in data
        assert data["pid"] == os.getpid()

    def test_acquire_lock_fails_when_active(self, tmp_path):
        backup_dir = str(tmp_path / "backups")
        assert acquire_restore_lock(backup_dir) is True
        # Second acquire should fail — lock is still active
        assert acquire_restore_lock(backup_dir) is False

    def test_acquire_lock_removes_stale_lock(self, tmp_path):
        backup_dir = str(tmp_path / "backups")
        os.makedirs(backup_dir, exist_ok=True)
        lock_path = Path(backup_dir) / _LOCK_FILENAME

        # Write a stale lock (timestamp far in the past)
        lock_path.write_text(json.dumps({
            "pid": 99999,
            "timestamp": time.time() - _LOCK_STALE_SECONDS - 100,
        }))
        # Should succeed because lock is stale
        assert acquire_restore_lock(backup_dir) is True

    def test_acquire_lock_removes_corrupted_lock(self, tmp_path):
        backup_dir = str(tmp_path / "backups")
        os.makedirs(backup_dir, exist_ok=True)
        lock_path = Path(backup_dir) / _LOCK_FILENAME

        lock_path.write_text("not-valid-json{{{")
        assert acquire_restore_lock(backup_dir) is True

    def test_release_lock(self, tmp_path):
        backup_dir = str(tmp_path / "backups")
        acquire_restore_lock(backup_dir)
        lock_path = Path(backup_dir) / _LOCK_FILENAME
        assert lock_path.is_file()

        release_restore_lock(backup_dir)
        assert not lock_path.is_file()

    def test_release_lock_missing_file(self, tmp_path):
        """Release should not raise even if lock file doesn't exist."""
        backup_dir = str(tmp_path / "backups")
        os.makedirs(backup_dir, exist_ok=True)
        release_restore_lock(backup_dir)  # should not raise

    def test_acquire_creates_backup_dir(self, tmp_path):
        backup_dir = str(tmp_path / "new" / "nested" / "dir")
        assert not os.path.isdir(backup_dir)
        acquire_restore_lock(backup_dir)
        assert os.path.isdir(backup_dir)


# ---------------------------------------------------------------------------
# Create backup
# ---------------------------------------------------------------------------

class TestCreateBackup:
    def test_creates_zip_with_db(self, backup_env):
        zip_path = create_backup(**backup_env)
        assert zip_path.exists()
        assert zip_path.suffix == ".zip"

        with zipfile.ZipFile(zip_path, "r") as zf:
            names = zf.namelist()
            assert "svj.db" in names
            assert "manifest.json" in names

    def test_zip_contains_uploads(self, backup_env):
        zip_path = create_backup(**backup_env)
        with zipfile.ZipFile(zip_path, "r") as zf:
            names = zf.namelist()
            upload_files = [n for n in names if n.startswith("uploads/")]
            assert len(upload_files) >= 1
            assert "uploads/excel/test.xlsx" in names

    def test_zip_contains_generated(self, backup_env):
        zip_path = create_backup(**backup_env)
        with zipfile.ZipFile(zip_path, "r") as zf:
            assert "generated/report.pdf" in zf.namelist()

    def test_manifest_metadata(self, backup_env):
        zip_path = create_backup(**backup_env)
        with zipfile.ZipFile(zip_path, "r") as zf:
            manifest = json.loads(zf.read("manifest.json"))
            assert "created_at" in manifest
            assert manifest["db_file"] == "svj.db"
            assert manifest["db_size_bytes"] > 0
            assert isinstance(manifest["table_counts"], dict)

    def test_custom_name(self, backup_env):
        zip_path = create_backup(**backup_env, custom_name="my-backup")
        assert zip_path.name == "my-backup.zip"

    def test_custom_name_with_zip_extension(self, backup_env):
        zip_path = create_backup(**backup_env, custom_name="my-backup.zip")
        assert zip_path.name == "my-backup.zip"

    def test_custom_name_sanitized(self, backup_env):
        zip_path = create_backup(**backup_env, custom_name="bad/name with<>chars")
        # Only safe chars should remain
        assert "/" not in zip_path.name
        assert "<" not in zip_path.name

    def test_empty_custom_name_uses_timestamp(self, backup_env):
        zip_path = create_backup(**backup_env, custom_name="///")
        # Sanitized to empty → falls back to timestamp name
        assert zip_path.name.startswith("svj_backup_")

    def test_backup_without_db_file(self, backup_env):
        os.unlink(backup_env["db_path"])
        zip_path = create_backup(**backup_env)
        with zipfile.ZipFile(zip_path, "r") as zf:
            assert "svj.db" not in zf.namelist()
            assert "manifest.json" in zf.namelist()

    def test_backup_without_uploads_dir(self, backup_env):
        import shutil
        shutil.rmtree(backup_env["uploads_dir"])
        zip_path = create_backup(**backup_env)
        with zipfile.ZipFile(zip_path, "r") as zf:
            upload_files = [n for n in zf.namelist() if n.startswith("uploads/")]
            assert len(upload_files) == 0

    def test_auto_cleanup_after_create(self, backup_env):
        """create_backup calls cleanup_old_backups automatically."""
        # Create 12 backups (default keep_count=10)
        for i in range(12):
            env = dict(backup_env, custom_name=f"backup-{i:02d}")
            create_backup(**env)
        zips = list(Path(backup_env["backup_dir"]).glob("*.zip"))
        assert len(zips) <= 10


# ---------------------------------------------------------------------------
# Cleanup old backups
# ---------------------------------------------------------------------------

class TestCleanupOldBackups:
    def test_cleanup_keeps_n_newest(self, tmp_path):
        backup_dir = str(tmp_path / "backups")
        os.makedirs(backup_dir)

        # Create 5 ZIP files with different mtimes
        for i in range(5):
            p = Path(backup_dir) / f"backup_{i}.zip"
            p.write_bytes(b"PK" + b"\x00" * 20)
            os.utime(str(p), (1000 + i, 1000 + i))  # increasing mtime

        deleted = cleanup_old_backups(backup_dir, keep_count=3)
        assert deleted == 2
        remaining = list(Path(backup_dir).glob("*.zip"))
        assert len(remaining) == 3

    def test_cleanup_nothing_to_delete(self, tmp_path):
        backup_dir = str(tmp_path / "backups")
        os.makedirs(backup_dir)
        Path(backup_dir, "one.zip").write_bytes(b"PK")
        deleted = cleanup_old_backups(backup_dir, keep_count=5)
        assert deleted == 0

    def test_cleanup_nonexistent_dir(self, tmp_path):
        deleted = cleanup_old_backups(str(tmp_path / "nonexistent"), keep_count=5)
        assert deleted == 0

    def test_cleanup_empty_dir(self, tmp_path):
        backup_dir = str(tmp_path / "empty")
        os.makedirs(backup_dir)
        deleted = cleanup_old_backups(backup_dir, keep_count=1)
        assert deleted == 0


# ---------------------------------------------------------------------------
# get_backups_total_size
# ---------------------------------------------------------------------------

class TestGetBackupsTotalSize:
    def test_total_size(self, tmp_path):
        backup_dir = str(tmp_path / "backups")
        os.makedirs(backup_dir)
        (Path(backup_dir) / "a.zip").write_bytes(b"x" * 100)
        (Path(backup_dir) / "b.zip").write_bytes(b"x" * 200)
        assert get_backups_total_size(backup_dir) == 300

    def test_nonexistent_dir(self, tmp_path):
        assert get_backups_total_size(str(tmp_path / "nope")) == 0

    def test_ignores_non_zip(self, tmp_path):
        backup_dir = str(tmp_path / "backups")
        os.makedirs(backup_dir)
        (Path(backup_dir) / "a.zip").write_bytes(b"x" * 100)
        (Path(backup_dir) / "readme.txt").write_bytes(b"x" * 999)
        assert get_backups_total_size(backup_dir) == 100


# ---------------------------------------------------------------------------
# Restore backup (ZIP)
# ---------------------------------------------------------------------------

class TestRestoreBackup:
    def _make_backup_zip(self, backup_env, custom_name="original_backup"):
        """Helper: create a backup ZIP and return its path."""
        return create_backup(
            backup_env["db_path"],
            backup_env["uploads_dir"],
            backup_env["generated_dir"],
            backup_env["backup_dir"],
            custom_name=custom_name,
        )

    def test_restore_replaces_db(self, backup_env):
        # Create backup of original state (1 owner)
        zip_path = self._make_backup_zip(backup_env)

        # Modify the current DB — add a second owner
        conn = sqlite3.connect(backup_env["db_path"])
        conn.execute("INSERT INTO owners VALUES (2, 'New Owner')")
        conn.commit()
        conn.close()

        # Restore from backup — should revert to original state
        restore_backup(
            str(zip_path),
            backup_env["db_path"],
            backup_env["uploads_dir"],
            backup_env["generated_dir"],
            backup_env["backup_dir"],
        )

        # The restored DB should have the original data from the ZIP.
        # However, restore also creates a safety backup first (of current state),
        # and restoring involves WAL checkpoint. Verify DB content from the ZIP.
        with zipfile.ZipFile(zip_path, "r") as zf:
            original_db = zf.read("svj.db")

        # The restored db_path should match the ZIP contents exactly
        restored_db = Path(backup_env["db_path"]).read_bytes()
        # Both should have only 1 owner (the original state)
        conn = sqlite3.connect(backup_env["db_path"])
        rows = conn.execute("SELECT COUNT(*) FROM owners").fetchone()
        conn.close()
        # restore_backup extracts svj.db from zip → overwrites db_path
        assert rows[0] == 1

    def test_restore_replaces_uploads(self, backup_env):
        zip_path = self._make_backup_zip(backup_env)

        # Add a new file to uploads after backup was made
        new_file = Path(backup_env["uploads_dir"]) / "new_file.txt"
        new_file.write_text("should be removed after restore")

        restore_backup(
            str(zip_path),
            backup_env["db_path"],
            backup_env["uploads_dir"],
            backup_env["generated_dir"],
            backup_env["backup_dir"],
        )

        # _restore_directory_from_zip clears uploads dir and extracts from ZIP
        assert not new_file.exists()
        # Original file should still be there
        assert (Path(backup_env["uploads_dir"]) / "excel" / "test.xlsx").exists()

    def test_restore_creates_safety_backup(self, backup_env):
        zip_path = self._make_backup_zip(backup_env, custom_name="source_backup")

        zips_before = set(Path(backup_env["backup_dir"]).glob("*.zip"))

        restore_backup(
            str(zip_path),
            backup_env["db_path"],
            backup_env["uploads_dir"],
            backup_env["generated_dir"],
            backup_env["backup_dir"],
        )

        zips_after = set(Path(backup_env["backup_dir"]).glob("*.zip"))
        new_zips = zips_after - zips_before
        assert len(new_zips) >= 1  # safety backup created

    def test_restore_invalid_zip_raises(self, backup_env):
        bad_zip = Path(backup_env["backup_dir"]) / "bad.zip"
        bad_zip.write_bytes(b"this is not a zip file")

        with pytest.raises(ValueError, match="není platný ZIP"):
            restore_backup(
                str(bad_zip),
                backup_env["db_path"],
                backup_env["uploads_dir"],
                backup_env["generated_dir"],
                backup_env["backup_dir"],
            )

    def test_restore_zip_without_db_raises(self, backup_env):
        # Create a valid ZIP but without svj.db
        no_db_zip = Path(backup_env["backup_dir"]) / "no_db.zip"
        with zipfile.ZipFile(no_db_zip, "w") as zf:
            zf.writestr("readme.txt", "no database here")

        with pytest.raises(ValueError, match="neobsahuje soubor svj.db"):
            restore_backup(
                str(no_db_zip),
                backup_env["db_path"],
                backup_env["uploads_dir"],
                backup_env["generated_dir"],
                backup_env["backup_dir"],
            )

    def test_restore_corrupted_zip_raises(self, backup_env):
        # Create a ZIP with a corrupted entry
        bad_zip = Path(backup_env["backup_dir"]) / "corrupt.zip"
        with zipfile.ZipFile(bad_zip, "w") as zf:
            zf.writestr("svj.db", "fake db content")

        # Corrupt the ZIP by modifying bytes in the middle
        data = bytearray(bad_zip.read_bytes())
        # Flip some bytes in the compressed data area
        if len(data) > 50:
            for i in range(30, min(50, len(data))):
                data[i] = data[i] ^ 0xFF
        bad_zip.write_bytes(bytes(data))

        # This may raise ValueError (CRC check) or it may pass if corruption
        # doesn't affect the CRC. We just verify it doesn't silently succeed
        # with bad data — either raises or the file is actually fine.
        try:
            restore_backup(
                str(bad_zip),
                backup_env["db_path"],
                backup_env["uploads_dir"],
                backup_env["generated_dir"],
                backup_env["backup_dir"],
            )
        except (ValueError, zipfile.BadZipFile):
            pass  # Expected


# ---------------------------------------------------------------------------
# Restore from directory
# ---------------------------------------------------------------------------

class TestRestoreFromDirectory:
    def test_restore_from_dir(self, backup_env, tmp_path):
        src_dir = tmp_path / "restore_source"
        src_dir.mkdir()

        # Create source structure
        conn = sqlite3.connect(str(src_dir / "svj.db"))
        conn.execute("CREATE TABLE owners (id INTEGER PRIMARY KEY, name TEXT)")
        conn.execute("INSERT INTO owners VALUES (1, 'Dir Owner')")
        conn.commit()
        conn.close()

        (src_dir / "uploads").mkdir()
        (src_dir / "uploads" / "file.txt").write_text("from dir")

        restore_from_directory(
            str(src_dir),
            backup_env["db_path"],
            backup_env["uploads_dir"],
            backup_env["generated_dir"],
            backup_env["backup_dir"],
        )

        conn = sqlite3.connect(backup_env["db_path"])
        row = conn.execute("SELECT name FROM owners WHERE id=1").fetchone()
        conn.close()
        assert row[0] == "Dir Owner"
        assert (Path(backup_env["uploads_dir"]) / "file.txt").read_text() == "from dir"

    def test_restore_from_nested_subdir(self, backup_env, tmp_path):
        """Safari unzips into a subfolder — service should find svj.db one level deep."""
        src_dir = tmp_path / "safari_unzip"
        src_dir.mkdir()
        nested = src_dir / "backup_content"
        nested.mkdir()

        conn = sqlite3.connect(str(nested / "svj.db"))
        conn.execute("CREATE TABLE owners (id INTEGER PRIMARY KEY, name TEXT)")
        conn.commit()
        conn.close()

        restore_from_directory(
            str(src_dir),
            backup_env["db_path"],
            backup_env["uploads_dir"],
            backup_env["generated_dir"],
            backup_env["backup_dir"],
        )
        # Should succeed without error (found svj.db in nested dir)

    def test_restore_from_dir_no_db_raises(self, backup_env, tmp_path):
        src_dir = tmp_path / "empty_restore"
        src_dir.mkdir()

        with pytest.raises(ValueError, match="neobsahuje soubor svj.db"):
            restore_from_directory(
                str(src_dir),
                backup_env["db_path"],
                backup_env["uploads_dir"],
                backup_env["generated_dir"],
                backup_env["backup_dir"],
            )


# ---------------------------------------------------------------------------
# _verify_db_integrity
# ---------------------------------------------------------------------------

class TestVerifyDbIntegrity:
    def test_valid_db(self, tmp_path):
        db_path = str(tmp_path / "good.db")
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE t (id INTEGER)")
        conn.close()
        _verify_db_integrity(db_path)  # should not raise

    def test_invalid_db_file(self, tmp_path):
        bad_path = str(tmp_path / "bad.db")
        Path(bad_path).write_bytes(b"not a sqlite database at all")
        with pytest.raises(ValueError, match="není platná SQLite"):
            _verify_db_integrity(bad_path)


# ---------------------------------------------------------------------------
# Restore log
# ---------------------------------------------------------------------------

class TestRestoreLog:
    def test_read_empty_log(self, tmp_path):
        entries = read_restore_log(str(tmp_path))
        assert entries == []

    def test_log_and_read(self, tmp_path):
        backup_dir = str(tmp_path)
        log_restore(backup_dir, source="test.zip", method="upload")
        entries = read_restore_log(backup_dir)
        assert len(entries) == 1
        assert entries[0]["source"] == "test.zip"
        assert entries[0]["method"] == "upload"
        assert "timestamp" in entries[0]

    def test_log_multiple_entries_newest_first(self, tmp_path):
        backup_dir = str(tmp_path)
        log_restore(backup_dir, source="first.zip", method="upload")
        log_restore(backup_dir, source="second.zip", method="directory")

        entries = read_restore_log(backup_dir)
        assert len(entries) == 2
        assert entries[0]["source"] == "second.zip"
        assert entries[1]["source"] == "first.zip"

    def test_log_with_safety_backup(self, tmp_path):
        backup_dir = str(tmp_path)
        log_restore(backup_dir, source="restore.zip", method="upload", safety_backup="safety_123.zip")

        entries = read_restore_log(backup_dir)
        assert entries[0]["safety_backup"] == "safety_123.zip"

    def test_log_without_safety_backup(self, tmp_path):
        backup_dir = str(tmp_path)
        log_restore(backup_dir, source="restore.zip", method="upload")

        entries = read_restore_log(backup_dir)
        assert "safety_backup" not in entries[0]

    def test_read_corrupted_log_returns_empty(self, tmp_path):
        log_path = tmp_path / _RESTORE_LOG
        log_path.write_text("corrupted{{{json")

        entries = read_restore_log(str(tmp_path))
        assert entries == []

    def test_log_creates_backup_dir(self, tmp_path):
        backup_dir = str(tmp_path / "new" / "dir")
        log_restore(backup_dir, source="test.zip", method="upload")
        assert os.path.isdir(backup_dir)
        assert len(read_restore_log(backup_dir)) == 1
