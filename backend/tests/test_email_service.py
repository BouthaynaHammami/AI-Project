from email.message import EmailMessage

from app.services import email_service


class FakeSMTP:
    sent_message: EmailMessage | None = None

    def __init__(self, host: str, port: int, timeout: int):
        assert host == "smtp.example.test"
        assert port == 587
        assert timeout == 15

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def starttls(self) -> None:
        pass

    def login(self, username: str, password: str) -> None:
        assert username == "smtp-user"
        assert password == "smtp-password"

    def send_message(self, message: EmailMessage) -> None:
        FakeSMTP.sent_message = message


def test_verification_email_includes_responsive_html_plain_text_and_inline_logo(monkeypatch):
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("SMTP_HOST", "smtp.example.test")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USER", "smtp-user")
    monkeypatch.setenv("SMTP_PASSWORD", "smtp-password")
    monkeypatch.setenv("SMTP_FROM", "AI Data Analyst <no-reply@example.test>")
    monkeypatch.setenv("SMTP_TLS", "true")
    monkeypatch.setattr(email_service.smtplib, "SMTP", FakeSMTP)
    FakeSMTP.sent_message = None

    email_service.send_email_code("person@example.test", "903885", "verify")

    message = FakeSMTP.sent_message
    assert message is not None
    assert message["Subject"] == "Vérifiez votre adresse e-mail"
    assert message.get_body(preferencelist=("plain",)).get_content().find("903885") >= 0
    html = message.get_body(preferencelist=("html",))
    assert html is not None
    html_content = html.get_content()
    assert "Vérifiez votre adresse e-mail" in html_content
    assert "10 minutes" in html_content
    assert "#0B1F3A" in html_content
    assert "#2563EB" in html_content
    assert "@media only screen and (max-width: 600px)" in html_content

    inline_logo = next(
        part for part in message.walk()
        if part.get_content_type() == "image/jpeg"
    )
    assert inline_logo["Content-ID"] == "<ai-data-analyst-logo>"
    assert inline_logo.get_content_disposition() == "inline"


def test_password_reset_email_uses_same_branded_template(monkeypatch):
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("SMTP_HOST", "smtp.example.test")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USER", "")
    monkeypatch.setenv("SMTP_PASSWORD", "")
    monkeypatch.setenv("SMTP_FROM", "no-reply@example.test")
    monkeypatch.setenv("SMTP_TLS", "false")
    monkeypatch.setattr(email_service.smtplib, "SMTP", FakeSMTP)
    FakeSMTP.sent_message = None

    email_service.send_email_code("person@example.test", "123456", "reset")

    message = FakeSMTP.sent_message
    assert message is not None
    assert message["Subject"] == "Réinitialisez votre mot de passe"
    assert "réinitialiser le mot de passe" in message.get_body(
        preferencelist=("plain",)
    ).get_content()
