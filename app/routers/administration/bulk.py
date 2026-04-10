"""Export, purge, hromadné úpravy, duplicity/slučování vlastníků."""

import io
import logging
import shutil
import zipfile
from datetime import datetime

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import RedirectResponse, Response
from sqlalchemy import func as sa_func
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import (
    Owner, OwnerUnit, Unit,
    ActivityAction, log_activity,
)
from app.services.code_list_service import CODE_LIST_CATEGORIES
from app.services.data_export import (
    EXPORT_ORDER, _EXPORTS as EXPORT_CATEGORIES,
    export_category_xlsx, export_category_csv,
)
from app.services.owner_exchange import recalculate_unit_votes
from app.services.owner_service import find_duplicate_groups, merge_owners
from app.utils import templates

from ._helpers import (
    BACKUP_DIR, GENERATED_DIR, UPLOADS_DIR,
    _BULK_FIELDS,
    _PURGE_CATEGORIES, _PURGE_ORDER, _PURGE_GROUPS,
    _get_code_list, _purge_counts,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ---- Purge page ----


@router.get("/smazat")
async def purge_page(request: Request, db: Session = Depends(get_db)):
    """Stránka pro hromadné mazání dat podle kategorií."""
    purge_counts = _purge_counts(db)
    return templates.TemplateResponse(request, "administration/purge.html", {
        "active_nav": "administration",
        "purge_categories": _PURGE_CATEGORIES,
        "purge_order": _PURGE_ORDER,
        "purge_groups": _PURGE_GROUPS,
        "purge_counts": purge_counts,
    })


@router.post("/smazat-data")
async def purge_data(request: Request, db: Session = Depends(get_db)):
    """Delete selected data categories after DELETE confirmation."""
    form_data = await request.form()
    confirmation = form_data.get("confirmation", "").strip()
    categories = form_data.getlist("categories")

    if confirmation != "DELETE" or not categories:
        return RedirectResponse("/sprava/smazat", status_code=302)

    # Delete in safe order — children before parents
    for key in _PURGE_ORDER:
        if key not in categories:
            continue
        cat = _PURGE_CATEGORIES.get(key)
        if not cat:
            continue
        for model in cat["models"]:
            db.query(model).delete()

    # Cascade: owners → sync (sync records reference owners, useless without them)
    if "owners" in categories and "sync" not in categories:
        for model in _PURGE_CATEGORIES["sync"]["models"]:
            db.query(model).delete()

    # Cascade: owners → spaces (tenant.owner_id FK → Owner)
    if "owners" in categories and "spaces" not in categories:
        for model in _PURGE_CATEGORIES["spaces"]["models"]:
            db.query(model).delete()

    # Clean uploaded files per category (only delete subdirectories of deleted categories)
    _CATEGORY_UPLOAD_DIRS = {
        "owners": ["excel"],
        "spaces": ["contracts"],
        "votings": ["word_templates", "scanned_ballots"],
        "tax": ["tax_pdfs"],
        "sync": ["csv"],
        "share_check": ["share_check"],
        "payments": ["csv"],
    }
    for cat_key in categories:
        for subdir in _CATEGORY_UPLOAD_DIRS.get(cat_key, []):
            target = UPLOADS_DIR / subdir
            if target.is_dir():
                shutil.rmtree(target, ignore_errors=True)
                target.mkdir(parents=True, exist_ok=True)
    # Cascade: owners purge also cleans sync + spaces files
    if "owners" in categories and "sync" not in categories:
        csv_dir = UPLOADS_DIR / "csv"
        if csv_dir.is_dir():
            shutil.rmtree(csv_dir, ignore_errors=True)
            csv_dir.mkdir(parents=True, exist_ok=True)
    if "owners" in categories and "spaces" not in categories:
        contracts_dir = UPLOADS_DIR / "contracts"
        if contracts_dir.is_dir():
            shutil.rmtree(contracts_dir, ignore_errors=True)
            contracts_dir.mkdir(parents=True, exist_ok=True)

    # Clean generated files (ballot PDFs etc.) only if votings are deleted
    if "votings" in categories and GENERATED_DIR.is_dir():
        shutil.rmtree(GENERATED_DIR, ignore_errors=True)
        GENERATED_DIR.mkdir(parents=True, exist_ok=True)

    # Delete backup ZIP files
    if "backups" in categories and BACKUP_DIR.is_dir():
        for f in BACKUP_DIR.glob("*.zip"):
            f.unlink(missing_ok=True)

    # Delete restore log
    if "restore_log" in categories:
        log_path = BACKUP_DIR / "restore_log.json"
        if log_path.is_file():
            log_path.unlink()

    log_activity(db, ActivityAction.DELETED, "system", "sprava",
                 description=f"Smazáno: {', '.join(categories)}")
    db.commit()
    return RedirectResponse("/sprava", status_code=302)


# ---- Export ----


@router.get("/export")
async def export_page(request: Request, db: Session = Depends(get_db)):
    """Stránka pro export dat podle kategorií."""
    purge_counts = _purge_counts(db)
    return templates.TemplateResponse(request, "administration/export.html", {
        "active_nav": "administration",
        "export_categories": EXPORT_CATEGORIES,
        "export_order": EXPORT_ORDER,
        "purge_counts": purge_counts,
    })


@router.get("/export/{category}/{fmt}")
async def export_data(category: str, fmt: str, db: Session = Depends(get_db)):
    """Download a data export in xlsx or csv format."""
    if category not in EXPORT_CATEGORIES or fmt not in ("xlsx", "csv"):
        return RedirectResponse("/sprava/export", status_code=302)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{category}_{timestamp}.{fmt}"

    if fmt == "xlsx":
        content = export_category_xlsx(db, category)
        media = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    else:
        content = export_category_csv(db, category)
        media = "text/csv; charset=utf-8"

    return Response(
        content=content,
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/export/hromadny")
async def export_bulk(request: Request, db: Session = Depends(get_db)):
    """Download a ZIP with exports for selected categories."""
    form_data = await request.form()
    categories = form_data.getlist("categories")
    fmt = form_data.get("fmt", "xlsx")
    if fmt not in ("xlsx", "csv"):
        fmt = "xlsx"

    categories = [c for c in categories if c in EXPORT_CATEGORIES]
    if not categories:
        return RedirectResponse("/sprava/export", status_code=302)

    # Single category — download directly
    if len(categories) == 1:
        cat = categories[0]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{cat}_{timestamp}.{fmt}"
        if fmt == "xlsx":
            content = export_category_xlsx(db, cat)
            media = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        else:
            content = export_category_csv(db, cat)
            media = "text/csv; charset=utf-8"
        return Response(
            content=content, media_type=media,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    # Multiple categories — pack into ZIP
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for cat in categories:
            if fmt == "xlsx":
                data = export_category_xlsx(db, cat)
            else:
                data = export_category_csv(db, cat)
            zf.writestr(f"{cat}.{fmt}", data)

    return Response(
        content=buf.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="export_{timestamp}.zip"'},
    )


# ---- Bulk edit endpoints ----


@router.get("/hromadne-upravy")
async def bulk_edit_page(request: Request, db: Session = Depends(get_db)):
    """Stránka hromadných úprav polí jednotek a vazeb."""
    # Compute stats for each field
    field_stats = {}
    for key, info in _BULK_FIELDS.items():
        model = Unit if info["model"] == "unit" else OwnerUnit
        col = getattr(model, info["column"])
        base = db.query(model)
        if model == OwnerUnit:
            base = base.filter(OwnerUnit.valid_to.is_(None))
        total_count = base.count()
        unique_count = db.query(sa_func.count(sa_func.distinct(col))).select_from(model)
        if model == OwnerUnit:
            unique_count = unique_count.filter(OwnerUnit.valid_to.is_(None))
        unique_count = unique_count.filter(col.isnot(None)).scalar() or 0
        field_stats[key] = {
            "unique_count": unique_count,
            "total_count": total_count,
            "model_label": "jednotek" if info["model"] == "unit" else "vazeb",
        }

    return templates.TemplateResponse(request, "administration/bulk_edit.html", {
        "active_nav": "administration",
        "fields": _BULK_FIELDS,
        "field_stats": field_stats,
    })


@router.get("/hromadne-upravy/hodnoty")
async def bulk_edit_values(request: Request, pole: str, db: Session = Depends(get_db)):
    """Seznam unikátních hodnot pro hromadnou úpravu daného pole."""
    field_info = _BULK_FIELDS.get(pole)
    if not field_info:
        return templates.TemplateResponse(request, "administration/bulk_edit_values.html", { "values": [], "field_key": pole, "field_label": "",
        })

    model = Unit if field_info["model"] == "unit" else OwnerUnit
    col = getattr(model, field_info["column"])

    base = db.query(col, sa_func.count().label("cnt"))
    if model == OwnerUnit:
        base = base.filter(OwnerUnit.valid_to.is_(None))
    rows = base.group_by(col).order_by(sa_func.count().desc()).all()

    values = [{"value": r[0], "count": r[1]} for r in rows]

    # Collect all existing non-null values for datalist suggestions
    suggestions = sorted(set(
        str(r[0]) for r in rows if r[0] is not None
    ))

    # Merge code list values into suggestions
    if pole in CODE_LIST_CATEGORIES:
        cl_values = [
            item.value for item in _get_code_list(db, pole)
        ]
        suggestions = sorted(set(suggestions) | set(cl_values))

    return templates.TemplateResponse(request, "administration/bulk_edit_values.html", {
        "values": values,
        "field_key": pole,
        "field_label": field_info["label"],
        "suggestions": suggestions,
    })


@router.get("/hromadne-upravy/zaznamy")
async def bulk_edit_records(
    request: Request, pole: str, hodnota: str = "", db: Session = Depends(get_db),
):
    """Záznamy s konkrétní hodnotou pole pro hromadnou úpravu."""
    field_info = _BULK_FIELDS.get(pole)
    if not field_info:
        return templates.TemplateResponse(request, "administration/bulk_edit_records.html", { "records": [], "model_type": "",
        })

    is_null = hodnota == "__null__"
    model = Unit if field_info["model"] == "unit" else OwnerUnit
    col = getattr(model, field_info["column"])

    back_url = f"/sprava/hromadne-upravy?pole={pole}&hodnota={hodnota}"

    if model == Unit:
        q = db.query(Unit).options(joinedload(Unit.owners).joinedload(OwnerUnit.owner))
        if is_null:
            q = q.filter(col.is_(None))
        else:
            q = q.filter(col == hodnota)
        records = q.order_by(Unit.unit_number).all()
        return templates.TemplateResponse(request, "administration/bulk_edit_records.html", { "records": records, "model_type": "unit",
            "back_url": back_url,
        })
    else:
        q = (
            db.query(OwnerUnit)
            .options(joinedload(OwnerUnit.owner), joinedload(OwnerUnit.unit))
            .filter(OwnerUnit.valid_to.is_(None))
        )
        if is_null:
            q = q.filter(col.is_(None))
        else:
            q = q.filter(col == hodnota)
        records = q.order_by(OwnerUnit.unit_id).all()
        return templates.TemplateResponse(request, "administration/bulk_edit_records.html", { "records": records, "model_type": "owner_unit",
            "back_url": back_url,
        })


@router.post("/hromadne-upravy/opravit")
async def bulk_edit_apply(
    request: Request,
    db: Session = Depends(get_db),
):
    """Aplikování hromadné změny hodnoty na vybrané záznamy."""
    form_data = await request.form()
    pole = form_data.get("pole", "")
    old_value = form_data.get("old_value", "")
    new_value = form_data.get("new_value", "")
    is_null = form_data.get("is_null", "")
    ids = form_data.getlist("ids")

    field_info = _BULK_FIELDS.get(pole)
    if not field_info:
        return RedirectResponse("/sprava/hromadne-upravy", status_code=302)

    model = Unit if field_info["model"] == "unit" else OwnerUnit
    col = getattr(model, field_info["column"])

    # Build filter
    if ids:
        # Filter by selected record IDs
        record_ids = [int(i) for i in ids]
        q = db.query(model).filter(model.id.in_(record_ids))
    elif is_null == "1":
        q = db.query(model).filter(col.is_(None))
    else:
        # Convert old_value for numeric columns
        filter_value = old_value
        if pole == "orientation_number":
            try:
                filter_value = int(old_value)
            except ValueError:
                logger.debug("Cannot convert orientation_number filter '%s' to int", old_value)
        elif pole == "share":
            try:
                filter_value = float(old_value)
            except ValueError:
                logger.debug("Cannot convert share filter '%s' to float", old_value)
        q = db.query(model).filter(col == filter_value)

    # Set new value (empty string → None)
    final_value = new_value.strip() if new_value.strip() else None

    # Type conversions for numeric fields
    if pole == "orientation_number" and final_value is not None:
        try:
            final_value = int(final_value)
        except ValueError:
            return RedirectResponse(
                f"/sprava/hromadne-upravy?pole={pole}", status_code=302
            )
    if pole == "share" and final_value is not None:
        try:
            final_value = float(final_value)
        except ValueError:
            return RedirectResponse(
                f"/sprava/hromadne-upravy?pole={pole}", status_code=302
            )

    q.update({col: final_value}, synchronize_session="fetch")

    # Recalculate votes when share changes
    if pole == "share":
        affected_ous = q.all()
        seen_units = set()
        for ou in affected_ous:
            if ou.unit_id not in seen_units:
                seen_units.add(ou.unit_id)
                unit = db.query(Unit).get(ou.unit_id)
                if unit:
                    recalculate_unit_votes(unit, db)

    db.commit()

    return RedirectResponse(
        f"/sprava/hromadne-upravy?pole={pole}", status_code=302
    )


# ---------------------------------------------------------------------------
# Deduplikace vlastníků
# ---------------------------------------------------------------------------

@router.get("/duplicity")
async def duplicates_page(
    request: Request,
    db: Session = Depends(get_db),
    back: str = Query(""),
):
    """Stránka detekce a slučování duplicitních vlastníků."""
    groups = find_duplicate_groups(db)
    back_url = back or "/sprava"

    return templates.TemplateResponse(request, "administration/duplicates.html", {
        "active_nav": "administration",
        "groups": groups,
        "total_groups": len(groups),
        "total_extra": sum(len(g["owners"]) - 1 for g in groups),
        "back_url": back_url,
    })


@router.post("/duplicity/sloucit")
async def merge_duplicate_group(
    request: Request,
    db: Session = Depends(get_db),
):
    """Merge a single duplicate group — target_id + dup_ids from form."""
    form = await request.form()
    target_id = int(form.get("target_id", 0))
    dup_ids = [int(v) for v in form.getlist("dup_ids")]

    if not target_id or not dup_ids:
        return RedirectResponse("/sprava/duplicity", status_code=302)

    target = db.query(Owner).options(
        joinedload(Owner.units).joinedload(OwnerUnit.unit)
    ).get(target_id)
    if not target:
        return RedirectResponse("/sprava/duplicity", status_code=302)

    duplicates = []
    for did in dup_ids:
        dup = db.query(Owner).options(
            joinedload(Owner.units).joinedload(OwnerUnit.unit)
        ).get(did)
        if dup and dup.id != target.id:
            duplicates.append(dup)

    merge_owners(target, duplicates, db)
    db.commit()

    return RedirectResponse("/sprava/duplicity", status_code=302)


@router.post("/duplicity/sloucit-vse")
async def merge_all_duplicates(
    request: Request,
    db: Session = Depends(get_db),
):
    """Merge ALL duplicate groups at once using recommended targets."""

    groups = find_duplicate_groups(db)
    merged_count = 0

    for group in groups:
        rec_id = group["recommended_id"]
        target = db.query(Owner).options(
            joinedload(Owner.units).joinedload(OwnerUnit.unit)
        ).get(rec_id)
        if not target:
            continue

        duplicates = []
        for o in group["owners"]:
            if o.id != rec_id:
                dup = db.query(Owner).options(
                    joinedload(Owner.units).joinedload(OwnerUnit.unit)
                ).get(o.id)
                if dup:
                    duplicates.append(dup)

        if duplicates:
            merge_owners(target, duplicates, db)
            merged_count += 1

    db.commit()

    return RedirectResponse("/sprava/duplicity", status_code=302)
