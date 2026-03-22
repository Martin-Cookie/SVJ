"""Sdílené konstanty a helper funkce pro modul administrace."""

import logging

from sqlalchemy import case, func as sa_func
from sqlalchemy.orm import Session

from app.config import settings
from app.models import (
    SvjInfo, SvjAddress, BoardMember, CodeListItem,
    Unit, OwnerUnit, Owner, Proxy,
    Voting, VotingItem, Ballot, BallotVote,
    TaxSession, TaxDocument, TaxDistribution,
    SyncSession, SyncRecord,
    ShareCheckSession, ShareCheckRecord, ShareCheckColumnMapping,
    PrescriptionYear, Prescription, PrescriptionItem,
    VariableSymbolMapping, BankStatement, Payment,
    UnitBalance, Settlement, SettlementItem,
    EmailTemplate, EmailLog, ImportLog, ActivityLog,
)
from app.services.backup_service import read_restore_log
from app.services.code_list_service import CODE_LIST_CATEGORIES

logger = logging.getLogger(__name__)

# ---- Path constants ----

DB_PATH = settings.database_path
UPLOADS_DIR = settings.upload_dir
GENERATED_DIR = settings.generated_dir
BACKUP_DIR = settings.backup_dir

# ---- Board member role sort ----

# Sort priority: Předseda/Předsedkyně first, then Místopředseda, then others
_role_lower = sa_func.lower(BoardMember.role)
_ROLE_SORT = case(
    (_role_lower.like("předseda%"), 0),
    (_role_lower.like("předsedkyně%"), 0),
    (_role_lower.like("místopředseda%"), 1),
    (_role_lower.like("místopředsedkyně%"), 1),
    else_=2,
)

# ---- Bulk edit field mapping ----

_BULK_FIELDS = {
    "space_type": {"label": "Typ prostoru", "model": "unit", "column": "space_type"},
    "section": {"label": "Sekce", "model": "unit", "column": "section"},
    "room_count": {"label": "Počet místností", "model": "unit", "column": "room_count"},
    "ownership_type": {"label": "Vlastnictví druh", "model": "owner_unit", "column": "ownership_type"},
    "share": {"label": "Vlastnictví/Podíl", "model": "owner_unit", "column": "share"},
    "address": {"label": "Adresa", "model": "unit", "column": "address"},
    "orientation_number": {"label": "Orientační číslo", "model": "unit", "column": "orientation_number"},
}

# ---- Purge categories ----

_PURGE_CATEGORIES = {
    "owners": {
        "label": "Vlastníci a jednotky",
        "description": "Vlastníci, jednotky, vazby vlastník-jednotka, plné moci",
        "models": [Proxy, OwnerUnit, Owner, Unit],
    },
    "votings": {
        "label": "Hlasování",
        "description": "Hlasování, body hlasování, hlasovací lístky, hlasy",
        "models": [BallotVote, Ballot, VotingItem, Voting],
    },
    "tax": {
        "label": "Daňové podklady",
        "description": "Daňové relace, dokumenty, distribuce",
        "models": [TaxDistribution, TaxDocument, TaxSession],
    },
    "sync": {
        "label": "Synchronizace",
        "description": "Synchronizační relace a záznamy",
        "models": [SyncRecord, SyncSession],
    },
    "share_check": {
        "label": "Kontrola podílu",
        "description": "Kontroly podílů SČD — relace, záznamy, mapování sloupců",
        "models": [ShareCheckRecord, ShareCheckSession, ShareCheckColumnMapping],
    },
    "payments": {
        "label": "Evidence plateb",
        "description": "Předpisy, VS mapování, výpisy, platby, zůstatky, vyúčtování",
        "models": [
            SettlementItem, Settlement,
            Payment, BankStatement,
            PrescriptionItem, Prescription, PrescriptionYear,
            VariableSymbolMapping, UnitBalance,
        ],
    },
    # Logy — rozpad na 3 podkategorie
    "email_logs": {
        "label": "Email logy",
        "description": "Záznamy o odeslaných emailech",
        "models": [EmailLog],
    },
    "import_logs": {
        "label": "Import logy",
        "description": "Záznamy o provedených importech",
        "models": [ImportLog],
    },
    "activity_logs": {
        "label": "Aktivita",
        "description": "Logy aktivit uživatelů",
        "models": [ActivityLog],
    },
    # Administrace — rozpad na 4 podkategorie
    "svj_info": {
        "label": "SVJ info a adresy",
        "description": "Informace o SVJ a adresy",
        "models": [SvjAddress, SvjInfo],
    },
    "board": {
        "label": "Výbor",
        "description": "Členové výboru",
        "models": [BoardMember],
    },
    "code_lists": {
        "label": "Číselníky",
        "description": "Položky číselníků (typy vlastnictví, prostorů apod.)",
        "models": [CodeListItem],
    },
    "email_templates": {
        "label": "Email šablony",
        "description": "Šablony pro hromadné rozesílání",
        "models": [EmailTemplate],
    },
    "backups": {
        "label": "Existující zálohy",
        "description": "ZIP soubory záloh v adresáři data/backups",
        "models": [],
    },
    "restore_log": {
        "label": "Historie obnovení",
        "description": "Záznam o provedených obnoveních ze záloh",
        "models": [],
    },
}

_PURGE_ORDER = [
    "owners", "votings", "tax", "sync", "share_check", "payments",
    "email_logs", "import_logs", "activity_logs",
    "svj_info", "board", "code_lists", "email_templates",
    "backups", "restore_log",
]

# Seskupení pro šablonu — standalone položky bez label, skupiny s label
_PURGE_GROUPS = [
    {"cat_keys": ["owners"]},
    {"cat_keys": ["votings"]},
    {"cat_keys": ["tax"]},
    {"cat_keys": ["sync"]},
    {"cat_keys": ["share_check"]},
    {"cat_keys": ["payments"]},
    {"label": "Logy", "cat_keys": ["email_logs", "import_logs", "activity_logs"]},
    {"label": "Administrace SVJ", "cat_keys": ["svj_info", "board", "code_lists", "email_templates"]},
    {"cat_keys": ["backups"]},
    {"cat_keys": ["restore_log"]},
]


# ---- Helper functions ----

def _get_or_create_svj_info(db: Session) -> SvjInfo:
    info = db.query(SvjInfo).first()
    if not info:
        info = SvjInfo()
        db.add(info)
        db.flush()
    return info


def _get_code_list(db: Session, category: str):
    """Return code list items for a category, sorted by (order, value)."""
    return (
        db.query(CodeListItem)
        .filter_by(category=category)
        .order_by(CodeListItem.order, CodeListItem.value)
        .all()
    )


def _get_usage_count(db: Session, category: str, value: str) -> int:
    """Return number of records using a code list value."""
    meta = CODE_LIST_CATEGORIES.get(category)
    if not meta:
        return 0
    model = meta["model"]
    col = getattr(model, meta["column"])
    q = db.query(model).filter(col == value)
    if model == OwnerUnit:
        q = q.filter(OwnerUnit.valid_to.is_(None))
    return q.count()


def _purge_counts(db: Session) -> dict:
    """Return {category_key: total_row_count} for each purge category."""
    counts = {}
    for key in _PURGE_ORDER:
        cat = _PURGE_CATEGORIES[key]
        if key == "backups":
            counts[key] = len(list(BACKUP_DIR.glob("*.zip"))) if BACKUP_DIR.is_dir() else 0
        elif key == "restore_log":
            counts[key] = len(read_restore_log(str(BACKUP_DIR)))
        else:
            counts[key] = sum(db.query(m).count() for m in cat["models"])
    return counts
