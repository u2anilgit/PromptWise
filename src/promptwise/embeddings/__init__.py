"""embeddings -- opt-in local embedding support (Phase 19 / candidate D2).

This package only does real work when the `embeddings` extras group
(`pip install "promptwise[embeddings]"`) is installed. Nothing here is
imported at server startup or from the base install path -- consumers
(core/semantic_cache.py, core/learning_store.py's hybrid search) import
this lazily, exactly like core/static_analysis.py's ruff/eslint dispatch.
"""
from __future__ import annotations
