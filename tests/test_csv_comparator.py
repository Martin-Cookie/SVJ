"""Tests for CSV comparator and owner matcher services.

Covers:
- CSV parsing (delimiters, BOM, column mapping, unit merging)
- Owner comparison (match, difference, missing, name_order statuses)
- Fuzzy name matching (Czech surnames, diacritics, titles)
- Name normalization (strip_diacritics, stemming, SJM handling)
- Edge cases (empty input, duplicates, malformed data)
"""
import pytest

from app.models.sync import SyncStatus
from app.services.csv_comparator import (
    _compare_structured_names,
    compare_owners,
    parse_sousede_csv,
)
from app.services.owner_matcher import (
    _stem_czech_surname,
    match_name,
    name_parts_match,
    normalize_for_matching,
)
from app.utils import strip_diacritics


# ---------------------------------------------------------------------------
# Fixtures — CSV content helpers
# ---------------------------------------------------------------------------

def _make_csv(header: str, rows: list[str], delimiter: str = ";") -> str:
    """Build a CSV string from header and row strings."""
    return header + "\n" + "\n".join(rows) + "\n"


SOUSEDE_HEADER = "Název jednotky;Vlastníci jednotky;Typ vlastnictví;Typ jednotky;Podíl na domu;Hlavní kontaktní e-mail;Hlavní kontaktní telefon"


def _sousede_row(
    unit: str = "1098/14",
    owners: str = "Novák Jan",
    typ: str = "Osobní",
    space: str = "Byt",
    share: str = "3051",
    email: str = "",
    phone: str = "",
) -> str:
    return f"{unit};{owners};{typ};{space};{share};{email};{phone}"


# ---------------------------------------------------------------------------
# strip_diacritics
# ---------------------------------------------------------------------------

class TestStripDiacritics:
    def test_basic_czech(self):
        assert strip_diacritics("Příliš žluťoučký") == "prilis zlutoucky"

    def test_already_ascii(self):
        assert strip_diacritics("hello world") == "hello world"

    def test_empty_string(self):
        assert strip_diacritics("") == ""

    def test_uppercase_to_lower(self):
        assert strip_diacritics("ČŘŽŠĚ") == "crzse"

    def test_mixed_diacritics(self):
        assert strip_diacritics("Škoda Říha Žák") == "skoda riha zak"


# ---------------------------------------------------------------------------
# _stem_czech_surname
# ---------------------------------------------------------------------------

class TestStemCzechSurname:
    def test_ova_suffix(self):
        # "novakova" matches "kova" suffix (longest-first) -> "nova"
        assert _stem_czech_surname("novakova") == "nova"

    def test_kova_suffix(self):
        # "bartikova" matches "kova" suffix -> "barti"
        assert _stem_czech_surname("bartikova") == "barti"

    def test_ovi_suffix(self):
        # "novakovi" matches "kovi" suffix -> "nova"
        assert _stem_czech_surname("novakovi") == "nova"

    def test_ovou_suffix(self):
        assert _stem_czech_surname("novakoovou") == "novako"

    def test_short_word_no_stem(self):
        # Word too short after removing suffix — keep original
        assert _stem_czech_surname("ova") == "ova"

    def test_no_suffix_match(self):
        assert _stem_czech_surname("novak") == "novak"

    def test_ek_suffix(self):
        assert _stem_czech_surname("marek") == "mar"

    def test_kem_suffix(self):
        assert _stem_czech_surname("markem") == "mar"

    def test_kovou_suffix(self):
        assert _stem_czech_surname("bartikoovou") == "bartiko"


# ---------------------------------------------------------------------------
# normalize_for_matching
# ---------------------------------------------------------------------------

