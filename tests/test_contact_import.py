"""Tests for app.services.contact_import — error handling, read_only mode."""
from unittest.mock import patch, MagicMock

from app.services.contact_import import preview_contact_import


def test_preview_invalid_file_generic_error(db_session):
    """Non-existent file should return generic error, not a traceback."""
    result = preview_contact_import(
        "/nonexistent/file.xlsx",
        db_session,
    )
    assert "error" in result
    assert "traceback" not in result["error"].lower()
    assert result["stats"]["total_rows"] == 0


def test_preview_returns_error_dict(db_session):
    """Error result should have proper structure with rows and stats."""
    result = preview_contact_import(
        "/nonexistent/file.xlsx",
        db_session,
    )
    assert isinstance(result, dict)
    assert "rows" in result
    assert "stats" in result
    assert isinstance(result["rows"], list)
    assert len(result["rows"]) == 0
    assert result["stats"]["matched_count"] == 0


@patch("app.services.contact_import.load_workbook")
def test_read_only_mode(mock_load_wb, db_session):
    """load_workbook should be called with read_only=True."""
    mock_wb = MagicMock()
    mock_wb.sheetnames = ["ZU"]
    mock_ws = MagicMock()
    mock_ws.iter_rows.return_value = []
    mock_wb.__getitem__ = MagicMock(return_value=mock_ws)
    mock_wb.active = mock_ws
    mock_load_wb.return_value = mock_wb

    preview_contact_import("/fake/file.xlsx", db_session)

    mock_load_wb.assert_called_once_with(
        "/fake/file.xlsx", read_only=True, data_only=True,
    )
