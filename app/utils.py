"""Shared utility functions used across routers and services."""
from pathlib import Path
from unicodedata import category, normalize

from fastapi import Request


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


def setup_jinja_filters(templates):
    """Register custom Jinja2 filters on a Jinja2Templates instance."""
    templates.env.filters["fmt_num"] = fmt_num
    return templates