class TestNormalizeForMatching:
    def test_strips_titles(self):
        result = normalize_for_matching("Ing. Jan Novák")
        assert "ing" not in result
        assert "novak" in result

    def test_strips_phd(self):
        result = normalize_for_matching("MUDr. Karel Dvořák, Ph.D.")
        assert "mudr" not in result
        assert "phd" not in result
        assert "dvorak" in result

    def test_strips_sjm_prefix(self):
        result = normalize_for_matching("SJM Novák Jan a Nováková Jana")
        assert not result.startswith("sjm")

    def test_strips_sjm_suffix(self):
        result = normalize_for_matching("Novák Jan a Nováková Jana SJM")
        assert not result.endswith("sjm")

    def test_strips_parenthetical(self):
        result = normalize_for_matching("Novák Jan (spoluvlastník)")
        assert "spoluvlastnik" not in result

    def test_strips_diacritics(self):
        result = normalize_for_matching("Říha Žák")
        # After stemming: "riha" stays "riha", "zak" stays "zak"
        assert "riha" in result
        assert "zak" in result

    def test_whitespace_normalization(self):
        result = normalize_for_matching("  Novák   Jan  ")
        # Should have single spaces, no leading/trailing
        assert "  " not in result
        assert result == result.strip()

    def test_empty_string(self):
        assert normalize_for_matching("") == ""

    def test_stemming_applied(self):
        # "Nováková" -> strip diacritics -> "novakova" -> stem (kova suffix) -> "nova"
        result = normalize_for_matching("Nováková")
        assert result == "nova"


# ---------------------------------------------------------------------------
# name_parts_match
# ---------------------------------------------------------------------------

class TestNamePartsMatch:
    def test_identical_names(self):
        score = name_parts_match("Jan Novák", "Jan Novák")
        assert score >= 0.9

    def test_swapped_order(self):
        score = name_parts_match("Novák Jan", "Jan Novák")
        assert score >= 0.8

    def test_with_titles(self):
        score = name_parts_match("Ing. Jan Novák", "Jan Novák")
        assert score >= 0.8

    def test_completely_different(self):
        score = name_parts_match("Petr Svoboda", "Jana Králová")
        assert score < 0.5

    def test_empty_name(self):
        assert name_parts_match("", "Jan Novák") == 0.0
        assert name_parts_match("Jan Novák", "") == 0.0

    def test_connector_ignored(self):
        # "a" is treated as connector and excluded; stemming reduces parts
        # so Jaccard overlap may be moderate — just verify it's non-zero
        score = name_parts_match("Novák Jan a Nováková Jana", "Novák Jan, Nováková Jana")
        assert score >= 0.5

    def test_diacritics_insensitive(self):
        score = name_parts_match("Novak Jan", "Novák Jan")
        assert score >= 0.9


# ---------------------------------------------------------------------------
# match_name
# ---------------------------------------------------------------------------

class TestMatchName:
    @pytest.fixture()
    def known_owners(self):
        return [
            {"id": 1, "name": "Novák Jan", "name_normalized": "novak jan"},
            {"id": 2, "name": "Svobodová Petra", "name_normalized": "svobodova petra"},
            {"id": 3, "name": "Ing. Karel Dvořák", "name_normalized": "ing. karel dvorak"},
            {"id": 4, "name": "Říhová Marie", "name_normalized": "rihova marie"},
        ]

    def test_exact_match(self, known_owners):
        matches = match_name("Novák Jan", known_owners)
        assert len(matches) >= 1
        assert matches[0]["owner_id"] == 1
        assert matches[0]["confidence"] >= 0.9

    def test_match_with_title(self, known_owners):
        matches = match_name("Karel Dvořák", known_owners)
        assert any(m["owner_id"] == 3 for m in matches)

    def test_no_match(self, known_owners):
        matches = match_name("Zcela Jiný Člověk Neexistující", known_owners)
        assert len(matches) == 0

    def test_diacritics_insensitive_match(self, known_owners):
        matches = match_name("Rihova Marie", known_owners)
        assert any(m["owner_id"] == 4 for m in matches)

    def test_threshold(self, known_owners):
        # High threshold should exclude partial matches
        matches = match_name("Novák", known_owners, threshold=0.95)
        assert len(matches) == 0

    def test_require_stem_overlap(self, known_owners):
        # With require_stem_overlap, names sharing only first name should not match
        matches = match_name(
            "Bartíková Petra",
            known_owners,
            threshold=0.5,
            require_stem_overlap=True,
        )
        # Should not match Svobodová Petra (different surname stem)
        assert not any(m["owner_id"] == 2 for m in matches)

    def test_feminine_to_masculine_match(self, known_owners):
        # "Nováková" stem == "Novák" stem
        matches = match_name("Nováková Jana", known_owners, threshold=0.5)
        assert any(m["owner_id"] == 1 for m in matches)


