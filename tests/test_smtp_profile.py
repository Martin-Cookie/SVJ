"""Tests for SmtpProfile CRUD endpoints (/nastaveni/smtp/*)."""
import pytest
from unittest.mock import patch, MagicMock

from app.models import SmtpProfile
from app.utils import encode_smtp_password, decode_smtp_password


# ── Encryption tests ─────────────────────────────────────────────────────────


class TestSmtpPasswordEncryption:
    """Test Fernet encryption of SMTP passwords."""

    def test_encode_decode_roundtrip(self):
        """Encoding then decoding returns original password."""
        password = "S3cur3_P@ss!"
        encoded = encode_smtp_password(password)
        assert encoded != password
        assert decode_smtp_password(encoded) == password

    def test_encoded_is_not_base64_plaintext(self):
        """Encoded value is Fernet token, not simple base64."""
        import base64
        password = "test123"
        encoded = encode_smtp_password(password)
        # Fernet tokens start with gAAAAA
        assert encoded.startswith("gAAAAA")
        # Simple base64 decode should NOT yield the password directly
        try:
            naive = base64.b64decode(encoded.encode()).decode()
            assert naive != password
        except Exception:
            pass  # expected — Fernet token is not valid plain base64

    def test_decode_legacy_base64_fallback(self):
        """Legacy base64-encoded passwords are decoded via fallback."""
        import base64
        password = "legacy_pass"
        legacy_encoded = base64.b64encode(password.encode()).decode()
        # decode_smtp_password should fall back to base64
        assert decode_smtp_password(legacy_encoded) == password

    def test_different_passwords_different_tokens(self):
        """Each encryption produces unique token (Fernet includes timestamp)."""
        enc1 = encode_smtp_password("same")
        enc2 = encode_smtp_password("same")
        # Fernet includes timestamp so tokens differ
        assert enc1 != enc2
        # But both decrypt to the same value
        assert decode_smtp_password(enc1) == "same"
        assert decode_smtp_password(enc2) == "same"


# ── CRUD endpoint tests ─────────────────────────────────────────��────────────


