from __future__ import annotations

"""
Generate personalized PDF ballots from a Word template.
Uses docxtpl to fill in owner data, then converts to PDF via LibreOffice.
"""
import subprocess
from pathlib import Path

from docxtpl import DocxTemplate

from app.config import settings


def generate_ballot_pdf(
    template_path: str,
    owner_data: dict,
    output_dir: str,
) -> str:
    """
    Generate a single PDF ballot for an owner.
    owner_data keys:
        owner_name, units_text, total_votes, items, proxy_name, date, voting_title
    Returns path to generated PDF.
    """
    doc = DocxTemplate(template_path)
    doc.render(owner_data)

    # Safe filename
    safe_name = (
        owner_data["owner_name"]
        .replace(" ", "_")
        .replace(".", "")
        .replace(",", "")
        .replace("/", "-")
    )
    docx_output = Path(output_dir) / f"listek_{safe_name}.docx"
    doc.save(str(docx_output))

    # Convert to PDF via LibreOffice
    pdf_path = convert_docx_to_pdf(str(docx_output), output_dir)

    # Clean up intermediate DOCX
    docx_output.unlink(missing_ok=True)

    return pdf_path


def convert_docx_to_pdf(docx_path: str, output_dir: str) -> str:
    cmd = [
        settings.libreoffice_path,
        "--headless",
        "--convert-to", "pdf",
        "--outdir", output_dir,
        docx_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        raise RuntimeError(f"LibreOffice conversion failed: {result.stderr}")

    pdf_name = Path(docx_path).stem + ".pdf"
    expected = Path(output_dir) / pdf_name
    if not expected.exists():
        raise FileNotFoundError(f"Expected PDF not found: {expected}")

    return str(expected)