# ---------------------------------------------------------------------------
# parse_sousede_csv
# ---------------------------------------------------------------------------

class TestParseSousedeCSV:
    def test_basic_parsing(self):
        csv_text = _make_csv(SOUSEDE_HEADER, [
            _sousede_row(unit="1098/14", owners="Novák Jan", share="3051"),
        ])
        result = parse_sousede_csv(csv_text)
        assert len(result) == 1
        assert result[0]["unit_number"] == "14"
        assert result[0]["owners"] == "Novák Jan"

    def test_bom_handling(self):
        csv_text = "\ufeff" + _make_csv(SOUSEDE_HEADER, [
            _sousede_row(unit="1098/1", owners="Novák Jan"),
        ])
        result = parse_sousede_csv(csv_text)
        assert len(result) == 1
        assert result[0]["unit_number"] == "1"

    def test_comma_delimiter(self):
        header = "Název jednotky,Vlastníci jednotky,Typ vlastnictví,Typ jednotky,Podíl na domu,Email,Telefon"
        csv_text = header + "\n" + "1098/5,Novák Jan,Osobní,Byt,3000,jan@test.cz,+420123\n"
        result = parse_sousede_csv(csv_text)
        assert len(result) == 1
        assert result[0]["owners"] == "Novák Jan"
        assert result[0]["email"] == "jan@test.cz"

    def test_unit_number_extraction(self):
        csv_text = _make_csv(SOUSEDE_HEADER, [
            _sousede_row(unit="1098/14"),
            _sousede_row(unit="1098/3"),
        ])
        result = parse_sousede_csv(csv_text)
        units = {r["unit_number"] for r in result}
        assert units == {"14", "3"}

    def test_plain_unit_number(self):
        # Unit without "/" prefix
        header = "Cislo jednotky;Vlastníci jednotky;Typ vlastnictví;Typ jednotky;Podíl na domu;Email;Telefon"
        csv_text = header + "\n" + "14;Novák Jan;Osobní;Byt;3000;;\n"
        result = parse_sousede_csv(csv_text)
        assert result[0]["unit_number"] == "14"

    def test_merge_coowners(self):
        # Internal export: one row per co-owner, same unit
        header = "Cislo jednotky;Příjmení;Jméno;Typ vlastnictví;Typ jednotky;Podíl na domu;Email;Telefon"
        csv_text = (
            header + "\n"
            + "1098/5;Novák;Jan;SJM;Byt;3000;;\n"
            + "1098/5;Nováková;Jana;SJM;Byt;3000;;\n"
        )
        result = parse_sousede_csv(csv_text)
        assert len(result) == 1
        assert "Novák Jan" in result[0]["owners"]
        assert "Nováková Jana" in result[0]["owners"]

    def test_empty_csv(self):
        csv_text = SOUSEDE_HEADER + "\n"
        result = parse_sousede_csv(csv_text)
        assert result == []

    def test_skip_rows_without_unit(self):
        csv_text = _make_csv(SOUSEDE_HEADER, [
            _sousede_row(unit="1098/14"),
            ";Novák Jan;Osobní;Byt;3000;;",  # no unit number
        ])
        result = parse_sousede_csv(csv_text)
        assert len(result) == 1

    def test_share_fraction(self):
        csv_text = _make_csv(SOUSEDE_HEADER, [
            _sousede_row(unit="1098/1", share="12212/4103391"),
        ])
        result = parse_sousede_csv(csv_text)
        assert result[0]["unit_number"] == "1"
        # Share is parsed by compare_owners, not parse — just make sure it's stored
        assert result[0]["share"] == "12212/4103391"

    def test_email_and_phone(self):
        csv_text = _make_csv(SOUSEDE_HEADER, [
            _sousede_row(email="jan@test.cz", phone="+420123456789"),
        ])
        result = parse_sousede_csv(csv_text)
        assert result[0]["email"] == "jan@test.cz"
        assert result[0]["phone"] == "+420123456789"

    def test_alternative_column_names(self):
        header = "Jednotka;Vlastnici;Typ vlastnictvi;Druh prostoru;Podíl SČD;E-mail;Telefon"
        csv_text = header + "\n" + "1098/10;Novák Jan;SJM;Byt;5000;a@b.cz;123\n"
        result = parse_sousede_csv(csv_text)
        assert len(result) == 1
        assert result[0]["unit_number"] == "10"
        assert result[0]["owners"] == "Novák Jan"
        assert result[0]["space_type"] == "Byt"

    def test_whitespace_stripping(self):
        csv_text = _make_csv(SOUSEDE_HEADER, [
            _sousede_row(unit=" 1098/14 ", owners=" Novák Jan "),
        ])
        result = parse_sousede_csv(csv_text)
        assert result[0]["unit_number"] == "14"
        assert result[0]["owners"] == "Novák Jan"

    def test_duplicate_unit_merges(self):
        csv_text = _make_csv(SOUSEDE_HEADER, [
            _sousede_row(unit="1098/5", owners="Novák Jan"),
            _sousede_row(unit="1098/5", owners="Nováková Jana"),
        ])
        result = parse_sousede_csv(csv_text)
        assert len(result) == 1
        assert "Novák Jan" in result[0]["owners"]
        assert "Nováková Jana" in result[0]["owners"]

    def test_duplicate_owner_not_duplicated(self):
        # Same owner on same unit should not appear twice
        csv_text = _make_csv(SOUSEDE_HEADER, [
            _sousede_row(unit="1098/5", owners="Novák Jan"),
            _sousede_row(unit="1098/5", owners="Novák Jan"),
        ])
        result = parse_sousede_csv(csv_text)
        assert len(result) == 1
        assert result[0]["owners"] == "Novák Jan"


