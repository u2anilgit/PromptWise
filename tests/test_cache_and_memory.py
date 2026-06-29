"""Safe enhancements — plan_cache min-token gate + real savings; memory upsert/ranking."""
import asyncio

from promptwise.config import load_config
from promptwise.core.cache_planner import CachePlanner
from promptwise.db.models import MemoryManager


# ── plan_cache ───────────────────────────────────────────────────────────────
def _planner():
    return CachePlanner(load_config("."))


def test_small_prefix_not_cached(_=None):
    p = _planner()
    # ~25 tokens of prefix — below the 1024-token provider minimum.
    msgs = [{"role": "system", "content": "short system preamble here"},
            {"role": "user", "content": "hello"}]
    res = p.plan(msgs, expected_reuse_count=10)
    assert res.breakpoints == []
    assert res.savings_pct == 0.0


def test_large_prefix_is_cached_with_real_savings():
    p = _planner()
    big = "word " * 5000  # ~6k tokens of cacheable prefix
    msgs = [{"role": "system", "content": big, "label": "big-context"},
            {"role": "user", "content": "now answer the question"}]
    res = p.plan(msgs, expected_reuse_count=5)
    assert res.breakpoints, "large reusable prefix should be cacheable"
    bp = res.breakpoints[0]
    assert bp["cacheable_tokens"] >= 1024
    assert res.savings_pct > 0.0


def test_haiku_higher_min_threshold():
    p = _planner()
    # ~1500 tokens: cacheable for sonnet (min 1024), NOT for haiku (min 2048).
    mid = "word " * 1200
    msgs = [{"role": "system", "content": mid}, {"role": "user", "content": "go"}]
    sonnet = p.plan(msgs, expected_reuse_count=5, model="claude-sonnet-4-6")
    haiku = p.plan(msgs, expected_reuse_count=5, model="claude-haiku-4-5-20251001")
    assert sonnet.breakpoints and not haiku.breakpoints


def test_no_reuse_no_breakpoints():
    p = _planner()
    msgs = [{"role": "system", "content": "word " * 5000}, {"role": "user", "content": "x"}]
    assert p.plan(msgs, expected_reuse_count=1).breakpoints == []


# ── memory upsert + ranking ──────────────────────────────────────────────────
def _mm(tmp_path):
    mm = MemoryManager(str(tmp_path / "mem.db"))
    asyncio.run(mm.init())
    return mm


def test_save_fact_upserts(tmp_path):
    mm = _mm(tmp_path)

    async def go():
        await mm.save_fact("deploy_target", "staging", scope="org")
        await mm.save_fact("deploy_target", "production", scope="org")
        return await mm.query_facts("deploy_target")

    facts = asyncio.run(go())
    assert len(facts) == 1
    assert facts[0]["value"] == "production"


def test_save_fact_distinct_scopes_kept(tmp_path):
    mm = _mm(tmp_path)

    async def go():
        await mm.save_fact("k", "v-org", scope="org")
        await mm.save_fact("k", "v-user", scope="user")
        return await mm.query_facts("k")

    facts = asyncio.run(go())
    assert {f["value"] for f in facts} == {"v-org", "v-user"}


def test_query_facts_ranks_by_overlap(tmp_path):
    mm = _mm(tmp_path)

    async def go():
        await mm.save_fact("alpha", "database connection pooling note", scope="org")
        await mm.save_fact("beta", "database sharding and database replicas", scope="org")
        return await mm.query_facts("database")

    facts = asyncio.run(go())
    # 'beta' mentions database twice -> ranked first
    assert facts[0]["key"] == "beta"
