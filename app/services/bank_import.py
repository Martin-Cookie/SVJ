"""Služba pro import bankovních výpisů z Fio CSV.

Formát Fio CSV:
- Řádky 1-8: metadata (účet, období, zůstatky, součty)
- Řádek 9: prázdný
- Řádek 10: hlavičky sloupců (19 sloupců, semicolon, quoted)
- Řádky 11+: transakce
- Kódování: UTF-8 s BOM
- Oddělovač: středník
"""

from __future__ import annotations

import csv
import io
import re
import logging
from datetime import date, datetime
from typing import Optional

logger = logging.getLogger(__name__)


# Fio CSV hlavičky (fixní pořadí)
FIO_COLUMNS = [
    "ID operace", "Datum", "Objem", "Měna", "Protiúčet",
    "Název protiúčtu", "Kód banky", "Název banky", "KS", "VS", "SS",
    "Poznámka", "Zpráva pro příjemce", "Typ", "Provedl", "Upřesnění",
    "Poznámka", "BIC", "ID pokynu",
]


def _parse_date(text: str) -> Optional[date]:
    """Parsuj datum z formátu DD.MM.YYYY."""
    try:
        return datetime.strptime(text.strip(), "%d.%m.%Y").date()
    except (ValueError, AttributeError):
        return None


def _parse_amount(text: str) -> float:
    """Parsuj částku (Fio formát: celé číslo nebo desetinné s čárkou)."""
    cleaned = text.strip().replace("\xa0", "").replace(" ", "").replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def _extract_metadata(lines: list[str]) -> dict:
    """Extrahuj metadata z prvních 8 řádků CSV."""
    metadata = {
        "bank_account": None,
        "period_from": None,
        "period_to": None,
        "opening_balance": None,
        "closing_balance": None,
        "total_income": None,
        "total_expense": None,
    }

    for line in lines[:9]:
        line = line.strip().strip('"')

        # Účet: "Výpis č. 1/2026 z účtu ""2900708337/2010"""
        m = re.search(r'z účtu\s*""?(\d+/\d+)', line)
        if m:
            metadata["bank_account"] = m.group(1)

        # Období: "Období: 01.01.2026 - 31.01.2026"
        m = re.search(r"Období:\s*(\d{2}\.\d{2}\.\d{4})\s*-\s*(\d{2}\.\d{2}\.\d{4})", line)
        if m:
            metadata["period_from"] = _parse_date(m.group(1))
            metadata["period_to"] = _parse_date(m.group(2))

        # Počáteční stav: "Počáteční stav účtu k 01.01.2026: 847255,31 CZK"
        m = re.search(r"Počáteční stav.*?:\s*([\d.,\s-]+)\s*CZK", line)
        if m:
            metadata["opening_balance"] = _parse_amount(m.group(1))

        # Koncový stav: "Koncový stav účtu k 31.01.2026: 259763,61 CZK"
        m = re.search(r"Koncový stav.*?:\s*([\d.,\s-]+)\s*CZK", line)
        if m:
            metadata["closing_balance"] = _parse_amount(m.group(1))

        # Příjmy: "Suma příjmů: +919732,3 CZK"
        m = re.search(r"Suma příjmů:\s*\+?([\d.,\s-]+)\s*CZK", line)
        if m:
            metadata["total_income"] = _parse_amount(m.group(1))

        # Výdaje: "Suma výdajů: -1507224 CZK"
        m = re.search(r"Suma výdajů:\s*([\d.,\s-]+)\s*CZK", line)
        if m:
            metadata["total_expense"] = abs(_parse_amount(m.group(1)))

    return metadata


def parse_fio_csv(file_content: bytes, filename: str) -> dict:
    """Parsuj Fio CSV bankovní výpis.

    Returns:
        dict s klíči:
        - metadata: dict (bank_account, period_from, period_to, ...)
        - transactions: list of dict (operation_id, date, amount, ...)
        - errors: list of str (chyby parsování)
    """
    # Dekóduj UTF-8 s BOM
    text = file_content.decode("utf-8-sig")
    lines = text.splitlines()

    if len(lines) < 11:
        return {
            "metadata": {},
            "transactions": [],
            "errors": ["Soubor je příliš krátký — neobsahuje transakce."],
        }

    # Metadata z řádků 1-8
    metadata = _extract_metadata(lines[:9])

    # Najdi řádek s hlavičkami (hledej "ID operace")
    header_idx = None
    for i, line in enumerate(lines):
        if '"ID operace"' in line or "ID operace" in line:
            header_idx = i
            break

    if header_idx is None:
        return {
            "metadata": metadata,
            "transactions": [],
            "errors": ["Nenalezeny hlavičky sloupců (ID operace)."],
        }

    # Parsuj transakce pomocí csv.reader
    csv_text = "\n".join(lines[header_idx:])
    reader = csv.reader(io.StringIO(csv_text), delimiter=";", quotechar='"')

    headers = next(reader, None)
    if not headers:
        return {
            "metadata": metadata,
            "transactions": [],
            "errors": ["Prázdné hlavičky."],
        }

    # Mapování sloupců (Fio má 2× "Poznámka" — index 11 a 16)
    col_map = {}
    for i, h in enumerate(headers):
        h_clean = h.strip()
        if h_clean == "Poznámka" and "poznamka1" in col_map:
            col_map["poznamka2"] = i
        elif h_clean == "Poznámka":
            col_map["poznamka1"] = i
        else:
            col_map[h_clean] = i

    transactions = []
    errors = []

    for row_num, row in enumerate(reader, start=header_idx + 2):
        if not row or all(not cell.strip() for cell in row):
            continue

        try:
            def _get(key, default=""):
                idx = col_map.get(key)
                if idx is not None and idx < len(row):
                    return row[idx].strip()
                return default

            operation_id = _get("ID operace")
            if not operation_id:
                continue

            amount_raw = _parse_amount(_get("Objem", "0"))
            direction = "income" if amount_raw >= 0 else "expense"

            vs = _get("VS")
            # Vyčisti VS (odstraň nuly, prázdné)
            if vs and vs != "0":
                vs = vs.lstrip("0") or vs  # Ponech alespoň originál
                vs = _get("VS")  # Použij originální hodnotu
            else:
                vs = None

            transactions.append({
                "operation_id": operation_id,
                "date": _parse_date(_get("Datum")),
                "amount": abs(amount_raw),
                "direction": direction,
                "counter_account": _get("Protiúčet") or None,
                "counter_account_name": _get("Název protiúčtu") or None,
                "bank_code": _get("Kód banky") or None,
                "bank_name": _get("Název banky") or None,
                "ks": _get("KS") or None,
                "vs": vs,
                "ss": _get("SS") if _get("SS") and _get("SS") != "0" else None,
                "note": _get("poznamka1") or None,
                "message": _get("Zpráva pro příjemce") or None,
                "payment_type": _get("Typ") or None,
            })

        except Exception as e:
            errors.append(f"Řádek {row_num}: {e}")

    logger.info(
        "Parsed Fio CSV '%s': %d transactions, %d errors, period %s–%s",
        filename, len(transactions), len(errors),
        metadata.get("period_from"), metadata.get("period_to"),
    )

    return {
        "metadata": metadata,
        "transactions": transactions,
        "errors": errors,
    }