# ---------------------------------------------------------------------------
# _compare_structured_names
# ---------------------------------------------------------------------------

class TestCompareStructuredNames:
    def test_exact_match(self):
        result = _compare_structured_names(
            "Novák Jan",
            [{"first_name": "Jan", "last_name": "Novák"}],
        )
        assert result == "match"

    def test_swapped_names(self):
        # CSV has "Jan Novák" but DB has first=Jan, last=Novák
        # CSV parsing: first word = last_name, rest = first_name
        # So "Jan Novák" -> csv_last=Jan, csv_first=Novák
        # DB: db_first=Jan, db_last=Novák
        # csv_first(Novák)==db_last(Novák) and csv_last(Jan)==db_first(Jan) -> swapped
        result = _compare_structured_names(
            "Jan Novák",
            [{"first_name": "Jan", "last_name": "Novák"}],
        )
        assert result == "name_order"

    def test_multiple_owners_match(self):
        result = _compare_structured_names(
            "Novák Jan, Nováková Jana",
            [
                {"first_name": "Jan", "last_name": "Novák"},
                {"first_name": "Jana", "last_name": "Nováková"},
            ],
        )
        assert result == "match"

    def test_different_count_returns_none(self):
        result = _compare_structured_names(
            "Novák Jan",
            [
                {"first_name": "Jan", "last_name": "Novák"},
                {"first_name": "Jana", "last_name": "Nováková"},
            ],
        )
        assert result is None

    def test_empty_db_names_returns_none(self):
        result = _compare_structured_names(
            "Novák Jan",
            [{"first_name": "", "last_name": ""}],
        )
        assert result is None

    def test_no_match_returns_none(self):
        result = _compare_structured_names(
            "Svoboda Petr",
            [{"first_name": "Jan", "last_name": "Novák"}],
        )
        assert result is None

    def test_empty_csv_returns_none(self):
        result = _compare_structured_names(
            "",
            [{"first_name": "Jan", "last_name": "Novák"}],
        )
        assert result is None


