# Session SQLAlchemy, connexion Postgres
from collections.abc import AsyncIterator
import ipaddress

from fastapi import Request
from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from crud_api.config import get_settings

settings = get_settings()


class Base(DeclarativeBase):
    # Toutes les tables vivent dans le schema `eparc` (voir parc.sql)
    metadata = MetaData(schema=settings.db_schema)


engine = create_async_engine(settings.database_url, echo=settings.db_echo, pool_pre_ping=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_db(request: Request) -> AsyncIterator[AsyncSession]:
    """Une session par requete. `session.info` transporte le contexte d'audit (IP, utilisateur)."""
    async with SessionLocal() as session:
        host = request.client.host if request.client else None
        try:
            session.info["ip"] = str(ipaddress.ip_address(host)) if host else None
        except ValueError:
            session.info["ip"] = None
        yield session
