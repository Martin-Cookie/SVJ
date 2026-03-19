from __future__ import annotations

"""
Email sending service using smtplib with attachment support.
"""
import html as html_module
import logging
import smtplib
import socket

logger = logging.getLogger(__name__)
from datetime import datetime
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import settings
from app.models.common import EmailLog, EmailStatus
from app.utils import strip_diacritics


def create_smtp_connection():
    """Create and return an authenticated SMTP connection for batch reuse."""
    if settings.smtp_host in ("smtp.example.com", ""):
        return None

    server = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30)
    if settings.smtp_use_tls:
        server.starttls()
    if settings.smtp_user:
        server.login(settings.smtp_user, settings.smtp_password)
    return server


def _build_message(
    to_name: str,
    to_addr: str,
    subject: str,
    body_html: str,
    attachments: list[str] | None = None,
) -> tuple[MIMEMultipart, list[str]]:
    """Build a MIME message for a single recipient. Returns (msg, attachment_paths)."""
    msg = MIMEMultipart()
    msg["From"] = f"{settings.smtp_from_name} <{settings.smtp_from_email}>"
    msg["To"] = f"{to_name} <{to_addr}>"
    msg["Subject"] = subject

    # Plain text z formuláře (bez HTML tagů) → konverze \n na <br>
    html = body_html
    if html and "<" not in html:
        html = html_module.escape(html).replace("\n", "<br>\n")
    msg.attach(MIMEText(html, "html", "utf-8"))

    attachment_full_paths = []
    for file_path in (attachments or []):
        path = Path(file_path)
        try:
            with open(path, "rb") as f:
                part = MIMEApplication(f.read(), _subtype=path.suffix.lstrip("."))
                part.add_header("Content-Disposition", "attachment", filename=path.name)
                msg.attach(part)
                attachment_full_paths.append(str(path))
        except (IOError, OSError) as e:
            logger.warning("Příloha %s nelze přečíst: %s", path, e)

    return msg, attachment_full_paths


def send_email(
    to_email: str,
    to_name: str,
    subject: str,
    body_html: str,
    attachments: list[str] | None = None,
    module: str = "",
    reference_id: int | None = None,
    db: Session | None = None,
    smtp_server: smtplib.SMTP | None = None,
) -> dict:
    # Support comma-separated multiple recipients — send separate email to each
    email_list = [e.strip() for e in to_email.split(",") if e.strip()]
    if not email_list:
        return {"success": False, "error": "Žádná emailová adresa"}

    # Validate SMTP configuration
    if settings.smtp_host in ("smtp.example.com", ""):
        error_msg = "SMTP server není nakonfigurován. Nastavte SMTP_HOST v souboru .env"
        if db:
            log = EmailLog(
                recipient_email=to_email,
                recipient_name=to_name, name_normalized=strip_diacritics(to_name or ""),
                subject=subject,
                body_preview=body_html[:500] if body_html else None,
                status=EmailStatus.FAILED,
                module=module,
                reference_id=reference_id,
                error_message=error_msg,
            )
            db.add(log)
            db.commit()
        return {"success": False, "error": error_msg}

    # Create own SMTP connection if not provided
    own_server = smtp_server is None
    server = smtp_server
    if own_server:
        try:
            server = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10)
            if settings.smtp_use_tls:
                server.starttls()
            if settings.smtp_user:
                server.login(settings.smtp_user, settings.smtp_password)
        except smtplib.SMTPAuthenticationError:
            error_msg = "Přihlášení k SMTP serveru selhalo. Zkontrolujte uživatelské jméno a heslo v Nastavení. Pro Gmail použijte App Password."
            if db:
                log = EmailLog(
                    recipient_email=to_email, recipient_name=to_name, name_normalized=strip_diacritics(to_name or ""), subject=subject,
                    body_preview=body_html[:500] if body_html else None,
                    status=EmailStatus.FAILED, module=module, reference_id=reference_id,
                    error_message=error_msg,
                )
                db.add(log)
                db.commit()
            return {"success": False, "error": error_msg}
        except socket.gaierror:
            error_msg = f"SMTP server '{settings.smtp_host}' není dostupný. Zkontrolujte nastavení v souboru .env"
            if db:
                log = EmailLog(
                    recipient_email=to_email, recipient_name=to_name, name_normalized=strip_diacritics(to_name or ""), subject=subject,
                    body_preview=body_html[:500] if body_html else None,
                    status=EmailStatus.FAILED, module=module, reference_id=reference_id,
                    error_message=error_msg,
                )
                db.add(log)
                db.commit()
            return {"success": False, "error": error_msg}
        except Exception as e:
            if db:
                log = EmailLog(
                    recipient_email=to_email, recipient_name=to_name, name_normalized=strip_diacritics(to_name or ""), subject=subject,
                    body_preview=body_html[:500] if body_html else None,
                    status=EmailStatus.FAILED, module=module, reference_id=reference_id,
                    error_message=str(e),
                )
                db.add(log)
                db.commit()
            return {"success": False, "error": str(e)}

    # Send separate email to each address
    errors = []
    for addr in email_list:
        msg, attachment_paths = _build_message(to_name, addr, subject, body_html, attachments)

        log = None
        if db:
            log = EmailLog(
                recipient_email=addr,
                recipient_name=to_name, name_normalized=strip_diacritics(to_name or ""),
                subject=subject,
                body_preview=body_html[:500] if body_html else None,
                status=EmailStatus.PENDING,
                module=module,
                reference_id=reference_id,
                attachment_paths=", ".join(attachment_paths) if attachment_paths else None,
            )
            db.add(log)
            db.flush()

        try:
            server.send_message(msg)
            if log:
                log.status = EmailStatus.SENT
                log.sent_at = datetime.utcnow()
        except Exception as e:
            errors.append(f"{addr}: {e}")
            if log:
                log.status = EmailStatus.FAILED
                log.error_message = str(e)

    if db:
        db.commit()

    if own_server and server:
        try:
            server.quit()
        except Exception:
            logger.debug("SMTP quit failed during cleanup", exc_info=True)

    if errors:
        return {"success": False, "error": "; ".join(errors)}
    return {"success": True, "error": None}


def send_to_owner_emails(
    owner_email: str,
    owner_name: str,
    subject: str,
    body_html: str,
    attachments: list[str] | None = None,
    module: str = "",
    reference_id: int | None = None,
    db: Session | None = None,
) -> list[dict]:
    """Send to all emails of an owner (SJM may have multiple, separated by ;)."""
    results = []
    emails = [e.strip() for e in owner_email.split(";") if e.strip()]

    for email in emails:
        result = send_email(
            to_email=email,
            to_name=owner_name,
            subject=subject,
            body_html=body_html,
            attachments=attachments,
            module=module,
            reference_id=reference_id,
            db=db,
        )
        results.append(result)

    return results
