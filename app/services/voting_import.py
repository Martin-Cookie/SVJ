"""
Service for importing voting results from Excel.

Expected Excel format:
- Row 1: headers
- Row 2+: data rows with owner name, unit number, and vote columns (FOR/AGAINST values)

The mapping dict describes which columns map to which roles:
{
    "owner_col": 0,
    "unit_col": 2,
    "items": [
        {"item_id": 5, "for_col": 3, "against_col": 4},
        {"item_id": 6, "for_col": 5, "against_col": 6}
    ]
}
"""
from __future__ import annotations

import json
from datetime import datetime

from openpyxl import load_workbook
from sqlalchemy.orm import Session

from app.models.owner import Owner, OwnerUnit, Unit
from app.models.voting import (
    Ballot, BallotStatus, BallotVote, Voting, VoteValue,
)


def _cell(row: tuple, idx: int) -> str | None:
    """Safely get cell value as stripped string, or None."""
    if idx is None or idx >= len(row) or row[idx] is None:
        return None
    val = str(row[idx]).strip()
    return val if val else None


def _cell_numeric(row: tuple, idx: int) -> float | None:
    """Safely get cell value as a number."""
    raw = _cell(row, idx)
    if raw is None:
        return None
    try:
        return float(raw)
    except (ValueError, TypeError):
        return None


def _parse_unit_number(raw: str) -> int | None:
    """Parse unit number from string, handling '1098/115' → 115 format."""
    if "/" in raw:
        raw = raw.split("/")[-1].strip()
    try:
        return int(float(raw))
    except (ValueError, TypeError):
        return None


def _is_for_value(val: str) -> bool:
    """Check if cell value represents a FOR vote (contains a number > 0)."""
    try:
        return float(val) > 0
    except (ValueError, TypeError):
        return False


def _parse_value_list(raw: str) -> set[str]:
    """Parse comma-separated value list into a set of uppercase strings."""
    if not raw:
        return set()
    return {v.strip().upper() for v in raw.split(",") if v.strip()}


def _match_vote(raw: str | None, num: float | None, for_values: set[str], against_values: set[str]) -> str | None:
    """Match a cell value against for/against value sets. Returns 'for', 'against', or None."""
    if raw is not None:
        upper = raw.upper()
        if upper in for_values:
            return "for"
        if upper in against_values:
            return "against"
    if num is not None:
        # Also check numeric as string (e.g. "1" in for_values, "0" in against_values)
        num_str = str(int(num)) if num == int(num) else str(num)
        if num_str in for_values:
            return "for"
        if num_str in against_values:
            return "against"
    return None


def read_excel_headers(file_path: str) -> list[str]:
    """Read first row (headers) from Excel file."""
    wb = load_workbook(file_path, read_only=True, data_only=True)
    ws = wb.active
    headers = []
    for row in ws.iter_rows(min_row=1, max_row=1, values_only=True):
        headers = [str(c).strip() if c is not None else f"Sloupec {i+1}" for i, c in enumerate(row)]
    wb.close()
    return headers


