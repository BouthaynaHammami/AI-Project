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


class FailedSMTP:
    def __init__(self, *_args, **_kwargs):
        raise OSError("SMTP server is unavailable")


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

    delivery_mode = email_service.send_email_code("person@example.test", "903885", "verify")

    assert delivery_mode == "email"
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

    delivery_mode = email_service.send_email_code("person@example.test", "123456", "reset")

    assert delivery_mode == "email"
    message = FakeSMTP.sent_message
    assert message is not None
    assert message["Subject"] == "Réinitialisez votre mot de passe"
    assert "réinitialiser le mot de passe" in message.get_body(
        preferencelist=("plain",)
    ).get_content()


def test_development_without_smtp_logs_code_instead_of_claiming_email_delivery(monkeypatch, caplog):
    monkeypatch.setenv("ENV", "dev")
    monkeypatch.delenv("SMTP_HOST", raising=False)
    monkeypatch.delenv("SMTP_FROM", raising=False)

    delivery_mode = email_service.send_email_code("person@example.test", "123456", "verify")

    assert delivery_mode == "console"
    assert "123456" in caplog.text


def test_production_without_smtp_reports_delivery_unavailable(monkeypatch):
    monkeypatch.setenv("ENV", "production")
    monkeypatch.delenv("SMTP_HOST", raising=False)
    monkeypatch.delenv("SMTP_FROM", raising=False)

    try:
        email_service.send_email_code("person@example.test", "123456", "verify")
    except RuntimeError as error:
        assert str(error) == "Email delivery is not configured."
    else:
        raise AssertionError("Email delivery should fail when SMTP is not configured.")


def test_development_with_unavailable_smtp_logs_code_to_backend_terminal(monkeypatch, caplog):
    monkeypatch.setenv("ENV", "dev")
    monkeypatch.setenv("SMTP_HOST", "localhost")
    monkeypatch.setenv("SMTP_PORT", "1025")
    monkeypatch.setenv("SMTP_FROM", "AI Data Analyst <no-reply@localhost>")
    monkeypatch.setenv("SMTP_TLS", "false")
    monkeypatch.setattr(email_service.smtplib, "SMTP", FailedSMTP)

    delivery_mode = email_service.send_email_code("person@example.test", "123456", "verify")

    assert delivery_mode == "console"
    assert "development email code" in caplog.text
    assert "123456" in caplog.text


def test_production_with_unavailable_smtp_reports_failure(monkeypatch):
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("SMTP_HOST", "localhost")
    monkeypatch.setenv("SMTP_PORT", "1025")
    monkeypatch.setenv("SMTP_FROM", "AI Data Analyst <no-reply@localhost>")
    monkeypatch.setenv("SMTP_TLS", "false")
    monkeypatch.setattr(email_service.smtplib, "SMTP", FailedSMTP)

    try:
        email_service.send_email_code("person@example.test", "123456", "verify")
    except RuntimeError as error:
        assert str(error) == "SMTP delivery failed."
    else:
        raise AssertionError("Email delivery should fail if production SMTP is unavailable.")