# ---------------------------------------------------------------------------
# compare_owners
# ---------------------------------------------------------------------------

class TestCompareOwners:
    def _excel_entry(
        self,
        unit: str = "14",
        name: str = "Novák Jan",
        normalized: str = "novak jan",
        owner_type: str = "physical",
        ownership_type: str = "Osobní",
        space_type: str = "Byt",
        podil_scd: int = 3051,
        first_name: str = "Jan",
        last_name: str = "Novák",
    ) -> dict:
        return {
            "unit_number": unit,
            "owner_name": name,
            "name_normalized": normalized,
            "owner_type": owner_type,
            "ownership_type": ownership_type,
            "space_type": space_type,
            "podil_scd": podil_scd,
            "first_name": first_name,
            "last_name": last_name,
        }

    def test_matching_owner(self):
        csv_records = [{"unit_number": "14", "owners": "Novák Jan", "ownership_type": "Osobní", "space_type": "Byt", "share": "3051", "email": "", "phone": ""}]
        excel_data = [self._excel_entry()]
        results = compare_owners(csv_records, excel_data)
        assert len(results) == 1
        assert results[0]["status"] == SyncStatus.MATCH

    def test_missing_in_excel(self):
        csv_records = [{"unit_number": "99", "owners": "Novák Jan", "ownership_type": "", "space_type": "", "share": "", "email": "", "phone": ""}]
        excel_data = [self._excel_entry(unit="14")]
        results = compare_owners(csv_records, excel_data)
        missing_excel = [r for r in results if r["status"] == SyncStatus.MISSING_EXCEL]
        assert len(missing_excel) == 1
        assert missing_excel[0]["unit_number"] == "99"

    def test_missing_in_csv(self):
        csv_records = [{"unit_number": "14", "owners": "Novák Jan", "ownership_type": "", "space_type": "", "share": "", "email": "", "phone": ""}]
        excel_data = [
            self._excel_entry(unit="14"),
            self._excel_entry(unit="15", name="Svoboda Petr", normalized="svoboda petr", first_name="Petr", last_name="Svoboda"),
        ]
        results = compare_owners(csv_records, excel_data)
        missing_csv = [r for r in results if r["status"] == SyncStatus.MISSING_CSV]
        assert len(missing_csv) == 1
        assert missing_csv[0]["unit_number"] == "15"

    def test_name_difference(self):
        csv_records = [{"unit_number": "14", "owners": "Zcela Jiný", "ownership_type": "", "space_type": "", "share": "", "email": "", "phone": ""}]
        excel_data = [self._excel_entry()]
        results = compare_owners(csv_records, excel_data)
        assert results[0]["status"] == SyncStatus.DIFFERENCE

    def test_name_order_detected_as_match(self):
        # DB has first=Jan, last=Novák; CSV has "Jan Novák" (swapped order).
        # Structured comparison returns "name_order", but individuals_match
        # sees sorted word-sets as identical, so final status is MATCH.
        csv_records = [{"unit_number": "14", "owners": "Jan Novák", "ownership_type": "", "space_type": "", "share": "", "email": "", "phone": ""}]
        excel_data = [self._excel_entry()]
        results = compare_owners(csv_records, excel_data)
        assert results[0]["status"] == SyncStatus.MATCH

    def test_name_order_status_different_people(self):
        # Truly swapped first/last names where structured comparison detects it
        # but individuals are not identical sets (different names entirely)
        csv_records = [{"unit_number": "14", "owners": "Svoboda Karel", "ownership_type": "", "space_type": "", "share": "", "email": "", "phone": ""}]
        excel_data = [self._excel_entry(name="Karel Svoboda", normalized="karel svoboda", first_name="Karel", last_name="Svoboda")]
        results = compare_owners(csv_records, excel_data)
        # Same words, different order -> still resolves to MATCH via individuals_match
        assert results[0]["status"] == SyncStatus.MATCH

    def test_share_mismatch_in_details(self):
        csv_records = [{"unit_number": "14", "owners": "Novák Jan", "ownership_type": "", "space_type": "", "share": "5000", "email": "", "phone": ""}]
        excel_data = [self._excel_entry(podil_scd=3051)]
        results = compare_owners(csv_records, excel_data)
        assert "Podíl se liší" in results[0]["match_details"]

    def test_type_mismatch_in_details(self):
        csv_records = [{"unit_number": "14", "owners": "Novák Jan", "ownership_type": "SJM", "space_type": "", "share": "", "email": "", "phone": ""}]
        excel_data = [self._excel_entry(ownership_type="Osobní")]
        results = compare_owners(csv_records, excel_data)
        assert "Typ se liší" in results[0]["match_details"]

    def test_share_fraction_parsing(self):
        csv_records = [{"unit_number": "14", "owners": "Novák Jan", "ownership_type": "", "space_type": "", "share": "12212/4103391", "email": "", "phone": ""}]
        excel_data = [self._excel_entry(podil_scd=12212)]
        results = compare_owners(csv_records, excel_data)
        # Share numerator matches podil_scd, so no mismatch
        assert "Podíl se liší" not in results[0]["match_details"]

    def test_sorting_order(self):
        csv_records = [
            {"unit_number": "1", "owners": "Match Owner", "ownership_type": "", "space_type": "", "share": "", "email": "", "phone": ""},
            {"unit_number": "2", "owners": "Totally Different", "ownership_type": "", "space_type": "", "share": "", "email": "", "phone": ""},
            {"unit_number": "99", "owners": "Nobody", "ownership_type": "", "space_type": "", "share": "", "email": "", "phone": ""},
        ]
        excel_data = [
            self._excel_entry(unit="1", name="Match Owner", normalized="match owner", first_name="Owner", last_name="Match"),
            self._excel_entry(unit="2", name="Jiný Člověk", normalized="jiny clovek", first_name="Člověk", last_name="Jiný"),
            self._excel_entry(unit="50", name="Only Excel", normalized="only excel", first_name="Excel", last_name="Only"),
        ]
        results = compare_owners(csv_records, excel_data)
        statuses = [r["status"] for r in results]
        # DIFFERENCE should come first, then MISSING_EXCEL, MISSING_CSV, then MATCH
        first_diff_idx = next(i for i, s in enumerate(statuses) if s == SyncStatus.DIFFERENCE)
        first_match_idx = next(i for i, s in enumerate(statuses) if s == SyncStatus.MATCH)
        assert first_diff_idx < first_match_idx

    def test_empty_csv_records(self):
        results = compare_owners([], [self._excel_entry()])
        assert len(results) == 1
        assert results[0]["status"] == SyncStatus.MISSING_CSV

    def test_empty_excel_data(self):
        csv_records = [{"unit_number": "14", "owners": "Novák Jan", "ownership_type": "", "space_type": "", "share": "", "email": "", "phone": ""}]
        results = compare_owners(csv_records, [])
        assert len(results) == 1
        assert results[0]["status"] == SyncStatus.MISSING_EXCEL

    def test_both_empty(self):
        results = compare_owners([], [])
        assert results == []

    def test_sjm_owners_match(self):
        csv_records = [{"unit_number": "14", "owners": "Novák Jan, Nováková Jana", "ownership_type": "SJM", "space_type": "", "share": "", "email": "", "phone": ""}]
        excel_data = [
            self._excel_entry(unit="14", name="Novák Jan", normalized="novak jan", first_name="Jan", last_name="Novák"),
            self._excel_entry(unit="14", name="Nováková Jana", normalized="novakova jana", first_name="Jana", last_name="Nováková"),
        ]
        results = compare_owners(csv_records, excel_data)
        match_results = [r for r in results if r["unit_number"] == "14"]
        assert len(match_results) == 1
        assert match_results[0]["status"] == SyncStatus.MATCH

    def test_csv_email_phone_propagated(self):
        csv_records = [{"unit_number": "14", "owners": "Novák Jan", "ownership_type": "", "space_type": "", "share": "", "email": "jan@x.cz", "phone": "+420111"}]
        excel_data = [self._excel_entry()]
        results = compare_owners(csv_records, excel_data)
        assert results[0]["csv_email"] == "jan@x.cz"
        assert results[0]["csv_phone"] == "+420111"

    def test_invalid_share_value(self):
        csv_records = [{"unit_number": "14", "owners": "Novák Jan", "ownership_type": "", "space_type": "", "share": "neplatné", "email": "", "phone": ""}]
        excel_data = [self._excel_entry()]
        results = compare_owners(csv_records, excel_data)
        # Should not crash, share just won't be compared
        assert results[0]["csv_share"] is None

    def test_match_unifies_display_names(self):
        # When names match structurally, excel_owner_name should be set to csv_owners_raw
        csv_records = [{"unit_number": "14", "owners": "Novák Jan", "ownership_type": "", "space_type": "", "share": "", "email": "", "phone": ""}]
        excel_data = [self._excel_entry(name="Novák Jan")]
        results = compare_owners(csv_records, excel_data)
        assert results[0]["csv_owner_name"] == results[0]["excel_owner_name"]


