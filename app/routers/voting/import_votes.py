import json
import shutil

from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session, joinedload

from app.config import settings
from app.database import get_db
from app.models import (
    Ballot, BallotVote, Owner, OwnerUnit, SvjInfo, Voting, VotingStatus,
    ActivityAction, log_activity,
)
from app.services.voting_import import (
    read_excel_headers, preview_voting_import, execute_voting_import, validate_mapping,
)
from app.utils import UPLOAD_LIMITS, build_import_wizard, is_safe_path, utcnow, validate_upload

from ._helpers import (
    _ballot_stats,
    _voting_wizard,
    logger,
    templates,
)


router = APIRouter()


def _load_saved_mapping(voting: Voting, db: Session) -> Optional[dict]:
    """Load saved import mapping: per-voting first, then global fallback with item_id remapping."""
    # 1. Per-voting mapping (exact match)
    if voting.import_column_mapping:
        try:
            return json.loads(voting.import_column_mapping)
        except (json.JSONDecodeError, TypeError):
            logger.debug("Failed to parse per-voting import mapping for voting %s", voting.id, exc_info=True)

    # 2. Global fallback from SvjInfo
    svj = db.query(SvjInfo).first()
    if not svj or not svj.voting_import_mapping:
        return None

    try:
        mapping = json.loads(svj.voting_import_mapping)
    except (json.JSONDecodeError, TypeError):
        return None

    # Remap item_ids by position: global mapping has item_ids from previous voting
    items_sorted = sorted(voting.items, key=lambda i: i.order)
    old_items = mapping.get("item_mappings") or mapping.get("items", [])
    new_items = []
    for idx, im in enumerate(old_items):
        if idx < len(items_sorted):
            new_items.append({
                **im,
                "item_id": items_sorted[idx].id,
            })
    mapping["item_mappings"] = new_items
    if "items" in mapping:
        del mapping["items"]

    return mapping


def _save_mapping_global(mapping_json: str, db: Session):
    """Save mapping globally to SvjInfo for reuse across votings (commit handled by caller)."""
    svj = db.query(SvjInfo).first()
    if svj:
        svj.voting_import_mapping = mapping_json


