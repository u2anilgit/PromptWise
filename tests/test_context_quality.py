import time

import pytest

from promptwise.core.context_ranker import score_context_quality


def test_structured_shard_with_heading_scores_high():
    shards = [{"id": "s1", "text": "# Heading\n- one\n- two"}]
    result = score_context_quality(shards)
    assert result["shards"][0]["structure_score"] == 1.0


def test_unstructured_prose_scores_zero_structure():
    shards = [{"id": "s1", "text": "just a plain paragraph with no bullets or headings whatsoever here today"}]
    result = score_context_quality(shards)
    assert result["shards"][0]["structure_score"] == 0.0


def test_trailing_ellipsis_flags_truncated():
    shards = [{"id": "s1", "text": "This shard trails off..."}]
    result = score_context_quality(shards)
    assert result["shards"][0]["truncated"] is True
    assert result["shards"][0]["completeness_score"] == 0.4


def test_short_shard_without_terminal_punctuation_not_penalized():
    """Short shards (<=200 chars) aren't required to end in punctuation --
    plenty of real titles/labels/list items legitimately don't."""
    shards = [{"id": "s1", "text": "a short label with no period at the end"}]
    result = score_context_quality(shards)
    assert result["shards"][0]["truncated"] is False
    assert result["shards"][0]["completeness_score"] == 1.0


def test_no_source_path_yields_no_staleness_penalty():
    shards = [{"id": "s1", "text": "some text"}]
    result = score_context_quality(shards)
    entry = result["shards"][0]
    assert entry["staleness_days"] is None
    assert entry["freshness_score"] == 1.0


def test_staleness_scores_from_file_mtime(tmp_path):
    doc = tmp_path / "doc.md"
    doc.write_text("content", encoding="utf-8")
    mtime = doc.stat().st_mtime
    shards = [{"id": "s1", "text": "some text", "source_path": str(doc)}]
    result = score_context_quality(shards, now=mtime + 30 * 86400)
    entry = result["shards"][0]
    assert entry["staleness_days"] == 30.0
    assert entry["freshness_score"] == 0.9178


def test_missing_source_file_does_not_raise():
    shards = [{"id": "s1", "text": "some text", "source_path": "/nonexistent/path/does/not/exist.md"}]
    result = score_context_quality(shards)
    assert result["shards"][0]["staleness_days"] is None
    assert result["shards"][0]["freshness_score"] == 1.0


def test_high_overlap_with_negation_marker_flags_contradiction():
    shards = [
        {"id": "a", "text": "the api endpoint accepts json payloads and requires an auth token"},
        {"id": "b", "text": "the api endpoint is deprecated and requires an auth token still"},
    ]
    result = score_context_quality(shards)
    by_id = {s["id"]: s for s in result["shards"]}
    assert by_id["a"]["contradicts"] == ["b"]
    assert by_id["b"]["contradicts"] == ["a"]
    assert by_id["a"]["quality_score"] == 0.4667


def test_low_overlap_shards_never_flagged():
    shards = [
        {"id": "a", "text": "the weather today is sunny and warm"},
        {"id": "b", "text": "quarterly revenue grew by twelve percent"},
    ]
    result = score_context_quality(shards)
    for entry in result["shards"]:
        assert entry["contradicts"] == []


def test_duplicate_shard_ids_raise_value_error():
    shards = [{"id": "a", "text": "one"}, {"id": "a", "text": "two"}]
    with pytest.raises(ValueError):
        score_context_quality(shards)


def test_empty_shard_list_returns_empty():
    assert score_context_quality([]) == {"shards": []}


import json

import pytest

import promptwise.handlers.policy_intel as policy_intel_handlers


class _FakeCtx:
    pass


@pytest.mark.asyncio
async def test_score_context_quality_handler_returns_shards():
    out = await policy_intel_handlers._handle_score_context_quality(
        _FakeCtx(), {"shards": [{"id": "s1", "text": "# Heading\n- one"}]})
    result = json.loads(out)
    assert result["shards"][0]["id"] == "s1"
    assert result["shards"][0]["structure_score"] == 1.0


@pytest.mark.asyncio
async def test_score_context_quality_handler_duplicate_id_returns_error_object():
    out = await policy_intel_handlers._handle_score_context_quality(
        _FakeCtx(), {"shards": [{"id": "a", "text": "x"}, {"id": "a", "text": "y"}]})
    result = json.loads(out)
    assert result["type"] == "DuplicateShardId"
