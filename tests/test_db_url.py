import asyncio

from promptwise.config import AppConfig, IdentityConfig
from promptwise.db.models import get_db_url, init_db, MemoryManager, db_health


def test_get_db_url_defaults_to_local_sqlite(tmp_path, monkeypatch):
    monkeypatch.setattr("promptwise.db.models.get_db_path", lambda: tmp_path / "promptwise.db")
    url = get_db_url(AppConfig())
    assert url == f"sqlite+aiosqlite:///{tmp_path / 'promptwise.db'}"


def test_get_db_url_uses_config_db_url_when_set():
    cfg = AppConfig(identity=IdentityConfig(db_url="postgresql+asyncpg://user:pass@host/promptwise"))
    assert get_db_url(cfg) == "postgresql+asyncpg://user:pass@host/promptwise"


def test_init_db_accepts_a_full_sqlite_url_without_double_wrapping(tmp_path, monkeypatch):
    monkeypatch.setattr("promptwise.db.models.get_db_path", lambda: tmp_path / "promptwise.db")

    async def _run():
        url = get_db_url(AppConfig())
        returned = await init_db(url)
        mm = MemoryManager(returned)
        await mm.init()
        return returned

    returned = asyncio.run(_run())
    assert returned == f"sqlite+aiosqlite:///{tmp_path / 'promptwise.db'}"


def test_db_health_reports_reachable_for_local_sqlite(tmp_path, monkeypatch):
    monkeypatch.setattr("promptwise.db.models.get_db_path", lambda: tmp_path / "promptwise.db")

    async def _run():
        url = get_db_url(AppConfig())
        await init_db(url)
        return await db_health(url)

    health = asyncio.run(_run())
    assert health == {"backend": "sqlite", "reachable": True, "warning": None}


def test_db_health_reports_unreachable_postgres_without_raising():
    async def _run():
        return await db_health("postgresql+asyncpg://user:pass@nonexistent-host-xyz/promptwise")

    health = asyncio.run(_run())
    assert health["backend"] == "postgresql"
    assert health["reachable"] is False
    assert health["warning"]


def test_init_db_falls_back_to_local_sqlite_when_postgres_unreachable(tmp_path, monkeypatch):
    monkeypatch.setattr("promptwise.db.models.get_db_path", lambda: tmp_path / "promptwise.db")

    async def _run():
        return await init_db("postgresql+asyncpg://user:pass@nonexistent-host-xyz/promptwise")

    returned = asyncio.run(_run())
    assert returned == f"sqlite+aiosqlite:///{tmp_path / 'promptwise.db'}"
    assert (tmp_path / "promptwise.db").exists()
