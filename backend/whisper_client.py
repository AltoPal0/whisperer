import os

import httpx

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
WHISPER_URL = "https://api.openai.com/v1/audio/transcriptions"
MAX_AUDIO_BYTES = 25 * 1024 * 1024  # 25 MB — limite Whisper


class WhisperError(Exception):
    pass


async def transcribe(audio_bytes: bytes, filename: str) -> dict:
    if len(audio_bytes) > MAX_AUDIO_BYTES:
        raise WhisperError(f"Fichier trop grand : {len(audio_bytes)} octets (max 25 MB)")

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            WHISPER_URL,
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
            files={"file": (filename, audio_bytes, _guess_mime(filename))},
            data={"model": "whisper-1", "response_format": "verbose_json"},
        )

    if response.status_code != 200:
        raise WhisperError(f"Whisper API erreur {response.status_code}: {response.text}")

    data = response.json()
    return {
        "text": data.get("text", "").strip(),
        "language": data.get("language", ""),
    }


def _guess_mime(filename: str) -> str:
    ext = filename.rsplit(".", 1)[-1].lower()
    return {
        "webm": "audio/webm",
        "mp4": "audio/mp4",
        "m4a": "audio/mp4",
        "wav": "audio/wav",
        "ogg": "audio/ogg",
    }.get(ext, "audio/webm")
