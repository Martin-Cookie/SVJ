from __future__ import annotations

"""
Extract owner name from tax PDF files using pdfplumber.
PDFs are text-based (not scanned).
"""
import os
import re

import pdfplumber


def extract_text_from_pdf(pdf_path: str) -> str:
    full_text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                full_text += text + "\n"
    return full_text


def extract_owner_from_tax_pdf(pdf_path: str) -> dict:
    text = extract_text_from_pdf(pdf_path)
    owner_name = parse_owner_name(text)
    owner_names = parse_owner_names_from_details(text)
    return {
        "full_text": text,
        "owner_name": owner_name,
        "owner_names": owner_names,
    }


_COMPANY_SUFFIXES = re.compile(
    r"(?:s\.r\.o\.|a\.s\.|z\.s\.|z\.ú\.|o\.s\.|k\.s\.|v\.o\.s\.|o\.p\.s\.|"
    r"spol\.\s*s\s*r\.?\s*o\.?|SE|s\.p\.)$",
    re.IGNORECASE,
)


def _is_company_suffix(name: str) -> bool:
    """Return True if the text looks like a short continuation fragment of a company name.

    A fragment is e.g. "GROUP s.r.o." (1 word + suffix) or just "s.r.o.".
    A full standalone company name like "NOTABENE ART s.r.o." (2+ words + suffix) is NOT a fragment.
    """
    stripped = name.strip()
    if _COMPANY_SUFFIXES.search(stripped):
        # If 2+ substantive words before the suffix, it's a standalone company name
        before_suffix = _COMPANY_SUFFIXES.sub("", stripped).strip()
        if len(before_suffix.split()) >= 2:
            return False
        return True
    # Single all-uppercase word (e.g. "GROUP") — likely a fragment
    words = stripped.split()
    if len(words) == 1 and words[0].isupper():
        return True
    return False


def _extract_name_from_sp_line(line: str) -> str | None:
    """Extract owner name appended after SP fraction(s).

    Handles both abbreviated 'SP 2 3108/907635 Kočí Martin' and
    full form 'Spoluvlastnický podíl 4: 12212 / 1903227 Gavrilovičová Kateřina'.
    Also handles multiple comma-separated fractions.
    """
    stripped = line.strip()
    # Pattern 1: "SP label fraction(s) Name"
    m = re.match(r"SP\s+\S+\s+\d+/\d+(?:,\s*\d+/\d+)*\s*(.*)", stripped)
    if not m:
        # Pattern 2: "Spoluvlastnický podíl N: fraction Name"
        m = re.match(
            r"[Ss]poluvlastnick[ýy]\s+pod[ií]l\s+\S+:?\s+\d+\s*/\s*\d+(?:,\s*\d+\s*/\s*\d+)*\s*(.*)",
            stripped,
        )
    if m:
        name = m.group(1).strip()
        # Filter out non-name text (must start with uppercase letter)
        if name and re.match(r"[A-ZÁČĎÉĚÍŇÓŘŠŤÚŮÝŽ0-9]", name):
            return name
    return None


def _merge_company_fragments(names: list[str]) -> list[str]:
    """Merge name fragments that belong to a single company name.

    Long company names get split across SP lines in the PDF, e.g.:
        SP 2 ... 35 ASSOCIATES INVESTMENT
        SP 3 ... GROUP s.r.o.
    should be merged into '35 ASSOCIATES INVESTMENT GROUP s.r.o.'
    """
    if not names:
        return names
    merged = [names[0]]
    for name in names[1:]:
        if _is_company_suffix(name):
            merged[-1] = merged[-1] + " " + name
        else:
            merged.append(name)
    return merged


