from __future__ import annotations

"""
IMAP bounce-check service.

Připojuje se ke schránce přes IMAP, hledá DSN (Delivery Status Notification)
zprávy, parsuje je dle RFC 3464 a ukládá do tabulky email_bounces.
Spárované adresy se mohou propsat do Owner.email_invalid pro vyloučení
z budoucích rozesílek.
"""

import email
import imaplib
import logging
import re
from datetime import datetime, timedelta
from email.message import Message
from email.utils import parsedate_to_datetime
from typing import Iterable

from sqlalchemy.orm import Session

from app.config import settings
from app.models import BounceType, EmailBounce, EmailLog, EmailStatus, Owner
from app.utils import utcnow

logger = logging.getLogger(__name__)


# Předměty bounce zpráv (case-insensitive)
_BOUNCE_SUBJECT_PATTERNS = [
    "delivery status notification",
    "undelivered mail returned to sender",
    "undeliverable",
    "mail delivery failed",
    "mail delivery failure",
    "returned mail",
    "failure notice",
    "delivery failure",
]

_HARD_STATUS_RE = re.compile(r"\b5\.\d+\.\d+\b")
_SOFT_STATUS_RE = re.compile(r"\b4\.\d+\.\d+\b")
_FINAL_RECIPIENT_RE = re.compile(r"final-recipient:\s*[^;]+;\s*([^\s\r\n]+)", re.IGNORECASE)
_ORIGINAL_RECIPIENT_RE = re.compile(r"original-recipient:\s*[^;]+;\s*([^\s\r\n]+)", re.IGNORECASE)
_X_FAILED_RE = re.compile(r"x-failed-recipients:\s*([^\s\r\n]+)", re.IGNORECASE)
_FOR_RE = re.compile(r"\bfor\s+<([^<>\s]+@[^<>\s]+)>", re.IGNORECASE)
_TO_HEADER_RE = re.compile(r"^to:\s*.*?<?([^<>\s,]+@[^<>\s,]+)>?", re.IGNORECASE | re.MULTILINE)
_DIAGNOSTIC_RE = re.compile(r"diagnostic-code:\s*[^;]+;\s*(.+?)(?:\r?\n[^\s]|\Z)", re.IGNORECASE | re.DOTALL)
_SMTP_CODE_RE = re.compile(r"\b(5\d{2}|4\d{2})\s")


def _derive_imap_host(smtp_host: str) -> str:
    """smtp.gmail.com → imap.gmail.com, smtp.seznam.cz → imap.seznam.cz."""
    if smtp_host.startswith("smtp."):
        return "imap." + smtp_host[5:]
    return smtp_host


def get_imap_accounts(db: Session) -> list[dict]:
    """Vrátí seznam IMAP účtů ke kontrole (profily z DB + fallback .env).

    Každý dict: {name, host, port, user, password}.
    """
    from app.models import SmtpProfile
    from app.utils import decode_smtp_password

    accounts: list[dict] = []
    seen_users: set[str] = set()

    # 1. SMTP profily z DB
    profiles = db.query(SmtpProfile).order_by(SmtpProfile.id).all()
    for p in profiles:
        host = p.imap_host or _derive_imap_host(p.smtp_host)
        user = p.smtp_user
        try:
            password = decode_smtp_password(p.smtp_password_b64)
        except Exception:
            continue
        if not user or not password or not host:
            continue
        key = f"{user}@{host}".lower()
        if key in seen_users:
            continue
        seen_users.add(key)
        accounts.append({
            "name": p.name,
            "host": host,
            "port": 993,
            "user": user,
            "password": password,
        })

    # 2. Fallback: .env IMAP/SMTP (pokud ještě není v seznamu)
    env_host = settings.imap_host
    env_user = settings.imap_user or settings.smtp_user
    env_password = settings.imap_password or settings.smtp_password
    if env_host and env_user and env_password and env_host not in ("imap.example.com", ""):
        key = f"{env_user}@{env_host}".lower()
        if key not in seen_users:
            accounts.append({
                "name": f".env ({env_user})",
                "host": env_host,
                "port": settings.imap_port,
                "user": env_user,
                "password": env_password,
            })

    return accounts


def connect_imap(host: str = "", port: int = 993,
                 user: str = "", password: str = "") -> imaplib.IMAP4_SSL:
    """Otevře IMAP spojení s danými credentials."""
    conn = imaplib.IMAP4_SSL(host, port)
    conn.login(user, password)
    return conn


def _is_bounce_subject(subject: str | None) -> bool:
    if not subject:
        return False
    s = subject.lower()
    return any(p in s for p in _BOUNCE_SUBJECT_PATTERNS)


