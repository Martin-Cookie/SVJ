"""Export data tables to Excel (.xlsx) and CSV formats."""
from __future__ import annotations

import csv
import io
from datetime import datetime

from openpyxl import Workbook
from sqlalchemy.orm import Session, joinedload

from app.models import (
    Owner, Unit, OwnerUnit, Proxy,
    Voting, VotingItem, Ballot, BallotVote,
    TaxSession, TaxDocument, TaxDistribution,
    SyncSession, SyncRecord,
    EmailLog, ImportLog,
    SvjInfo, SvjAddress, BoardMember,
)

# ── Column definitions per export category ──────────────────────────

_EXPORTS: dict[str, dict] = {
    "owners": {
        "label": "Vlastníci a jednotky",
        "headers": [
            "Jednotka", "Č. prostoru", "Podíl SČD", "Plocha m²",
            "Místnosti", "Druh prostoru", "Sekce", "Orient. číslo",
            "Adresa jednotky", "LV", "Typ vlastnictví", "Podíl",
            "Hlasy", "Jméno", "Příjmení", "Titul", "RČ / IČ",
            "Trvalá ulice", "Trvalá část obce", "Trvalá město",
            "Trvalá PSČ", "Trvalá stát",
            "Kor. ulice", "Kor. část obce", "Kor. město",
            "Kor. PSČ", "Kor. stát",
            "Telefon", "Telefon pevný", "Email", "Email 2",
            "Vlastník od", "Poznámka",
        ],
    },
    "votings": {
        "label": "Hlasování",
        "headers": [
            "Hlasování", "Stav", "Začátek", "Konec",
            "Kvórum %", "Celkem hlasů",
            "Bod č.", "Bod – název",
            "Vlastník", "Jednotky", "Hlasy lístku",
            "Hlas", "Počet hlasů",
        ],
    },
    "tax": {
        "label": "Daňové podklady",
        "headers": [
            "Relace", "Rok", "Dokument", "Jednotka",
            "Extrahované jméno", "Vlastník", "Stav párování",
            "Shoda %", "Email odeslán", "Poznámka",
        ],
    },
    "sync": {
        "label": "Synchronizace",
        "headers": [
            "Relace", "Datum", "Jednotka",
            "Jméno CSV", "Jméno Excel",
            "Vlastnictví CSV", "Vlastnictví Excel",
            "Email CSV", "Telefon CSV",
            "Druh prostoru CSV", "Druh prostoru Excel",
            "Podíl CSV", "Podíl Excel",
            "Stav", "Řešení", "Opravené jméno", "Poznámka",
        ],
    },
    "logs": {
        "label": "Logy",
        "headers": [
            "Typ", "Datum", "Příjemce / Soubor",
            "Předmět / Typ importu",
            "Stav", "Detail",
        ],
    },
    "administration": {
        "label": "Administrace SVJ",
        "headers": [
            "Typ záznamu", "Hodnota 1", "Hodnota 2",
            "Hodnota 3", "Hodnota 4",
        ],
    },
}

EXPORT_ORDER = ["owners", "votings", "tax", "sync", "logs", "administration"]


def _fmt(val) -> str:
    if val is None:
        return ""
    if isinstance(val, datetime):
        return val.strftime("%d.%m.%Y %H:%M")
    return str(val)


def _date(val) -> str:
    if val is None:
        return ""
    return val.strftime("%d.%m.%Y") if hasattr(val, "strftime") else str(val)


# ── Row generators ──────────────────────────────────────────────────

def _rows_owners(db: Session):
    owners = (
        db.query(Owner).filter_by(is_active=True)
        .options(joinedload(Owner.units).joinedload(OwnerUnit.unit))
        .order_by(Owner.name_normalized)
        .all()
    )
    for owner in owners:
        rc_ic = owner.company_id or owner.birth_number or ""
        for ou in owner.units:
            u = ou.unit
            yield [
                u.unit_number, u.building_number or "", u.podil_scd,
                u.floor_area, u.room_count or "", u.space_type or "",
                u.section or "", u.orientation_number, u.address or "",
                u.lv_number, ou.ownership_type or "", ou.share, ou.votes,
                owner.first_name, owner.last_name or "", owner.title or "",
                rc_ic,
                owner.perm_street or "", owner.perm_district or "",
                owner.perm_city or "", owner.perm_zip or "",
                owner.perm_country or "",
                owner.corr_street or "", owner.corr_district or "",
                owner.corr_city or "", owner.corr_zip or "",
                owner.corr_country or "",
                owner.phone or "", owner.phone_landline or "",
                owner.email or "", owner.email_secondary or "",
                owner.owner_since or "", owner.note or "",
            ]


