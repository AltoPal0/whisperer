import html as html_lib
import os
import re
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

load_dotenv()

import mailer
from db import (
    Channel,
    SessionLocal,
    create_channel,
    delete_transcription,
    get_channel,
    init_db,
    list_all_transcriptions,
    list_channels,
    list_transcriptions,
    list_transcriptions_since,
    save_transcription,
)
from whisper_client import WhisperError, transcribe

FRONTEND_DIR = Path(__file__).parent.parent / "frontend"
ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "").strip()

CHANNEL_CODE_RE = re.compile(r"^[a-zA-Z0-9]{3,32}$")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(lifespan=lifespan)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _check_admin(token: str) -> None:
    if not ADMIN_TOKEN or token != ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="Accès refusé")


def _t_to_dict(t) -> dict:
    return {
        "id": t.id,
        "text": t.text,
        "language": t.language,
        "duration_ms": t.duration_ms,
        "created_at": t.created_at.isoformat(),
    }


# ── Santé ────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok"}


# ── Canal public ─────────────────────────────────────────────────────────────

@app.get("/api/channel/{code}")
async def api_get_channel(code: str):
    async with SessionLocal() as session:
        channel = await get_channel(session, code)
    if not channel:
        raise HTTPException(status_code=404, detail="Canal introuvable")
    return {"code": channel.code, "name": channel.name}


@app.post("/api/transcribe")
async def api_transcribe(
    audio: UploadFile,
    channel: str = Query(..., min_length=3, max_length=32),
    duration_ms: int = Query(default=0, ge=0),
):
    async with SessionLocal() as session:
        ch = await get_channel(session, channel)
    if not ch:
        raise HTTPException(status_code=404, detail="Canal introuvable")

    audio_bytes = await audio.read()
    filename = audio.filename or "audio.webm"

    try:
        result = await transcribe(audio_bytes, filename)
    except WhisperError as e:
        raise HTTPException(status_code=502, detail=str(e))

    async with SessionLocal() as session:
        row = await save_transcription(
            session,
            text=result["text"],
            language=result["language"],
            duration_ms=duration_ms,
            channel_code=channel,
        )

    return _t_to_dict(row)


@app.get("/api/transcriptions")
async def api_list(
    channel: str = Query(..., min_length=3, max_length=32),
    limit: int = Query(default=20, ge=1, le=50),
):
    async with SessionLocal() as session:
        ch = await get_channel(session, channel)
        if not ch:
            raise HTTPException(status_code=404, detail="Canal introuvable")
        rows = await list_transcriptions(session, channel, limit)
    return {"transcriptions": [_t_to_dict(r) for r in rows]}


@app.delete("/api/transcriptions/{transcription_id}", status_code=204)
async def api_delete(
    transcription_id: str,
    channel: str = Query(..., min_length=3, max_length=32),
):
    async with SessionLocal() as session:
        deleted = await delete_transcription(session, transcription_id, channel)
    if not deleted:
        raise HTTPException(status_code=404, detail="Introuvable")


# ── Admin — canaux ───────────────────────────────────────────────────────────

class CreateChannelRequest(BaseModel):
    code: str
    name: str


@app.post("/api/admin/channels", status_code=201)
async def api_create_channel(body: CreateChannelRequest, token: str = Query(...)):
    _check_admin(token)
    if not CHANNEL_CODE_RE.match(body.code):
        raise HTTPException(status_code=422, detail="Le code doit être alphanumérique (3–32 caractères)")
    async with SessionLocal() as session:
        existing = await get_channel(session, body.code)
        if existing:
            raise HTTPException(status_code=409, detail="Ce code est déjà utilisé")
        channel = await create_channel(session, code=body.code, name=body.name)
    return {"code": channel.code, "name": channel.name}


@app.get("/api/admin/channels")
async def api_list_channels(token: str = Query(...)):
    _check_admin(token)
    async with SessionLocal() as session:
        channels = await list_channels(session)
    return {"channels": [{"code": c.code, "name": c.name, "created_at": c.created_at.isoformat()} for c in channels]}


# ── Admin — transcriptions ────────────────────────────────────────────────────

@app.get("/api/admin/transcriptions")
async def api_admin_list(token: str = Query(...), channel: str = Query(default="")):
    _check_admin(token)
    async with SessionLocal() as session:
        if channel:
            rows = await list_transcriptions(session, channel, limit=500)
        else:
            rows = await list_all_transcriptions(session)
    return {
        "transcriptions": [
            {**_t_to_dict(r), "channel_code": r.channel_code}
            for r in rows
        ]
    }


# ── Admin — digest ───────────────────────────────────────────────────────────

@app.post("/api/admin/send-digest")
async def api_send_digest(token: str = Query(...)):
    _check_admin(token)

    if not mailer.is_configured():
        raise HTTPException(
            status_code=503,
            detail="Email non configuré (SMTP_HOST, SMTP_USER, SMTP_PASS, DIGEST_TO requis)",
        )

    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    date_str = today.strftime("%Y-%m-%d")

    async with SessionLocal() as session:
        transcriptions = await list_transcriptions_since(session, today)
        channels = {c.code: c for c in await list_channels(session)}

    # Grouper par canal
    by_channel: dict[str, list] = defaultdict(list)
    for t in transcriptions:
        by_channel[t.channel_code].append(_t_to_dict(t))

    if not by_channel:
        return {"sent": 0, "date": date_str, "message": "Aucune transcription aujourd'hui"}

    sent = 0
    errors = []
    for code, items in by_channel.items():
        channel_name = channels[code].name if code in channels else code
        try:
            await mailer.send_channel_digest(code, channel_name, date_str, items)
            sent += 1
        except Exception as e:
            errors.append({"channel": code, "error": str(e)})

    return {"sent": sent, "date": date_str, "errors": errors}


# ── Serve channel app ─────────────────────────────────────────────────────────

@app.get("/manifest/c/{code}")
async def channel_manifest(code: str):
    async with SessionLocal() as session:
        channel = await get_channel(session, code)
    if not channel:
        raise HTTPException(status_code=404, detail="Canal introuvable")
    manifest = {
        "id": f"/c/{code}",
        "name": channel.name,
        "short_name": channel.name,
        "description": "Dictaphone instantané propulsé par Whisper",
        "start_url": f"/c/{code}",
        "display": "standalone",
        "orientation": "portrait",
        "background_color": "#080810",
        "theme_color": "#080810",
        "icons": [
            {"src": "/icons/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any maskable"},
            {"src": "/icons/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any maskable"},
        ],
    }
    return JSONResponse(content=manifest, headers={
        "Content-Type": "application/manifest+json",
        "Cache-Control": "no-cache",
    })


@app.get("/c/{code}")
async def channel_app(code: str):
    async with SessionLocal() as session:
        channel = await get_channel(session, code)
    if not channel:
        raise HTTPException(status_code=404, detail="Canal introuvable")
    safe_name = html_lib.escape(channel.name, quote=True)
    html_content = (FRONTEND_DIR / "index.html").read_text(encoding="utf-8")
    html_content = html_content.replace('href="/manifest.json"', f'href="/manifest/c/{code}"')
    html_content = html_content.replace(
        '<meta name="apple-mobile-web-app-title" content="TAIC app" />',
        f'<meta name="apple-mobile-web-app-title" content="{safe_name}" />',
    )
    html_content = html_content.replace('<title>TAIC app</title>', f'<title>{safe_name}</title>')
    return HTMLResponse(content=html_content)


# Sert le frontend statique — doit être monté après les routes API
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