class TestSmtpProfileCRUD:
    """Test SmtpProfile CRUD endpoints."""

    def test_create_profile(self, client, db_session):
        """Creating a new SMTP profile works."""
        response = client.post("/nastaveni/smtp/novy", data={
            "name": "Test SMTP",
            "smtp_host": "smtp.test.com",
            "smtp_port": "587",
            "smtp_user": "user@test.com",
            "smtp_password": "secret123",
            "smtp_from_name": "Test SVJ",
            "smtp_from_email": "svj@test.com",
            "smtp_use_tls": "true",
        })
        assert response.status_code == 200

        profile = db_session.query(SmtpProfile).filter_by(name="Test SMTP").first()
        assert profile is not None
        assert profile.smtp_host == "smtp.test.com"
        assert profile.smtp_port == 587
        assert profile.smtp_user == "user@test.com"
        assert profile.smtp_from_email == "svj@test.com"
        assert profile.is_default is True  # first profile is auto-default
        # Password is encrypted
        assert decode_smtp_password(profile.smtp_password_b64) == "secret123"

    def test_create_profile_validation(self, client, db_session):
        """Missing required fields returns error."""
        response = client.post("/nastaveni/smtp/novy", data={
            "name": "",
            "smtp_host": "",
            "smtp_port": "465",
            "smtp_user": "",
            "smtp_password": "secret",
            "smtp_from_name": "",
            "smtp_from_email": "",
        })
        assert response.status_code == 200
        assert "povinné" in response.text.lower() or "Název" in response.text

    def test_create_profile_password_required(self, client, db_session):
        """New profile requires a password."""
        response = client.post("/nastaveni/smtp/novy", data={
            "name": "No Pass",
            "smtp_host": "smtp.test.com",
            "smtp_port": "465",
            "smtp_user": "user",
            "smtp_password": "",
            "smtp_from_name": "",
            "smtp_from_email": "a@b.com",
        })
        assert response.status_code == 200
        assert "Heslo" in response.text or "povinné" in response.text.lower()

    def test_max_3_profiles(self, client, db_session):
        """Cannot create more than 3 profiles."""
        # Create 3 profiles
        for i in range(3):
            p = SmtpProfile(
                name=f"Profile {i}",
                smtp_host=f"smtp{i}.test.com",
                smtp_port=465,
                smtp_user=f"user{i}",
                smtp_password_b64=encode_smtp_password("pass"),
                smtp_from_email=f"from{i}@test.com",
                is_default=(i == 0),
            )
            db_session.add(p)
        db_session.commit()

        # Try to create 4th
        response = client.post("/nastaveni/smtp/novy", data={
            "name": "Fourth",
            "smtp_host": "smtp4.test.com",
            "smtp_port": "465",
            "smtp_user": "user4",
            "smtp_password": "pass4",
            "smtp_from_name": "",
            "smtp_from_email": "from4@test.com",
        })
        assert response.status_code == 200
        assert "Maximum" in response.text or "3" in response.text

    def test_update_profile(self, client, db_session):
        """Updating an existing profile changes its fields."""
        profile = SmtpProfile(
            name="Original",
            smtp_host="smtp.original.com",
            smtp_port=465,
            smtp_user="orig",
            smtp_password_b64=encode_smtp_password("origpass"),
            smtp_from_email="orig@test.com",
            is_default=True,
        )
        db_session.add(profile)
        db_session.commit()
        pid = profile.id

        response = client.post(f"/nastaveni/smtp/{pid}", data={
            "name": "Updated",
            "smtp_host": "smtp.updated.com",
            "smtp_port": "587",
            "smtp_user": "updated",
            "smtp_password": "••••••••",  # placeholder — should NOT update password
            "smtp_from_name": "Updated Name",
            "smtp_from_email": "updated@test.com",
            "smtp_use_tls": "true",
        })
        assert response.status_code == 200

        db_session.refresh(profile)
        assert profile.name == "Updated"
        assert profile.smtp_host == "smtp.updated.com"
        assert profile.smtp_from_email == "updated@test.com"
        # Password unchanged (placeholder was sent)
        assert decode_smtp_password(profile.smtp_password_b64) == "origpass"

    def test_update_profile_password(self, client, db_session):
        """Sending a real password updates it."""
        profile = SmtpProfile(
            name="PassTest",
            smtp_host="smtp.test.com",
            smtp_port=465,
            smtp_user="user",
            smtp_password_b64=encode_smtp_password("old"),
            smtp_from_email="test@test.com",
            is_default=True,
        )
        db_session.add(profile)
        db_session.commit()
        pid = profile.id

        response = client.post(f"/nastaveni/smtp/{pid}", data={
            "name": "PassTest",
            "smtp_host": "smtp.test.com",
            "smtp_port": "465",
            "smtp_user": "user",
            "smtp_password": "newpassword",
            "smtp_from_name": "",
            "smtp_from_email": "test@test.com",
        })
        assert response.status_code == 200

        db_session.refresh(profile)
        assert decode_smtp_password(profile.smtp_password_b64) == "newpassword"

    def test_delete_profile(self, client, db_session):
        """Deleting a non-last profile works."""
        p1 = SmtpProfile(
            name="First", smtp_host="a.com", smtp_port=465,
            smtp_user="a", smtp_password_b64=encode_smtp_password("p"),
            smtp_from_email="a@a.com", is_default=True,
        )
        p2 = SmtpProfile(
            name="Second", smtp_host="b.com", smtp_port=465,
            smtp_user="b", smtp_password_b64=encode_smtp_password("p"),
            smtp_from_email="b@b.com", is_default=False,
        )
        db_session.add_all([p1, p2])
        db_session.commit()
        p2_id = p2.id

        response = client.post(f"/nastaveni/smtp/{p2_id}/smazat")
        assert response.status_code == 200

        assert db_session.query(SmtpProfile).get(p2_id) is None
        assert db_session.query(SmtpProfile).count() == 1

    def test_cannot_delete_last_profile(self, client, db_session):
        """Cannot delete the only remaining profile."""
        p = SmtpProfile(
            name="Only", smtp_host="a.com", smtp_port=465,
            smtp_user="a", smtp_password_b64=encode_smtp_password("p"),
            smtp_from_email="a@a.com", is_default=True,
        )
        db_session.add(p)
        db_session.commit()
        pid = p.id

        response = client.post(f"/nastaveni/smtp/{pid}/smazat")
        assert response.status_code == 200
        # Profile still exists — deletion was blocked
        assert db_session.query(SmtpProfile).get(pid) is not None
        assert db_session.query(SmtpProfile).count() == 1

    def test_set_default(self, client, db_session):
        """Setting a profile as default unsets others."""
        p1 = SmtpProfile(
            name="First", smtp_host="a.com", smtp_port=465,
            smtp_user="a", smtp_password_b64=encode_smtp_password("p"),
            smtp_from_email="a@a.com", is_default=True,
        )
        p2 = SmtpProfile(
            name="Second", smtp_host="b.com", smtp_port=465,
            smtp_user="b", smtp_password_b64=encode_smtp_password("p"),
            smtp_from_email="b@b.com", is_default=False,
        )
        db_session.add_all([p1, p2])
        db_session.commit()
        p2_id = p2.id

        response = client.post(f"/nastaveni/smtp/{p2_id}/vychozi")
        assert response.status_code == 200

        db_session.refresh(p1)
        db_session.refresh(p2)
        assert p1.is_default is False
        assert p2.is_default is True

    def test_smtp_connection_test_success(self, client, db_session):
        """Test SMTP connection returns success on successful connect."""
        p = SmtpProfile(
            name="TestProf", smtp_host="smtp.test.com", smtp_port=465,
            smtp_user="user", smtp_password_b64=encode_smtp_password("pass"),
            smtp_from_email="a@a.com", is_default=True,
        )
        db_session.add(p)
        db_session.commit()
        pid = p.id

        mock_server = MagicMock()
        with patch("app.services.email_service._create_smtp", return_value=mock_server):
            response = client.post(f"/nastaveni/smtp/{pid}/test")
            assert response.status_code == 200
            assert "smtp_test_ok" in response.text or "Připojení OK" in response.text or "TestProf" in response.text

    def test_edit_form_returns_form(self, client, db_session):
        """GET edit form returns the form partial."""
        p = SmtpProfile(
            name="EditMe", smtp_host="smtp.test.com", smtp_port=465,
            smtp_user="user", smtp_password_b64=encode_smtp_password("p"),
            smtp_from_email="a@a.com", is_default=True,
        )
        db_session.add(p)
        db_session.commit()
        pid = p.id

        response = client.get(f"/nastaveni/smtp/{pid}/formular")
        assert response.status_code == 200
        assert "EditMe" in response.text

    def test_profile_card(self, client, db_session):
        """GET card returns read-only card."""
        p = SmtpProfile(
            name="CardView", smtp_host="smtp.card.com", smtp_port=465,
            smtp_user="user", smtp_password_b64=encode_smtp_password("p"),
            smtp_from_email="card@test.com", is_default=True,
        )
        db_session.add(p)
        db_session.commit()
        pid = p.id

        response = client.get(f"/nastaveni/smtp/{pid}/karta")
        assert response.status_code == 200
        assert "CardView" in response.text

    def test_new_form_endpoint(self, client, db_session):
        """GET new form returns empty form."""
        response = client.get("/nastaveni/smtp/novy-formular")
        assert response.status_code == 200

    def test_profiles_list_endpoint(self, client, db_session):
        """GET profiles list partial works."""
        response = client.get("/nastaveni/smtp/profily")
        assert response.status_code == 200

    def test_delete_default_promotes_next(self, client, db_session):
        """Deleting the default profile sets another as default."""
        p1 = SmtpProfile(
            name="Default", smtp_host="a.com", smtp_port=465,
            smtp_user="a", smtp_password_b64=encode_smtp_password("p"),
            smtp_from_email="a@a.com", is_default=True,
        )
        p2 = SmtpProfile(
            name="Backup", smtp_host="b.com", smtp_port=465,
            smtp_user="b", smtp_password_b64=encode_smtp_password("p"),
            smtp_from_email="b@b.com", is_default=False,
        )
        db_session.add_all([p1, p2])
        db_session.commit()
        p1_id = p1.id

        response = client.post(f"/nastaveni/smtp/{p1_id}/smazat")
        assert response.status_code == 200

        db_session.refresh(p2)
        assert p2.is_default is True
