"""Tests for Batcher."""

from promptwise_v3.core.batcher import Batcher


def test_batch_single_task():
    b = Batcher()
    result = b.batch(["task 1"])
    assert result.batched_prompt == "task 1"
    assert result.saving_pct == 0.0


def test_batch_multiple_tasks():
    b = Batcher()
    result = b.batch([f"task {i}" for i in range(5)])
    assert "task 1" in result.batched_prompt
    assert "task 2" in result.batched_prompt
    assert result.saving_pct > 0


def test_batch_empty():
    b = Batcher()
    result = b.batch([])
    assert result.batched_prompt == ""
    assert result.saving_pct == 0.0


def test_batch_two_tasks():
    b = Batcher()
    result = b.batch(["write code", "review code"])
    assert result.saving_pct >= 0
    assert result.individual_tokens > 0
