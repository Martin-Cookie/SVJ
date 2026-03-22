"""Testy pro hlasovací modul — modely, wizard, ballot stats, import služba."""

from datetime import datetime

import pytest
from openpyxl import Workbook

from app.models import (
    Ballot, BallotStatus, BallotVote, Owner, OwnerUnit, SvjInfo, Unit,
    Voting, VotingItem, VotingStatus, VoteValue,
)
from app.routers.voting._helpers import _ballot_stats, _voting_wizard
from app.services.voting_import import (
    _cell,
    _cell_numeric,
    _check_comparisons,
    _match_vote,
    _parse_unit_number,
    _parse_value_list,
    execute_voting_import,
    preview_voting_import,
    validate_mapping,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def seed_voting(db_session):
    """Seed: 2 units, 2 owners (sole), 1 voting with 2 items, ballots generated."""
    db = db_session

    u1 = Unit(unit_number=101, building_number="A")
    u2 = Unit(unit_number=102, building_number="A")
    db.add_all([u1, u2])
    db.flush()

    o1 = Owner(
        first_name="Jan", last_name="Novák",
        name_with_titles="Novák Jan", name_normalized="novak jan",
    )
    o2 = Owner(
        first_name="Marie", last_name="Svobodová",
        name_with_titles="Svobodová Marie", name_normalized="svobodova marie",
    )
    db.add_all([o1, o2])
    db.flush()

    ou1 = OwnerUnit(owner_id=o1.id, unit_id=u1.id, ownership_type="sole", votes=100)
    ou2 = OwnerUnit(owner_id=o2.id, unit_id=u2.id, ownership_type="sole", votes=200)
    db.add_all([ou1, ou2])
    db.flush()

    v = Voting(title="Shromáždění 2026", status=VotingStatus.ACTIVE)
    db.add(v)
    db.flush()

    item1 = VotingItem(voting_id=v.id, order=1, title="Bod 1")
    item2 = VotingItem(voting_id=v.id, order=2, title="Bod 2")
    db.add_all([item1, item2])
    db.flush()

    # Ballots
    b1 = Ballot(
        voting_id=v.id, owner_id=o1.id,
        total_votes=100, units_text="101",
        status=BallotStatus.GENERATED,
    )
    b2 = Ballot(
        voting_id=v.id, owner_id=o2.id,
        total_votes=200, units_text="102",
        status=BallotStatus.GENERATED,
    )
    db.add_all([b1, b2])
    db.flush()

    # BallotVotes (empty)
    for ballot in [b1, b2]:
        for item in [item1, item2]:
            bv = BallotVote(
                ballot_id=ballot.id, voting_item_id=item.id,
                votes_count=ballot.total_votes,
            )
            db.add(bv)
    db.flush()

    return {
        "db": db, "voting": v,
        "items": [item1, item2],
        "owners": [o1, o2],
        "units": [u1, u2],
        "ballots": [b1, b2],
    }


@pytest.fixture()
def seed_sjm(db_session):
    """Seed: 1 unit with 2 SJM co-owners sharing it."""
    db = db_session

    u1 = Unit(unit_number=201, building_number="B")
    u2 = Unit(unit_number=202, building_number="B")
    db.add_all([u1, u2])
    db.flush()

    o1 = Owner(
        first_name="Pavel", last_name="Dvořák",
        name_with_titles="Dvořák Pavel", name_normalized="dvorak pavel",
    )
    o2 = Owner(
        first_name="Jana", last_name="Dvořáková",
        name_with_titles="Dvořáková Jana", name_normalized="dvorakova jana",
    )
    o3 = Owner(
        first_name="Petr", last_name="Nový",
        name_with_titles="Nový Petr", name_normalized="novy petr",
    )
    db.add_all([o1, o2, o3])
    db.flush()

    # SJM pair on unit 201
    ou1 = OwnerUnit(owner_id=o1.id, unit_id=u1.id, ownership_type="SJM", votes=150)
    ou2 = OwnerUnit(owner_id=o2.id, unit_id=u1.id, ownership_type="SJM", votes=150)
    # Sole owner on unit 202
    ou3 = OwnerUnit(owner_id=o3.id, unit_id=u2.id, ownership_type="sole", votes=100)
    db.add_all([ou1, ou2, ou3])
    db.flush()

    return {"db": db, "owners": [o1, o2, o3], "units": [u1, u2]}


# ---------------------------------------------------------------------------
# 1. VotingStatus enum
# ---------------------------------------------------------------------------

class TestVotingStatus:
    def test_enum_values(self):
        assert VotingStatus.DRAFT.value == "draft"
        assert VotingStatus.ACTIVE.value == "active"
        assert VotingStatus.CLOSED.value == "closed"
        assert VotingStatus.CANCELLED.value == "cancelled"

    def test_str_enum_comparison(self):
        assert VotingStatus.DRAFT == "draft"
        assert VotingStatus.ACTIVE == "active"


class TestBallotStatus:
    def test_enum_values(self):
        assert BallotStatus.GENERATED.value == "generated"
        assert BallotStatus.SENT.value == "sent"
        assert BallotStatus.RECEIVED.value == "received"
        assert BallotStatus.PROCESSED.value == "processed"
        assert BallotStatus.INVALID.value == "invalid"


class TestVoteValue:
    def test_enum_values(self):
        assert VoteValue.FOR.value == "for"
        assert VoteValue.AGAINST.value == "against"
        assert VoteValue.ABSTAIN.value == "abstain"
        assert VoteValue.INVALID.value == "invalid"


# ---------------------------------------------------------------------------
# 2. Model properties
# ---------------------------------------------------------------------------

class TestVotingModel:
    def test_has_processed_ballots_false(self, seed_voting):
        v = seed_voting["voting"]
        assert v.has_processed_ballots is False

    def test_has_processed_ballots_true(self, seed_voting):
        db = seed_voting["db"]
        b = seed_voting["ballots"][0]
        b.status = BallotStatus.PROCESSED
        db.flush()
        v = seed_voting["voting"]
        assert v.has_processed_ballots is True


# ---------------------------------------------------------------------------
# 3. Wizard helper — _voting_wizard()
# ---------------------------------------------------------------------------

class TestVotingWizard:
    def test_draft_no_items(self, db_session):
        v = Voting(title="Test", status=VotingStatus.DRAFT)
        db_session.add(v)
        db_session.flush()

        result = _voting_wizard(v)
        assert result["wizard_current"] == 1
        assert result["wizard_total"] == 5
        assert result["wizard_label"] == "Nastavení"
        # Step 1 active, rest pending
        assert result["wizard_steps"][0]["status"] == "active"
        assert result["wizard_steps"][1]["status"] == "pending"

    def test_draft_with_items(self, db_session):
        v = Voting(title="Test", status=VotingStatus.DRAFT)
        db_session.add(v)
        db_session.flush()
        item = VotingItem(voting_id=v.id, order=1, title="Bod")
        db_session.add(item)
        db_session.flush()

        result = _voting_wizard(v)
        assert result["wizard_current"] == 2
        assert result["wizard_label"] == "Generování lístků"
        assert result["wizard_steps"][0]["status"] == "done"
        assert result["wizard_steps"][1]["status"] == "active"

    def test_active_no_processed(self, seed_voting):
        v = seed_voting["voting"]
        result = _voting_wizard(v)
        assert result["wizard_current"] == 3
        assert result["wizard_label"] == "Zpracování"
        # Steps 1,2 done
        assert result["wizard_steps"][0]["status"] == "done"
        assert result["wizard_steps"][1]["status"] == "done"
        assert result["wizard_steps"][2]["status"] == "active"

    def test_active_with_processed(self, seed_voting):
        db = seed_voting["db"]
        b = seed_voting["ballots"][0]
        b.status = BallotStatus.PROCESSED
        db.flush()

        v = seed_voting["voting"]
        result = _voting_wizard(v)
        # Has processed but not all → still step 3
        assert result["wizard_current"] == 3
        # max_done = 4 (has processed), steps 1-4 done
        assert result["wizard_steps"][3]["status"] == "done"

    def test_active_all_processed(self, seed_voting):
        db = seed_voting["db"]
        for b in seed_voting["ballots"]:
            b.status = BallotStatus.PROCESSED
        db.flush()

        v = seed_voting["voting"]
        result = _voting_wizard(v)
        assert result["wizard_current"] == 5
        assert result["wizard_label"] == "Uzavření"

    def test_closed(self, seed_voting):
        v = seed_voting["voting"]
        v.status = VotingStatus.CLOSED
        seed_voting["db"].flush()

        result = _voting_wizard(v)
        assert result["wizard_current"] == 5
        # All steps done
        for step in result["wizard_steps"]:
            assert step["status"] == "done"

    def test_explicit_current_step(self, seed_voting):
        v = seed_voting["voting"]
        result = _voting_wizard(v, current_step=2)
        assert result["wizard_current"] == 2
        assert result["wizard_label"] == "Generování lístků"


# ---------------------------------------------------------------------------
# 4. Ballot stats — _ballot_stats()
# ---------------------------------------------------------------------------

class TestBallotStats:
    def test_basic_counts(self, seed_voting):
        db = seed_voting["db"]
        v = seed_voting["voting"]

        stats = _ballot_stats(v, db)
        assert stats["total_ballots"] == 2
        assert stats["status_counts"]["generated"] == 2
        assert stats["status_counts"]["processed"] == 0
        assert stats["total_generated_votes"] == 300  # 100 + 200
        assert stats["total_processed_votes"] == 0

    def test_processed_votes(self, seed_voting):
        db = seed_voting["db"]
        v = seed_voting["voting"]
        b1 = seed_voting["ballots"][0]

        # Process ballot 1 with actual votes
        b1.status = BallotStatus.PROCESSED
        b1.processed_at = datetime.utcnow()
        for bv in b1.votes:
            bv.vote = VoteValue.FOR
        db.flush()

        stats = _ballot_stats(v, db)
        assert stats["status_counts"]["processed"] == 1
        assert stats["status_counts"]["generated"] == 1
        assert stats["total_processed_votes"] == 100

    def test_quorum_reached(self, seed_voting):
        db = seed_voting["db"]
        v = seed_voting["voting"]
        v.quorum_threshold = 0.5

        # Add SvjInfo with total_shares
        svj = SvjInfo(name="Test SVJ", total_shares=300)
        db.add(svj)
        db.flush()

        # Process both ballots → 300 votes out of 300 shares
        for b in seed_voting["ballots"]:
            b.status = BallotStatus.PROCESSED
            b.processed_at = datetime.utcnow()
            for bv in b.votes:
                bv.vote = VoteValue.FOR
        db.flush()

        stats = _ballot_stats(v, db)
        assert stats["declared_shares"] == 300
        assert stats["quorum_reached"] is True

    def test_quorum_not_reached(self, seed_voting):
        db = seed_voting["db"]
        v = seed_voting["voting"]
        v.quorum_threshold = 0.5

        svj = SvjInfo(name="Test SVJ", total_shares=1000)
        db.add(svj)
        db.flush()

        # Process only ballot 1 → 100/1000 < 50%
        b1 = seed_voting["ballots"][0]
        b1.status = BallotStatus.PROCESSED
        b1.processed_at = datetime.utcnow()
        for bv in b1.votes:
            bv.vote = VoteValue.FOR
        db.flush()

        stats = _ballot_stats(v, db)
        assert stats["quorum_reached"] is False

    def test_no_declared_shares(self, seed_voting):
        db = seed_voting["db"]
        v = seed_voting["voting"]
        stats = _ballot_stats(v, db)
        assert stats["declared_shares"] == 0
        assert stats["quorum_reached"] is False

    def test_partial_ballots_count(self, seed_voting):
        db = seed_voting["db"]
        v = seed_voting["voting"]

        # Process ballot 1 but vote only on 1 of 2 items
        b1 = seed_voting["ballots"][0]
        b1.status = BallotStatus.PROCESSED
        b1.processed_at = datetime.utcnow()
        b1.votes[0].vote = VoteValue.FOR  # Only 1st item
        db.flush()

        stats = _ballot_stats(v, db)
        assert stats["partial_ballots_count"] == 1

    def test_no_partial_when_all_voted(self, seed_voting):
        db = seed_voting["db"]
        v = seed_voting["voting"]

        b1 = seed_voting["ballots"][0]
        b1.status = BallotStatus.PROCESSED
        b1.processed_at = datetime.utcnow()
        for bv in b1.votes:
            bv.vote = VoteValue.FOR
        db.flush()

        stats = _ballot_stats(v, db)
        assert stats["partial_ballots_count"] == 0


# ---------------------------------------------------------------------------
# 5. Vote aggregation
# ---------------------------------------------------------------------------

class TestVoteAggregation:
    def test_total_votes_per_ballot(self, seed_voting):
        b1, b2 = seed_voting["ballots"]
        assert b1.total_votes == 100
        assert b2.total_votes == 200

    def test_votes_count_matches_ballot(self, seed_voting):
        """Each BallotVote.votes_count should match the ballot's total_votes."""
        for b in seed_voting["ballots"]:
            for bv in b.votes:
                assert bv.votes_count == b.total_votes


# ---------------------------------------------------------------------------
# 6. Import — helper functions
# ---------------------------------------------------------------------------

class TestImportHelpers:
    def test_cell_valid(self):
        assert _cell(("foo", "bar"), 0) == "foo"
        assert _cell(("foo", "bar"), 1) == "bar"

    def test_cell_none(self):
        assert _cell((None, "bar"), 0) is None
        assert _cell(("foo",), 5) is None

    def test_cell_strips_whitespace(self):
        assert _cell(("  hello  ",), 0) == "hello"

    def test_cell_empty_string(self):
        assert _cell(("  ",), 0) is None

    def test_cell_numeric_valid(self):
        assert _cell_numeric(("42",), 0) == 42.0
        assert _cell_numeric(("3.14",), 0) == 3.14

    def test_cell_numeric_none(self):
        assert _cell_numeric((None,), 0) is None
        assert _cell_numeric(("abc",), 0) is None

    def test_parse_unit_number_simple(self):
        assert _parse_unit_number("101") == 101

    def test_parse_unit_number_with_slash(self):
        assert _parse_unit_number("1098/115") == 115

    def test_parse_unit_number_float(self):
        assert _parse_unit_number("42.0") == 42

    def test_parse_unit_number_invalid(self):
        assert _parse_unit_number("abc") is None


class TestParseValueList:
    def test_exact_values(self):
        exact, cmp = _parse_value_list("1, ANO, YES")
        assert exact == {"1", "ANO", "YES"}
        assert cmp == []

    def test_comparison_rules(self):
        exact, cmp = _parse_value_list(">0, <=5")
        assert exact == set()
        assert (">", 0.0) in cmp
        assert ("<=", 5.0) in cmp

    def test_mixed(self):
        exact, cmp = _parse_value_list("1, >0, ANO")
        assert "1" in exact
        assert "ANO" in exact
        assert (">", 0.0) in cmp

    def test_empty(self):
        exact, cmp = _parse_value_list("")
        assert exact == set()
        assert cmp == []


class TestCheckComparisons:
    def test_greater_than(self):
        assert _check_comparisons(5, [(">", 0)]) is True
        assert _check_comparisons(0, [(">", 0)]) is False

    def test_less_than(self):
        assert _check_comparisons(-1, [("<", 0)]) is True
        assert _check_comparisons(0, [("<", 0)]) is False

    def test_gte(self):
        assert _check_comparisons(0, [(">=", 0)]) is True

    def test_lte(self):
        assert _check_comparisons(0, [("<=", 0)]) is True

    def test_no_match(self):
        assert _check_comparisons(5, [("<", 0)]) is False


class TestMatchVote:
    def test_for_exact(self):
        for_vals = ({"ANO", "1"}, [])
        against_vals = ({"NE", "0"}, [])
        assert _match_vote("ANO", None, for_vals, against_vals) == "for"

    def test_against_exact(self):
        for_vals = ({"ANO"}, [])
        against_vals = ({"NE"}, [])
        assert _match_vote("NE", None, for_vals, against_vals) == "against"

    def test_abstain_exact(self):
        for_vals = ({"ANO"}, [])
        against_vals = ({"NE"}, [])
        abstain_vals = ({"ZDRŽEL"}, [])
        assert _match_vote("ZDRŽEL", None, for_vals, against_vals, abstain_vals) == "abstain"

    def test_numeric_match(self):
        for_vals = ({"1"}, [])
        against_vals = ({"0"}, [])
        assert _match_vote(None, 1.0, for_vals, against_vals) == "for"
        assert _match_vote(None, 0.0, for_vals, against_vals) == "against"

    def test_comparison_match(self):
        for_vals = (set(), [(">", 0)])
        against_vals = (set(), [("<", 0)])
        assert _match_vote(None, 5.0, for_vals, against_vals) == "for"
        assert _match_vote(None, -1.0, for_vals, against_vals) == "against"

    def test_no_match(self):
        for_vals = ({"ANO"}, [])
        against_vals = ({"NE"}, [])
        assert _match_vote("MAYBE", None, for_vals, against_vals) is None
        assert _match_vote(None, None, for_vals, against_vals) is None


# ---------------------------------------------------------------------------
# 7. Import — validate_mapping
# ---------------------------------------------------------------------------

class TestValidateMapping:
    def test_valid_mapping(self):
        mapping = {
            "owner_col": 0,
            "unit_col": 1,
            "item_mappings": [
                {"item_id": 1, "for_col": 2, "against_col": 3},
            ],
        }
        assert validate_mapping(mapping) is None

    def test_valid_with_items_key(self):
        """Accepts 'items' as alias for 'item_mappings'."""
        mapping = {
            "owner_col": 0,
            "unit_col": 1,
            "items": [
                {"item_id": 1, "for_col": 2},
            ],
        }
        assert validate_mapping(mapping) is None

    def test_missing_owner_col(self):
        mapping = {"unit_col": 1, "item_mappings": [{"item_id": 1, "for_col": 2}]}
        err = validate_mapping(mapping)
        assert err is not None
        assert "owner_col" in err

    def test_missing_unit_col(self):
        mapping = {"owner_col": 0, "item_mappings": [{"item_id": 1, "for_col": 2}]}
        err = validate_mapping(mapping)
        assert err is not None
        assert "unit_col" in err

    def test_negative_col(self):
        mapping = {"owner_col": -1, "unit_col": 1, "item_mappings": [{"item_id": 1, "for_col": 2}]}
        assert validate_mapping(mapping) is not None

    def test_empty_items(self):
        mapping = {"owner_col": 0, "unit_col": 1, "item_mappings": []}
        assert validate_mapping(mapping) is not None

    def test_missing_items(self):
        mapping = {"owner_col": 0, "unit_col": 1}
        assert validate_mapping(mapping) is not None

    def test_item_missing_cols(self):
        mapping = {
            "owner_col": 0, "unit_col": 1,
            "item_mappings": [{"item_id": 1}],
        }
        assert validate_mapping(mapping) is not None

    def test_item_for_col_only(self):
        mapping = {
            "owner_col": 0, "unit_col": 1,
            "item_mappings": [{"item_id": 1, "for_col": 2}],
        }
        assert validate_mapping(mapping) is None

    def test_item_against_col_only(self):
        mapping = {
            "owner_col": 0, "unit_col": 1,
            "item_mappings": [{"item_id": 1, "against_col": 3}],
        }
        assert validate_mapping(mapping) is None

    def test_not_a_dict(self):
        assert validate_mapping("bad") is not None
        assert validate_mapping(None) is not None

    def test_invalid_start_row(self):
        mapping = {
            "owner_col": 0, "unit_col": 1, "start_row": 0,
            "item_mappings": [{"item_id": 1, "for_col": 2}],
        }
        assert validate_mapping(mapping) is not None

    def test_item_negative_for_col(self):
        mapping = {
            "owner_col": 0, "unit_col": 1,
            "item_mappings": [{"item_id": 1, "for_col": -1}],
        }
        assert validate_mapping(mapping) is not None


# ---------------------------------------------------------------------------
# 8. Import — preview + execute (Excel-based)
# ---------------------------------------------------------------------------

def _create_test_excel(tmp_path, rows, headers=None):
    """Helper: create a test .xlsx file and return its path."""
    wb = Workbook()
    ws = wb.active
    if headers:
        ws.append(headers)
    for row in rows:
        ws.append(row)
    path = str(tmp_path / "test_import.xlsx")
    wb.save(path)
    return path


class TestPreviewVotingImport:
    def test_basic_match(self, seed_voting, tmp_path):
        db = seed_voting["db"]
        v = seed_voting["voting"]
        items = seed_voting["items"]

        headers = ["Vlastník", "Jednotka", "Bod 1", "Bod 2"]
        rows = [
            ["Novák Jan", 101, 1, 0],
            ["Svobodová Marie", 102, 0, 1],
        ]
        path = _create_test_excel(tmp_path, rows, headers)

        mapping = {
            "owner_col": 0,
            "unit_col": 1,
            "start_row": 2,
            "for_values": "1",
            "against_values": "0",
            "item_mappings": [
                {"item_id": items[0].id, "for_col": 2},
                {"item_id": items[1].id, "for_col": 3},
            ],
        }

        result = preview_voting_import(path, mapping, v, db)
        assert result["total_rows"] == 2
        assert len(result["matched"]) == 2
        assert len(result["unmatched"]) == 0

    def test_unmatched_unit(self, seed_voting, tmp_path):
        db = seed_voting["db"]
        v = seed_voting["voting"]
        items = seed_voting["items"]

        rows = [["Unknown", 999, 1, 0]]
        path = _create_test_excel(tmp_path, rows, ["A", "B", "C", "D"])

        mapping = {
            "owner_col": 0, "unit_col": 1, "start_row": 2,
            "for_values": "1", "against_values": "0",
            "item_mappings": [{"item_id": items[0].id, "for_col": 2}],
        }

        result = preview_voting_import(path, mapping, v, db)
        assert len(result["unmatched"]) == 1
        assert result["unmatched"][0]["reason"] == "Jednotka nenalezena v lístcích"

    def test_missing_unit_number(self, seed_voting, tmp_path):
        db = seed_voting["db"]
        v = seed_voting["voting"]
        items = seed_voting["items"]

        rows = [["Novák Jan", None, 1, 0]]
        path = _create_test_excel(tmp_path, rows, ["A", "B", "C", "D"])

        mapping = {
            "owner_col": 0, "unit_col": 1, "start_row": 2,
            "for_values": "1", "against_values": "0",
            "item_mappings": [{"item_id": items[0].id, "for_col": 2}],
        }

        result = preview_voting_import(path, mapping, v, db)
        assert len(result["unmatched"]) == 1
        assert "Chybí číslo jednotky" in result["unmatched"][0]["reason"]

    def test_empty_rows_skipped(self, seed_voting, tmp_path):
        db = seed_voting["db"]
        v = seed_voting["voting"]
        items = seed_voting["items"]

        rows = [
            [None, None, None, None],  # empty
            ["Novák Jan", 101, 1, 0],
        ]
        path = _create_test_excel(tmp_path, rows, ["A", "B", "C", "D"])

        mapping = {
            "owner_col": 0, "unit_col": 1, "start_row": 2,
            "for_values": "1", "against_values": "0",
            "item_mappings": [{"item_id": items[0].id, "for_col": 2}],
        }

        result = preview_voting_import(path, mapping, v, db)
        assert result["total_rows"] == 1  # empty row skipped

    def test_no_match_values(self, seed_voting, tmp_path):
        """Rows where vote values are unrecognized go to no_match."""
        db = seed_voting["db"]
        v = seed_voting["voting"]
        items = seed_voting["items"]

        rows = [["Novák Jan", 101, "MAYBE", "DUNNO"]]
        path = _create_test_excel(tmp_path, rows, ["A", "B", "C", "D"])

        mapping = {
            "owner_col": 0, "unit_col": 1, "start_row": 2,
            "for_values": "1, ANO",
            "against_values": "0, NE",
            "item_mappings": [
                {"item_id": items[0].id, "for_col": 2},
                {"item_id": items[1].id, "for_col": 3},
            ],
        }

        result = preview_voting_import(path, mapping, v, db)
        assert len(result["no_match"]) >= 1

    def test_duplicate_detection(self, seed_voting, tmp_path):
        """Duplicate ballot assignments are detected in preview."""
        db = seed_voting["db"]
        v = seed_voting["voting"]
        items = seed_voting["items"]

        # Same unit twice → same ballot matched twice
        rows = [
            ["Novák Jan", 101, 1, 0],
            ["Novák Jan", 101, 0, 1],
        ]
        path = _create_test_excel(tmp_path, rows, ["A", "B", "C", "D"])

        mapping = {
            "owner_col": 0, "unit_col": 1, "start_row": 2,
            "for_values": "1", "against_values": "0",
            "item_mappings": [
                {"item_id": items[0].id, "for_col": 2},
                {"item_id": items[1].id, "for_col": 3},
            ],
        }

        result = preview_voting_import(path, mapping, v, db)
        assert len(result["duplicates"]) >= 1


class TestExecuteVotingImport:
    def test_basic_execute(self, seed_voting, tmp_path):
        db = seed_voting["db"]
        v = seed_voting["voting"]
        items = seed_voting["items"]
        b1, b2 = seed_voting["ballots"]

        headers = ["Vlastník", "Jednotka", "Bod 1", "Bod 2"]
        rows = [
            ["Novák Jan", 101, 1, 0],
            ["Svobodová Marie", 102, 1, 1],
        ]
        path = _create_test_excel(tmp_path, rows, headers)

        mapping = {
            "owner_col": 0, "unit_col": 1, "start_row": 2,
            "for_values": "1", "against_values": "0",
            "item_mappings": [
                {"item_id": items[0].id, "for_col": 2},
                {"item_id": items[1].id, "for_col": 3},
            ],
        }

        result = execute_voting_import(path, mapping, v, db)
        assert result["processed_count"] == 2
        assert result["skipped_count"] == 0

        # Check ballot statuses
        assert b1.status == BallotStatus.PROCESSED
        assert b2.status == BallotStatus.PROCESSED

        # Check votes on b1 (re-query to get fresh state)
        b1_fresh = db.query(Ballot).get(b1.id)
        votes_b1 = {bv.voting_item_id: bv.vote for bv in b1_fresh.votes}
        assert votes_b1[items[0].id] == VoteValue.FOR
        assert votes_b1[items[1].id] == VoteValue.AGAINST

        # Check votes on b2
        b2_fresh = db.query(Ballot).get(b2.id)
        votes_b2 = {bv.voting_item_id: bv.vote for bv in b2_fresh.votes}
        assert votes_b2[items[0].id] == VoteValue.FOR
        assert votes_b2[items[1].id] == VoteValue.FOR

    def test_append_mode_preserves_existing(self, seed_voting, tmp_path):
        """In append mode (default), existing votes are not overwritten."""
        db = seed_voting["db"]
        v = seed_voting["voting"]
        items = seed_voting["items"]
        b1 = seed_voting["ballots"][0]

        # Pre-set a vote on b1
        b1.status = BallotStatus.PROCESSED
        b1.votes[0].vote = VoteValue.AGAINST
        db.flush()

        rows = [["Novák Jan", 101, 1, 1]]
        path = _create_test_excel(tmp_path, rows, ["A", "B", "C", "D"])

        mapping = {
            "owner_col": 0, "unit_col": 1, "start_row": 2,
            "for_values": "1", "against_values": "0",
            "item_mappings": [
                {"item_id": items[0].id, "for_col": 2},
                {"item_id": items[1].id, "for_col": 3},
            ],
        }

        execute_voting_import(path, mapping, v, db)

        # First vote should remain AGAINST (not overwritten)
        assert b1.votes[0].vote == VoteValue.AGAINST

    def test_clear_existing_mode(self, seed_voting, tmp_path):
        """clear_existing resets non-matched ballots and overwrites votes."""
        db = seed_voting["db"]
        v = seed_voting["voting"]
        items = seed_voting["items"]
        b1, b2 = seed_voting["ballots"]

        # Pre-process b2
        b2.status = BallotStatus.PROCESSED
        b2.processed_at = datetime.utcnow()
        for bv in b2.votes:
            bv.vote = VoteValue.FOR
        db.flush()

        # Import only covers b1 (unit 101)
        rows = [["Novák Jan", 101, 1, 0]]
        path = _create_test_excel(tmp_path, rows, ["A", "B", "C", "D"])

        mapping = {
            "owner_col": 0, "unit_col": 1, "start_row": 2,
            "for_values": "1", "against_values": "0",
            "clear_existing": True,
            "item_mappings": [
                {"item_id": items[0].id, "for_col": 2},
                {"item_id": items[1].id, "for_col": 3},
            ],
        }

        result = execute_voting_import(path, mapping, v, db)
        assert result["processed_count"] == 1
        assert result["cleared_count"] == 1
        assert result["clear_existing"] is True

        # b2 should be reset
        assert b2.status == BallotStatus.GENERATED
        assert b2.processed_at is None

    def test_saves_mapping_to_voting(self, seed_voting, tmp_path):
        """Import saves column mapping JSON on the voting object."""
        db = seed_voting["db"]
        v = seed_voting["voting"]
        items = seed_voting["items"]

        rows = [["Novák Jan", 101, 1, 0]]
        path = _create_test_excel(tmp_path, rows, ["A", "B", "C", "D"])

        mapping = {
            "owner_col": 0, "unit_col": 1, "start_row": 2,
            "for_values": "1", "against_values": "0",
            "item_mappings": [{"item_id": items[0].id, "for_col": 2}],
        }

        execute_voting_import(path, mapping, v, db)
        assert v.import_column_mapping is not None
        import json
        saved = json.loads(v.import_column_mapping)
        assert saved["owner_col"] == 0

    def test_abstain_vote(self, seed_voting, tmp_path):
        db = seed_voting["db"]
        v = seed_voting["voting"]
        items = seed_voting["items"]
        b1 = seed_voting["ballots"][0]

        rows = [["Novák Jan", 101, "ZDRŽEL", "ZDRŽEL"]]
        path = _create_test_excel(tmp_path, rows, ["A", "B", "C", "D"])

        mapping = {
            "owner_col": 0, "unit_col": 1, "start_row": 2,
            "for_values": "1, ANO",
            "against_values": "0, NE",
            "abstain_values": "ZDRŽEL, ZDRŽEL SE",
            "item_mappings": [
                {"item_id": items[0].id, "for_col": 2},
                {"item_id": items[1].id, "for_col": 3},
            ],
        }

        execute_voting_import(path, mapping, v, db)

        for bv in b1.votes:
            assert bv.vote == VoteValue.ABSTAIN


# ---------------------------------------------------------------------------
# 9. SJM pairing — preview with shared unit
# ---------------------------------------------------------------------------

class TestSjmImportPreview:
    def test_sjm_both_owners_matched(self, seed_sjm, tmp_path):
        """When Excel row has votes for an SJM unit, both co-owners get matched."""
        db = seed_sjm["db"]
        o1, o2, o3 = seed_sjm["owners"]
        u1, u2 = seed_sjm["units"]

        # Create voting + items + ballots for the SJM scenario
        v = Voting(title="SJM Test", status=VotingStatus.ACTIVE)
        db.add(v)
        db.flush()
        item = VotingItem(voting_id=v.id, order=1, title="Bod 1")
        db.add(item)
        db.flush()

        # Separate ballots for each SJM owner
        b1 = Ballot(voting_id=v.id, owner_id=o1.id, total_votes=150, units_text="201", status=BallotStatus.GENERATED)
        b2 = Ballot(voting_id=v.id, owner_id=o2.id, total_votes=150, units_text="201", status=BallotStatus.GENERATED)
        b3 = Ballot(voting_id=v.id, owner_id=o3.id, total_votes=100, units_text="202", status=BallotStatus.GENERATED)
        db.add_all([b1, b2, b3])
        db.flush()

        for b in [b1, b2, b3]:
            bv = BallotVote(ballot_id=b.id, voting_item_id=item.id, votes_count=b.total_votes)
            db.add(bv)
        db.flush()

        # Excel: one row for unit 201 with a vote
        rows = [["Dvořák Pavel", 201, 1]]
        path = _create_test_excel(tmp_path, rows, ["Vlastník", "Jednotka", "Bod"])

        mapping = {
            "owner_col": 0, "unit_col": 1, "start_row": 2,
            "for_values": "1", "against_values": "0",
            "item_mappings": [{"item_id": item.id, "for_col": 2}],
        }

        result = preview_voting_import(path, mapping, v, db)

        # Both SJM partners should be matched (ballots share unit 201)
        matched_ballot_ids = {e["ballot_id"] for e in result["matched"]}
        assert b1.id in matched_ballot_ids
        assert b2.id in matched_ballot_ids
        assert len(result["matched"]) == 2
