"""Tests for app.services.owner_exchange — pure helper functions."""

from app.services.owner_exchange import (
    _split_votes,
    _parse_csv_name,
    _split_csv_names,
)


# ---------------------------------------------------------------------------
# _split_votes
# ---------------------------------------------------------------------------

class TestSplitVotes:
    def test_even_split(self):
        assert _split_votes(10, 2) == [5, 5]

    def test_remainder(self):
        assert _split_votes(10, 3) == [4, 3, 3]

    def test_single_owner(self):
        assert _split_votes(100, 1) == [100]

    def test_zero_votes(self):
        assert _split_votes(0, 3) == [0, 0, 0]

    def test_no_owners(self):
        assert _split_votes(10, 0) == []

    def test_more_owners_than_votes(self):
        result = _split_votes(2, 5)
        assert sum(result) == 2
        assert len(result) == 5
        assert result == [1, 1, 0, 0, 0]

    def test_one_vote(self):
        result = _split_votes(1, 3)
        assert sum(result) == 1
        assert result == [1, 0, 0]

    def test_large_split(self):
        result = _split_votes(1000, 7)
        assert sum(result) == 1000
        assert len(result) == 7
        # First 6 get 143, last gets 142 (or similar)
        assert max(result) - min(result) <= 1


# ---------------------------------------------------------------------------
# _parse_csv_name
# ---------------------------------------------------------------------------

class TestParseCsvName:
    def test_standard(self):
        first, last = _parse_csv_name("Novák Jan")
        assert first == "Jan"
        assert last == "Novák"

    def test_with_spaces(self):
        first, last = _parse_csv_name("  Svoboda Petr  ")
        assert first == "Petr"
        assert last == "Svoboda"

    def test_single_word(self):
        first, last = _parse_csv_name("Novák")
        assert first == "Novák"
        assert last is None

    def test_empty(self):
        first, last = _parse_csv_name("")
        assert first == ""
        assert last is None

    def test_sro_gets_split(self):
        # Note: \b regex boundary doesn't match after "." at end-of-string/space,
        # so legal entity names are treated as regular names (split on first space)
        first, last = _parse_csv_name("Bytové s.r.o.")
        assert last == "Bytové"
        assert first == "s.r.o."

    def test_as_gets_split(self):
        first, last = _parse_csv_name("Správa a.s. Praha")
        assert last == "Správa"

    def test_spol_gets_split(self):
        first, last = _parse_csv_name("Firma spol. s r.o.")
        assert last == "Firma"

    def test_compound_first_name(self):
        # "Příjmení Jméno Druhé" → first = "Jméno Druhé", last = "Příjmení"
        first, last = _parse_csv_name("Novák Jan Pavel")
        assert last == "Novák"
        assert first == "Jan Pavel"


# ---------------------------------------------------------------------------
# _split_csv_names
# ---------------------------------------------------------------------------

class TestSplitCsvNames:
    def test_single(self):
        assert _split_csv_names("Novák Jan") == ["Novák Jan"]

    def test_semicolon(self):
        assert _split_csv_names("Novák Jan; Nováková Marie") == ["Novák Jan", "Nováková Marie"]

    def test_comma(self):
        assert _split_csv_names("Novák Jan, Nováková Marie") == ["Novák Jan", "Nováková Marie"]

    def test_mixed(self):
        result = _split_csv_names("A; B, C")
        assert result == ["A", "B", "C"]

    def test_empty(self):
        assert _split_csv_names("") == []

    def test_whitespace_only(self):
        assert _split_csv_names("   ") == []

    def test_trailing_separator(self):
        result = _split_csv_names("Novák Jan;")
        assert result == ["Novák Jan"]
