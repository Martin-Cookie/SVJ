from __future__ import annotations

"""
Extract owner name from tax PDF files using pdfplumber.
PDFs are text-based (not scanned).
"""
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
    return {
        "full_text": text,
        "owner_name": owner_name,
    }


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
            if value:
                return value
            # Name might be on the next line
            if i + 1 < len(lines) and lines[i + 1].strip():
                return lines[i + 1].strip()

        # Pattern: "SJ:" or "SJM:" prefix
        if re.match(r"^SJM?\s*:", stripped, re.IGNORECASE):
            parts = stripped.split(":", 1)
            if len(parts) > 1 and parts[1].strip():
                return parts[1].strip()

    return None


def parse_unit_from_filename(filename: str) -> tuple[str, str]:
    name = filename.rsplit(".", 1)[0]
    match = re.match(r"(\d+)([a-zA-Z])?$", name)
    if match:
        return match.group(1), (match.group(2) or "").upper()
    return name, ""
