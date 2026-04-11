"""Tests for fuzzy name matching in app.services.owner_matcher."""
from app.services.owner_matcher import (
    match_name,
    name_parts_match,
    normalize_for_matching,
)


def _owner(id_: int, name: str) -> dict:
    return {"id": id_, "name": name, "name_normalized": name.lower()}


def test_normalize_strips_titles_and_diacritics():
    assert "phd" not in normalize_for_matching("Ing. Jan Novák, Ph.D.")
    assert "ing" not in normalize_for_matching("Ing. Jan Novák, Ph.D.")
    # Bez diakritiky
    assert "á" not in normalize_for_matching("Novák")
    assert "č" not in normalize_for_matching("Čapek")


def test_normalize_mba_llm():
    assert "mba" not in normalize_for_matching("Jan Novák, M.B.A.").lower()
    assert "llm" not in normalize_for_matching("Petr Svoboda, LL.M.").lower()


def test_normalize_strips_architekt_prefix():
    result = normalize_for_matching("arch. Jan Novák")
    assert "arch" not in result
    assert "novak" in result.lower()


def test_normalize_strips_sjm_prefix():
    assert "sjm" not in normalize_for_matching("SJM Novák Jan").lower()
    assert "sjm" not in normalize_for_matching("SJ Novák Jan").lower()


def test_match_name_basic():
    owners = [_owner(1, "Jan Novák"), _owner(2, "Petr Svoboda")]
    matches = match_name("Jan Novák", owners, threshold=0.7)
    assert matches
    assert matches[0]["owner_id"] == 1
    assert matches[0]["confidence"] >= 0.9


def test_match_name_title_variant():
    owners = [_owner(1, "Jan Novák")]
    matches = match_name("Ing. Jan Novák, Ph.D.", owners, threshold=0.7)
    assert matches
    assert matches[0]["owner_id"] == 1


def test_match_name_czech_surname_stem():
    # Skloňované tvary by měly dojít ke stejnému kmeni
    owners = [_owner(1, "Marie Nováková")]
    matches = match_name("Marií Novákovou", owners, threshold=0.6)
    assert matches
    assert matches[0]["owner_id"] == 1


def test_stem_overlap_rejects_firstname_only():
    # Jen křestní jméno se shoduje — různá příjmení musí být zamítnuta
    owners = [_owner(1, "Barbora Birčáková")]
    matches = match_name(
        "Barbora Bartíková", owners, threshold=0.6, require_stem_overlap=True
    )
    # Neshoda příjmení → žádný match (nebo pod threshold)
    assert not matches or matches[0]["confidence"] < 0.75


def test_name_parts_match_sjm():
    # SJM tvar: dva vlastníci v jednom řetězci
    score = name_parts_match("Jan Novák a Marie Nováková", "Jan Novák")
    assert score >= 0.5


def test_short_first_name_not_over_stemmed():
    # "Eva" je kratší než 3 znaky po stripování → nesmí se zkrátit na "E"
    result = normalize_for_matching("Eva")
    assert result == "eva"