@router.get("/{voting_id}/import")
async def import_upload_page(
    voting_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    """Stránka nahrání souboru pro import hlasů z Excelu."""
    voting = db.query(Voting).options(
        joinedload(Voting.items),
        joinedload(Voting.ballots).joinedload(Ballot.votes),
    ).get(voting_id)
    if not voting:
        return RedirectResponse("/hlasovani", status_code=302)

    saved_mapping = _load_saved_mapping(voting, db)

    has_processed = voting.has_processed_ballots
    return templates.TemplateResponse(request, "voting/import_upload.html", {
        "active_nav": "voting",
        "voting": voting,
        "saved_mapping": saved_mapping,
        **build_import_wizard(1),
        "active_bubble": "",
        "show_close_voting": has_processed,
        **_ballot_stats(voting, db),
        **_voting_wizard(voting, 3),
    })


@router.post("/{voting_id}/import")
async def import_upload(
    voting_id: int,
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Nahrání Excel souboru a zobrazení mapování sloupců."""
    voting = db.query(Voting).options(
        joinedload(Voting.items),
        joinedload(Voting.ballots).joinedload(Ballot.votes),
    ).get(voting_id)
    if not voting:
        return RedirectResponse("/hlasovani", status_code=302)

    has_processed = voting.has_processed_ballots
    err = await validate_upload(file, **UPLOAD_LIMITS["excel"]) if file.filename else "Nahrajte soubor ve formátu .xlsx"
    if err:
        return templates.TemplateResponse(request, "voting/import_upload.html", {
            "active_nav": "voting",
            "voting": voting,
            "saved_mapping": None,
            **build_import_wizard(1),
            "active_bubble": "",
            "flash_message": err,
            "flash_type": "error",
            "show_close_voting": has_processed,
            **_ballot_stats(voting, db),
            **_voting_wizard(voting, 3),
        })

    timestamp = utcnow().strftime("%Y%m%d_%H%M%S")
    dest = settings.upload_dir / "excel" / f"{timestamp}_{file.filename}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)

    headers = read_excel_headers(str(dest))

    # Load saved mapping if available (per-voting or global fallback)
    saved_mapping = _load_saved_mapping(voting, db)

    return templates.TemplateResponse(request, "voting/import_mapping.html", {
        "active_nav": "voting",
        "voting": voting,
        "headers": headers,
        "file_path": str(dest),
        "filename": file.filename,
        "saved_mapping": saved_mapping,
        **build_import_wizard(2),
        "active_bubble": "",
        "show_close_voting": has_processed,
        **_ballot_stats(voting, db),
        **_voting_wizard(voting, 3),
    })


@router.post("/{voting_id}/import/mapovani")
async def import_back_to_mapping(
    voting_id: int,
    request: Request,
    file_path: str = Form(...),
    db: Session = Depends(get_db),
):
    """Return to mapping page from preview (back navigation)."""
    voting = db.query(Voting).options(
        joinedload(Voting.items),
        joinedload(Voting.ballots).joinedload(Ballot.votes),
    ).get(voting_id)
    if not voting:
        return RedirectResponse("/hlasovani", status_code=302)

    if not Path(file_path).exists() or not is_safe_path(Path(file_path), settings.upload_dir):
        return RedirectResponse(f"/hlasovani/{voting_id}/import", status_code=302)

    headers = read_excel_headers(file_path)
    saved_mapping = _load_saved_mapping(voting, db)
    has_processed = voting.has_processed_ballots

    return templates.TemplateResponse(request, "voting/import_mapping.html", {
        "active_nav": "voting",
        "voting": voting,
        "headers": headers,
        "file_path": file_path,
        "filename": Path(file_path).name,
        "saved_mapping": saved_mapping,
        **build_import_wizard(2),
        "active_bubble": "",
        "show_close_voting": has_processed,
        **_ballot_stats(voting, db),
        **_voting_wizard(voting, 3),
    })


@router.post("/{voting_id}/import/nahled")
async def import_preview(
    voting_id: int,
    request: Request,
    file_path: str = Form(...),
    mapping_json: str = Form(...),
    save_mapping: str = Form(""),
    db: Session = Depends(get_db),
):
    """Náhled importovaných hlasů před potvrzením."""
    voting = db.query(Voting).options(
        joinedload(Voting.items),
        joinedload(Voting.ballots).joinedload(Ballot.owner).joinedload(Owner.units).joinedload(OwnerUnit.unit),
        joinedload(Voting.ballots).joinedload(Ballot.votes),
    ).get(voting_id)
    if not voting:
        return RedirectResponse("/hlasovani", status_code=302)

    if not is_safe_path(Path(file_path), settings.upload_dir):
        return RedirectResponse(f"/hlasovani/{voting_id}/import", status_code=302)

    try:
        mapping = json.loads(mapping_json)
    except (json.JSONDecodeError, TypeError):
        return RedirectResponse(f"/hlasovani/{voting_id}/import", status_code=302)

    mapping_error = validate_mapping(mapping)
    if mapping_error:
        logger.warning("Invalid import mapping: %s", mapping_error)
        return RedirectResponse(f"/hlasovani/{voting_id}/import", status_code=302)

    # Save mapping for next time (only if user checked the box)
    if save_mapping:
        voting.import_column_mapping = mapping_json
        _save_mapping_global(mapping_json, db)

    preview = preview_voting_import(file_path, mapping, voting, db)

    # Build item lookup for template
    item_lookup = {item.id: item for item in voting.items}

    has_processed = voting.has_processed_ballots
    return templates.TemplateResponse(request, "voting/import_preview.html", {
        "active_nav": "voting",
        "voting": voting,
        "preview": preview,
        "mapping": mapping,
        "mapping_json": mapping_json,
        "file_path": file_path,
        "item_lookup": item_lookup,
        **build_import_wizard(3),
        "active_bubble": "",
        "show_close_voting": has_processed,
        **_ballot_stats(voting, db),
        **_voting_wizard(voting, 3),
    })


@router.post("/{voting_id}/import/potvrdit")
async def import_confirm(
    voting_id: int,
    request: Request,
    file_path: str = Form(...),
    mapping_json: str = Form(...),
    db: Session = Depends(get_db),
):
    """Potvrzení a provedení importu hlasů do lístků."""
    voting = db.query(Voting).options(
        joinedload(Voting.items),
        joinedload(Voting.ballots).joinedload(Ballot.owner).joinedload(Owner.units).joinedload(OwnerUnit.unit),
        joinedload(Voting.ballots).joinedload(Ballot.votes),
    ).get(voting_id)
    if not voting:
        return RedirectResponse("/hlasovani", status_code=302)

    # Check voting is active before importing
    if voting.status != VotingStatus.ACTIVE:
        return RedirectResponse(f"/hlasovani/{voting_id}", status_code=302)

    if not is_safe_path(Path(file_path), settings.upload_dir):
        return RedirectResponse(f"/hlasovani/{voting_id}/import", status_code=302)

    if not Path(file_path).exists():
        return RedirectResponse(f"/hlasovani/{voting_id}/import", status_code=302)

    try:
        mapping = json.loads(mapping_json)
    except (json.JSONDecodeError, TypeError):
        return RedirectResponse(f"/hlasovani/{voting_id}/import", status_code=302)

    mapping_error = validate_mapping(mapping)
    if mapping_error:
        logger.warning("Invalid import mapping: %s", mapping_error)
        return RedirectResponse(f"/hlasovani/{voting_id}/import", status_code=302)

    result = execute_voting_import(file_path, mapping, voting, db)

    # Save mapping globally for reuse in future votings
    _save_mapping_global(mapping_json, db)

    log_activity(db, ActivityAction.IMPORTED, "voting", "hlasovani",
                 entity_id=voting.id, entity_name=voting.title,
                 description=f"Import výsledků: {result.get('processed_count', 0)} lístků")

    # Single atomic commit for all changes
    db.commit()

    # Clean up uploaded Excel file after successful commit
    try:
        Path(file_path).unlink(missing_ok=True)
    except Exception:
        logger.debug("Failed to clean up import file: %s", file_path)

    has_processed = voting.has_processed_ballots
    return templates.TemplateResponse(request, "voting/import_result.html", {
        "active_nav": "voting",
        "voting": voting,
        "result": result,
        **build_import_wizard(4),
        "active_bubble": "",
        "show_close_voting": has_processed,
        **_ballot_stats(voting, db),
        **_voting_wizard(voting, 4),
    })
