import os
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Index, Integer, String, Text, delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

CLOUD_SQL_CONNECTION_NAME = os.environ.get("CLOUD_SQL_CONNECTION_NAME", "")
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite+aiosqlite:///./whisperer.db")

if CLOUD_SQL_CONNECTION_NAME:
    from google.cloud.sql.connector import Connector

    _connector = Connector()

    async def _getconn():
        return await _connector.connect_async(
            CLOUD_SQL_CONNECTION_NAME,
            "asyncpg",
            user=os.environ["DB_USER"],
            password=os.environ["DB_PASS"],
            db=os.environ.get("DB_NAME", "whisperer"),
        )

    # Pool réduit par défaut : l'instance Cloud SQL partagée (db-f1-micro) n'accepte que 25 connexions
    engine = create_async_engine(
        "postgresql+asyncpg://",
        async_creator=_getconn,
        echo=False,
        pool_size=int(os.environ.get("DB_POOL_SIZE", "2")),
        max_overflow=int(os.environ.get("DB_MAX_OVERFLOW", "2")),
    )
else:
    engine = create_async_engine(DATABASE_URL, echo=False)

SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class Channel(Base):
    __tablename__ = "channels"

    code = Column(String(32), primary_key=True)
    name = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


class Transcription(Base):
    __tablename__ = "transcriptions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    text = Column(Text, nullable=False)
    language = Column(String(10))
    duration_ms = Column(Integer)
    channel_code = Column(String(32), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("idx_transcriptions_channel_created", "channel_code", "created_at"),
    )


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


# ── Channels ────────────────────────────────────────────────────────────────

async def create_channel(session: AsyncSession, code: str, name: str) -> Channel:
    channel = Channel(code=code, name=name)
    session.add(channel)
    await session.commit()
    await session.refresh(channel)
    return channel


async def get_channel(session: AsyncSession, code: str) -> Channel | None:
    result = await session.execute(select(Channel).where(Channel.code == code))
    return result.scalar_one_or_none()


async def list_channels(session: AsyncSession) -> list[Channel]:
    result = await session.execute(select(Channel).order_by(Channel.created_at.asc()))
    return list(result.scalars().all())


# ── Transcriptions ───────────────────────────────────────────────────────────

async def save_transcription(session: AsyncSession, text: str, language: str, duration_ms: int, channel_code: str) -> Transcription:
    row = Transcription(text=text, language=language, duration_ms=duration_ms, channel_code=channel_code)
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


async def list_transcriptions(session: AsyncSession, channel_code: str, limit: int = 20) -> list[Transcription]:
    result = await session.execute(
        select(Transcription)
        .where(Transcription.channel_code == channel_code)
        .order_by(Transcription.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def list_transcriptions_since(session: AsyncSession, since: datetime) -> list[Transcription]:
    result = await session.execute(
        select(Transcription)
        .where(Transcription.created_at >= since)
        .order_by(Transcription.channel_code, Transcription.created_at.asc())
    )
    return list(result.scalars().all())


async def list_all_transcriptions(session: AsyncSession, limit: int = 500) -> list[Transcription]:
    result = await session.execute(
        select(Transcription)
        .order_by(Transcription.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def delete_transcription(session: AsyncSession, transcription_id: str, channel_code: str) -> bool:
    result = await session.execute(
        delete(Transcription)
        .where(Transcription.id == transcription_id, Transcription.channel_code == channel_code)
        .returning(Transcription.id)
    )
    await session.commit()
    return result.rowcount > 0
