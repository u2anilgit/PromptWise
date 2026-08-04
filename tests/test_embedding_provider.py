"""Phase 19 / candidate D2 -- embedding provider: fail-open behavior,
network gating, config parsing, and the cost/router isolation guarantee.

This test environment deliberately does NOT have the `embeddings` extras
group (fastembed) installed -- that's not a test-setup gap, it's the
actual base-install condition every non-opted-in user runs in, and it's
exactly the path that most needs to be proven safe. Where a test needs to
exercise the "dependency present" branches, it does so by monkeypatching
FASTEMBED_AVAILABLE / TextEmbedding rather than requiring a real install
and a real (network-gated) model download.
"""
import ast
from pathlib import Path

import pytest

from promptwise.embeddings.provider import (
    EmbeddingConfig,
    EmbeddingProvider,
    cosine_similarity,
    load_embedding_config,
)
import promptwise.embeddings.provider as provider_mod


def test_dependency_not_installed_in_base_test_env():
    # Ground truth for every other test in this file: the base install
    # (no `embeddings` extra) really does leave fastembed unimportable.
    assert provider_mod.FASTEMBED_AVAILABLE is False


def test_embed_fails_open_without_dependency():
    p = EmbeddingProvider()
    assert p.embed("hello world") is None


def test_embed_many_fails_open_without_dependency():
    p = EmbeddingProvider()
    out = p.embed_many(["a", "b", "c"])
    assert out == [None, None, None]


def test_status_reports_not_ready_without_dependency():
    p = EmbeddingProvider()
    status = p.status()
    assert status["dependency_installed"] is False
    assert status["ready"] is False
    assert status["model_cached_locally"] is False


def test_default_config_is_network_off():
    cfg = load_embedding_config(Path("/nonexistent/embeddings.yaml"))
    assert cfg.allow_network is False
    assert cfg.model_name == provider_mod.DEFAULT_MODEL_NAME
    assert cfg.model_path is None


def test_config_parses_from_yaml(tmp_path):
    cfg_file = tmp_path / "embeddings.yaml"
    cfg_file.write_text(
        "allow_network: true\nmodel_name: some/other-model\nmodel_path: /models/foo\n",
        encoding="utf-8",
    )
    cfg = load_embedding_config(cfg_file)
    assert cfg.allow_network is True
    assert cfg.model_name == "some/other-model"
    assert cfg.model_path == "/models/foo"


def test_malformed_config_falls_back_to_defaults(tmp_path):
    cfg_file = tmp_path / "embeddings.yaml"
    cfg_file.write_text("not: [valid: yaml: at: all", encoding="utf-8")
    cfg = load_embedding_config(cfg_file)
    assert cfg == EmbeddingConfig()


def test_would_be_ready_false_when_dependency_missing():
    p = EmbeddingProvider(EmbeddingConfig(allow_network=True))
    assert p._would_be_ready() is False  # dependency itself is the blocker here


def test_would_be_ready_false_when_network_off_and_nothing_cached(monkeypatch):
    monkeypatch.setattr(provider_mod, "FASTEMBED_AVAILABLE", True)
    monkeypatch.setattr(provider_mod, "_model_cached_locally", lambda cfg: False)
    p = EmbeddingProvider(EmbeddingConfig(allow_network=False))
    assert p._would_be_ready() is False


def test_would_be_ready_true_when_model_already_cached(monkeypatch):
    monkeypatch.setattr(provider_mod, "FASTEMBED_AVAILABLE", True)
    monkeypatch.setattr(provider_mod, "_model_cached_locally", lambda cfg: True)
    p = EmbeddingProvider(EmbeddingConfig(allow_network=False))
    assert p._would_be_ready() is True  # cached -> no network needed regardless


def test_would_be_ready_true_with_explicit_model_path(tmp_path, monkeypatch):
    monkeypatch.setattr(provider_mod, "FASTEMBED_AVAILABLE", True)
    model_dir = tmp_path / "local-model"
    model_dir.mkdir()
    p = EmbeddingProvider(EmbeddingConfig(allow_network=False, model_path=str(model_dir)))
    assert p._would_be_ready() is True


def test_would_be_ready_false_with_missing_model_path(tmp_path, monkeypatch):
    monkeypatch.setattr(provider_mod, "FASTEMBED_AVAILABLE", True)
    p = EmbeddingProvider(EmbeddingConfig(model_path=str(tmp_path / "does_not_exist")))
    assert p._would_be_ready() is False


def test_ensure_model_never_raises_when_underlying_call_fails(monkeypatch):
    monkeypatch.setattr(provider_mod, "FASTEMBED_AVAILABLE", True)
    monkeypatch.setattr(provider_mod, "_model_cached_locally", lambda cfg: True)

    def _boom(**kwargs):
        raise RuntimeError("simulated model load failure")

    monkeypatch.setattr(provider_mod, "TextEmbedding", _boom)
    p = EmbeddingProvider(EmbeddingConfig(allow_network=True))
    assert p.embed("hi") is None  # fails open, not raises