def _decode_header(value: str | None) -> str:
    if not value:
        return ""
    parts = email.header.decode_header(value)
    out = []
    for text, charset in parts:
        if isinstance(text, bytes):
            try:
                out.append(text.decode(charset or "utf-8", errors="replace"))
            except (LookupError, UnicodeDecodeError):
                out.append(text.decode("utf-8", errors="replace"))
        else:
            out.append(text)
    return "".join(out)


def _walk_text_parts(msg: Message) -> Iterable[str]:
    """Yield všechny text/* a message/delivery-status části jako string."""
    for part in msg.walk():
        ctype = part.get_content_type()
        if ctype in ("text/plain", "text/rfc822-headers", "message/delivery-status"):
            try:
                payload = part.get_payload(decode=True)
                if payload is None:
                    continue
                charset = part.get_content_charset() or "utf-8"
                yield payload.decode(charset, errors="replace")
            except Exception:
                continue


def _parse_bounce(msg: Message) -> dict:
    """Z bounce emailu vytáhne adresu, důvod, diagnostic code, typ.

    Vrací dict: {recipient, bounce_type, reason, diagnostic_code, original_subject, bounced_at}
    """
    recipient = None
    diagnostic = None
    bounce_type = BounceType.UNKNOWN
    reason_lines: list[str] = []

    text_chunks = list(_walk_text_parts(msg))
    full_text = "\n".join(text_chunks)

    # 1. Final-Recipient z DSN (RFC 3464)
    m = _FINAL_RECIPIENT_RE.search(full_text)
    if m:
        recipient = m.group(1).strip().strip("<>")
    if not recipient:
        m = _ORIGINAL_RECIPIENT_RE.search(full_text)
        if m:
            recipient = m.group(1).strip().strip("<>")
    if not recipient:
        m = _X_FAILED_RE.search(full_text)
        if m:
            recipient = m.group(1).strip().strip("<>")

    # 2. Diagnostic-Code
    m = _DIAGNOSTIC_RE.search(full_text)
    if m:
        diagnostic = " ".join(m.group(1).split())[:500]

    # 3. Status code 5.x.x → hard, 4.x.x → soft
    if _HARD_STATUS_RE.search(full_text):
        bounce_type = BounceType.HARD
    elif _SOFT_STATUS_RE.search(full_text):
        bounce_type = BounceType.SOFT
    elif diagnostic:
        smtp_match = _SMTP_CODE_RE.search(diagnostic)
        if smtp_match:
            bounce_type = BounceType.HARD if smtp_match.group(1).startswith("5") else BounceType.SOFT

    # 4. Fallback: "for <email>" (Postfix vzor)
    if not recipient:
        m = _FOR_RE.search(full_text)
        if m:
            recipient = m.group(1).strip()
    # 5. Fallback: To: hlavička z embedded message/rfc822
    if not recipient:
        m = _TO_HEADER_RE.search(full_text)
        if m:
            recipient = m.group(1).strip()

    # Vyloučit naši vlastní adresu (return-path / from)
    own_addresses = {
        (settings.smtp_user or "").lower(),
        (settings.smtp_from_email or "").lower(),
        (settings.imap_user or "").lower(),
    }
    if recipient and recipient.lower() in own_addresses:
        recipient = None

    # 6. Reason — vezmi prvních pár neprázdných řádků s "550", "user", "mailbox", "rejected"
    keywords = ("550", "551", "552", "553", "554", "user", "mailbox", "rejected", "unknown", "blocked", "quota")
    for line in full_text.splitlines():
        s = line.strip()
        if not s or len(s) > 300:
            continue
        if any(k in s.lower() for k in keywords):
            reason_lines.append(s)
            if len(reason_lines) >= 3:
                break

    reason = "\n".join(reason_lines) if reason_lines else (diagnostic or None)

    # 6. Original Subject — pokus z message/rfc822 části
    original_subject = None
    for part in msg.walk():
        if part.get_content_type() == "message/rfc822":
            inner = part.get_payload()
            if isinstance(inner, list) and inner:
                original_subject = _decode_header(inner[0].get("Subject"))
                break
    if not original_subject:
        # fallback: hledej Subject: v textu
        for line in full_text.splitlines():
            if line.lower().startswith("subject:"):
                original_subject = line.split(":", 1)[1].strip()[:500]
                break

    # 7. Datum bounce
    bounced_at = None
    date_hdr = msg.get("Date")
    if date_hdr:
        try:
            bounced_at = parsedate_to_datetime(date_hdr).replace(tzinfo=None)
        except Exception:
            bounced_at = None

    return {
        "recipient": recipient,
        "bounce_type": bounce_type,
        "reason": reason,
        "diagnostic_code": diagnostic,
        "original_subject": original_subject,
        "bounced_at": bounced_at,
    }


