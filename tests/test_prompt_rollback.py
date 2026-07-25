"""rollback_prompt must restore an old version's content as the new current
row without mutating or deleting any existing history row (migration-safety:
PromptModel gets no new column, so 'current' is defined purely by latest ts)."""
import asyncio

from promptwise.db.models import MemoryManager


def _mm(tmp_path):
    mm = MemoryManager(str(tmp_path / "mem.db"))
    asyncio.run(mm.init())
    return mm


def test_get_prompt_version_returns_none_when_missing(tmp_path):
    mm = _mm(tmp_path)
    assert asyncio.run(mm.get_prompt_version("greeting", "1.0.0")) is None


def test_get_prompt_version_returns_latest_matching_row(tmp_path):
    mm = _mm(tmp_path)
    asyncio.run(mm.save_prompt("greeting", "Hello A", version="1.0.0"))
    asyncio.run(mm.save_prompt("greeting", "Hello A (fixed typo)", version="1.0.0"))
    row = asyncio.run(mm.get_prompt_version("greeting", "1.0.0"))
    assert row["content"] == "Hello A (fixed typo)"


def test_rollback_prompt_returns_none_when_version_missing(tmp_path):
    mm = _mm(tmp_path)
    asyncio.run(mm.save_prompt("greeting", "Hello A", version="1.0.0"))
    assert asyncio.run(mm.rollback_prompt("greeting", "9.9.9")) is None


def test_rollback_prompt_restores_old_content_as_new_current_row(tmp_path):
    mm = _mm(tmp_path)
    asyncio.run(mm.save_prompt("greeting", "Hello A", version="1.0.0"))
    asyncio.run(mm.save_prompt("greeting", "Hello B (broken)", version="2.0.0"))

    result = asyncio.run(mm.rollback_prompt("greeting", "1.0.0"))
    assert result is not None
    assert result["new_prompt_id"] != result["source_prompt_id"]

    all_rows = asyncio.run(mm.search_prompts("greeting"))
    exact = [p for p in all_rows if p["name"] == "greeting"]
    # 2 original saves + 1 rollback insert -- nothing deleted, nothing mutated.
    assert len(exact) == 3
    # search_prompts orders by ts desc, so index 0 is now-current.
    assert exact[0]["content"] == "Hello A"
    assert exact[0]["version"] == "1.0.0"


def test_rollback_prompt_does_not_mutate_existing_rows(tmp_path):
    mm = _mm(tmp_path)
    asyncio.run(mm.save_prompt("greeting", "Hello A", version="1.0.0"))
    asyncio.run(mm.save_prompt("greeting", "Hello B (broken)", version="2.0.0"))
    before = sorted(asyncio.run(mm.search_prompts("greeting")), key=lambda p: p["version"])

    asyncio.run(mm.rollback_prompt("greeting", "1.0.0"))

    after = sorted(asyncio.run(mm.search_prompts("greeting")), key=lambda p: p["version"])
    # The original two rows (by version+content pairing) are both still present, untouched.
    for b in before:
        assert any(a["version"] == b["version"] and a["content"] == b["content"] for a in after)
