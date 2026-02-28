"""Shared utility functions used across routers and services."""
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