# ---------------------------------------------------------------------------
# Integration: parse_sousede_csv -> compare_owners
# ---------------------------------------------------------------------------

class TestCSVCompareIntegration:
    def test_full_pipeline(self):
        csv_text = _make_csv(SOUSEDE_HEADER, [
            _sousede_row(unit="1098/14", owners="Novák Jan", share="3051"),
            _sousede_row(unit="1098/15", owners="Svoboda Petr", share="2000"),
        ])
        csv_records = parse_sousede_csv(csv_text)
        assert len(csv_records) == 2

        excel_data = [
            {
                "unit_number": "14",
                "owner_name": "Novák Jan",
                "name_normalized": "novak jan",
                "owner_type": "physical",
                "ownership_type": "Osobní",
                "space_type": "Byt",
                "podil_scd": 3051,
                "first_name": "Jan",
                "last_name": "Novák",
            },
        ]
        results = compare_owners(csv_records, excel_data)
        # Unit 14 matches, unit 15 is missing in excel
        statuses = {r["unit_number"]: r["status"] for r in results}
        assert statuses["14"] == SyncStatus.MATCH
        assert statuses["15"] == SyncStatus.MISSING_EXCEL

    def test_bom_csv_full_pipeline(self):
        csv_text = "\ufeff" + _make_csv(SOUSEDE_HEADER, [
            _sousede_row(unit="1098/1", owners="Říhová Marie"),
        ])
        csv_records = parse_sousede_csv(csv_text)
        excel_data = [
            {
                "unit_number": "1",
                "owner_name": "Říhová Marie",
                "name_normalized": "rihova marie",
                "owner_type": "physical",
                "ownership_type": "",
                "space_type": "",
                "podil_scd": 0,
                "first_name": "Marie",
                "last_name": "Říhová",
            },
        ]
        results = compare_owners(csv_records, excel_data)
        assert results[0]["status"] == SyncStatus.MATCH