def preview_voting_import(file_path: str, mapping: dict, voting: Voting, db: Session) -> dict:
    """Parse Excel with mapping and return preview without modifying DB."""
    wb = load_workbook(file_path, read_only=True, data_only=True)
    ws = wb.active

    owner_col = mapping["owner_col"]
    unit_col = mapping["unit_col"]
    start_row = mapping.get("start_row", 2)
    item_mappings = mapping.get("item_mappings") or mapping.get("items", [])

    # Parse user-defined values for PRO/PROTI
    for_values = _parse_value_list(mapping.get("for_values", "1, ANO, YES, X, PRO"))
    against_values = _parse_value_list(mapping.get("against_values", "0, NE, NO, PROTI"))

    matched = []
    unmatched = []
    errors = []

    # Build lookup: unit_number → list of (owner_id, ballot_id)
    ballot_lookup = {}
    for ballot in voting.ballots:
        owner = ballot.owner
        for ou in owner.units:
            unit_num = ou.unit.unit_number
            ballot_lookup.setdefault(unit_num, []).append(ballot)

    # Track which ballots we've already seen (for dedup across rows)
    seen_ballots = {}

    for row_idx, row in enumerate(ws.iter_rows(min_row=start_row, values_only=True), start=start_row):
        owner_name = _cell(row, owner_col)
        unit_raw = _cell(row, unit_col)

        if not owner_name and not unit_raw:
            continue

        if not unit_raw:
            unmatched.append({
                "row": row_idx,
                "owner_name": owner_name or "",
                "unit_number": "",
                "reason": "Chybí číslo jednotky",
            })
            continue

        unit_number = _parse_unit_number(unit_raw)
        if unit_number is None:
            unmatched.append({
                "row": row_idx,
                "owner_name": owner_name or "",
                "unit_number": unit_raw,
                "reason": f"Neplatné číslo jednotky: {unit_raw}",
            })
            continue

        # Find ballot via unit number
        ballots_for_unit = ballot_lookup.get(unit_number, [])
        if not ballots_for_unit:
            unmatched.append({
                "row": row_idx,
                "owner_name": owner_name or "",
                "unit_number": unit_number,
                "reason": "Jednotka nenalezena v lístcích",
            })
            continue

        # Parse vote choices for each item (ballot-independent)
        vote_choices = {}
        for im in item_mappings:
            item_id = im["item_id"]
            for_col = im.get("for_col")
            against_col = im.get("against_col")

            # Primary column — match value against for/against sets
            if for_col is not None:
                raw = _cell(row, for_col)
                num = _cell_numeric(row, for_col)
                result = _match_vote(raw, num, for_values, against_values)
                if result:
                    vote_choices[item_id] = result

            # Secondary column (PROTI zvlášť) — only if primary didn't match
            if against_col is not None and item_id not in vote_choices:
                raw = _cell(row, against_col)
                num = _cell_numeric(row, against_col)
                # In against column, for_values → PROTI, against_values → PRO (inverted)
                result = _match_vote(raw, num, for_values, against_values)
                if result == "for":
                    vote_choices[item_id] = "against"
                elif result == "against":
                    vote_choices[item_id] = "for"

        # Primary ballot = direct unit match; co-owners only if there are votes
        targets = ballots_for_unit if vote_choices else [ballots_for_unit[0]]
        for ballot in targets:
            votes = {
                item_id: {"vote": vote, "count": ballot.total_votes}
                for item_id, vote in vote_choices.items()
            }

            # Merge with previously seen rows for same ballot
            if ballot.id in seen_ballots:
                existing = seen_ballots[ballot.id]
                for item_id, vote_data in votes.items():
                    existing["votes"][item_id] = vote_data
                continue

            entry = {
                "row": row_idx,
                "owner_name": ballot.owner.display_name or owner_name,
                "unit_number": unit_number,
                "ballot_id": ballot.id,
                "votes": votes,
            }
            seen_ballots[ballot.id] = entry
            matched.append(entry)

    wb.close()

    return {
        "total_rows": len(matched) + len(unmatched),
        "matched": matched,
        "unmatched": unmatched,
        "errors": errors,
    }


def execute_voting_import(file_path: str, mapping: dict, voting: Voting, db: Session) -> dict:
    """Execute the import: update BallotVote records and ballot statuses."""
    clear_existing = mapping.get("clear_existing", False)
    preview = preview_voting_import(file_path, mapping, voting, db)

    processed_count = 0
    skipped_count = 0
    cleared_count = 0
    errors = []

    # Set of ballot IDs that will be updated from import
    matched_ballot_ids = {entry["ballot_id"] for entry in preview["matched"]}

    # If clear mode: reset all ballots that are NOT in matched set back to unprocessed
    if clear_existing:
        for ballot in voting.ballots:
            if ballot.id not in matched_ballot_ids and ballot.status == BallotStatus.PROCESSED:
                ballot.status = BallotStatus.GENERATED
                ballot.processed_at = None
                for bv in ballot.votes:
                    bv.vote = None
                    # Keep votes_count (the weight) as is
                cleared_count += 1

    # Use already-loaded ballot objects (avoids potential ORM identity issues)
    ballot_by_id = {b.id: b for b in voting.ballots}

    for entry in preview["matched"]:
        ballot = ballot_by_id.get(entry["ballot_id"])
        if not ballot:
            skipped_count += 1
            continue

        has_votes = False
        for bv in ballot.votes:
            item_id = bv.voting_item_id
            if item_id in entry["votes"]:
                vote_data = entry["votes"][item_id]
                # In append mode: skip if vote already set
                if not clear_existing and bv.vote is not None:
                    continue
                bv.vote = VoteValue.FOR if vote_data["vote"] == "for" else VoteValue.AGAINST
                bv.votes_count = vote_data["count"]
                has_votes = True
            elif clear_existing:
                # Clear mode: reset votes not in import
                bv.vote = None
                has_votes = True

        if has_votes or entry["votes"]:
            ballot.status = BallotStatus.PROCESSED
            ballot.processed_at = datetime.utcnow()
            processed_count += 1
        else:
            skipped_count += 1

    # Save mapping for next time
    voting.import_column_mapping = json.dumps(mapping, ensure_ascii=False)
    db.commit()

    return {
        "processed_count": processed_count,
        "skipped_count": skipped_count,
        "cleared_count": cleared_count,
        "unmatched_count": len(preview["unmatched"]),
        "clear_existing": clear_existing,
        "errors": preview["errors"],
    }
