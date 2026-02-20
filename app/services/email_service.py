from __future__ import annotations

"""
Email sending service using smtplib with attachment support.
"""
import smtplib
from datetime import datetime
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import settings
from app.models.common import EmailLog, EmailStatus


def send_email(
    to_email: str,
    to_name: str,
    subject: str,
    body_html: str,
    attachments: list[str] | None = None,
    module: str = "",
    reference_id: int | None = None,
    db: Session | None = None,
) -> dict:
    msg = MIMEMultipart()
    msg["From"] = f"{settings.smtp_from_name} <{settings.smtp_from_email}>"
    msg["To"] = f"{to_name} <{to_email}>"
    msg["Subject"] = subject

    msg.attach(MIMEText(body_html, "html", "utf-8"))

    attachment_names = []
    for file_path in (attachments or []):
        path = Path(file_path)
        if not path.exists():
            continue
        with open(path, "rb") as f:
            part = MIMEApplication(f.read(), _subtype=path.suffix.lstrip("."))
            part.add_header("Content-Disposition", "attachment", filename=path.name)
            msg.attach(part)
            attachment_names.append(path.name)

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
            attachment_paths=", ".join(attachment_names) if attachment_names else None,
        )
        db.add(log)
        db.flush()

    try:
        if settings.smtp_use_tls:
            server = smtplib.SMTP(settings.smtp_host, settings.smtp_port)
            server.starttls()
        else:
            server = smtplib.SMTP(settings.smtp_host, settings.smtp_port)

        if settings.smtp_user:
            server.login(settings.smtp_user, settings.smtp_password)

        server.send_message(msg)
        server.quit()

        if log:
            log.status = EmailStatus.SENT
            log.sent_at = datetime.utcnow()
            db.commit()

        return {"success": True, "error": None}

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
