from __future__ import annotations

"""
Fuzzy name matching for linking extracted names to known owners.
Used by Module B (tax PDFs) and Module C (CSV comparison).
"""
import re
from difflib import SequenceMatcher

from unidecode import unidecode

TITLE_PATTERNS = [
    r"\bIng\.\s*", r"\bMgr\.\s*", r"\bBc\.\s*", r"\bMUDr\.\s*",
    r"\bJUDr\.\s*", r"\bRNDr\.\s*", r"\bPhDr\.\s*", r"\bDoc\.\s*",
    r"\bProf\.\s*", r",?\s*Ph\.?D\.?\s*", r",?\s*CSc\.?\s*",
    r",?\s*MBA\s*", r"\bDiS\.\s*",
]


def normalize_for_matching(name: str) -> str:
    result = name.strip()
    for pattern in TITLE_PATTERNS:
        result = re.sub(pattern, " ", result, flags=re.IGNORECASE)
    # Remove SJ/SJM suffix
    result = re.sub(r"\s+SJM?\s*$", "", result, flags=re.IGNORECASE)
    # Remove parenthetical notes
    result = re.sub(r"\([^)]*\)", "", result)
    result = " ".join(result.split()).strip(" ,")
    result = result.lower()
    return unidecode(result)


def name_parts_match(name1: str, name2: str) -> float:
    """Compare two names by splitting into parts and checking overlap."""
    parts1 = set(normalize_for_matching(name1).split())
    parts2 = set(normalize_for_matching(name2).split())
    if not parts1 or not parts2:
        return 0.0
    # Remove connectors
    connectors = {"a", "and", "und"}
    parts1 -= connectors
    parts2 -= connectors
    if not parts1 or not parts2:
        return 0.0
    intersection = parts1 & parts2
    union = parts1 | parts2
    return len(intersection) / len(union) if union else 0.0


def match_name(
    candidate: str,
    known_owners: list[dict],
    threshold: float = 0.70,
) -> list[dict]:
    """
    Find best matches for a candidate name among known owners.
    known_owners: [{"id": int, "name": str, "name_normalized": str}, ...]
    Returns matches sorted by confidence descending.
    """
    candidate_norm = normalize_for_matching(candidate)
    matches = []

    for owner in known_owners:
        owner_norm = normalize_for_matching(owner.get("name_normalized", owner["name"]))
        # Sequence matcher ratio
        seq_ratio = SequenceMatcher(None, candidate_norm, owner_norm).ratio()
        # Parts-based ratio
        parts_ratio = name_parts_match(candidate, owner["name"])
        # Use the better of the two
        confidence = max(seq_ratio, parts_ratio)

        if confidence >= threshold:
            matches.append({
                "owner_id": owner["id"],
                "owner_name": owner["name"],
                "confidence": round(confidence, 3),
            })

    matches.sort(key=lambda m: m["confidence"], reverse=True)
    return matches
