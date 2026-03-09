"""Shared utility functions used across routers and services."""
import re
import time as _time
from pathlib import Path
from typing import List, Optional
from unicodedata import category, normalize

from fastapi import Request, UploadFile


def strip_diacritics(text: str) -> str:
    """Remove diacritics and lowercase for search/matching."""
    nfkd = normalize("NFD", text)
    return "".join(c for c in nfkd if category(c) != "Mn").lower()


def build_list_url(request: Request) -> str:
    """Build current page URL with query params for list_url context variable."""
    url = str(request.url.path)
    if request.url.query:
        url += "?" + str(request.url.query)
    return url


def is_htmx_partial(request: Request) -> bool:
    """Check if request is an HTMX partial (not boosted navigation)."""
    return bool(
        request.headers.get("HX-Request")
        and not request.headers.get("HX-Boosted")
    )


def fmt_num(value) -> str:
    """Format number with thousand separators. Hides .0 for whole numbers."""
    if value is None:
        return "—"
    if float(value) == int(value):
        return "{:,}".format(int(value)).replace(",", " ")
    return "{:,}".format(value).replace(",", " ")


def is_safe_path(file_path: Path, *allowed_dirs: Path) -> bool:
    """Check that resolved file_path is inside one of the allowed directories.

    Uses relative_to() instead of startswith() to prevent prefix attacks
    (e.g. /data/uploads_evil matching /data/uploads).
    Compatible with Python 3.9+ (no Path.is_relative_to).
    """
    try:
        resolved = file_path.resolve()
        for allowed in allowed_dirs:
            try:
                resolved.relative_to(allowed.resolve())
                return True
            except ValueError:
                continue
        return False
    except (OSError, ValueError):
        return False


# ── Centralizované upload limity ──────────────────────────────────────
UPLOAD_LIMITS = {
    "excel":    {"max_size_mb": 50,  "extensions": [".xlsx", ".xls"]},
    "csv":      {"max_size_mb": 50,  "extensions": [".csv"]},
    "csv_xlsx": {"max_size_mb": 50,  "extensions": [".csv", ".xlsx", ".xls"]},
    "pdf":      {"max_size_mb": 100, "extensions": [".pdf"]},
    "docx":     {"max_size_mb": 10,  "extensions": [".docx"]},
    "backup":   {"max_size_mb": 200, "extensions": [".zip"]},
    "db":       {"max_size_mb": 200, "extensions": [".db"]},
    "folder":   {"max_size_mb": 500, "extensions": []},
}


async def validate_upload(
    file: UploadFile,
    max_size_mb: int,
    allowed_extensions: List[str],
) -> Optional[str]:
    """Validate uploaded file size and extension.

    Returns error message (Czech) if invalid, None if valid.
    After validation the file seek position is reset to 0 so the caller
    can read the content normally.
    """
    # --- Extension check ---
    filename = file.filename or ""
    ext = Path(filename).suffix.lower()
    if ext not in [e.lower() for e in allowed_extensions]:
        nice = ", ".join(allowed_extensions)
        return f"Nepovolený typ souboru ({ext or 'bez přípony'}). Povolené: {nice}"

    # --- Size check ---
    max_bytes = max_size_mb * 1024 * 1024
    # Use pre-computed size if available (avoids reading entire file into memory)
    if file.size is not None:
        size_bytes = file.size
    else:
        content = await file.read()
        size_bytes = len(content)
        await file.seek(0)
    if size_bytes > max_bytes:
        size_nice = f"{size_bytes / (1024 * 1024):.1f}"
        return f"Soubor je příliš velký ({size_nice} MB). Maximum: {max_size_mb} MB"

    return None


async def validate_uploads(
    files: List[UploadFile],
    max_size_mb: int,
    allowed_extensions: List[str],
) -> Optional[str]:
    """Validate a list of uploaded files. Returns first error or None."""
    for file in files:
        if not file.filename:
            continue
        err = await validate_upload(file, max_size_mb, allowed_extensions)
        if err:
            return f"{file.filename}: {err}"
    return None


def excel_auto_width(ws, max_width: int = 45):
    """Auto-adjust column widths in an openpyxl worksheet."""
    for col in ws.columns:
        max_len = 0
        col_letter = col[0].column_letter
        for cell in col:
            if cell.value is not None:
                max_len = max(max_len, len(str(cell.value)))
        ws.column_dimensions[col_letter].width = min(max_len + 2, max_width)


_EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")


def is_valid_email(email: str) -> bool:
    """Basic email format validation."""
    return bool(_EMAIL_RE.match(email))


def setup_jinja_filters(templates):
    """Register custom Jinja2 filters on a Jinja2Templates instance."""
    templates.env.filters["fmt_num"] = fmt_num
    return templates


def compute_eta(current: int, total: int, started_at: float) -> dict:
    """Compute progress percentage, elapsed and ETA text.

    Returns dict with keys: pct, elapsed, eta.
    """
    pct = int(current / total * 100) if total > 0 else 0
    elapsed = _time.monotonic() - started_at

    eta_text = ""
    if current > 0 and total > 0:
        remaining = (total - current) * (elapsed / current)
        if remaining >= 60:
            eta_text = f"{int(remaining // 60)} min {int(remaining % 60)} s"
        elif remaining >= 1:
            eta_text = f"{int(remaining)} s"

    if elapsed >= 60:
        elapsed_text = f"{int(elapsed // 60)} min {int(elapsed % 60)} s"
    else:
        elapsed_text = f"{int(elapsed)} s"

    return {"pct": pct, "elapsed": elapsed_text, "eta": eta_text}
