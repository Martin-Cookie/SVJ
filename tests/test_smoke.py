"""Smoke tests — app starts, routes exist, basic pages load.

Používá in-memory SQLite TestClient (viz conftest.py). Neskipujeme na CI —
testy zachytí rozbitou registraci routerů, chybějící template proměnné
a 500 chyby na prázdné DB.
"""
import pytest


def test_app_starts(client):
    """FastAPI app should start and return a response for root."""
    response = client.get("/")
    # Root redirects to /prehled or returns 200
    assert response.status_code in (200, 302, 307)


def test_owners_package_routes(client):
    """Owners package should register key routes."""
    from app.main import app

    route_paths = [r.path for r in app.routes]
    assert any("/vlastnici" in p for p in route_paths)


@pytest.mark.parametrize("url", [
    "/",
    "/vlastnici",
    "/jednotky",
    "/najemci",
    "/prostory",
    "/hlasovani",
    "/rozesilani",
    "/platby",
    "/platby/predpisy",
    "/platby/symboly",
    "/platby/vypisy",
    "/platby/zustatky",
    "/synchronizace",
    "/sprava",
    "/nastaveni",
    "/kontrola-podilu",
    "/rozesilani/bounces",
])
def test_top_level_urls_return_ok(client, url):
    """Smoke — všechny top-level URL musí vrátit 200/302/307 (ne 500).

    Zachytí: rozbitou registraci routeru, chybějící template proměnnou,
    N+1 selhání na prázdné DB, 500 na missing context key.
    """
    response = client.get(url)
    assert response.status_code in (200, 302, 307), (
        f"{url} vrátilo {response.status_code}"
    )
