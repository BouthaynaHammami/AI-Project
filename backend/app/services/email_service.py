import logging
import os
import smtplib
from html import escape
from typing import Literal
from pathlib import Path
from email.message import EmailMessage
from urllib.parse import urlsplit

logger = logging.getLogger(__name__)
LOGO_PATH = Path(__file__).resolve().parents[3] / "ai-data-analyst-icon.jpg"
EmailDeliveryMode = Literal["email", "console", "unavailable"]


def get_email_delivery_mode() -> EmailDeliveryMode:
    if os.getenv("SMTP_HOST", "").strip() and os.getenv("SMTP_FROM", "").strip():
        return "email"
    if os.getenv("ENV", "").lower() == "dev":
        return "console"
    return "unavailable"


def _frontend_url() -> str | None:
    for configured_origin in os.getenv("FRONTEND_ORIGIN", "").split(","):
        origin = configured_origin.strip().rstrip("/")
        if not origin:
            continue
        parsed_origin = urlsplit(origin)
        if parsed_origin.scheme in {"http", "https"} and parsed_origin.netloc:
            return origin
        logger.warning("Skipping email action link because FRONTEND_ORIGIN is not a valid HTTP(S) URL.")
    return None


def _email_content(code: str, purpose: str) -> tuple[str, str, str]:
    is_verification = purpose == "verify"
    if is_verification:
        subject = "Vérifiez votre adresse e-mail"
        title = "Vérifiez votre adresse e-mail"
        intro = (
            "Merci de vous être inscrit sur AI Data Analyst. "
            "Utilisez le code ci-dessous pour vérifier votre adresse e-mail."
        )
        security_note = "Si vous n’êtes pas à l’origine de cette demande, vous pouvez ignorer cet e-mail."
    else:
        subject = "Réinitialisez votre mot de passe"
        title = "Réinitialisez votre mot de passe"
        intro = "Utilisez le code ci-dessous pour réinitialiser le mot de passe de votre compte AI Data Analyst."
        security_note = "Si vous n’êtes pas à l’origine de cette demande, vous pouvez ignorer cet e-mail. Votre mot de passe ne sera pas modifié."

    frontend_url = _frontend_url()
    plain_action = f"Accéder à AI Data Analyst : {frontend_url}\n\n" if frontend_url else ""
    plain_text = (
        f"Bonjour,\n\n{intro}\n\n"
        f"Votre code : {code}\n\n"
        f"Ce code expire dans 10 minutes.\n\n{plain_action}"
        f"{security_note}\n\n"
        "© 2026 AI Data Analyst. Tous droits réservés."
    )
    action_link = (
        f"""\
                <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin:0 0 24px;">
                  <tr>
                    <td class="action-button" align="center" bgcolor="#2563EB" style="background-color:#2563EB;border-radius:8px;">
                      <a href="{escape(frontend_url, quote=True)}" style="display:block;padding:14px 20px;color:#FFFFFF;font-size:14px;line-height:20px;font-weight:700;text-align:center;text-decoration:none;border-radius:8px;">
                        Ouvrir AI Data Analyst
                      </a>
                    </td>
                  </tr>
                </table>"""
        if frontend_url
        else ""
    )
    html = f"""\
<!doctype html>
<html lang="fr">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="color-scheme" content="light">
    <title>{subject}</title>
    <style>
      @media only screen and (max-width: 600px) {{
        .page-padding {{ padding: 20px 12px !important; }}
        .card-padding {{ padding: 28px 22px !important; }}
        .code-box {{ padding-left: 20px !important; font-size: 34px !important; letter-spacing: 8px !important; }}
        .action-button a {{ padding: 15px 18px !important; }}
      }}
    </style>
  </head>
  <body style="margin:0;padding:0;background-color:#EFF6FF;font-family:Arial,Helvetica,sans-serif;color:#0B1F3A;">
    <div style="display:none;max-height:0;overflow:hidden;opacity:0;color:transparent;">{intro}</div>
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background-color:#EFF6FF;">
      <tr>
        <td class="page-padding" align="center" style="padding:36px 16px;">
          <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="max-width:560px;">
            <tr>
              <td align="center" style="padding:0 0 16px;">
                <table role="presentation" cellspacing="0" cellpadding="0" border="0">
                  <tr>
                    <td align="center" valign="middle" bgcolor="#FFFFFF" style="padding:16px 22px;background-color:#FFFFFF;border:1px solid #DBEAFE;border-radius:12px;">
                      <table role="presentation" cellspacing="0" cellpadding="0" border="0">
                        <tr>
                          <td valign="middle" style="padding-right:12px;">
                            <img src="cid:ai-data-analyst-logo" width="44" height="44" alt="Logo AI Data Analyst" style="display:block;width:44px;height:44px;border:0;border-radius:10px;">
                          </td>
                          <td valign="middle" style="font-size:18px;line-height:24px;font-weight:700;color:#0B1F3A;white-space:nowrap;">
                            AI Data Analyst
                          </td>
                        </tr>
                      </table>
                    </td>
                  </tr>
                </table>
              </td>
            </tr>
            <tr>
              <td class="card-padding" style="padding:40px 44px;background-color:#FFFFFF;border:1px solid #DBEAFE;border-radius:16px;box-shadow:0 8px 28px rgba(11,31,58,0.07);">
                <p style="margin:0 0 10px;font-size:11px;line-height:16px;font-weight:700;letter-spacing:1.6px;color:#3B82F6;text-transform:uppercase;">AI DATA ANALYST</p>
                <h1 style="margin:0 0 22px;font-size:28px;line-height:36px;font-weight:700;letter-spacing:-0.5px;color:#0B1F3A;">{title}</h1>
                <p style="margin:0 0 10px;font-size:16px;line-height:25px;color:#0B1F3A;">Bonjour,</p>
                <p style="margin:0 0 24px;font-size:15px;line-height:24px;color:#475569;">{intro}</p>
                <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin:0 0 18px;">
                  <tr>
                    <td class="code-box" align="center" dir="ltr" style="padding:20px 12px 20px 24px;background-color:#EFF6FF;border:1px solid #DBEAFE;border-radius:12px;font-family:Arial,Helvetica,sans-serif;font-size:40px;line-height:48px;font-weight:700;letter-spacing:12px;color:#2563EB;font-variant-numeric:tabular-nums;">
                      {code}
                    </td>
                  </tr>
                </table>
                <p style="margin:0 0 26px;text-align:center;font-size:13px;line-height:20px;color:#475569;">
                  <span style="color:#2563EB;font-weight:700;">&#9201;</span>
                  Ce code expire dans <strong style="color:#0B1F3A;">10 minutes</strong>.
                </p>
                {action_link}
                <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin:0 0 24px;">
                  <tr>
                    <td style="padding:14px 16px;background-color:#F8FAFC;border-left:3px solid #3B82F6;border-radius:4px;font-size:12px;line-height:19px;color:#64748B;">
                      <strong style="color:#0B1F3A;">&#128272; Pour votre sécurité</strong><br>
                      {security_note}
                    </td>
                  </tr>
                </table>
                <p style="margin:0;font-size:13px;line-height:21px;color:#64748B;">
                  Ouvrez AI Data Analyst et saisissez le code ci-dessus pour continuer.
                </p>
              </td>
            </tr>
            <tr>
              <td style="padding:22px 12px 0;">
                <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
                  <tr><td style="border-top:1px solid #DBEAFE;font-size:1px;line-height:1px;">&nbsp;</td></tr>
                  <tr>
                    <td align="center" style="padding:18px 0 0;font-size:11px;line-height:18px;color:#94A3B8;">
                      © 2026 AI Data Analyst. Tous droits réservés.
                    </td>
                  </tr>
                </table>
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>"""
    return subject, plain_text, html


