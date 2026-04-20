"""Tests for water meters module — helpers, deviation calculation, smoke tests."""
import pytest
from datetime import date
from types import SimpleNamespace

from app.routers.water_meters._helpers import (
    compute_consumption,
    compute_deviations,
    parse_unit_label,
    normalize_unit_label,
)


# ---------------------------------------------------------------------------
# parse_unit_label
# ---------------------------------------------------------------------------

class TestParseUnitLabel:
    def test_simple(self):
        assert parse_unit_label("A 111") == (111, "A", "")

    def test_with_suffix(self):
        assert parse_unit_label("B 212 A") == (212, "B", "A")

    def test_suffix_no_space(self):
        assert parse_unit_label("C 143B") == (143, "C", "B")

    def test_multi_letter(self):
        assert parse_unit_label("AK 11") == (11, "AK", "")

    def test_zero(self):
        assert parse_unit_label("0") == (None, "", "")

    def test_empty(self):
        assert parse_unit_label("") == (None, "", "")

    def test_none(self):
        assert parse_unit_label(None) == (None, "", "")

    def test_number_only(self):
        assert parse_unit_label("111") == (111, "", "")


# ---------------------------------------------------------------------------
# normalize_unit_label
# ---------------------------------------------------------------------------

class TestNormalizeUnitLabel:
    def test_suffix_no_space(self):
        assert normalize_unit_label("C 143B") == "C 143 B"

    def test_no_space(self):
        assert normalize_unit_label("D212") == "D 212"

    def test_multi_letter_suffix(self):
        assert normalize_unit_label("BK 11A") == "BK 11 A"

    def test_already_normalized(self):
        assert normalize_unit_label("A 111") == "A 111"

    def test_zero(self):
        assert normalize_unit_label("0") == ""


# ---------------------------------------------------------------------------
# compute_consumption
# ---------------------------------------------------------------------------

def _make_meter(readings_data, meter_type="cold"):
    """Create a SimpleNamespace meter with readings."""
    readings = [
        SimpleNamespace(reading_date=d, value=v)
        for d, v in readings_data
    ]
    return SimpleNamespace(
        id=1,
        readings=readings,
        meter_type=meter_type,
    )


class TestComputeConsumption:
    def test_two_readings(self):
        meter = _make_meter([
            (date(2025, 1, 1), 100.0),
            (date(2025, 6, 1), 112.5),
        ])
        assert compute_consumption(meter) == 12.5

    def test_one_reading_returns_none(self):
        meter = _make_meter([(date(2025, 1, 1), 100.0)])
        assert compute_consumption(meter) is None

    def test_no_readings_returns_none(self):
        meter = _make_meter([])
        assert compute_consumption(meter) is None

    def test_three_readings_uses_last_two(self):
        """Consumption = last - second to last (chronological)."""
        meter = _make_meter([
            (date(2025, 1, 1), 100.0),
            (date(2025, 6, 1), 110.0),
            (date(2025, 12, 1), 118.0),
        ])
        assert compute_consumption(meter) == 8.0

    def test_none_value_returns_none(self):
        meter = _make_meter([
            (date(2025, 1, 1), 100.0),
            (date(2025, 6, 1), None),
        ])
        assert compute_consumption(meter) is None


# ---------------------------------------------------------------------------
# compute_deviations
# ---------------------------------------------------------------------------

class TestComputeDeviations:
    def test_empty_list(self):
        assert compute_deviations([]) == {}

    def test_single_meter_no_deviation(self):
        """Single meter = avg is itself, deviation is 0."""
        meter = _make_meter([
            (date(2025, 1, 1), 100.0),
            (date(2025, 6, 1), 110.0),
        ])
        result = compute_deviations([meter])
        assert result[1]["consumption"] == 10.0
        assert result[1]["deviation_pct"] == 0.0

    def test_two_meters_opposite_deviations(self):
        m1 = SimpleNamespace(
            id=1,
            readings=[
                SimpleNamespace(reading_date=date(2025, 1, 1), value=100.0),
                SimpleNamespace(reading_date=date(2025, 6, 1), value=110.0),
            ],
            meter_type="cold",
        )
        m2 = SimpleNamespace(
            id=2,
            readings=[
                SimpleNamespace(reading_date=date(2025, 1, 1), value=200.0),
                SimpleNamespace(reading_date=date(2025, 6, 1), value=230.0),
            ],
            meter_type="cold",
        )
        result = compute_deviations([m1, m2])
        # Avg = (10 + 30) / 2 = 20
        # m1: (10-20)/20 = -50%
        # m2: (30-20)/20 = +50%
        assert result[1]["deviation_pct"] == -50.0
        assert result[2]["deviation_pct"] == 50.0

    def test_meter_without_readings(self):
        meter = _make_meter([])
        result = compute_deviations([meter])
        assert result[1]["consumption"] is None
        assert result[1]["deviation_pct"] is None


# ---------------------------------------------------------------------------
# Smoke tests
# ---------------------------------------------------------------------------

def test_vodometry_returns_ok(client):
    """Smoke: /vodometry page loads on empty DB."""
    response = client.get("/vodometry")
    assert response.status_code == 200


def test_vodometry_rozeslat_returns_ok(client):
    """Smoke: /vodometry/rozeslat page loads."""
    response = client.get("/vodometry/rozeslat")
    assert response.status_code == 200


def test_vodometry_import_returns_ok(client):
    """Smoke: /vodometry/import page loads."""
    response = client.get("/vodometry/import")
    assert response.status_code == 200


def test_vodometry_export_xlsx(client):
    """Smoke: /vodometry/exportovat/xlsx returns a file."""
    response = client.get("/vodometry/exportovat/xlsx")
    assert response.status_code == 200
    assert "spreadsheet" in response.headers.get("content-type", "")


def test_vodometry_export_csv(client):
    """Smoke: /vodometry/exportovat/csv returns a file."""
    response = client.get("/vodometry/exportovat/csv")
    assert response.status_code == 200
    assert "csv" in response.headers.get("content-type", "")
