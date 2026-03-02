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

_CZECH_SURNAME_SUFFIXES = [
    # Sorted longest-first; must be ASCII (applied after unidecode)
    "kovou", "kovi", "kove", "kova", "ovou", "ovi", "ove", "ova", "kem", "ek", "i",
]


def _stem_czech_surname(word: str) -> str:
    """Reduce Czech surname to rough stem for matching."""
    for s in _CZECH_SURNAME_SUFFIXES:
        if word.endswith(s) and len(word) - len(s) >= 3:
            return word[: -len(s)]
    return word


def normalize_for_matching(name: str) -> str:
    result = name.strip()
    for pattern in TITLE_PATTERNS:
        result = re.sub(pattern, " ", result, flags=re.IGNORECASE)
    # Remove SJ/SJM prefix and suffix
    result = re.sub(r"^SJM?\s+", "", result, flags=re.IGNORECASE)
    result = re.sub(r"\s+SJM?\s*$", "", result, flags=re.IGNORECASE)
    # Remove parenthetical notes
    result = re.sub(r"\([^)]*\)", "", result)
    result = " ".join(result.split()).strip(" ,")
    result = result.lower()
    result = unidecode(result)
    # Apply Czech surname stemming to each word
    result = " ".join(_stem_czech_surname(w) for w in result.split())
    return result


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
    if not intersection:
        return 0.0
    union = parts1 | parts2
    jaccard = len(intersection) / len(union)
    # Overlap coefficient: if all parts of the shorter name match, score high
    overlap = len(intersection) / min(len(parts1), len(parts2))
    return max(jaccard, overlap * 0.8)


def _get_stemmed_parts(name: str) -> tuple[set, set]:
    """Return (all_stemmed_parts, parts_where_suffix_was_removed).

    The second set identifies likely surnames (words that had a Czech
    gender suffix stripped, e.g. -ová, -ková).
    """
    result = name.strip()
    for pattern in TITLE_PATTERNS:
        result = re.sub(pattern, " ", result, flags=re.IGNORECASE)
    result = re.sub(r"^SJM?\s+", "", result, flags=re.IGNORECASE)
    result = re.sub(r"\s+SJM?\s*$", "", result, flags=re.IGNORECASE)
    result = re.sub(r"\([^)]*\)", "", result)
    result = " ".join(result.split()).strip(" ,")
    result = result.lower()
    result = unidecode(result)

    connectors = {"a", "and", "und"}
    all_parts = set()
    surname_parts = set()
    for w in result.split():
        if w in connectors:
            continue
        stemmed = _stem_czech_surname(w)
        all_parts.add(stemmed)
        if stemmed != w:
            surname_parts.add(stemmed)
    return all_parts, surname_parts


def match_name(
    candidate: str,
    known_owners: list[dict],
    threshold: float = 0.70,
    require_stem_overlap: bool = False,
) -> list[dict]:
    """
    Find best matches for a candidate name among known owners.
    known_owners: [{"id": int, "name": str, "name_normalized": str}, ...]
    require_stem_overlap: if True, at least one stemmed surname part must
        be shared (prevents false positives like Bartíková→Birčáková where
        only the first name "Barbora" matches).
    Returns matches sorted by confidence descending.
    """
    candidate_norm = normalize_for_matching(candidate)
    cand_parts, cand_surnames = (
        _get_stemmed_parts(candidate) if require_stem_overlap else (None, None)
    )
    matches = []

    for owner in known_owners:
        owner_norm = normalize_for_matching(owner.get("name_normalized", owner["name"]))
        # Sequence matcher ratio
        seq_ratio = SequenceMatcher(None, candidate_norm, owner_norm).ratio()
        # Parts-based ratio (uses stemmed forms)
        parts_ratio = name_parts_match(candidate, owner["name"])
        # No shared stemmed parts and low sequence similarity → skip
        if parts_ratio == 0 and seq_ratio < 0.75:
            continue

        # Surname stem check: if either name has a detected surname
        # (Czech suffix removed), require at least one surname stem to match
        if require_stem_overlap:
            own_parts, own_surnames = _get_stemmed_parts(owner["name"])
            surname_stems = cand_surnames | own_surnames
            if surname_stems:
                shared = cand_parts & own_parts
                if not (shared & surname_stems):
                    continue  # only first names match, surnames differ

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