def _rows_votings(db: Session):
    votings = (
        db.query(Voting)
        .options(
            joinedload(Voting.items),
            joinedload(Voting.ballots).joinedload(Ballot.owner),
            joinedload(Voting.ballots).joinedload(Ballot.votes),
        )
        .order_by(Voting.created_at.desc())
        .all()
    )
    for v in votings:
        for b in v.ballots:
            owner_name = b.owner.display_name if b.owner else ""
            for bv in b.votes:
                item = bv.voting_item
                yield [
                    v.title, v.status.value,
                    _date(v.start_date), _date(v.end_date),
                    v.quorum_threshold * 100, v.total_votes_possible,
                    item.order if item else "", item.title if item else "",
                    owner_name, b.units_text or "", b.total_votes,
                    bv.vote.value if bv.vote else "",
                    bv.votes_count,
                ]


def _rows_tax(db: Session):
    sessions = (
        db.query(TaxSession)
        .options(
            joinedload(TaxSession.documents)
            .joinedload(TaxDocument.distributions)
            .joinedload(TaxDistribution.owner),
        )
        .order_by(TaxSession.created_at.desc())
        .all()
    )
    for s in sessions:
        for doc in s.documents:
            for dist in doc.distributions:
                owner_name = dist.owner.display_name if dist.owner else ""
                yield [
                    s.title, s.year or "",
                    doc.filename, doc.unit_number or "",
                    doc.extracted_owner_name or "",
                    owner_name,
                    dist.match_status.value if dist.match_status else "",
                    round(dist.match_confidence * 100, 1) if dist.match_confidence else "",
                    "Ano" if dist.email_sent else "Ne",
                    dist.admin_note or "",
                ]


def _rows_sync(db: Session):
    sessions = (
        db.query(SyncSession)
        .options(joinedload(SyncSession.records))
        .order_by(SyncSession.created_at.desc())
        .all()
    )
    for s in sessions:
        for r in s.records:
            yield [
                s.csv_filename, _fmt(s.created_at),
                r.unit_number or "",
                r.csv_owner_name or "", r.excel_owner_name or "",
                r.csv_ownership_type or "", r.excel_ownership_type or "",
                r.csv_email or "", r.csv_phone or "",
                r.csv_space_type or "", r.excel_space_type or "",
                r.csv_share, r.excel_podil_scd,
                r.status.value if r.status else "",
                r.resolution.value if r.resolution else "",
                r.admin_corrected_name or "", r.admin_note or "",
            ]


def _rows_logs(db: Session):
    for e in db.query(EmailLog).order_by(EmailLog.created_at.desc()).all():
        yield [
            "Email", _fmt(e.created_at),
            f"{e.recipient_name or ''} <{e.recipient_email}>",
            e.subject or "",
            e.status.value if e.status else "",
            e.error_message or "",
        ]
    for i in db.query(ImportLog).order_by(ImportLog.created_at.desc()).all():
        yield [
            "Import", _fmt(i.created_at),
            i.filename,
            i.import_type or "",
            f"{i.rows_imported}/{i.rows_total}",
            i.errors or "",
        ]


def _rows_administration(db: Session):
    info = db.query(SvjInfo).options(joinedload(SvjInfo.addresses)).first()
    if info:
        yield ["SVJ info", info.name or "", info.building_type or "",
               str(info.total_shares or ""), ""]
        for addr in info.addresses:
            yield ["Adresa", addr.address, "", "", ""]
    for m in db.query(BoardMember).order_by(BoardMember.group, BoardMember.order).all():
        yield [
            "Výbor" if m.group == "board" else "Kontrolní orgán",
            m.name, m.role or "", m.email or "", m.phone or "",
        ]


_ROW_GENERATORS = {
    "owners": _rows_owners,
    "votings": _rows_votings,
    "tax": _rows_tax,
    "sync": _rows_sync,
    "logs": _rows_logs,
    "administration": _rows_administration,
}


# ── Public API ──────────────────────────────────────────────────────

def export_category_xlsx(db: Session, category: str) -> bytes:
    """Return XLSX bytes for the given category."""
    info = _EXPORTS[category]
    gen = _ROW_GENERATORS[category]

    wb = Workbook()
    ws = wb.active
    ws.title = info["label"][:31]  # Excel sheet name limit
    ws.append(info["headers"])
    for cell in ws[1]:
        cell.font = cell.font.copy(bold=True)

    for row in gen(db):
        ws.append([_fmt(v) if isinstance(v, datetime) else v for v in row])

    # Auto-width
    for col in ws.columns:
        max_len = 0
        for cell in col:
            if cell.value is not None:
                max_len = max(max_len, len(str(cell.value)))
        ws.column_dimensions[col[0].column_letter].width = min(max_len + 2, 50)

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def export_category_csv(db: Session, category: str) -> bytes:
    """Return UTF-8 CSV bytes for the given category."""
    info = _EXPORTS[category]
    gen = _ROW_GENERATORS[category]

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(info["headers"])
    for row in gen(db):
        writer.writerow([_fmt(v) for v in row])

    return buf.getvalue().encode("utf-8-sig")  # BOM for Excel compatibility