def test_embed_uses_loaded_model_and_caches_it(monkeypatch):
    calls = {"loads": 0}

    class _FakeModel:
        def embed(self, texts):
            for _ in texts:
                yield [0.1, 0.2, 0.3]

    def _fake_ctor(**kwargs):
        calls["loads"] += 1
        return _FakeModel()

    monkeypatch.setattr(provider_mod, "FASTEMBED_AVAILABLE", True)
    monkeypatch.setattr(provider_mod, "_model_cached_locally", lambda cfg: True)
    monkeypatch.setattr(provider_mod, "TextEmbedding", _fake_ctor)

    p = EmbeddingProvider(EmbeddingConfig(allow_network=True))
    v1 = p.embed("hello")
    v2 = p.embed("world")
    assert v1 == [0.1, 0.2, 0.3]
    assert v2 == [0.1, 0.2, 0.3]
    assert calls["loads"] == 1  # lazy singleton -- loaded once, reused


def test_embed_many_uses_loaded_model(monkeypatch):
    class _FakeModel:
        def embed(self, texts):
            for i, _ in enumerate(texts):
                yield [float(i), 0.0]

    monkeypatch.setattr(provider_mod, "FASTEMBED_AVAILABLE", True)
    monkeypatch.setattr(provider_mod, "_model_cached_locally", lambda cfg: True)
    monkeypatch.setattr(provider_mod, "TextEmbedding", lambda **kw: _FakeModel())

    p = EmbeddingProvider(EmbeddingConfig(allow_network=True))
    out = p.embed_many(["a", "b", "c"])
    assert out == [[0.0, 0.0], [1.0, 0.0], [2.0, 0.0]]


def test_status_reports_ready_when_model_loadable(monkeypatch):
    monkeypatch.setattr(provider_mod, "FASTEMBED_AVAILABLE", True)
    monkeypatch.setattr(provider_mod, "_model_cached_locally", lambda cfg: True)
    p = EmbeddingProvider(EmbeddingConfig(allow_network=False))
    status = p.status()
    assert status["dependency_installed"] is True
    assert status["ready"] is True
    assert status["model_cached_locally"] is True


# ── cosine_similarity ──────────────────────────────────────────────────────
def test_cosine_similarity_identical_vectors():
    assert cosine_similarity([1.0, 2.0, 3.0], [1.0, 2.0, 3.0]) == pytest.approx(1.0)


def test_cosine_similarity_orthogonal_vectors():
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)


def test_cosine_similarity_opposite_vectors():
    assert cosine_similarity([1.0, 0.0], [-1.0, 0.0]) == pytest.approx(-1.0)


def test_cosine_similarity_empty_or_mismatched_returns_zero():
    assert cosine_similarity([], []) == 0.0
    assert cosine_similarity([1.0], [1.0, 2.0]) == 0.0
    assert cosine_similarity([0.0, 0.0], [1.0, 1.0]) == 0.0  # zero-norm vector


# ── cost/router isolation guarantee ─────────────────────────────────────────
def test_embed_never_touches_cost_or_router(monkeypatch):
    """Using the embedding provider must never write a cost_logs row or
    call the router -- it's local ONNX inference, not an LLM call. Verified
    two ways: (1) statically, this module doesn't import router.py/budget.py
    at all (source-scanned below); (2) behaviorally, patching record_cost to
    explode proves embed() never reaches it even when a model *is* loaded."""
    class _FakeModel:
        def embed(self, texts):
            for _ in texts:
                yield [0.1, 0.2]

    monkeypatch.setattr(provider_mod, "FASTEMBED_AVAILABLE", True)
    monkeypatch.setattr(provider_mod, "_model_cached_locally", lambda cfg: True)
    monkeypatch.setattr(provider_mod, "TextEmbedding", lambda **kw: _FakeModel())

    def _explode(*args, **kwargs):
        raise AssertionError("embedding must never record cost or call the router")

    monkeypatch.setattr("promptwise.db.models.record_cost", _explode, raising=False)

    p = EmbeddingProvider(EmbeddingConfig(allow_network=True))
    assert p.embed("no cost here") == [0.1, 0.2]


def test_provider_module_does_not_import_router_or_budget():
    """Static guard, independent of the monkeypatch test above: parse
    provider.py's own imports and assert router/budget are absent. Catches
    a future edit wiring cost tracking into this module by accident."""
    src = Path(provider_mod.__file__).read_text(encoding="utf-8")
    tree = ast.parse(src)
    imported_modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)
    forbidden = {"promptwise.core.router", "promptwise.plugins.budget", "promptwise.db.models"}
    assert not (imported_modules & forbidden), imported_modules & forbidden