def parse_owner_names_from_details(text: str) -> list[str]:
    """Extract individual owner names from 'Údaje o vlastníkovi:' section.

    In tax PDFs, the owner detail block appears on page 1 with names on the
    right side of SP (spoluvlastnický podíl) lines:
        SP 1 5615/4103391 Údaje o vlastníkovi:
        SP 2 3108/907635  Kočí Martin
        SP 2S 0/0
        SP 3 0/0          Kočová Jana
    """
    lines = text.split("\n")
    names = []
    in_details = False

    for line in lines:
        stripped = line.strip()

        # Detect start of owner details block
        if re.search(r"[úu]daje o vlastn[ií]k", stripped, re.IGNORECASE):
            in_details = True
            # Check if a name is on the same line after the section header
            # e.g. "Údaje o vlastníkovi: Kočí Martin"
            m = re.search(r"[úu]daje o vlastn[ií]k[^:]*:\s*(.+)", stripped, re.IGNORECASE)
            if m:
                val = m.group(1).strip()
                if val and re.match(r"[A-ZÁČĎÉĚÍŇÓŘŠŤÚŮÝŽ0-9]", val):
                    names.append(val)
            continue

        if in_details:
            # Stop at known section boundaries
            if re.match(
                r"(Vlastn[ií]k:|Vyúčtov|Případné|Stavy|Typ vlastnictv|Služba|Celkem|Celkov|Výnos|Tento"
                r"|Předpis|Bankovní|CELKEM|Důležité|Číslo popisné|Číslo prostoru|Adresa:|Vchod)",
                stripped, re.IGNORECASE,
            ):
                break
            # Try to extract name from SP line
            name = _extract_name_from_sp_line(stripped)
            if name:
                names.append(name)
            # Standalone name line (not an SP line) — e.g. "SJM Kočovi" between SP rows
            # or name starting with digit (e.g. "35 ASSOCIATES INVESTMENT GROUP")
            # or company suffix fragment (e.g. "s.r.o.", "a.s.")
            elif not re.match(r"^(?:SP\s|[Ss]poluvlastnick)", stripped) and stripped:
                if re.match(r"(?:SJM?\s|[A-ZÁČĎÉĚÍŇÓŘŠŤÚŮÝŽ][a-záčďéěíňóřšťúůýž])", stripped):
                    names.append(stripped)
                elif re.match(r"\d+\s+[A-ZÁČĎÉĚÍŇÓŘŠŤÚŮÝŽ]", stripped):
                    names.append(stripped)
                elif _COMPANY_SUFFIXES.search(stripped):
                    names.append(stripped)

    return _merge_company_fragments(names)


def parse_owner_name(text: str) -> str | None:
    lines = text.split("\n")
    for i, line in enumerate(lines):
        stripped = line.strip()
        # Pattern: "Vlastník:" or "Jméno:" or "Údaje o vlastníkovi"
        match = re.match(
            r"(?:vlastn[ií]k|jm[eé]no|majitel|[úu]daje o vlastn[ií]k)"
            r"[^:]*:\s*(.*)",
            stripped, re.IGNORECASE,
        )
        if match:
            value = match.group(1).strip()
            value_from_next = False
            if not value:
                # Name might be on the next line
                if i + 1 < len(lines) and lines[i + 1].strip():
                    value = lines[i + 1].strip()
                    value_from_next = True
            if value:
                # Append continuation lines for company names (e.g. "GROUP s.r.o.")
                j = (i + 2) if value_from_next else (i + 1)
                while j < len(lines):
                    next_line = lines[j].strip()
                    if next_line and _is_company_suffix(next_line):
                        value = value + " " + next_line
                        j += 1
                    else:
                        break
                return value

        # Pattern: "SJ:" or "SJM:" prefix
        if re.match(r"^SJM?\s*:", stripped, re.IGNORECASE):
            parts = stripped.split(":", 1)
            if len(parts) > 1 and parts[1].strip():
                return parts[1].strip()

    return None


def parse_unit_from_filename(filename: str) -> tuple[str, str]:
    # Use basename only (webkitdirectory may send paths like "dir/9A.pdf")
    name = os.path.basename(filename).rsplit(".", 1)[0]
    match = re.match(r"(\d+)([a-zA-Z])?$", name)
    if match:
        return match.group(1), (match.group(2) or "").upper()
    return name, ""
