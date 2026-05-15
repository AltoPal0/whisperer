import asyncio
import json
import logging
import os
import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

log = logging.getLogger(__name__)

SMTP_HOST = os.environ.get("SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "465"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASS = os.environ.get("SMTP_PASS", "")
SMTP_FROM = os.environ.get("SMTP_FROM", "") or SMTP_USER
DIGEST_TO = os.environ.get("DIGEST_TO", "")


def is_configured() -> bool:
    return bool(SMTP_HOST and SMTP_USER and SMTP_PASS and DIGEST_TO)


async def send_channel_digest(channel_code: str, channel_name: str, date_str: str, transcriptions: list[dict]) -> None:
    payload = {
        "channel": channel_code,
        "channel_name": channel_name,
        "date": date_str,
        "count": len(transcriptions),
        "transcriptions": transcriptions,
    }
    body = json.dumps(payload, ensure_ascii=False, indent=2)
    subject = f"@{channel_code}"

    def _send():
        log.info("SMTP: connexion à %s:%s", SMTP_HOST, SMTP_PORT)
        msg = MIMEMultipart()
        msg["From"] = SMTP_FROM
        msg["To"] = DIGEST_TO
        msg["Subject"] = subject
        msg.attach(MIMEText(f"{len(transcriptions)} note(s) — voir pièce jointe.", "plain", "utf-8"))
        attachment = MIMEApplication(body.encode("utf-8"), Name=f"{channel_code}_{date_str}.json")
        attachment["Content-Disposition"] = f'attachment; filename="{channel_code}_{date_str}.json"'
        msg.attach(attachment)

        if SMTP_PORT == 465:
            with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as smtp:
                smtp.set_debuglevel(1)
                smtp.login(SMTP_USER, SMTP_PASS)
                smtp.send_message(msg)
        else:
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as smtp:
                smtp.set_debuglevel(1)
                smtp.starttls()
                smtp.login(SMTP_USER, SMTP_PASS)
                smtp.send_message(msg)

        log.info("SMTP: email envoyé → %s (sujet: %s)", DIGEST_TO, subject)

    await asyncio.to_thread(_send)
