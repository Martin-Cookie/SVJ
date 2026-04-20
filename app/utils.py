"""Shared utility functions used across routers and services."""
import base64
import logging
import re
import time as _time
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional
from unicodedata import category, normalize

from cryptography.fernet import Fernet, InvalidToken
from fastapi import Request, UploadFile

_logger = logging.getLogger(__name__)

# ── SMTP password encryption ────────────────────────────────────────────────
_SMTP_KEY_PATH = Path(__file__).resolve().parent.parent / "data" / ".smtp_key"
_fernet: Optional[Fernet] = None


def _get_fernet() -> Fernet:
    """Lazy-load or generate Fernet key from data/.smtp_key."""
    global _fernet
    if _fernet is not None:
        return _fernet
    if _SMTP_KEY_PATH.exists():
        key = _SMTP_KEY_PATH.read_bytes().strip()
    else:
        key = Fernet.generate_key()
        _SMTP_KEY_PATH.parent.mkdir(parents=True, exist_ok=True)
        _SMTP_KEY_PATH.write_bytes(key)
    _fernet = Fernet(key)
    return _fernet


def utcnow() -> datetime:
    """Naive UTC datetime — náhrada za deprecated datetime.utcnow() (Python 3.12+)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def strip_diacritics(text: str) -> str:
    """Remove diacritics and lowercase for search/matching."""
    nfkd = normalize("NFD", text)
    return "".join(c for c in nfkd if category(c) != "Mn").lower()


def encode_smtp_password(plain: str) -> str:
    """Fernet šifrování SMTP hesla pro uložení v DB."""
    return _get_fernet().encrypt(plain.encode()).decode()


def decode_smtp_password(stored: str) -> str:
    """Dešifrování SMTP hesla z DB. Fallback na base64 pro zpětnou kompatibilitu."""
    try:
        return _get_fernet().decrypt(stored.encode()).decode()
    except (InvalidToken, Exception):
        # Fallback: staré base64-only heslo — dekódovat a vrátit
        try:
            return base64.b64decode(stored.encode()).decode()
        except Exception:
            _logger.warning("Cannot decrypt SMTP password — returning empty")
            return ""


def flash_from_params(request: Request, flash_map: dict, **extra_ctx) -> tuple[str, str]:
    """Read flash code from query params and resolve to (message, type).

    ``flash_map`` maps flash codes to ``(message, type)`` tuples.
    Message may contain ``{key}`` placeholders filled from query params or *extra_ctx*.
    Returns ``("", "")`` when no flash or unknown code.

    Usage::

        flash_message, flash_type = flash_from_params(request, {
            "import_ok": ("Import dokončen — {count} záznamů.", "success"),
            "deleted":   ("Smazáno.", "success"),
        })
    """
    code = request.query_params.get("flash", "")
    if not code or code not in flash_map:
        return "", ""
    msg_tpl, flash_type = flash_map[code]
    ctx = dict(extra_ctx)
    for k, v in request.query_params.items():
        if v:
            ctx[k] = v
    try:
        msg = msg_tpl.format_map(ctx)
    except (KeyError, IndexError):
        msg = msg_tpl
    return msg, flash_type


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
    "excel":    {"max_size_mb": 50,  "allowed_extensions": [".xlsx", ".xls"]},
    "csv":      {"max_size_mb": 50,  "allowed_extensions": [".csv"]},
    "csv_xlsx": {"max_size_mb": 50,  "allowed_extensions": [".csv", ".xlsx", ".xls"]},
    "pdf":      {"max_size_mb": 100, "allowed_extensions": [".pdf"]},
    "docx":     {"max_size_mb": 10,  "allowed_extensions": [".docx"]},
    "backup":   {"max_size_mb": 200, "allowed_extensions": [".zip"]},
    "db":       {"max_size_mb": 200, "allowed_extensions": [".db"]},
    "folder":   {"max_size_mb": 500, "allowed_extensions": []},
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


def get_invalid_emails(db) -> set:
    """Načte všechny emailové adresy vlastníků označených jako email_invalid (hard bounce)."""
    from app.models import Owner
    invalid = set()
    for o in db.query(Owner).filter(Owner.email_invalid == True).all():  # noqa: E712
        for field in (o.email, o.email_secondary):
            if field:
                for e in field.replace(",", ";").split(";"):
                    e = e.strip().lower()
                    if e:
                        invalid.add(e)
    return invalid


def setup_jinja_filters(templates):
    """Register custom Jinja2 filters on a Jinja2Templates instance."""
    templates.env.filters["fmt_num"] = fmt_num
    return templates


def _create_templates():
    """Create shared Jinja2Templates instance with custom filters."""
    from fastapi.templating import Jinja2Templates
    t = Jinja2Templates(directory="app/templates")
    setup_jinja_filters(t)
    return t


templates = _create_templates()


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


def build_wizard_steps(
    step_defs: list,
    current_step: int,
    max_done: int,
    sending_step: Optional[int] = None,
) -> list:
    """Build wizard step list with statuses (done/active/pending/sending).

    step_defs: list of {"label": "..."} dicts
    current_step: 1-based current step
    max_done: highest completed step number
    sending_step: if set, this step gets "sending" status when it's current
    """
    steps = []
    for i, s in enumerate(step_defs, 1):
        if i < current_step and i <= max_done:
            status = "done"
        elif i == current_step:
            if sending_step and i == sending_step:
                status = "sending"
            else:
                status = "done" if i <= max_done else "active"
        elif i <= max_done:
            status = "done"
        else:
            status = "pending"
        steps.append({"label": s["label"], "status": status})
    return steps


_IMPORT_STEPS = [
    {"label": "Nahrání"},
    {"label": "Mapování"},
    {"label": "Náhled"},
    {"label": "Výsledek"},
]


def build_import_wizard(current_step: int) -> dict:
    """Build wizard context for import workflows (4 fixed steps).

    Returns dict with wizard_steps, wizard_current, wizard_total for wizard_stepper.html.
    """
    steps = build_wizard_steps(_IMPORT_STEPS, current_step, max_done=current_step - 1)
    return {
        "wizard_steps": steps,
        "wizard_current": current_step,
        "wizard_total": 4,
    }


def build_name_with_titles(title: Optional[str], first_name: str, last_name: Optional[str]) -> str:
    """Build display name: title + příjmení + jméno."""
    parts = []
    if title:
        parts.append(title)
    if last_name:
        parts.append(last_name)
    if first_name:
        parts.append(first_name)
    return " ".join(parts)


def render_email_template(template_str: str, context: dict) -> str:
    """Render email template string with Jinja2 variables.

    Supports {{ variable }} syntax. Unknown variables render as empty string.
    """
    from jinja2 import BaseLoader, Environment
    env = Environment(loader=BaseLoader(), undefined=__import__("jinja2").Undefined)
    # Register fmt_num filter for number formatting
    env.filters["fmt_num"] = fmt_num
    try:
        tmpl = env.from_string(template_str)
        return tmpl.render(**context)
    except Exception:
        return template_str
