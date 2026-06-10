"""Tests for CompressionEngine."""

from promptwise_v3.core.compression import CompressionEngine


def test_compress_removes_filler():
    c = CompressionEngine()
    result = c.compress("I think this is basically a good idea, actually.")
    assert result.tokens_saved > 0
    assert len(result.compressed) > 0


def test_compress_preserves_code():
    c = CompressionEngine()
    text = """So basically, here's a function:
```python
def hello():
    print("Hello, world!")
```"""
    result = c.compress(text)
    assert "def hello():" in result.compressed
    assert "print" in result.compressed


def test_compress_empty():
    c = CompressionEngine()
    result = c.compress("")
    assert result.compressed == ""
    assert result.tokens_saved == 0


def test_compress_no_filler():
    c = CompressionEngine()
    text = "Short and clear."
    result = c.compress(text)
    assert result.compressed == text


def test_compress_removes_pleasantries():
    c = CompressionEngine()
    result = c.compress("Sure, no problem! Here you go:")
    assert "Here you go:" in result.compressed


def test_compress_tracks_rules():
    c = CompressionEngine()
    result = c.compress("I think maybe this is basically good")
    assert len(result.rules_applied) > 0