def send_email_code(recipient: str, code: str, purpose: str) -> EmailDeliveryMode:
    host = os.getenv("SMTP_HOST", "").strip()
    sender = os.getenv("SMTP_FROM", "").strip()
    if not host or not sender:
        if os.getenv("ENV", "").lower() == "dev":
            logger.warning("Development email code for %s (%s): %s", recipient, purpose, code)
            return "console"
        logger.error("Email delivery is not configured.")
        raise RuntimeError("Email delivery is not configured.")

    port = int(os.getenv("SMTP_PORT", "587"))
    username = os.getenv("SMTP_USER", "")
    password = os.getenv("SMTP_PASSWORD", "")
    use_tls = os.getenv("SMTP_TLS", "true").lower() in {"1", "true", "yes"}
    message = EmailMessage()
    subject, plain_text, html = _email_content(code, purpose)
    message["Subject"] = subject
    message["From"] = sender
    message["To"] = recipient
    message.set_content(plain_text)
    message.add_alternative(html, subtype="html")
    html_part = message.get_payload()[-1]
    try:
        logo = LOGO_PATH.read_bytes()
    except OSError as exc:
        logger.error("Email logo asset could not be read (%s).", type(exc).__name__)
        raise RuntimeError("Email logo asset could not be read.") from exc
    html_part.add_related(
        logo,
        maintype="image",
        subtype="jpeg",
        cid="<ai-data-analyst-logo>",
        filename=LOGO_PATH.name,
        disposition="inline",
    )

    try:
        with smtplib.SMTP(host, port, timeout=15) as server:
            if use_tls:
                server.starttls()
            if username:
                server.login(username, password)
            server.send_message(message)
    except (OSError, smtplib.SMTPException) as exc:
        if os.getenv("ENV", "").lower() == "dev":
            logger.warning(
                "SMTP delivery failed for %s (%s); development email code for %s (%s): %s",
                recipient,
                type(exc).__name__,
                recipient,
                purpose,
                code,
            )
            return "console"
        logger.error("SMTP delivery failed (%s).", type(exc).__name__)
        raise RuntimeError("SMTP delivery failed.") from exc
    return "email"
