"""core.knowledgebase -- opt-in, org-shared store of design
patterns/architecture/tech-stack decisions. A backend-agnostic interface
(KnowledgeBackend) with one concrete backend (FileBackend, a shared JSON
file -- works local or over a synced/network path with zero infra). A
server-backed backend is a future swap behind the same interface, not
built here (see the design doc's Non-goals). Every operation is intended
to fail open from the caller's side -- callers in handlers/agile.py and
core/scaffold.py wrap use of this module in try/except so a KB problem
never blocks the skill's own output.
"""
from __future__ import annotations

import json
import threading
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from pathlib import Path

_DEFAULT_STORE_PATH = Path.home() / ".promptwise" / "knowledgebase.json"
VALID_STATUSES = ("unreviewed", "trusted", "rejected")


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def new_entry_id() -> str:
    return uuid.uuid4().hex


@dataclass
class KnowledgeEntry:
    id: str
    title: str
    tags: list[str]
    summary: str
    source_prompt: str
    artifact_ref: str
    status: str
    created_by: str
    created_at: str
    reviewed_by: str = ""
    reviewed_at: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "KnowledgeEntry":
        return cls(**{f: d.get(f, "" if f not in ("tags",) else []) for f in cls.__dataclass_fields__})


class KnowledgeBackend(ABC):
    @abstractmethod
    def save_entry(self, entry: KnowledgeEntry) -> None: ...

    @abstractmethod
    def list_entries(self, status: str | None = None) -> list[KnowledgeEntry]: ...

    @abstractmethod
    def get_entry(self, entry_id: str) -> KnowledgeEntry | None: ...

    @abstractmethod
    def update_status(self, entry_id: str, status: str, reviewed_by: str) -> bool: ...


class FileBackend(KnowledgeBackend):
    """Shared JSON file, `{"entries": [...]}`. A threading.Lock guards
    read-modify-write within one process; concurrent writers on different
    machines sharing a synced folder are last-write-wins (documented
    limitation -- a real transactional store is the design doc's
    out-of-scope server-backend future work, not this backend's job)."""

    def __init__(self, store_path: str | Path | None = None):
        self.store_path = Path(store_path) if store_path else _DEFAULT_STORE_PATH
        self._lock = threading.Lock()

    def _load(self) -> dict:
        if not self.store_path.exists():
            return {"entries": []}
        try:
            return json.loads(self.store_path.read_text(encoding="utf-8"))
        except Exception:
            return {"entries": []}

    def _save(self, data: dict) -> None:
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        self.store_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def save_entry(self, entry: KnowledgeEntry) -> None:
        with self._lock:
            data = self._load()
            entries = [e for e in data.get("entries", []) if e.get("id") != entry.id]
            entries.append(entry.to_dict())
            self._save({"entries": entries})

    def list_entries(self, status: str | None = None) -> list[KnowledgeEntry]:
        data = self._load()
        out = [KnowledgeEntry.from_dict(e) for e in data.get("entries", [])]
        if status:
            out = [e for e in out if e.status == status]
        return out

    def get_entry(self, entry_id: str) -> KnowledgeEntry | None:
        for e in self.list_entries():
            if e.id == entry_id:
                return e
        return None

    def update_status(self, entry_id: str, status: str, reviewed_by: str) -> bool:
        with self._lock:
            data = self._load()
            entries = data.get("entries", [])
            for e in entries:
                if e.get("id") == entry_id:
                    e["status"] = status
                    e["reviewed_by"] = reviewed_by
                    e["reviewed_at"] = _now_iso()
                    self._save({"entries": entries})
                    return True
            return False


from promptwise.core.text_match import contains_keyword


@dataclass
class MatchResult:
    best: KnowledgeEntry | None
    score: float
    method: str  # "tag" | "embedding" | "none"


def _get_embedding_provider():
    """Lazy, fail-open -- mirrors core/semantic_cache.py's _get_provider()
    exactly. Returns None (never raises) if the `embeddings` extra isn't
    installed or the provider can't initialize."""
    try:
        from promptwise.embeddings.provider import EmbeddingProvider
        return EmbeddingProvider()
    except Exception:
        return None


def match(backend: KnowledgeBackend, text: str, min_tag_hits: int = 1,
          min_similarity: float = 0.6) -> MatchResult:
    candidates = [e for e in backend.list_entries() if e.status != "rejected"]
    if not candidates:
        return MatchResult(best=None, score=0.0, method="none")

    # 1. tag filter -- cheap, same word-boundary matcher skill_loader uses
    text_lower = text.lower()
    tag_scored = []
    for e in candidates:
        hits = sum(1 for t in e.tags if contains_keyword(text_lower, t.lower()))
        if hits >= min_tag_hits:
            tag_scored.append((hits, e))
    if tag_scored:
        tag_scored.sort(key=lambda pair: pair[0], reverse=True)
        # prefer trusted over unreviewed on a tie
        top_hits = tag_scored[0][0]
        tied = [e for hits, e in tag_scored if hits == top_hits]
        tied.sort(key=lambda e: 0 if e.status == "trusted" else 1)
        return MatchResult(best=tied[0], score=float(top_hits), method="tag")

    # 2. embedding rerank fallback over the full candidate set
    provider = _get_embedding_provider()
    if provider is None:
        return MatchResult(best=None, score=0.0, method="none")

    from promptwise.embeddings.provider import cosine_similarity

    query_vec = provider.embed(text)
    if query_vec is None:
        return MatchResult(best=None, score=0.0, method="none")

    best_entry, best_sim = None, 0.0
    for e in candidates:
        vec = provider.embed(e.source_prompt or e.summary)
        if vec is None:
            continue
        sim = cosine_similarity(query_vec, vec)
        if sim > best_sim:
            best_entry, best_sim = e, sim

    if best_entry is not None and best_sim >= min_similarity:
        return MatchResult(best=best_entry, score=best_sim, method="embedding")
    return MatchResult(best=None, score=0.0, method="none")


def kb_precheck(text: str, created_by: str = "", capture: dict | None = None) -> dict | None:
    """Fail-open pre-check. On a hit, returns a note dict (see Task 5). On
    a miss, if `capture` is given (derived by the caller from its own
    structured output, no extra LLM call), silently saves a new
    `unreviewed` entry and returns None -- capture is a background side
    effect, never surfaced back to the caller's own output."""
    try:
        from promptwise.core.admin_config import get_admin_settings
        settings = get_admin_settings()
        if not settings.get("features", {}).get("knowledgebase.enabled", False):
            return None
        from promptwise.handlers.knowledgebase import _backend
        backend = _backend()
        result = match(backend, text)
        if result.best is not None:
            return {
                "title": result.best.title,
                "summary": result.best.summary,
                "artifact_ref": result.best.artifact_ref,
                "status": result.best.status,
                "match_method": result.method,
            }
        if capture is not None:
            backend.save_entry(KnowledgeEntry(
                id=new_entry_id(), title=capture.get("title", ""),
                tags=capture.get("tags", []), summary=capture.get("summary", ""),
                source_prompt=text, artifact_ref=capture.get("artifact_ref", ""),
                status="unreviewed", created_by=created_by, created_at=_now_iso(),
            ))
        return None
    except Exception:
        return None
