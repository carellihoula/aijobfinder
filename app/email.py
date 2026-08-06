import asyncio
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.config import settings
from app.logger import get_logger

logger = get_logger(__name__)


def _send_sync(to: str, msg: MIMEMultipart) -> None:
    context = ssl.create_default_context()
    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as smtp:
        smtp.ehlo()
        smtp.starttls(context=context)
        smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        smtp.sendmail(settings.SMTP_FROM, to, msg.as_string())


async def send_email(to: str, subject: str, html: str) -> None:
    if not settings.SMTP_HOST:
        logger.info("[email] DEV — To: %s | Subject: %s\n%s", to, subject, html)
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM}>"
    msg["To"] = to
    msg.attach(MIMEText(html, "html"))

    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _send_sync, to, msg)
        logger.info("[email] Sent to %s — %s", to, subject)
    except Exception as exc:
        logger.error("[email] Failed to send to %s: %s", to, exc)


async def send_verification_email(to: str, token: str) -> None:
    link = f"{settings.APP_URL}/verify-email?token={token}"
    html = f"""
    <div style="font-family:sans-serif;max-width:480px;margin:auto;padding:32px">
      <h2 style="color:#111">Vérifiez votre adresse e-mail</h2>
      <p style="color:#555">Cliquez sur le bouton ci-dessous pour activer votre compte AILFJ.</p>
      <a href="{link}" style="display:inline-block;margin:24px 0;padding:12px 24px;background:#6366f1;color:#fff;text-decoration:none;border-radius:8px;font-weight:600">
        Vérifier mon adresse e-mail
      </a>
      <p style="color:#999;font-size:12px">Ce lien expire dans 24 heures. Si vous n'avez pas créé de compte, ignorez cet e-mail.</p>
      <p style="color:#ccc;font-size:11px">{link}</p>
    </div>
    """
    await send_email(to, "Vérifiez votre adresse e-mail — AILFJ", html)


async def send_reset_email(to: str, token: str) -> None:
    link = f"{settings.APP_URL}/reset-password?token={token}"
    html = f"""
    <div style="font-family:sans-serif;max-width:480px;margin:auto;padding:32px">
      <h2 style="color:#111">Réinitialisation de mot de passe</h2>
      <p style="color:#555">Vous avez demandé à réinitialiser votre mot de passe. Cliquez ci-dessous :</p>
      <a href="{link}" style="display:inline-block;margin:24px 0;padding:12px 24px;background:#6366f1;color:#fff;text-decoration:none;border-radius:8px;font-weight:600">
        Réinitialiser mon mot de passe
      </a>
      <p style="color:#999;font-size:12px">Ce lien expire dans 1 heure. Si vous n'avez pas fait cette demande, ignorez cet e-mail.</p>
      <p style="color:#ccc;font-size:11px">{link}</p>
    </div>
    """
    await send_email(to, "Réinitialisation de mot de passe — AILFJ", html)
