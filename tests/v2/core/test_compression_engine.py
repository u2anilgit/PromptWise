import pytest
from promptwise_v2.core.compression_engine import CompressionEngine


@pytest.fixture
def engine():
    return CompressionEngine()


def test_removes_articles(engine):
    result = engine.compress("The quick brown fox jumps over the lazy dog")
    assert "The " not in result.compressed
    assert "the " not in result.compressed


def test_removes_filler(engine):
    result = engine.compress("I was just wondering if you could basically help me")
    assert "just" not in result.compressed
    assert "basically" not in result.compressed


def test_removes_pleasantries(engine):
    result = engine.compress("Sure! I'd be happy to help you with that today.")
    assert "Sure" not in result.compressed


def test_removes_hedging(engine):
    result = engine.compress("This might potentially be something that could perhaps work")
    assert "might" not in result.compressed
    assert "perhaps" not in result.compressed


def test_saving_pct_positive_on_verbose(engine):
    result = engine.compress(
        "Sure, I'd be really happy to help you with that! "
        "The quick brown fox jumps over the lazy dog. "
        "This might potentially be something."
    )
    assert result.saving_pct > 0


def test_rules_applied_listed(engine):
    result = engine.compress("Sure! The quick fox.")
    assert len(result.rules_applied) > 0


def test_code_blocks_preserved(engine):
    code = "```python\nthe_var = 'hello'\n```"
    result = engine.compress(f"Sure! Here is the code:\n{code}")
    assert "the_var" in result.compressed


def test_empty_input(engine):
    result = engine.compress("")
    assert result.compressed == ""
    assert result.saving_pct == 0.0
