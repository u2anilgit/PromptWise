"""audit_log — tamper-evident, hash-chained record of AI-assisted changes.

This is "the trace" the market says coding tools lack: each governed task appends
a record linked to the previous one by SHA-256, so the chain is verifiable and any
edit is detectable. Stdlib only (hashlib/json/time), optional JSONL persistence.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

GENESIS = "0" * 64

_LOCK_STALE_SECS = 30.0
_LOCK_TIMEOUT_SECS = 10.0
_LOCK_POLL_SECS = 0.02


class _FileLock:
    """Cross-process mutex via atomic O_CREAT|O_EXCL sidecar file (stdlib only).

    Multiple processes (e.g. concurrent subagents' PostToolUse hooks) can call
    AuditLog.append() on the same path at once; without this, each holds a
    stale in-memory record count and both compute the same next index, which
    corrupts the hash chain (duplicate/missing index, broken links).
    """

    def __init__(self, lock_path: Path):
        self._lock_path = lock_path
        self._fd: int | None = None

    def __enter__(self) -> "_FileLock":
        deadline = time.monotonic() + _LOCK_TIMEOUT_SECS
        while True:
            try:
                self._fd = os.open(str(self._lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                return self
            except (FileExistsError, PermissionError):
                # PermissionError: on Windows, os.remove() of the lock file by the
                # previous holder isn't always instantaneously visible to a
                # concurrent O_CREAT|O_EXCL, so a competing open can transiently
                # raise this instead of FileExistsError. Treat it the same way.
                try:
                    if time.monotonic() - self._lock_path.stat().st_mtime > _LOCK_STALE_SECS:
                        os.remove(self._lock_path)
                        continue
                except OSError:
                    pass
                if time.monotonic() > deadline:
                    raise TimeoutError(f"timed out waiting for audit log lock: {self._lock_path}")
                time.sleep(_LOCK_POLL_SECS)

    def __exit__(self, *exc_info) -> None:
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None
        try:
            os.remove(self._lock_path)
        except OSError:
            pass


@dataclass
class AuditRecord:
    index: int
    timestamp: str
    task: str
    actor: str = ""
    agent: str = ""               # "claude-code" | "cursor" | "codex" ...
    model: str = ""
    cost_usd: float = 0.0
    rules_applied: list[str] = field(default_factory=list)
    gate_decision: str = ""        # PASS/CONCERNS/FAIL/WAIVED
    compliance_decision: str = ""  # e.g. "gated:passed" / "n/a"
    files_touched: list[str] = field(default_factory=list)
    prev_hash: str = GENESIS
    hash: str = ""

    def _payload(self) -> dict:
        d = asdict(self)
        d.pop("hash", None)
        return d

    def compute_hash(self) -> str:
        canonical = json.dumps(self._payload(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class AuditLog:
    """Append-only hash chain. In-memory by default; pass a path for JSONL persistence."""

    def __init__(self, path: str | Path | None = None, sinks: list | None = None):
        self.path = Path(path) if path else None
        self.records: list[AuditRecord] = []
        # Optional, opt-in SIEM-streamable side channels (webhook/syslog --
        # see audit_sinks.py). The JSONL file above stays the default sink
        # and the source of truth; a sink failure here must never break the
        # chain or raise out of append() (see _forward_to_sinks).
        self.sinks = list(sinks) if sinks else []
        if self.path and self.path.exists():
            self._load()

    def _forward_to_sinks(self, rec: AuditRecord) -> None:
        if not self.sinks:
            return
        payload = asdict(rec)
        for sink in self.sinks:
            try:
                sink.send(payload)
            except Exception:
                pass  # a broken/unreachable sink must never break the chain

    def _load(self) -> None:
        if not self.path:
            return
        self.records = []
        if not self.path.exists():
            return
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            self.records.append(AuditRecord(**json.loads(line)))

    def _lock_path(self) -> Path:
        assert self.path is not None
        return self.path.with_name(self.path.name + ".lock")

    def _persist(self, rec: AuditRecord) -> None:
        if not self.path:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(asdict(rec), sort_keys=True) + "\n")

    def append(
        self,
        task: str,
        *,
        actor: str = "",
        agent: str = "",
        model: str = "",
        cost_usd: float = 0.0,
        rules_applied: list[str] | None = None,
        gate_decision: str = "",
        compliance_decision: str = "",
        files_touched: list[str] | None = None,
    ) -> AuditRecord:
        if self.path:
            with _FileLock(self._lock_path()):
                self._load()  # another process may have appended since our __init__
                rec = self._build_record(
                    task, actor=actor, agent=agent, model=model, cost_usd=cost_usd,
                    rules_applied=rules_applied, gate_decision=gate_decision,
                    compliance_decision=compliance_decision, files_touched=files_touched,
                )
                self.records.append(rec)
                self._persist(rec)
                self._forward_to_sinks(rec)
                return rec
        rec = self._build_record(
            task, actor=actor, agent=agent, model=model, cost_usd=cost_usd,
            rules_applied=rules_applied, gate_decision=gate_decision,
            compliance_decision=compliance_decision, files_touched=files_touched,
        )
        self.records.append(rec)
        self._forward_to_sinks(rec)
        return rec

    def _build_record(
        self,
        task: str,
        *,
        actor: str = "",
        agent: str = "",
        model: str = "",
        cost_usd: float = 0.0,
        rules_applied: list[str] | None = None,
        gate_decision: str = "",
        compliance_decision: str = "",
        files_touched: list[str] | None = None,
    ) -> AuditRecord:
        prev = self.records[-1].hash if self.records else GENESIS
        rec = AuditRecord(
            index=len(self.records),
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            task=task,
            actor=actor,
            agent=agent,
            model=model,
            cost_usd=float(cost_usd),
            rules_applied=list(rules_applied or []),
            gate_decision=gate_decision,
            compliance_decision=compliance_decision,
            files_touched=list(files_touched or []),
            prev_hash=prev,
        )
        rec.hash = rec.compute_hash()
        return rec

    def verify(self) -> tuple[bool, str]:
        """Re-walk the chain; returns (ok, message)."""
        prev = GENESIS
        for i, rec in enumerate(self.records):
            if rec.index != i:
                return False, f"index mismatch at {i}"
            if rec.prev_hash != prev:
                return False, f"broken link at record {i}"
            if rec.compute_hash() != rec.hash:
                return False, f"tampered content at record {i}"
            prev = rec.hash
        return True, f"verified {len(self.records)} record(s)"

    def export_json(self) -> str:
        return json.dumps([asdict(r) for r in self.records], indent=2)

    def export_text(self) -> str:
        lines = ["AI-change audit trail", "=" * 21, ""]
        for r in self.records:
            files = ", ".join(r.files_touched) or "-"
            lines.append(
                f"[{r.index}] {r.timestamp} · {r.agent or '-'}/{r.model or '-'} · "
                f"${r.cost_usd:.4f}\n    task: {r.task}\n    gate: {r.gate_decision or '-'} · "
                f"compliance: {r.compliance_decision or '-'} · files: {files}\n"
                f"    rules: {', '.join(r.rules_applied) or '-'}"
            )
        return "\n".join(lines)