def _match_owner(db: Session, recipient: str) -> Owner | None:
    if not recipient:
        return None
    addr = recipient.lower().strip()
    # Owner.email může obsahovat víc adres oddělených ; nebo ,
    candidates = (
        db.query(Owner)
        .filter(
            (Owner.email.ilike(f"%{addr}%"))
            | (Owner.email_secondary.ilike(f"%{addr}%"))
        )
        .all()
    )
    for owner in candidates:
        emails = []
        for field in (owner.email, owner.email_secondary):
            if field:
                emails.extend(e.strip().lower() for e in re.split(r"[;,]", field))
        if addr in emails:
            return owner
    return None


def _match_email_log(db: Session, recipient: str) -> EmailLog | None:
    if not recipient:
        return None
    return (
        db.query(EmailLog)
        .filter(EmailLog.recipient_email.ilike(recipient))
        .filter(EmailLog.status == EmailStatus.SENT)
        .order_by(EmailLog.sent_at.desc().nulls_last())
        .first()
    )


def _last_check_timestamp(db: Session) -> datetime | None:
    last = db.query(EmailBounce).order_by(EmailBounce.created_at.desc()).first()
    return last.created_at if last else None


def _fetch_bounces_for_account(
    db: Session,
    account: dict,
    existing_uids: set[str],
    mark_invalid: bool = True,
    on_progress: callable = None,
    cancelled: callable = None,
) -> dict:
    """Kontrola bounces pro jeden IMAP účet.

    Args:
        account: {name, host, port, user, password}
        existing_uids: sada již zpracovaných IMAP UID
        on_progress: callback(scanned, total, new_count) volaný po každém emailu
        cancelled: callable() → True pokud má být kontrola zrušena

    Returns:
        dict {success, new_count, scanned, total_uids, error}
    """
    new_count = 0
    scanned = 0
    total_uids = 0
    error: str | None = None

    try:
        conn = connect_imap(
            host=account["host"],
            port=account.get("port", 993),
            user=account["user"],
            password=account["password"],
        )
    except Exception as exc:
        return {"success": False, "error": f"IMAP {account['name']}: {exc}", "new_count": 0, "scanned": 0, "total_uids": 0}

    try:
        conn.select("INBOX")

        last_check = _last_check_timestamp(db)
        since = (last_check - timedelta(days=1)) if last_check else (utcnow() - timedelta(days=30))
        since_str = since.strftime("%d-%b-%Y")

        status, data = conn.search(None, f'(SINCE "{since_str}")')
        if status != "OK":
            # Fallback: některé servery (Seznam) nepodporují SINCE → zkusit ALL
            logger.warning("IMAP SINCE selhal pro %s, zkouším ALL", account["name"])
            status, data = conn.search(None, "ALL")
            if status != "OK":
                return {"success": False, "error": f"IMAP SEARCH selhal: {status}", "new_count": 0, "scanned": 0, "total_uids": 0}

        uids = data[0].split() if data and data[0] else []
        uids = uids[-500:]
        total_uids = len(uids)

        # Exclude own address from bounce recipient matching
        own_addresses = {
            account["user"].lower(),
            (settings.smtp_user or "").lower(),
            (settings.smtp_from_email or "").lower(),
            (settings.imap_user or "").lower(),
        }

        for i, uid in enumerate(uids):
            if cancelled and cancelled():
                break

            uid_str = uid.decode() if isinstance(uid, bytes) else str(uid)
            if uid_str in existing_uids:
                if on_progress:
                    on_progress(i + 1, total_uids, new_count)
                continue

            status, msg_data = conn.fetch(uid, "(RFC822)")
            if status != "OK" or not msg_data or not msg_data[0]:
                if on_progress:
                    on_progress(i + 1, total_uids, new_count)
                continue

            raw = msg_data[0][1]
            if not isinstance(raw, (bytes, bytearray)):
                if on_progress:
                    on_progress(i + 1, total_uids, new_count)
                continue

            msg = email.message_from_bytes(raw)
            subject = _decode_header(msg.get("Subject"))

            if not _is_bounce_subject(subject):
                if on_progress:
                    on_progress(i + 1, total_uids, new_count)
                continue

            scanned += 1
            parsed = _parse_bounce(msg)

            if not parsed["recipient"]:
                if on_progress:
                    on_progress(i + 1, total_uids, new_count)
                continue

            # Skip own address
            if parsed["recipient"] and parsed["recipient"].lower() in own_addresses:
                if on_progress:
                    on_progress(i + 1, total_uids, new_count)
                continue

            if (
                parsed["bounce_type"] == BounceType.UNKNOWN
                and not parsed["diagnostic_code"]
                and not parsed["reason"]
            ):
                if on_progress:
                    on_progress(i + 1, total_uids, new_count)
                continue

            owner = _match_owner(db, parsed["recipient"])
            email_log = _match_email_log(db, parsed["recipient"])

            bounce = EmailBounce(
                recipient_email=parsed["recipient"],
                owner_id=owner.id if owner else None,
                email_log_id=email_log.id if email_log else None,
                bounce_type=parsed["bounce_type"],
                reason=parsed["reason"],
                diagnostic_code=parsed["diagnostic_code"],
                subject=parsed["original_subject"] or subject,
                module=email_log.module if email_log else None,
                reference_id=email_log.reference_id if email_log else None,
                bounced_at=parsed["bounced_at"],
                imap_uid=uid_str,
                imap_message_id=msg.get("Message-ID"),
            )
            db.add(bounce)
            existing_uids.add(uid_str)
            new_count += 1

            if mark_invalid and owner and parsed["bounce_type"] == BounceType.HARD:
                owner.email_invalid = True
                owner.email_invalid_reason = (parsed["reason"] or parsed["diagnostic_code"] or "Hard bounce")[:500]

            try:
                conn.store(uid, "+FLAGS", "\\Seen")
            except Exception:
                pass

            if on_progress:
                on_progress(i + 1, total_uids, new_count)

        db.commit()
    except Exception as exc:
        logger.exception("Bounce check selhal pro %s: %s", account["name"], exc)
        db.rollback()
        error = str(exc)
    finally:
        try:
            conn.logout()
        except Exception:
            pass

    return {
        "success": error is None,
        "error": error,
        "new_count": new_count,
        "scanned": scanned,
        "total_uids": total_uids,
    }


