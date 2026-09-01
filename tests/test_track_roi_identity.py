import asyncio
import json

from promptwise.core.identity import Identity
from promptwise.db.models import MemoryManager, init_db
import promptwise.handlers.roi as roi_mod


class _FakeROI:
    def calculate(self, **kwargs):
        from types import SimpleNamespace
        return SimpleNamespace(roi_ratio=2.0, estimated_time_saved_min=30.0,
                                productivity_score=1.0, total_cost_usd=1.5,
                                tokens_saved=kwargs.get("tokens_saved", 0))


class _FakeCtx:
    def __init__(self, memory, identity):
        self.roi = _FakeROI()
        self.memory = memory
        self.identity = identity


def test_track_roi_persists_identity_username_and_groups(tmp_path, monkeypatch):
    monkeypatch.setattr("promptwise.db.models.get_db_path", lambda: tmp_path / "promptwise.db")

    async def _run():
        db_path = await init_db()
        mm = MemoryManager(db_path)
        await mm.init()
        identity = Identity(username="jdoe", domain="CORP", groups=["PromptWise-Admins"], email="", source="env")
        ctx = _FakeCtx(mm, identity)
        await roi_mod._handle_track_roi(ctx, {"session_id": "s1", "total_cost_usd": 1.5, "tokens_saved": 100, "calls": 1})
        stats = await mm.get_roi_stats(period="weekly")
        return stats

    stats = asyncio.run(_run())
    assert stats[-1]["developer"] == "jdoe"
    assert stats[-1]["role"] == "AD:PromptWise-Admins"


def test_track_roi_falls_back_to_anonymous_dev_when_no_identity(tmp_path, monkeypatch):
    monkeypatch.setattr("promptwise.db.models.get_db_path", lambda: tmp_path / "promptwise.db")

    async def _run():
        db_path = await init_db()
        mm = MemoryManager(db_path)
        await mm.init()
        ctx = _FakeCtx(mm, None)
        await roi_mod._handle_track_roi(ctx, {"session_id": "s1", "total_cost_usd": 1.5, "tokens_saved": 100, "calls": 1})
        return await mm.get_roi_stats(period="weekly")

    stats = asyncio.run(_run())
    assert stats[-1]["developer"] == "Anonymous"
    assert stats[-1]["role"] == "Dev"
