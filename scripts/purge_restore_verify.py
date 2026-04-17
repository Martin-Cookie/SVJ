#!/usr/bin/env python3
"""Purge/Restore/Verify test — izolovaný sandbox v /tmp.

Spustí end-to-end test:
1. Statická kontrola pokrytí purge (modely vs _PURGE_CATEGORIES)
2. Statická kontrola pokrytí zálohy (grep file writes mimo settings dirs)
3. Zkopíruje reálná data do /tmp sandboxu
4. Vytvoří zálohu
5. Udělá baseline snímek DB countů
6. Smaže všechna data (POST /sprava/smazat-data)
7. Ověří že DB je prázdná
8. Obnoví zálohu (POST /sprava/zaloha/{file}/obnovit)
9. Porovná counts s baseline
10. Smoke test list stránek (HTTP 200)
11. Deep test detail entit (joinedload relací)

Výsledek: markdown report v data/purge_restore_reports/ + exit code 0/1.
Sandbox se vždy smaže (i při selhání), reálná data zůstanou nedotčená.

Spouští se: python scripts/purge_restore_verify.py
"""

from __future__ import annotations

import os
import shutil
import sys
import traceback
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ---------------------------------------------------------------------------
# Sandbox setup (must run before any `from app.*` import)
# ---------------------------------------------------------------------------