def fetch_bounces(db: Session, mark_invalid: bool = True) -> dict:
    """Jednoduchý vstup (bez progress) — kontrola VŠECH IMAP účtů.

    Returns:
        dict {success, new_count, scanned, error}
    """
    accounts = get_imap_accounts(db)
    if not accounts:
        return {"success": False, "error": "Žádný IMAP účet nakonfigurován", "new_count": 0, "scanned": 0}

    existing_uids = {
        row[0] for row in
        db.query(EmailBounce.imap_uid).filter(EmailBounce.imap_uid.isnot(None)).all()
    }

    total_new = 0
    total_scanned = 0
    errors: list[str] = []

    for acc in accounts:
        result = _fetch_bounces_for_account(db, acc, existing_uids, mark_invalid)
        total_new += result["new_count"]
        total_scanned += result["scanned"]
        if result["error"]:
            errors.append(result["error"])

    return {
        "success": len(errors) == 0,
        "error": "; ".join(errors) if errors else None,
        "new_count": total_new,
        "scanned": total_scanned,
    }


def humanize_reason(text: str | None, bounce_type: BounceType) -> str:
    """Přeloží surový SMTP/DSN text do srozumitelné české věty."""
    if not text:
        if bounce_type == BounceType.HARD:
            return "Adresa nedoručitelná"
        if bounce_type == BounceType.SOFT:
            return "Dočasné selhání doručení"
        return "Neznámý důvod"
    t = text.lower()
    if any(k in t for k in ("5.1.1", "no such user", "user unknown", "no such mailbox",
                             "mailbox does not exist", "recipient address rejected: user",
                             "address rejected", "does not exist")):
        return "Adresa příjemce neexistuje"
    if "5.4.1" in t or "access denied" in t:
        return "Příjemce odmítl zprávu (přístup zamítnut)"
    if any(k in t for k in ("5.7.", "policy", "blocked", "spam", "blacklist", "reject due to policy")):
        return "Zpráva odmítnuta firewallem nebo spam filtrem"
    if any(k in t for k in ("quota", "mailbox full", "5.2.2")):
        return "Plná schránka příjemce"
    if "5.2.1" in t or "disabled" in t or "deactivated" in t:
        return "Schránka deaktivována"
    if any(k in t for k in ("greylisted", "try again later", "temporary", "4.7.", "4.2.", "4.4.")):
        return "Dočasné selhání — zkuste znovu později"
    if "relay" in t or "5.7.1" in t:
        return "Server odmítl přeposlání zprávy"
    if "dns" in t or "host not found" in t or "no mx" in t:
        return "Doména neexistuje (DNS chyba)"
    if "timeout" in t or "connection" in t:
        return "Spojení se serverem příjemce selhalo"
    if "550" in t:
        return "Adresa nedoručitelná"
    if "554" in t:
        return "Zpráva odmítnuta serverem příjemce"
    if "552" in t:
        return "Zpráva přesahuje limit velikosti"
    if bounce_type == BounceType.HARD:
        return "Adresa nedoručitelná"
    if bounce_type == BounceType.SOFT:
        return "Dočasné selhání doručení"
    return "Neznámý důvod"


def count_bounces_for_reference(db: Session, module: str, reference_id: int) -> int:
    return (
        db.query(EmailBounce)
        .filter(EmailBounce.module == module, EmailBounce.reference_id == reference_id)
        .count()
    )
