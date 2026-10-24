"""Tests d'integration : necessitent une base PostgreSQL vide dediee.

    export TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/parc_test
    uv run pytest

ATTENTION : le schema `eparc` de cette base est supprime puis recree a chaque session.
"""
import os
from pathlib import Path

import pytest

TEST_URL = os.environ.get("TEST_DATABASE_URL")
if TEST_URL:
    os.environ["DATABASE_URL"] = TEST_URL  # avant l'import de crud_api
    os.environ["AUTH_ENABLED"] = "false"
    os.environ["BOOTSTRAP_ADMIN_PASSWORD"] = ""

SQL_DIR = Path(__file__).resolve().parents[2] / "Base de données"
_first = "parc.sql" if (SQL_DIR / "parc.sql").exists() else "parc_1.sql"
SQL_FILES = [_first, "parc_2.sql", "parc_3.sql", "parc_4.sql", "parc_5.sql"]


def _sql(name: str) -> str:
    return (SQL_DIR / name).read_text(encoding="utf-8-sig")


def pytest_collection_modifyitems(config, items):
    if TEST_URL:
        return
    skip = pytest.mark.skip(reason="TEST_DATABASE_URL non defini")
    for item in items:
        item.add_marker(skip)


async def _run_scripts(*, reset: bool) -> None:
    """Execute les scripts SQL tels quels (plusieurs instructions : protocole simple d'asyncpg)."""
    import asyncpg

    conn = await asyncpg.connect(TEST_URL.replace("+asyncpg", "", 1))
    try:
        if reset:
            await conn.execute("DROP SCHEMA IF EXISTS eparc CASCADE")
        else:
            tables = await conn.fetchval(
                "SELECT string_agg(format('%I.%I', schemaname, tablename), ', ') "
                "FROM pg_tables WHERE schemaname = 'eparc'"
            )
            await conn.execute(f"TRUNCATE {tables} RESTART IDENTITY CASCADE")
        for name in SQL_FILES:
            await conn.execute(_sql(name))
    finally:
        await conn.close()


@pytest.fixture(scope="session", autouse=True)
async def _database():
    if not TEST_URL:
        yield
        return
    await _run_scripts(reset=True)
    yield
    from crud_api.core.database import engine

    await engine.dispose()


@pytest.fixture(autouse=True)
async def _clean(_database):
    """Vide toutes les tables avant chaque test, puis recharge les donnees initiales (roles, categories)."""
    if TEST_URL:
        await _run_scripts(reset=False)
    yield


@pytest.fixture
async def client():
    import httpx
    from crud_api.main import app

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test/api/v1") as c:
        yield c
