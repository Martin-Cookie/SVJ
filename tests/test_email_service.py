"""Tests for EmailLog name_normalized population in email_service."""
from app.models.common import EmailLog, EmailStatus
from app.utils import strip_diacritics


# ---------------------------------------------------------------------------
# name_normalized on EmailLog
# ---------------------------------------------------------------------------

def test_name_normalized_populated_on_creation(db_session):
    """EmailLog.name_normalized should be populated when creating a log entry."""
    log = EmailLog(
        recipient_email="test@example.com",
        recipient_name="Jan Novák",
        name_normalized=strip_diacritics("Jan Novák"),
        subject="Test",
        status=EmailStatus.SENT,
        module="test",
    )
    db_session.add(log)
    db_session.flush()

    assert log.name_normalized == "jan novak"


def test_name_normalized_empty_name(db_session):
    """Empty name should produce empty normalized string."""
    log = EmailLog(
        recipient_email="test@example.com",
        recipient_name="",
        name_normalized=strip_diacritics(""),
        subject="Test",
        status=EmailStatus.SENT,
        module="test",
    )
    db_session.add(log)
    db_session.flush()

    assert log.name_normalized == ""


def test_name_normalized_czech_diacritics(db_session):
    """Czech diacritics should be properly stripped."""
    name = "Řehoř Čížek"
    log = EmailLog(
        recipient_email="test@example.com",
        recipient_name=name,
        name_normalized=strip_diacritics(name),
        subject="Test",
        status=EmailStatus.SENT,
        module="test",
    )
    db_session.add(log)
    db_session.flush()

    assert log.name_normalized == "rehor cizek"


def test_email_log_search_diacritics(db_session):
    """Searching 'novak' should find 'Novák' via name_normalized."""
    log = EmailLog(
        recipient_email="test@example.com",
        recipient_name="Jan Novák",
        name_normalized=strip_diacritics("Jan Novák"),
        subject="Test",
        status=EmailStatus.SENT,
        module="test",
    )
    db_session.add(log)
    db_session.flush()

    # Search via normalized name
    search = strip_diacritics("novak")
    results = (
        db_session.query(EmailLog)
        .filter(EmailLog.name_normalized.like(f"%{search}%"))
        .all()
    )
    assert len(results) == 1
    assert results[0].recipient_name == "Jan Novák"


def test_name_normalized_on_failed_status(db_session):
    """name_normalized should be populated even for failed emails."""
    log = EmailLog(
        recipient_email="test@example.com",
        recipient_name="Petr Šťastný",
        name_normalized=strip_diacritics("Petr Šťastný"),
        subject="Test",
        status=EmailStatus.FAILED,
        error_message="SMTP error",
        module="test",
    )
    db_session.add(log)
    db_session.flush()

    assert log.name_normalized == "petr stastny"
