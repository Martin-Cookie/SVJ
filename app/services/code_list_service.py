"""Code list service — shared code list operations."""
from sqlalchemy.orm import Session

from app.models import CodeListItem, OwnerUnit, Unit

CODE_LIST_CATEGORIES = {
    "space_type": {"label": "Typ prostoru", "model": Unit, "column": "space_type"},
    "section": {"label": "Sekce", "model": Unit, "column": "section"},
    "room_count": {"label": "Počet místností", "model": Unit, "column": "room_count"},
    "ownership_type": {"label": "Typ vlastnictví", "model": OwnerUnit, "column": "ownership_type"},
}

CODE_LIST_ORDER = ["space_type", "section", "room_count", "ownership_type"]


def get_all_code_lists(db: Session) -> dict:
    """Return {category: [items]} for all code list categories."""
    items = (
        db.query(CodeListItem)
        .order_by(CodeListItem.category, CodeListItem.order, CodeListItem.value)
        .all()
    )
    result = {cat: [] for cat in CODE_LIST_ORDER}
    for item in items:
        if item.category in result:
            result[item.category].append(item)
    return result