def setup_sandbox() -> Path:
    """Zkopíruje reálná data do /tmp sandboxu a přepíše env pro pydantic settings."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    sandbox = Path(f"/tmp/svj-test-{ts}")
    sandbox.mkdir(parents=True)

    real_db = PROJECT_ROOT / "data" / "svj.db"
    real_uploads = PROJECT_ROOT / "data" / "uploads"
    real_generated = PROJECT_ROOT / "data" / "generated"
    real_env = PROJECT_ROOT / ".env"

    if real_db.exists():
        shutil.copy2(real_db, sandbox / "svj.db")
    if real_uploads.exists():
        shutil.copytree(real_uploads, sandbox / "uploads")
    else:
        (sandbox / "uploads").mkdir()
    if real_generated.exists():
        shutil.copytree(real_generated, sandbox / "generated")
    else:
        (sandbox / "generated").mkdir()

    (sandbox / "backups").mkdir()
    (sandbox / "temp").mkdir()

    if real_env.exists():
        shutil.copy2(real_env, sandbox / ".env")

    # Override pydantic settings via env (must happen before app.config import)
    os.environ["DATABASE_PATH"] = str(sandbox / "svj.db")
    os.environ["UPLOAD_DIR"] = str(sandbox / "uploads")
    os.environ["GENERATED_DIR"] = str(sandbox / "generated")
    os.environ["BACKUP_DIR"] = str(sandbox / "backups")
    os.environ["TEMP_DIR"] = str(sandbox / "temp")

    return sandbox


# ---------------------------------------------------------------------------
# Phase 0: Static purge coverage check
# ---------------------------------------------------------------------------

def check_purge_coverage() -> dict:
    """Ověří že všechny modely v Base.metadata jsou v _PURGE_CATEGORIES."""
    from app.database import Base
    import app.models  # noqa: F401 — načte všechny modely
    from app.routers.administration._helpers import _PURGE_CATEGORIES

    all_tables = set(Base.metadata.tables.keys())
    covered = set()
    for cat in _PURGE_CATEGORIES.values():
        for model in cat.get("models", []):
            covered.add(model.__tablename__)

    uncovered = sorted(all_tables - covered)

    return {
        "phase": "0. Static purge coverage",
        "status": "FAIL" if uncovered else "PASS",
        "details": {
            "total_tables": len(all_tables),
            "covered": len(covered),
            "uncovered": uncovered or "—",
        },
    }


# ---------------------------------------------------------------------------
# Phase 1: Static backup coverage check (grep)
# ---------------------------------------------------------------------------

def check_backup_coverage() -> dict:
    """Prohledá app/*.py za file-write operace mimo settings adresáře.

    Context-aware: pro každý match se podívá na okolní řádky (±5) a hledá
    odkaz na `settings.*_dir` nebo ekvivalent. Pokud najde → OK (safe root).
    """
    import re

    pattern = re.compile(
        r"""(\bopen\(['"][^'"]+['"]|"""
        r"""\.mkdir\(parents=|"""
        r"""shutil\.(copy|copyfileobj|copytree|move|rmtree))"""
    )

    # Safe root indicators — pokud je kdekoli v okolním bloku, match je OK
    safe_roots = re.compile(
        r"""settings\.|upload_dir|generated_dir|backup_dir|"""
        r"""database_path|temp_dir|DB_PATH|UPLOADS_DIR|GENERATED_DIR|"""
        r"""BACKUP_DIR|TEMP_DIR|tempfile\.|NamedTemporaryFile|"""
        r"""env_path|\.env|reports_dir|BASE_DIR|"""
        r"""ballot.*pdf_path|generate.*\.docx|word_templates"""
    )

    # Soubory, které přirozeně pracují s file paths — vyloučené z kontroly
    whitelisted_files = {
        "app/services/backup_service.py",  # je celé o zálohách
        "app/routers/administration/backups.py",  # backup/restore router
        "app/main.py",  # lifespan mkdir
    }

    CONTEXT = 5
    suspicious = []
    app_dir = PROJECT_ROOT / "app"
    for py_file in app_dir.rglob("*.py"):
        rel = py_file.relative_to(PROJECT_ROOT)
        if str(rel) in whitelisted_files:
            continue
        try:
            lines = py_file.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for lineno, line in enumerate(lines, 1):
            if not pattern.search(line):
                continue
            stripped = line.strip()
            if re.search(r"""open\([^)]*['"]r[b]?['"]""", stripped):
                continue
            # Check context window
            start = max(0, lineno - 1 - CONTEXT)
            end = min(len(lines), lineno - 1 + CONTEXT + 1)
            context = "\n".join(lines[start:end])
            if safe_roots.search(context):
                continue
            suspicious.append(f"{rel}:{lineno}: {stripped[:120]}")

    return {
        "phase": "1. Static backup coverage",
        "status": "WARN" if suspicious else "PASS",
        "details": {
            "note": "grep po open/mkdir/shutil mimo settings adresáře (může dát false positives)",
            "suspicious_count": len(suspicious),
            "samples": suspicious[:10] if suspicious else "—",
        },
    }


# ---------------------------------------------------------------------------
# Phase 2-7: Dynamic test in sandbox (TestClient)
# ---------------------------------------------------------------------------

def _count_all_tables(db_path: Path) -> dict:
    """Počítá řádky ve všech tabulkách přes raw sqlite3 (obchází SQLAlchemy pool).

    Force WAL checkpoint před čtením — po restore může být starý WAL obsah
    který by kombinoval s čerstvě přepsaným main DB souborem.
    """
    import sqlite3

    counts = {}
    conn = sqlite3.connect(str(db_path))
    try:
        # Force WAL flush — zabrání stale reads po restoru
        try:
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        except sqlite3.OperationalError:
            pass
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r[0] for r in cursor.fetchall() if not r[0].startswith("sqlite_")]
        for tbl in sorted(tables):
            cursor.execute(f"SELECT COUNT(*) FROM {tbl}")
            counts[tbl] = cursor.fetchone()[0]
    finally:
        conn.close()
    return counts


def _db_file_info(db_path: Path) -> dict:
    """Diagnostika — velikost main DB + WAL + SHM souborů."""
    import hashlib

    def _info(p: Path):
        if not p.exists():
            return "—"
        size = p.stat().st_size
        sha = hashlib.sha256(p.read_bytes()).hexdigest()[:10]
        return f"{size}B sha={sha}"

    return {
        "svj.db": _info(db_path),
        "svj.db-wal": _info(db_path.with_suffix(".db-wal")),
        "svj.db-shm": _info(db_path.with_suffix(".db-shm")),
    }


def _get_first_id(db_path: Path, table: str) -> int | None:
    """Vrátí první id z tabulky přes raw sqlite3, nebo None pokud je prázdná."""
    import sqlite3

    conn = sqlite3.connect(str(db_path))
    try:
        cursor = conn.cursor()
        cursor.execute(f"SELECT id FROM {table} ORDER BY id LIMIT 1")
        row = cursor.fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def run_dynamic_test(sandbox: Path) -> list[dict]:
    """Fáze 2-7: Backup → purge → restore → verify přes TestClient."""
    from fastapi.testclient import TestClient
    from app.main import app
    from app.routers.administration._helpers import _PURGE_ORDER

    db_path = sandbox / "svj.db"
    results = []
    results.append({
        "phase": "2. Sandbox setup",
        "status": "PASS",
        "details": {"path": str(sandbox)},
    })

    with TestClient(app) as client:
        # ----- Phase 3: Create backup -----
        resp = client.post(
            "/sprava/zaloha/vytvorit",
            data={"filename": "purge_test_backup"},
            follow_redirects=False,
        )
        loc = resp.headers.get("location", "")
        if resp.status_code != 302 or "chyba" in loc:
            results.append({
                "phase": "3. Create backup",
                "status": "FAIL",
                "details": {"status": resp.status_code, "location": loc},
            })
            return results

        backup_files = list((sandbox / "backups").glob("*.zip"))
        backup_files = [f for f in backup_files if not f.name.startswith("_safety_")]
        if not backup_files:
            results.append({
                "phase": "3. Create backup",
                "status": "FAIL",
                "details": {"error": "ZIP soubor nebyl vytvořen"},
            })
            return results
        backup_filename = backup_files[0].name
        results.append({
            "phase": "3. Create backup",
            "status": "PASS",
            "details": {
                "filename": backup_filename,
                "size_kb": backup_files[0].stat().st_size // 1024,
            },
        })

        # ----- Phase 4: Baseline counts (post-backup = backup contents) -----
        baseline = _count_all_tables(db_path)
        total_baseline = sum(baseline.values())
        results.append({
            "phase": "4. Baseline counts (post-backup)",
            "status": "PASS" if total_baseline > 0 else "WARN",
            "details": {
                "total_rows": total_baseline,
                "tables": len(baseline),
                "note": "pokud reálná DB je prázdná, test nemá co ověřit",
            },
        })

        if total_baseline == 0:
            results.append({
                "phase": "5-7. Skipped",
                "status": "WARN",
                "details": "Reálná DB je prázdná, purge/restore/verify přeskočeny",
            })
            return results

        # ----- Phase 5: Purge all -----
        # Vynecháváme "backups" a "restore_log" — purge by je smazal včetně naší
        # testovací zálohy, kterou potřebujeme pro následný restore. Odpovídá
        # reálnému scénáři: admin neodstraňuje záloh, ze které chce obnovit.
        purge_categories = [c for c in _PURGE_ORDER if c not in ("backups", "restore_log")]
        purge_form = {
            "confirmation": "DELETE",
            "categories": purge_categories,
        }
        resp = client.post(
            "/sprava/smazat-data",
            data=purge_form,
            follow_redirects=False,
        )
        purge_loc = resp.headers.get("location", "")
        # Router při invalid form redirectne zpět na /sprava/smazat, při úspěchu na /sprava
        if resp.status_code != 302 or "/sprava/smazat" in purge_loc:
            results.append({
                "phase": "5. Purge",
                "status": "FAIL",
                "details": {
                    "status": resp.status_code,
                    "location": purge_loc,
                    "note": "router redirectnul zpět na purge stránku — form neprošel validací",
                    "body": resp.text[:300],
                },
            })
            return results

        post_purge = _count_all_tables(db_path)
        # Tolerance: purge endpoint sám volá log_activity → activity_logs má 1 záznam
        non_empty = {k: v for k, v in post_purge.items() if v > 0}
        allowed_residual = {"activity_logs"}
        unexpected = {k: v for k, v in non_empty.items() if k not in allowed_residual}

        if unexpected:
            results.append({
                "phase": "5. Purge",
                "status": "FAIL",
                "details": {
                    "note": "tabulky zůstaly neprázdné po purge",
                    "unexpected": unexpected,
                },
            })
            return results

        results.append({
            "phase": "5. Purge",
            "status": "PASS",
            "details": {
                "deleted_rows": total_baseline - sum(post_purge.values()),
                "residual_activity_logs": post_purge.get("activity_logs", 0),
            },
        })

        # ----- Phase 6: Restore -----
        resp = client.post(
            f"/sprava/zaloha/{backup_filename}/obnovit",
            follow_redirects=False,
        )
        loc = resp.headers.get("location", "")
        if resp.status_code != 302 or "chyba" in loc:
            results.append({
                "phase": "6. Restore",
                "status": "FAIL",
                "details": {"status": resp.status_code, "location": loc},
            })
            return results
        # Diagnostic: srovnej hash souboru po restore vs hash svj.db uvnitř backup ZIPu
        import hashlib
        import zipfile as _zf

        post_restore_sha = hashlib.sha256(db_path.read_bytes()).hexdigest()[:12]
        backup_dir_contents = sorted(p.name for p in (sandbox / "backups").iterdir())
        backup_sha = "?"
        backup_db_size = 0
        # ZIP with our original backup name — or find any non-safety ZIP
        candidate_zips = [
            p for p in (sandbox / "backups").glob("*.zip")
            if not p.name.startswith("_safety_")
        ]
        try:
            if candidate_zips:
                with _zf.ZipFile(candidate_zips[0]) as z:
                    with z.open("svj.db") as f:
                        content = f.read()
                        backup_sha = hashlib.sha256(content).hexdigest()[:12]
                        backup_db_size = len(content)
            else:
                backup_sha = "no non-safety ZIP found"
        except Exception as e:
            backup_sha = f"err: {e}"

        file_info_after_restore = _db_file_info(db_path)

        # Force WAL/SHM cleanup — jiná connection může držet stale state
        wal_file = db_path.with_suffix(".db-wal")
        shm_file = db_path.with_suffix(".db-shm")
        wal_existed = wal_file.exists()
        shm_existed = shm_file.exists()

        results.append({
            "phase": "6. Restore",
            "status": "PASS",
            "details": {
                "filename": backup_filename,
                "flash": loc,
                "db_files_after": file_info_after_restore,
                "backup_db_sha": backup_sha,
                "backup_db_size": backup_db_size,
                "post_restore_sha": post_restore_sha,
                "hash_match": backup_sha == post_restore_sha,
                "wal_existed": wal_existed,
                "shm_existed": shm_existed,
                "backup_dir_contents": backup_dir_contents,
            },
        })

        # ----- Phase 7a: Verify counts match baseline -----
        post_restore = _count_all_tables(db_path)

        mismatches = {}
        for tbl, b in baseline.items():
            p = post_restore.get(tbl, 0)
            if tbl == "activity_logs":
                # Restore a purge oba loggují → tolerance až +5
                if p < b or p > b + 5:
                    mismatches[tbl] = f"baseline={b}, post={p}"
            elif p != b:
                mismatches[tbl] = f"baseline={b}, post={p}"

        results.append({
            "phase": "7a. Verify counts vs baseline",
            "status": "FAIL" if mismatches else "PASS",
            "details": {
                "tables_checked": len(baseline),
                "mismatches": mismatches or "—",
            },
        })

        # ----- Phase 7b: HTTP smoke test -----
        smoke_urls = [
            "/", "/vlastnici", "/jednotky", "/prostory", "/najemci",
            "/hlasovani", "/rozesilani", "/platby", "/synchronizace",
            "/kontrola-podilu", "/sprava", "/nastaveni",
        ]
        smoke_results = {}
        failed_urls = []
        for url in smoke_urls:
            r = client.get(url, follow_redirects=True)
            smoke_results[url] = r.status_code
            if r.status_code != 200:
                failed_urls.append(f"{url} → {r.status_code}")

        results.append({
            "phase": "7b. HTTP smoke test (list stránky)",
            "status": "FAIL" if failed_urls else "PASS",
            "details": {
                "tested": len(smoke_urls),
                "failed": failed_urls or "—",
            },
        })

        # ----- Phase 7c: Deep detail test (IDs přes raw sqlite3) -----
        detail_map = [
            ("owners", "/vlastnici/{id}"),
            ("units", "/jednotky/{id}"),
            ("spaces", "/prostory/{id}"),
            ("tenants", "/najemci/{id}"),
            ("votings", "/hlasovani/{id}"),
            ("tax_sessions", "/rozesilani/{id}"),
            ("sync_sessions", "/synchronizace/{id}"),
            ("bank_statements", "/platby/vypisy/{id}"),
            ("share_check_sessions", "/kontrola-podilu/{id}"),
        ]

        detail_results = []
        failed_details = []
        for table, url_pat in detail_map:
            entity_id = _get_first_id(db_path, table)
            if entity_id is None:
                detail_results.append(f"{table}: bez dat (skip)")
                continue
            url = url_pat.format(id=entity_id)
            r = client.get(url, follow_redirects=True)
            if r.status_code != 200:
                msg = f"{table} {url} → {r.status_code}"
                detail_results.append(msg)
                failed_details.append(msg)
            else:
                detail_results.append(f"{table} {url} → 200")

        results.append({
            "phase": "7c. Deep detail test (joinedload relací)",
            "status": "FAIL" if failed_details else "PASS",
            "details": {
                "results": detail_results,
            },
        })

    return results


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def write_report(phases: list[dict], sandbox: Path) -> Path:
    reports_dir = PROJECT_ROOT / "data" / "purge_restore_reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = reports_dir / f"report_{ts}.md"

    statuses = [p["status"] for p in phases]
    passed = sum(1 for s in statuses if s == "PASS")
    failed = sum(1 for s in statuses if s == "FAIL")
    warned = sum(1 for s in statuses if s == "WARN")
    total = len(phases)

    overall = "PASS" if failed == 0 else "FAIL"

    lines = [
        f"# Purge/Restore/Verify report — {ts}",
        "",
        f"**Celkový výsledek**: **{overall}**",
        f"**Fáze**: {passed}/{total} PASS, {failed} FAIL, {warned} WARN",
        f"**Sandbox**: `{sandbox}`",
        "",
        "---",
        "",
    ]

    for p in phases:
        icon = {"PASS": "✅", "FAIL": "❌", "WARN": "⚠️"}.get(p["status"], "?")
        lines.append(f"## {icon} {p['phase']} — {p['status']}")
        lines.append("")
        details = p.get("details", {})
        if isinstance(details, dict):
            for k, v in details.items():
                if isinstance(v, (list, tuple)):
                    if not v:
                        lines.append(f"- **{k}**: —")
                    else:
                        lines.append(f"- **{k}**:")
                        for item in v:
                            lines.append(f"  - `{item}`")
                elif isinstance(v, dict):
                    if not v:
                        lines.append(f"- **{k}**: —")
                    else:
                        lines.append(f"- **{k}**:")
                        for ik, iv in v.items():
                            lines.append(f"  - `{ik}`: `{iv}`")
                else:
                    lines.append(f"- **{k}**: `{v}`")
        else:
            lines.append(f"```\n{details}\n```")
        lines.append("")

    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    print("=== Purge/Restore/Verify test ===")
    start = datetime.now()

    sandbox = setup_sandbox()
    print(f"Sandbox: {sandbox}")

    phases: list[dict] = []
    try:
        # Static checks (imports app modules → used sandbox env)
        phases.append(check_purge_coverage())
        phases.append(check_backup_coverage())

        # Dynamic test
        phases.extend(run_dynamic_test(sandbox))
    except Exception as e:
        phases.append({
            "phase": "EXCEPTION",
            "status": "FAIL",
            "details": {
                "error": str(e),
                "traceback": traceback.format_exc()[:2000],
            },
        })
    finally:
        report_path = write_report(phases, sandbox)
        shutil.rmtree(sandbox, ignore_errors=True)

    elapsed = (datetime.now() - start).total_seconds()

    passed = sum(1 for p in phases if p["status"] == "PASS")
    failed = sum(1 for p in phases if p["status"] == "FAIL")
    warned = sum(1 for p in phases if p["status"] == "WARN")

    print()
    print(f"Report: {report_path}")
    print(f"Sandbox smazán: {sandbox}")
    print(f"Fáze: {len(phases)} ({passed} PASS, {failed} FAIL, {warned} WARN)")
    print(f"Čas: {elapsed:.1f}s")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
