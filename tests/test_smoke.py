"""Smoke tests — app starts, routes exist, basic pages load."""


def test_app_starts(client):
    """FastAPI app should start and return a response for root."""
    response = client.get("/")
    # Root redirects to /prehled or returns 200
    assert response.status_code in (200, 302, 307), f"Got {response.status_code}: {response.text[:500]}"


def test_owners_package_routes(client):
    """Owners package should register key routes."""
    from app.main import app

    route_paths = [r.path for r in app.routes]
    assert "/vlastnici/" in route_paths or any("/vlastnici" in p for p in route_paths)


def test_dashboard_loads(client):
    """GET / (dashboard) should return 200."""
    response = client.get("/")
    assert response.status_code == 200, f"Got {response.status_code}: {response.text[:500]}"
