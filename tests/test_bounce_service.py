"""Tests for app.services.bounce_service — pure functions (no DB/IMAP)."""
import email
from email.message import EmailMessage

from app.models import BounceType
from app.services.bounce_service import (
    _derive_imap_host,
    _is_bounce_subject,
    _decode_header,
    _parse_bounce,
    humanize_reason,
)


# ---------------------------------------------------------------------------
# _derive_imap_host
# ---------------------------------------------------------------------------

class TestDeriveImapHost:
    def test_gmail(self):
        assert _derive_imap_host("smtp.gmail.com") == "imap.gmail.com"

    def test_seznam(self):
        assert _derive_imap_host("smtp.seznam.cz") == "imap.seznam.cz"

    def test_no_smtp_prefix(self):
        assert _derive_imap_host("mail.example.com") == "mail.example.com"

    def test_empty(self):
        assert _derive_imap_host("") == ""


# ---------------------------------------------------------------------------
# _is_bounce_subject
# ---------------------------------------------------------------------------

class TestIsBounceSubject:
    def test_dsn(self):
        assert _is_bounce_subject("Delivery Status Notification (Failure)") is True

    def test_undelivered(self):
        assert _is_bounce_subject("Undelivered Mail Returned to Sender") is True

    def test_failure_notice(self):
        assert _is_bounce_subject("Failure Notice") is True

    def test_normal_subject(self):
        assert _is_bounce_subject("Re: Odečty vodoměrů") is False

    def test_none(self):
        assert _is_bounce_subject(None) is False

    def test_empty(self):
        assert _is_bounce_subject("") is False

    def test_case_insensitive(self):
        assert _is_bounce_subject("MAIL DELIVERY FAILED") is True


# ---------------------------------------------------------------------------
# _decode_header
# ---------------------------------------------------------------------------

class TestDecodeHeader:
    def test_plain(self):
        assert _decode_header("Hello World") == "Hello World"

    def test_none(self):
        assert _decode_header(None) == ""

    def test_empty(self):
        assert _decode_header("") == ""

    def test_encoded_utf8(self):
        encoded = "=?utf-8?B?T2TEjXR5IHZvZG9txJtyxa8=?="
        result = _decode_header(encoded)
        assert "vodoměr" in result.lower()


# ---------------------------------------------------------------------------
# _parse_bounce
# ---------------------------------------------------------------------------

def _make_dsn_message(
    final_recipient: str = "",
    status: str = "",
    diagnostic: str = "",
    subject: str = "Delivery Status Notification",
    date_str: str = "Mon, 20 Apr 2026 10:00:00 +0200",
) -> EmailMessage:
    """Build a minimal DSN bounce email for testing."""
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["Date"] = date_str
    msg["From"] = "mailer-daemon@example.com"

    # Build DSN body
    dsn_parts = []
    if final_recipient:
        dsn_parts.append(f"Final-Recipient: rfc822; {final_recipient}")
    if status:
        dsn_parts.append(f"Status: {status}")
    if diagnostic:
        dsn_parts.append(f"Diagnostic-Code: smtp; {diagnostic}")
    body = "\n".join(dsn_parts) if dsn_parts else "unknown error"
    msg.set_content(body)
    return msg


class TestParseBounce:
    def test_hard_bounce(self):
        msg = _make_dsn_message(
            final_recipient="user@example.com",
            status="5.1.1",
            diagnostic="550 5.1.1 user unknown",
        )
        result = _parse_bounce(msg)
        assert result["recipient"] == "user@example.com"
        assert result["bounce_type"] == BounceType.HARD

    def test_soft_bounce(self):
        msg = _make_dsn_message(
            final_recipient="user@example.com",
            status="4.2.2",
            diagnostic="452 4.2.2 mailbox full",
        )
        result = _parse_bounce(msg)
        assert result["recipient"] == "user@example.com"
        assert result["bounce_type"] == BounceType.SOFT

    def test_no_recipient(self):
        msg = _make_dsn_message()
        result = _parse_bounce(msg)
        assert result["recipient"] is None

    def test_x_failed_recipients_fallback(self):
        msg = EmailMessage()
        msg["Subject"] = "Delivery Status Notification"
        msg["Date"] = "Mon, 20 Apr 2026 10:00:00 +0200"
        msg.set_content("X-Failed-Recipients: bob@example.com\n550 user unknown")
        result = _parse_bounce(msg)
        assert result["recipient"] == "bob@example.com"

    def test_for_bracket_fallback(self):
        msg = EmailMessage()
        msg["Subject"] = "Undelivered Mail Returned to Sender"
        msg["Date"] = "Mon, 20 Apr 2026 10:00:00 +0200"
        msg.set_content("The email for <alice@test.org> could not be delivered.\n550 unknown user")
        result = _parse_bounce(msg)
        assert result["recipient"] == "alice@test.org"

    def test_bounced_at_parsed(self):
        msg = _make_dsn_message(
            final_recipient="user@example.com",
            status="5.1.1",
        )
        result = _parse_bounce(msg)
        assert result["bounced_at"] is not None
        assert result["bounced_at"].year == 2026

    def test_diagnostic_extracted(self):
        msg = _make_dsn_message(
            final_recipient="user@example.com",
            status="5.1.1",
            diagnostic="550 5.1.1 The email account does not exist",
        )
        result = _parse_bounce(msg)
        assert result["diagnostic_code"] is not None
        assert "does not exist" in result["diagnostic_code"]


# ---------------------------------------------------------------------------
# humanize_reason
# ---------------------------------------------------------------------------

class TestHumanizeReason:
    def test_user_unknown(self):
        result = humanize_reason("550 5.1.1 user unknown", BounceType.HARD)
        assert "neexistuje" in result.lower()

    def test_mailbox_full(self):
        result = humanize_reason("452 4.2.2 mailbox full quota exceeded", BounceType.SOFT)
        assert "schránk" in result.lower()

    def test_spam_blocked(self):
        result = humanize_reason("550 5.7.1 blocked by spam filter policy", BounceType.HARD)
        assert "spam" in result.lower() or "odmítn" in result.lower()

    def test_dns_error(self):
        result = humanize_reason("Host not found, DNS error", BounceType.HARD)
        assert "DNS" in result or "doména" in result.lower()

    def test_none_hard(self):
        result = humanize_reason(None, BounceType.HARD)
        assert "nedoručitelná" in result.lower()

    def test_none_soft(self):
        result = humanize_reason(None, BounceType.SOFT)
        assert "dočasn" in result.lower()

    def test_none_unknown(self):
        result = humanize_reason(None, BounceType.UNKNOWN)
        assert "neznám" in result.lower()

    def test_disabled_mailbox(self):
        result = humanize_reason("550 5.2.1 mailbox disabled", BounceType.HARD)
        assert "deaktiv" in result.lower()

    def test_relay_denied(self):
        result = humanize_reason("550 5.7.1 relay access denied", BounceType.HARD)
        # Could match spam filter or relay
        assert result != ""

    def test_generic_550(self):
        result = humanize_reason("550 something weird", BounceType.HARD)
        assert "nedoručitelná" in result.lower()

    def test_timeout(self):
        result = humanize_reason("connection timeout after 30s", BounceType.SOFT)
        assert "spojení" in result.lower() or "selhalo" in result.lower()
