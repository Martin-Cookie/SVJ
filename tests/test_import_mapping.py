"""Tests for app.services.import_mapping — auto-detection, validation, context building."""
from app.services.import_mapping import (
    auto_detect_mapping,
    build_mapping_context,
    validate_contact_mapping,
    validate_owner_mapping,
    CONTACT_FIELD_DEFS,
    CONTACT_FIELD_GROUPS,
    OWNER_FIELD_DEFS,
    OWNER_FIELD_GROUPS,
)


# ---------------------------------------------------------------------------
# auto_detect_mapping
# ---------------------------------------------------------------------------

def test_auto_detect_exact_match():
    """Header 'Číslo jednotky KN' should match unit_kn (via candidates)."""
    headers = ["Číslo jednotky KN", "Jméno", "Příjmení", "Email"]
    result = auto_detect_mapping(headers, OWNER_FIELD_DEFS)

    assert result["unit_kn"]["col"] == 0
    assert result["unit_kn"]["status"] == "auto"
    assert result["first_name"]["col"] == 1
    assert result["first_name"]["status"] == "auto"


def test_auto_detect_diacritics_insensitive():
    """'cislo jednotky kn' (no diacritics) should still match unit_kn."""
    headers = ["cislo jednotky kn", "jmeno"]
    result = auto_detect_mapping(headers, OWNER_FIELD_DEFS)

    assert result["unit_kn"]["col"] == 0
    assert result["unit_kn"]["status"] == "auto"


def test_auto_detect_with_saved_mapping():
    """Saved mapping should take priority over auto-detection."""
    headers = ["Email", "Jméno", "Číslo jednotky"]
    saved = {"fields": {"unit_kn": 2, "first_name": 1}}

    result = auto_detect_mapping(headers, OWNER_FIELD_DEFS, saved_mapping=saved)

    assert result["unit_kn"]["col"] == 2
    assert result["unit_kn"]["status"] == "saved"
    assert result["first_name"]["col"] == 1
    assert result["first_name"]["status"] == "saved"
    # Email should be auto-detected
    assert result["email_evidence"]["col"] == 0
    assert result["email_evidence"]["status"] == "auto"


# ---------------------------------------------------------------------------
# validate_owner_mapping
# ---------------------------------------------------------------------------

def test_validate_owner_mapping_missing_required():
    """Missing required field unit_kn should return error string."""
    mapping = {"fields": {"first_name": 0}}
    # unit_kn is required but missing
    err = validate_owner_mapping(mapping)
    assert err is not None
    assert "Číslo jednotky" in err


def test_validate_owner_mapping_ok():
    """Valid mapping with all required fields should return None."""
    mapping = {"fields": {"unit_kn": 0, "first_name": 1}}
    err = validate_owner_mapping(mapping)
    assert err is None


def test_validate_owner_mapping_invalid_format():
    """Invalid dict format should return error."""
    assert validate_owner_mapping({}) is not None
    assert validate_owner_mapping({"fields": "not_a_dict"}) is not None


# ---------------------------------------------------------------------------
# validate_contact_mapping
# ---------------------------------------------------------------------------

def test_validate_contact_mapping_missing_required():
    """Missing required field match_name should return error."""
    mapping = {"fields": {"email": 0}}
    err = validate_contact_mapping(mapping)
    assert err is not None
    assert "Jméno" in err


def test_validate_contact_mapping_ok():
    """Valid contact mapping should return None."""
    mapping = {"fields": {"match_name": 0}}
    err = validate_contact_mapping(mapping)
    assert err is None


# ---------------------------------------------------------------------------
# build_mapping_context
# ---------------------------------------------------------------------------

def test_build_mapping_context():
    """build_mapping_context should return correct structure with stats."""
    headers = ["Číslo jednotky KN", "Jméno", "Email"]
    ctx = build_mapping_context(headers, OWNER_FIELD_DEFS, OWNER_FIELD_GROUPS)

    assert "headers" in ctx
    assert "groups_data" in ctx
    assert "stats" in ctx

    stats = ctx["stats"]
    assert stats["total"] == len(OWNER_FIELD_DEFS)
    assert stats["matched"] >= 2  # at least unit_kn and first_name
    assert stats["required_missing"] == 0  # both required fields matched

    # groups_data should have same structure as OWNER_FIELD_GROUPS
    assert len(ctx["groups_data"]) == len(OWNER_FIELD_GROUPS)
    for gd in ctx["groups_data"]:
        assert "key" in gd
        assert "label" in gd
        assert "color" in gd
        assert "fields" in gd
