from __future__ import annotations

"""
Email sending service using smtplib with attachment support.
"""
import asyncio
import html as html_module
import logging
import re
import smtplib
import socket
from email.header import Header
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr, formatdate
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import settings
from app.models.common import EmailLog, EmailStatus
from app.utils import decode_smtp_password, strip_diacritics, utcnow

logger = logging.getLogger(__name__)


_TAG_RE = re.compile(r"<[^>]+>")


def _html_to_plain(html: str | None) -> str | None:
    if not html:
        return None
    text = html.replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n")
    text = text.replace("</p>", "\n").replace("</div>", "\n").replace("</tr>", "\n")
    text = _TAG_RE.sub("", text)
    text = html_module.unescape(text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _create_smtp(host: str, port: int, use_tls: bool, timeout: int = 30) -> smtplib.SMTP | smtplib.SMTP_SSL:
    """Create SMTP connection with SSL (port 465) or STARTTLS support."""
    if port == 465:
        server = smtplib.SMTP_SSL(host, port, timeout=timeout)
    else:
        server = smtplib.SMTP(host, port, timeout=timeout)
        if use_tls:
            server.starttls()
    return server


def _imap_save_to_sent(msg, smtp_host: str, user: str, password: str, use_tls: bool) -> None:
    """Uloží odeslaný email do složky Odeslaných přes IMAP (fire-and-forget)."""
    import datetime
    import imaplib
    import email.utils

    # Odvodit IMAP host z SMTP host: smtp.x.cz → imap.x.cz
    imap_host = smtp_host.replace("smtp.", "imap.", 1)
    logger.info("IMAP: pokus o uložení do Odeslaných na %s (user=%s)", imap_host, user)
    try:
        imap = imaplib.IMAP4_SSL(imap_host, 993, timeout=10)
        imap.login(user, password)
        logger.info("IMAP: přihlášení OK na %s", imap_host)

        # Auto-detect Sent folder
        sent_folder = None
        _, folders = imap.list()
        logger.info("IMAP: nalezené složky: %s", folders)
        for f in (folders or []):
            decoded = f.decode("utf-8", errors="replace") if isinstance(f, bytes) else f
            if "\\Sent" in decoded:
                # Extrahovat název složky: '(\\HasNoChildren \\Sent) "/" "Sent"' → "Sent"
                parts = decoded.rsplit('"', 2)
                if len(parts) >= 2:
                    sent_folder = parts[-2]
                logger.info("IMAP: detekována Sent složka z flagu: %s (raw: %s)", sent_folder, decoded)
                break

        if not sent_folder:
            # Fallback — běžné názvy
            for name in ("Sent", "INBOX.Sent", "[Gmail]/Sent Mail", "Sent Items",
                          "Odeslaná pošta", "INBOX.Odeslaná pošta"):
                status, _ = imap.select(name, readonly=True)
                if status == "OK":
                    sent_folder = name
                    logger.info("IMAP: Sent složka nalezena fallbackem: %s", sent_folder)
                    break

        if sent_folder:
            msg_bytes = msg.as_bytes()
            # Bezpečný Date parsing
            try:
                date_dt = email.utils.parsedate_to_datetime(msg["Date"]) if msg["Date"] else datetime.datetime.now()
            except Exception:
                date_dt = datetime.datetime.now()
            date = imaplib.Time2Internaldate(date_dt)
            result = imap.append(sent_folder, "\\Seen", date, msg_bytes)
            logger.info("IMAP: email uložen do %s na %s — výsledek: %s", sent_folder, imap_host, result)
        else:
            logger.warning("IMAP: nenalezena složka Odeslaných na %s", imap_host)

        imap.logout()
    except Exception as e:
        logger.error("IMAP uložení do Odeslaných selhalo (%s): %s", imap_host, e, exc_info=True)


def _get_default_profile():
    """Načte výchozí SmtpProfile z DB (is_default=True) nebo None."""
    from app.database import SessionLocal
    from app.models.smtp_profile import SmtpProfile
    db = SessionLocal()
    try:
        return db.query(SmtpProfile).filter_by(is_default=True).first()
    finally:
        db.close()


def _get_profile_by_id(profile_id: int):
    """Načte SmtpProfile dle ID nebo None."""
    from app.database import SessionLocal
    from app.models.smtp_profile import SmtpProfile
    db = SessionLocal()
    try:
        return db.query(SmtpProfile).get(profile_id)
    finally:
        db.close()


def _smtp_params_from_profile(profile):
    """Extrahuje SMTP parametry z profilu. Vrací dict."""
    return {
        "host": profile.smtp_host,
        "port": profile.smtp_port,
        "user": profile.smtp_user,
        "password": decode_smtp_password(profile.smtp_password_b64) if profile.smtp_password_b64 else "",
        "from_name": profile.smtp_from_name or "",
        "from_email": profile.smtp_from_email,
        "use_tls": profile.smtp_use_tls,
        "imap_save_sent": profile.imap_save_sent or False,
    }


def _smtp_params_from_settings():
    """Extrahuje SMTP parametry z globálních settings (.env) jako fallback."""
    return {
        "host": settings.smtp_host,
        "port": settings.smtp_port,
        "user": settings.smtp_user,
        "password": settings.smtp_password,
        "from_name": settings.smtp_from_name,
        "from_email": settings.smtp_from_email,
        "use_tls": settings.smtp_use_tls,
        "imap_save_sent": False,
    }


def get_smtp_params(profile_id: int | None = None) -> dict:
    """Vrátí SMTP parametry: dle profile_id > default profil > .env fallback."""
    profile = None
    if profile_id:
        profile = _get_profile_by_id(profile_id)
    if not profile:
        profile = _get_default_profile()
    if profile:
        return _smtp_params_from_profile(profile)
    return _smtp_params_from_settings()


def create_smtp_connection(profile_id: int | None = None):
    """Create and return an authenticated SMTP connection for batch reuse.

    Používá profil dle profile_id > default profil > .env fallback.
    """
    params = get_smtp_params(profile_id)
    if params["host"] in ("smtp.example.com", ""):
        return None

    server = _create_smtp(params["host"], params["port"], params["use_tls"], timeout=30)
    if params["user"]:
        server.login(params["user"], params["password"])
    return server


def _build_message(
    to_name: str,
    to_addr: str,
    subject: str,
    body_html: str,
    attachments: list[str] | None = None,
    from_name: str | None = None,
    from_email: str | None = None,
) -> tuple[MIMEMultipart, list[str]]:
    """Build a MIME message for a single recipient. Returns (msg, attachment_paths)."""
    msg = MIMEMultipart()
    _from_name = from_name if from_name is not None else settings.smtp_from_name
    _from_email = from_email or settings.smtp_from_email
    msg["From"] = formataddr((str(Header(_from_name, "utf-8")), _from_email))
    msg["To"] = formataddr((str(Header(to_name, "utf-8")), to_addr))
    msg["Subject"] = Header(subject, "utf-8")
    msg["Date"] = formatdate(localtime=True)

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


def _create_error_log(db: Session, to_email: str, to_name: str, subject: str,
                     body_html: str, module: str, reference_id: int | None,
                     error_msg: str) -> None:
    """Vytvořit EmailLog záznam pro chybový stav."""
    log = EmailLog(
        recipient_email=to_email,
        recipient_name=to_name,
        name_normalized=strip_diacritics(to_name or ""),
        subject=subject,
        body_preview=(_html_to_plain(body_html) or "")[:500] if body_html else None,
        status=EmailStatus.FAILED,
        module=module,
        reference_id=reference_id,
        error_message=error_msg,
    )
    db.add(log)
    db.commit()


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
    smtp_profile_id: int | None = None,
) -> dict:
    # Support comma-separated multiple recipients — send separate email to each
    email_list = [e.strip() for e in to_email.split(",") if e.strip()]
    if not email_list:
        return {"success": False, "error": "Žádná emailová adresa"}

    # Resolve SMTP params (profile > default > .env)
    params = get_smtp_params(smtp_profile_id)

    # Validate SMTP configuration
    if params["host"] in ("smtp.example.com", ""):
        error_msg = "SMTP server není nakonfigurován. Nastavte SMTP profil v Nastavení."
        if db:
            _create_error_log(db, to_email, to_name, subject, body_html, module, reference_id, error_msg)
        return {"success": False, "error": error_msg}

    # Create own SMTP connection if not provided
    own_server = smtp_server is None
    server = smtp_server
    if own_server:
        try:
            server = _create_smtp(params["host"], params["port"], params["use_tls"], timeout=10)
            if params["user"]:
                server.login(params["user"], params["password"])
        except smtplib.SMTPAuthenticationError:
            error_msg = "Přihlášení k SMTP serveru selhalo. Zkontrolujte uživatelské jméno a heslo v Nastavení. Pro Gmail použijte App Password."
            if db:
                _create_error_log(db, to_email, to_name, subject, body_html, module, reference_id, error_msg)
            return {"success": False, "error": error_msg}
        except socket.gaierror:
            error_msg = f"SMTP server '{params['host']}' není dostupný. Zkontrolujte nastavení SMTP profilu."
            if db:
                _create_error_log(db, to_email, to_name, subject, body_html, module, reference_id, error_msg)
            return {"success": False, "error": error_msg}
        except Exception as e:
            if db:
                _create_error_log(db, to_email, to_name, subject, body_html, module, reference_id, str(e))
            return {"success": False, "error": str(e)}

    # Send separate email to each address
    errors = []
    for addr in email_list:
        msg, attachment_paths = _build_message(
            to_name, addr, subject, body_html, attachments,
            from_name=params["from_name"], from_email=params["from_email"],
        )

        log = None
        if db:
            log = EmailLog(
                recipient_email=addr,
                recipient_name=to_name, name_normalized=strip_diacritics(to_name or ""),
                subject=subject,
                body_preview=(_html_to_plain(body_html) or "")[:500] if body_html else None,
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
                log.sent_at = utcnow()
            # Uložit kopii do IMAP Odeslaných (fire-and-forget)
            if params.get("imap_save_sent") and params.get("user"):
                try:
                    _imap_save_to_sent(msg, params["host"], params["user"], params["password"], params["use_tls"])
                except Exception:
                    pass  # Nikdy neblokovat odesílání
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


async def async_send_email(
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
    """Async wrapper pro send_email — neblokuje request thread."""
    return await asyncio.to_thread(
        send_email, to_email, to_name, subject, body_html,
        attachments, module, reference_id, db, smtp_server,
    )


async def async_send_to_owner_emails(
    owner_email: str,
    owner_name: str,
    subject: str,
    body_html: str,
    attachments: list[str] | None = None,
    module: str = "",
    reference_id: int | None = None,
    db: Session | None = None,
) -> list[dict]:
    """Async wrapper pro send_to_owner_emails — neblokuje request thread."""
    return await asyncio.to_thread(
        send_to_owner_emails, owner_email, owner_name, subject, body_html,
        attachments, module, reference_id, db,
    )
