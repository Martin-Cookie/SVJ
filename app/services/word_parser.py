from __future__ import annotations

"""
Parse a Word (.docx) ballot template to extract voting items.
Looks for patterns like:
  "BOD 1: ..." or "1. ..." or "1) ..."
"""
import re

from docx import Document


def extract_voting_items(docx_path: str) -> list[dict]:
    doc = Document(docx_path)
    items = []
    current_item = None

    # Multiple patterns for numbered items
    patterns = [
        re.compile(r"^\s*BOD\s+(\d+)\s*[:.]\s*(.+)", re.IGNORECASE),
        re.compile(r"^\s*(\d+)\s*[.)]\s*(.+)"),
        re.compile(r"^\s*(\d+)\s*[:.]\s*(.+)"),
    ]

    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue

        matched = False
        for pattern in patterns:
            match = pattern.match(text)
            if match:
                if current_item:
                    items.append(current_item)
                order = int(match.group(1))
                title = match.group(2).strip()
                current_item = {
                    "order": order,
                    "title": title,
                    "description": "",
                }
                matched = True
                break

        if not matched and current_item:
            # Skip table-like content and checkbox markers
            if text.startswith(("SOUHLASÍM", "NESOUHLASÍM", "☐", "□")):
                continue
            if current_item["description"]:
                current_item["description"] += "\n"
            current_item["description"] += text

    if current_item:
        items.append(current_item)

    return items


def extract_full_text(docx_path: str) -> str:
    doc = Document(docx_path)
    texts = []
    for para in doc.paragraphs:
        if para.text.strip():
            texts.append(para.text.strip())
    return "\n".join(texts)
