from __future__ import annotations

"""
Email sending service using smtplib with attachment support.
"""
import html as html_module
import smtplib
import socket
from datetime import datetime
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import settings
from app.models.common import EmailLog, EmailStatus


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
    # Support comma-separated multiple recipients
    email_list = [e.strip() for e in to_email.split(",") if e.strip()]
    if not email_list:
        return {"success": False, "error": "Žádná emailová adresa"}

    msg = MIMEMultipart()
    msg["From"] = f"{settings.smtp_from_name} <{settings.smtp_from_email}>"
    msg["To"] = ", ".join(f"{to_name} <{e}>" for e in email_list)
    msg["Subject"] = subject

    # Plain text z formuláře (bez HTML tagů) → konverze \n na <br>
    if body_html and "<" not in body_html:
        body_html = html_module.escape(body_html).replace("\n", "<br>\n")
    msg.attach(MIMEText(body_html, "html", "utf-8"))

    attachment_names = []
    attachment_full_paths = []
    for file_path in (attachments or []):
        path = Path(file_path)
        if not path.exists():
            continue
        with open(path, "rb") as f:
            part = MIMEApplication(f.read(), _subtype=path.suffix.lstrip("."))
            part.add_header("Content-Disposition", "attachment", filename=path.name)
            msg.attach(part)
            attachment_names.append(path.name)
            attachment_full_paths.append(str(path))

    # Log the email attempt
    log = None
    if db:
        log = EmailLog(
            recipient_email=to_email,
            recipient_name=to_name,
            subject=subject,
            body_preview=body_html[:500] if body_html else None,
            status=EmailStatus.PENDING,
            module=module,
            reference_id=reference_id,
            attachment_paths=", ".join(attachment_full_paths) if attachment_full_paths else None,
        )
        db.add(log)
        db.flush()

    # Validate SMTP configuration
    if settings.smtp_host in ("smtp.example.com", ""):
        error_msg = "SMTP server není nakonfigurován. Nastavte SMTP_HOST v souboru .env"
        if log:
            log.status = EmailStatus.FAILED
            log.error_message = error_msg
            db.commit()
        return {"success": False, "error": error_msg}

    try:
        # Reuse provided connection or create a new one
        own_server = smtp_server is None
        if own_server:
            if settings.smtp_use_tls:
                server = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10)
                server.starttls()
            else:
                server = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10)

            if settings.smtp_user:
                server.login(settings.smtp_user, settings.smtp_password)
        else:
            server = smtp_server

        server.send_message(msg)

        if own_server:
            server.quit()

        if log:
            log.status = EmailStatus.SENT
            log.sent_at = datetime.utcnow()
            db.commit()

        return {"success": True, "error": None}

    except smtplib.SMTPAuthenticationError:
        error_msg = "Přihlášení k SMTP serveru selhalo. Zkontrolujte uživatelské jméno a heslo v Nastavení. Pro Gmail použijte App Password."
        if log:
            log.status = EmailStatus.FAILED
            log.error_message = error_msg
            db.commit()
        return {"success": False, "error": error_msg}

    except socket.gaierror:
        error_msg = f"SMTP server '{settings.smtp_host}' není dostupný. Zkontrolujte nastavení v souboru .env"
        if log:
            log.status = EmailStatus.FAILED
            log.error_message = error_msg
            db.commit()
        return {"success": False, "error": error_msg}

    except Exception as e:
        if log:
            log.status = EmailStatus.FAILED
            log.error_message = str(e)
            db.commit()

        return {"success": False, "error": str(e)}


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
