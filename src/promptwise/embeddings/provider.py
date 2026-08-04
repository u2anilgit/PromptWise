"""embeddings.provider -- lazy, fail-open local embedding provider (Phase 19 /
candidate D2). See docs/PHASE19_ROADMAP.md for the full design.

Guarded import, same shape as core/static_analysis.py's ruff/eslint
dispatch: this module always imports cleanly whether or not the optional
`embeddings` extras group (`pip install "promptwise[embeddings]"`) is
installed. Every public method fails open (returns None / False) rather
than raising, so callers (core/semantic_cache.py, learning_store.py's
future hybrid search) can always fall back to their existing non-semantic
path without a try/except of their own.

Cost note: embedding text is local ONNX inference, not an LLM call. This
module never imports core/router.py or plugins/budget.py and never writes
a cost_logs row -- using it does not increase token spend or show up in
any cost/budget report. See test_embedding_provider.py's
test_embed_never_touches_cost_or_router for the regression guard.

Network note: the ONLY network-capable code path is the one-time model
download inside _ensure_model(), and only when allow_network=True *and*
the model isn't already cached locally. Every other code path in this
module is 100% local compute once a model is loaded (or fails open before
ever touching the network).
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

try:  # PyYAML is already a PromptWise dependency (policy/model registry/governor use it)
    import yaml
except Exception:  # pragma: no cover - yaml always present in practice
    yaml = None  # type: ignore

try:  # only present if the `embeddings` extras group is installed
    from fastembed import TextEmbedding  # type: ignore
    FASTEMBED_AVAILABLE = True
except Exception:
    TextEmbedding = None  # type: ignore
    FASTEMBED_AVAILABLE = False

_DEFAULT_CONFIG_PATH = Path("config") / "embeddings.yaml"
DEFAULT_MODEL_NAME = "BAAI/bge-small-en-v1.5"


@dataclass
class EmbeddingConfig:
    """Parsed config/embeddings.yaml. Defaults are conservative (no network)
    even when the extras group is installed."""
    allow_network: bool = False
    model_name: str = DEFAULT_MODEL_NAME
    model_path: str | None = None  # bring-your-own-model, fully egress-locked case


def load_embedding_config(config_path: Path | str | None = None) -> EmbeddingConfig:
    path = Path(config_path) if config_path else _DEFAULT_CONFIG_PATH
    if yaml is None or not path.exists():
        return EmbeddingConfig()
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return EmbeddingConfig()
    return EmbeddingConfig(
        allow_network=bool(data.get("allow_network", False)),
        model_name=str(data.get("model_name") or DEFAULT_MODEL_NAME),
        model_path=data.get("model_path") or None,
    )


def _model_cached_locally(config: EmbeddingConfig) -> bool:
    """Best-effort check so a *second* run never needs allow_network even
    though the *first* one did. A configured model_path is trusted as-is
    (the operator is asserting it's already there); otherwise this checks
    fastembed/HF Hub's own local cache for an existing snapshot."""
    if config.model_path:
        return Path(config.model_path).exists()
    try:
        from huggingface_hub import scan_cache_dir  # type: ignore
        cache = scan_cache_dir()
        wanted = config.model_name.lower().replace("/", "--")
        return any(wanted in repo.repo_id.lower().replace("/", "--") for repo in cache.repos)
    except Exception:
        return False


class EmbeddingProvider:
    """Lazy singleton wrapper around fastembed.TextEmbedding. The model
    loads on first real call, not at construction -- an install with the
    extras group present but unused pays no RAM/load-time cost."""

    def __init__(self, config: EmbeddingConfig | None = None):
        self.config = config or load_embedding_config()
        self._model = None
        self._load_attempted = False

    @property
    def dependency_installed(self) -> bool:
        return FASTEMBED_AVAILABLE

    def status(self) -> dict:
        """For the embedding_status MCP tool / doctor -- never loads the
        model just to report status."""
        return {
            "dependency_installed": FASTEMBED_AVAILABLE,
            "model_name": self.config.model_name,
            "model_path": self.config.model_path,
            "allow_network": self.config.allow_network,
            "model_cached_locally": _model_cached_locally(self.config) if FASTEMBED_AVAILABLE else False,
            "ready": self._would_be_ready(),
        }

    def _would_be_ready(self) -> bool:
        if not FASTEMBED_AVAILABLE:
            return False
        if self.config.model_path:
            return Path(self.config.model_path).exists()
        return self.config.allow_network or _model_cached_locally(self.config)

    def _ensure_model(self):
        if self._model is not None or self._load_attempted:
            return self._model
        self._load_attempted = True
        if not FASTEMBED_AVAILABLE:
            return None
        if not self._would_be_ready():
            return None  # fail open: no network permitted and nothing cached yet
        try:
            kwargs: dict = {"model_name": self.config.model_name}
            if self.config.model_path:
                kwargs["specific_model_path"] = self.config.model_path
            self._model = TextEmbedding(**kwargs)  # type: ignore[misc]
        except Exception:
            self._model = None
        return self._model

    def embed(self, text: str) -> list[float] | None:
        """Embed one piece of text. Returns None on any failure (extra not
        installed, network not permitted and nothing cached, or the
        underlying inference call raising) -- never raises."""
        model = self._ensure_model()
        if model is None:
            return None
        try:
            vec = next(iter(model.embed([text or ""])))
            return [float(x) for x in vec]
        except Exception:
            return None

    def embed_many(self, texts: list[str]) -> list[list[float] | None]:
        model = self._ensure_model()
        if model is None:
            return [None for _ in texts]
        try:
            vecs = list(model.embed([t or "" for t in texts]))
            return [[float(x) for x in v] for v in vecs]
        except Exception:
            return [None for _ in texts]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Pure-stdlib cosine similarity -- deliberately no numpy import here,
    so this helper (and anything that only calls it, like a future
    similarity-threshold calibration routine) works even in a process
    where fastembed/numpy aren't importable. 0.0 for mismatched/empty
    vectors rather than raising."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)
