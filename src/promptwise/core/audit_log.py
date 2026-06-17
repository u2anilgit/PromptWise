"""audit_log — tamper-evident, hash-chained record of AI-assisted changes.

This is "the trace" the market says coding tools lack: each governed task appends
a record linked to the previous one by SHA-256, so the chain is verifiable and any
edit is detectable. Stdlib only (hashlib/json/time), optional JSONL persistence.
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

GENESIS = "0" * 64


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

    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else None
        self.records: list[AuditRecord] = []
        if self.path and self.path.exists():
            self._load()

    def _load(self) -> None:
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            self.records.append(AuditRecord(**json.loads(line)))

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
        self.records.append(rec)
        self._persist(rec)
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
