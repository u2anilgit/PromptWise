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
