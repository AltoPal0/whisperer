import asyncio
import json
import logging
import os

import httpx

log = logging.getLogger(__name__)

RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
SMTP_FROM = os.environ.get("SMTP_FROM", "")
DIGEST_TO = os.environ.get("DIGEST_TO", "")


def is_configured() -> bool:
    return bool(RESEND_API_KEY and SMTP_FROM and DIGEST_TO)


async def send_channel_digest(channel_code: str, channel_name: str, date_str: str, transcriptions: list[dict]) -> None:
    payload = {
        "channel": channel_code,
        "channel_name": channel_name,
        "date": date_str,
        "count": len(transcriptions),
        "transcriptions": transcriptions,
    }
    body = json.dumps(payload, ensure_ascii=False, indent=2)
    filename = f"{channel_code}_{date_str}.json"
    subject = f"@{channel_code}"

    import base64
    attachment_b64 = base64.b64encode(body.encode("utf-8")).decode("ascii")

    resend_payload = {
        "from": SMTP_FROM,
        "to": [DIGEST_TO],
        "subject": subject,
        "text": f"{len(transcriptions)} note(s) — voir pièce jointe.",
        "attachments": [
            {
                "filename": filename,
                "content": attachment_b64,
            }
        ],
    }

    log.info("Resend: envoi digest %s → %s", channel_code, DIGEST_TO)
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {RESEND_API_KEY}", "Content-Type": "application/json"},
            json=resend_payload,
            timeout=30,
        )
        response.raise_for_status()
        log.info("Resend: email envoyé, id=%s", response.json().get("id"))
