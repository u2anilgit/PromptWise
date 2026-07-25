"""replay_prompt_version runs a registered prompt's content through the
existing eval harness (offline record/dry-run mode -- no network), and can
optionally diff a second version's run for regression comparison."""
import asyncio
import json
import typing

import promptwise.server as s
from promptwise.db.models import MemoryManager


def _mm(tmp_path):
    mm = MemoryManager(str(tmp_path / "mem.db"))
    asyncio.run(mm.init())
    return mm


def _ctx(mm):
    class _FakeCtx:
        memory = mm
    return typing.cast(s.ServerContext, _FakeCtx())


def test_replay_prompt_version_missing_version_errors(tmp_path):
    mm = _mm(tmp_path)
    out = json.loads(asyncio.run(s._handle_replay_prompt_version(_ctx(mm), {"name": "greeting", "version": "1.0.0"})))
    assert "error" in out


def test_replay_prompt_version_runs_default_case_in_record_mode(tmp_path):
    mm = _mm(tmp_path)
    asyncio.run(mm.save_prompt("greeting", "Say hello politely.", version="1.0.0"))

    out = json.loads(asyncio.run(s._handle_replay_prompt_version(_ctx(mm), {"name": "greeting", "version": "1.0.0"})))
    assert out["name"] == "greeting"
    assert out["run"]["mode"] == "record"
    assert out["run"]["counts"]["cases"] == 1


def test_replay_prompt_version_uses_supplied_cases_and_scores_content(tmp_path):
    mm = _mm(tmp_path)
    asyncio.run(mm.save_prompt("greeting", "Hello there, friend!", version="1.0.0"))

    cases = [{"id": "polite", "expect_contains": ["hello"], "task_class": "greeting_check"}]
    out = json.loads(asyncio.run(s._handle_replay_prompt_version(
        _ctx(mm), {"name": "greeting", "version": "1.0.0", "cases": cases})))
    result = out["run"]["results"][0]
    assert result["case_id"] == "polite"
    # record-mode output embeds the resolved prompt text -- the substituted
    # registry content, not a placeholder that ignores it.
    assert "Hello there, friend!" in result["output"]


def test_replay_prompt_version_compare_version_runs_both(tmp_path):
    mm = _mm(tmp_path)
    asyncio.run(mm.save_prompt("greeting", "Hello A", version="1.0.0"))
    asyncio.run(mm.save_prompt("greeting", "Hello B", version="2.0.0"))

    out = json.loads(asyncio.run(s._handle_replay_prompt_version(
        _ctx(mm), {"name": "greeting", "version": "1.0.0", "compare_version": "2.0.0"})))
    assert "compare_run" in out
    assert out["compare_run"]["counts"]["cases"] == 1


def test_replay_prompt_version_compare_version_missing_reports_error_not_crash(tmp_path):
    mm = _mm(tmp_path)
    asyncio.run(mm.save_prompt("greeting", "Hello A", version="1.0.0"))

    out = json.loads(asyncio.run(s._handle_replay_prompt_version(
        _ctx(mm), {"name": "greeting", "version": "1.0.0", "compare_version": "9.9.9"})))
    assert "compare_error" in out
    assert "compare_run" not in out
