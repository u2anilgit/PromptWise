"""eval_harness — a durable eval + regression harness that closes the learning loop.

Static prompts drift silently across model versions. This module pins expected
behaviour as a small suite of *cases* (prompt + rubric), runs each case across
tiers, scores the output with the existing quality logic, diffs the result
against a stored baseline to flag regressions, and exposes a pass/fail gate.

Design contract (matches ``adaptive_router.py`` / ``quality*.py`` conventions):

* **Tiers, never branded ids.** Cases name a tier (``fast`` / ``balanced`` /
  ``powerful``); concrete model resolution stays in the registry/router.
* **Offline default, air-gap safe.** With no local runtime the harness runs in
  a deterministic *record/dry-run* mode — it records the case and a placeholder
  result and never touches the network. A local runtime (``local_runtime``) is
  used only when one is injected/available; a live cloud model is never required.
* **Reuse, don't reinvent.** Scoring composes ``core.quality.QualityGuard`` (and
  the ``expect_contains`` / ``expect_absent`` rubric) — the same quality signal
  the rest of PromptWise already trusts.
* **Closes the loop.** Every scored case is written into the 7.1 outcome store
  (``adaptive_router.OutcomeStore`` / ``record_route_outcome``) so adaptive
  routing learns from eval results — the required WP7.3 integration point.
* **Stdlib only.** ``json`` cases + bundled ``sqlite3`` into the local DB; no
  server, no network, no new dependency.
"""
from __future__ import annotations

import json
import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

# Cheapest -> most expensive; mirrors adaptive_router.TIER_ORDER.
TIER_ORDER: tuple[str, ...] = ("fast", "balanced", "powerful")


# ── eval case (prompt + rubric) ──────────────────────────────────────────────
@dataclass
class EvalCase:
    """A single eval case: a prompt plus a rubric of what a good answer must do.

    ``min_score`` overrides the harness bar for this case when set. The rubric is
    intentionally simple + deterministic (stdlib): required/forbidden substrings
    layered on the existing quality signals.
    """
    id: str
    prompt: str
    task_class: str = "eval"
    tier: str = "balanced"
    expect_contains: list[str] = field(default_factory=list)
    expect_absent: list[str] = field(default_factory=list)
    min_score: float | None = None
    skill: str = ""
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict) -> "EvalCase":
        return cls(
            id=str(d.get("id") or d.get("case_id") or uuid.uuid4().hex[:8]),
            prompt=str(d.get("prompt", "")),
            task_class=str(d.get("task_class", "eval")),
            tier=str(d.get("tier", "balanced")),
            expect_contains=list(d.get("expect_contains", []) or []),
            expect_absent=list(d.get("expect_absent", []) or []),
            min_score=(float(d["min_score"]) if d.get("min_score") is not None else None),
            skill=str(d.get("skill", "")),
            metadata=dict(d.get("metadata", {}) or {}),
        )

    def to_dict(self) -> dict:
        return {"id": self.id, "prompt": self.prompt, "task_class": self.task_class,
                "tier": self.tier, "expect_contains": list(self.expect_contains),
                "expect_absent": list(self.expect_absent), "min_score": self.min_score,
                "skill": self.skill, "metadata": dict(self.metadata)}


def load_cases(path: str | Path) -> list[EvalCase]:
    """Load cases from a JSON file or a directory of JSON files.

    A file may hold a single case object, a bare list of cases, or a
    ``{"cases": [...]}`` wrapper. Fail-soft per file (a bad file is skipped, not
    fatal) so one broken case never sinks a whole suite.
    """
    p = Path(path)
    files = sorted(p.glob("*.json")) if p.is_dir() else [p]
    cases: list[EvalCase] = []
    for f in files:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(data, dict) and "cases" in data:
            data = data["cases"]
        if isinstance(data, dict):
            data = [data]
        for item in data or []:
            if isinstance(item, dict):
                cases.append(EvalCase.from_dict(item))
    return cases


# ── results / regressions / run report ───────────────────────────────────────
@dataclass
class EvalResult:
    case_id: str
    task_class: str
    tier: str
    output: str
    score: float
    verdict: str          # "met" | "not_met"
    signals: list[str]
    mode: str             # "local" | "record"
    ts: str = ""

    def to_dict(self) -> dict:
        return {"case_id": self.case_id, "task_class": self.task_class, "tier": self.tier,
                "output": self.output, "score": round(self.score, 4), "verdict": self.verdict,
                "signals": list(self.signals), "mode": self.mode, "ts": self.ts}


@dataclass
class Regression:
    case_id: str
    tier: str
    baseline_verdict: str
    current_verdict: str
    baseline_score: float
    current_score: float
    reason: str

    def to_dict(self) -> dict:
        return {"case_id": self.case_id, "tier": self.tier,
                "baseline_verdict": self.baseline_verdict, "current_verdict": self.current_verdict,
                "baseline_score": round(self.baseline_score, 4),
                "current_score": round(self.current_score, 4), "reason": self.reason}


@dataclass
class EvalRun:
    suite: str
    results: list[EvalResult]
    regressions: list[Regression]
    gate: str             # "pass" | "fail"
    mode: str             # "local" if any case ran on a runtime, else "record"

    @property
    def passed(self) -> bool:
        return self.gate == "pass"

    def to_dict(self) -> dict:
        return {"suite": self.suite, "gate": self.gate, "mode": self.mode,
                "results": [r.to_dict() for r in self.results],
                "regressions": [r.to_dict() for r in self.regressions],
                "counts": {"cases": len(self.results),
                           "met": sum(1 for r in self.results if r.verdict == "met"),
                           "not_met": sum(1 for r in self.results if r.verdict == "not_met"),
                           "regressions": len(self.regressions)}}


# ── result + baseline store (sync sqlite, mirrors OutcomeStore) ───────────────
def _default_db() -> Path:
    try:
        from promptwise.db.models import get_db_path
        return get_db_path()
    except Exception:
        d = Path.home() / ".promptwise"
        d.mkdir(parents=True, exist_ok=True)
        return d / "promptwise.db"


class EvalResultStore:
    """Sync, stdlib-sqlite store of eval results + per-(suite,case,tier) baselines.

    Schema mirrors ``db.models.EvalResultModel`` / ``EvalBaselineModel`` (same
    tables + columns) so the async accessors and this sync path interoperate on
    one file. ``CREATE TABLE IF NOT EXISTS`` is idempotent whichever side wins.
    """

    def __init__(self, db_path: str | Path | None = None):
        self.db_path = Path(db_path) if db_path else _default_db()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure(self) -> None:
        conn = self._connect()
        try:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS eval_results (
                       result_id TEXT PRIMARY KEY,
                       ts TEXT NOT NULL,
                       suite TEXT NOT NULL DEFAULT 'default',
                       case_id TEXT NOT NULL DEFAULT '',
                       task_class TEXT NOT NULL DEFAULT '',
                       tier TEXT NOT NULL DEFAULT '',
                       score REAL NOT NULL DEFAULT 0,
                       verdict TEXT NOT NULL DEFAULT 'not_met',
                       mode TEXT NOT NULL DEFAULT 'record',
                       signals TEXT NOT NULL DEFAULT '[]'
                   )""")
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_eval_results_suite "
                "ON eval_results(suite)")
            conn.execute(
                """CREATE TABLE IF NOT EXISTS eval_baselines (
                       suite TEXT NOT NULL DEFAULT 'default',
                       case_id TEXT NOT NULL DEFAULT '',
                       tier TEXT NOT NULL DEFAULT '',
                       score REAL NOT NULL DEFAULT 0,
                       verdict TEXT NOT NULL DEFAULT 'not_met',
                       ts TEXT NOT NULL,
                       PRIMARY KEY (suite, case_id, tier)
                   )""")
            conn.commit()
        finally:
            conn.close()

    def record_result(self, r: EvalResult, suite: str = "default") -> None:
        conn = self._connect()
        try:
            conn.execute(
                "INSERT INTO eval_results "
                "(result_id, ts, suite, case_id, task_class, tier, score, verdict, mode, signals) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (uuid.uuid4().hex, r.ts, suite, r.case_id, r.task_class, r.tier,
                 float(r.score), r.verdict, r.mode, json.dumps(list(r.signals))))
            conn.commit()
        finally:
            conn.close()

    def results(self, suite: str | None = None) -> list[dict]:
        conn = self._connect()
        try:
            if suite:
                rows = conn.execute(
                    "SELECT * FROM eval_results WHERE suite = ? ORDER BY ts",
                    (suite,)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM eval_results ORDER BY ts").fetchall()
        finally:
            conn.close()
        return [{"case_id": r["case_id"], "task_class": r["task_class"], "tier": r["tier"],
                 "score": r["score"], "verdict": r["verdict"], "mode": r["mode"],
                 "signals": json.loads(r["signals"]), "ts": r["ts"], "suite": r["suite"]}
                for r in rows]

    def save_baseline(self, case_id: str, tier: str, score: float, verdict: str,
                      suite: str = "default", ts: str | None = None) -> None:
        ts = ts or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        conn = self._connect()
        try:
            conn.execute(
                "INSERT OR REPLACE INTO eval_baselines "
                "(suite, case_id, tier, score, verdict, ts) VALUES (?, ?, ?, ?, ?, ?)",
                (suite, case_id, tier, float(score), verdict, ts))
            conn.commit()
        finally:
            conn.close()

    def get_baseline(self, case_id: str, tier: str, suite: str = "default") -> dict | None:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT score, verdict, ts FROM eval_baselines "
                "WHERE suite = ? AND case_id = ? AND tier = ?",
                (suite, case_id, tier)).fetchone()
        finally:
            conn.close()
        return {"score": row["score"], "verdict": row["verdict"], "ts": row["ts"]} if row else None


# ── local-runtime adapter (optional, on-device only) ─────────────────────────
def local_runtime_runner(model: str, *, base_url: str | None = None, http_post=None):
    """Build a ``runner(prompt, tier) -> str`` backed by the on-device runtime.

    This is opt-in: pass the result as ``EvalHarness(runner=...)`` only when a
    local model is actually available. It talks to ``localhost`` (an on-device
    call, not an air-gap violation) and is fail-soft — an unreachable daemon
    yields ``None`` so the harness falls back to record mode.
    """
    from promptwise.core.local_runtime import DEFAULT_OLLAMA_URL, OllamaClient
    client = OllamaClient(base_url or DEFAULT_OLLAMA_URL, http_post)

    def _run(prompt: str, tier: str) -> str | None:
        res = client.generate(model, prompt)
        return (res or {}).get("response") if res else None

    return _run


# ── the harness ──────────────────────────────────────────────────────────────
class EvalHarness:
    """Run eval cases, score them, diff against a baseline, and close the loop.

    ``runner`` is an injected ``callable(prompt, tier) -> str | None``. When it is
    ``None`` (or returns nothing) the harness falls back to a deterministic
    *record/dry-run* mode that never requires cloud or network.
    """

    def __init__(self, *, runner=None, outcome_store=None, result_store=None,
                 bar: float = 0.6, suite: str = "default", tolerance: float = 1e-9,
                 guard=None):
        self.runner = runner
        self.outcome_store = outcome_store
        self.result_store = result_store if result_store is not None else EvalResultStore()
        self.bar = float(bar)
        self.suite = suite
        self.tolerance = float(tolerance)
        if guard is not None:
            self.guard = guard
        else:
            from promptwise.core.quality import QualityGuard
            self.guard = QualityGuard(confidence_threshold=self.bar)

    # -- scoring (reuses the existing quality logic + rubric) ------------------
    def score(self, case: EvalCase, output: str) -> tuple[float, str, list[str]]:
        qr = self.guard.check(output or "", skill_name=case.skill)
        score = float(qr.score)
        signals = list(qr.signals)
        low = (output or "").lower()
        for term in case.expect_contains:
            if term.lower() not in low:
                signals.append(f"missing_expected:{term}")
                score -= 0.5
        for term in case.expect_absent:
            if term.lower() in low:
                signals.append(f"contains_forbidden:{term}")
                score -= 0.5
        score = max(0.0, min(1.0, score))
        bar = case.min_score if case.min_score is not None else self.bar
        verdict = "met" if score >= bar else "not_met"
        return score, verdict, signals

    # -- producing an output (runtime when available, else record mode) -------
    def _produce(self, case: EvalCase, tier: str) -> tuple[str, str]:
        if self.runner is not None:
            try:
                out = self.runner(case.prompt, tier)
                if out is not None:
                    return str(out), "local"
            except Exception:
                pass  # fail-soft -> record mode
        # OFFLINE DEFAULT: deterministic dry-run placeholder. Never network.
        placeholder = (f"[record-mode dry-run] no local runtime available.\n"
                       f"case={case.id} tier={tier}\nprompt: {case.prompt}")
        return placeholder, "record"

    def run_case(self, case: EvalCase, tier: str | None = None) -> EvalResult:
        tier = tier or case.tier
        output, mode = self._produce(case, tier)
        score, verdict, signals = self.score(case, output)
        result = EvalResult(
            case_id=case.id, task_class=case.task_class, tier=tier, output=output,
            score=score, verdict=verdict, signals=signals, mode=mode,
            ts=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
        # persist the result
        try:
            self.result_store.record_result(result, suite=self.suite)
        except Exception:
            pass  # storage is best-effort; a full disk must not sink an eval
        # close the loop into the 7.1 outcome store
        self._record_outcome(result)
        return result

    def _record_outcome(self, result: EvalResult) -> None:
        """Feed the scored verdict into the 7.1 adaptive-routing outcome store."""
        if self.outcome_store is None:
            return
        try:
            self.outcome_store.record(
                result.task_class, result.tier, quality_signal=result.verdict)
        except Exception:
            pass  # fail-open: eval must not break because the loop write failed

    def run(self, cases: list[EvalCase], tiers: list[str] | None = None) -> EvalRun:
        results: list[EvalResult] = []
        for case in cases:
            for tier in (tiers if tiers else [case.tier]):
                results.append(self.run_case(case, tier))
        regressions = self._regressions(results)
        gate = "fail" if regressions else "pass"
        mode = "local" if any(r.mode == "local" for r in results) else "record"
        return EvalRun(suite=self.suite, results=results, regressions=regressions,
                       gate=gate, mode=mode)

    # -- baseline diff --------------------------------------------------------
    def _regressions(self, results: list[EvalResult]) -> list[Regression]:
        regs: list[Regression] = []
        for r in results:
            base = self.result_store.get_baseline(r.case_id, r.tier, self.suite)
            if not base:
                continue  # no baseline -> nothing to regress against
            reason = ""
            if base["verdict"] == "met" and r.verdict == "not_met":
                reason = "verdict regressed met -> not_met"
            elif r.score < base["score"] - self.tolerance:
                reason = f"score dropped {base['score']:.2f} -> {r.score:.2f}"
            if reason:
                regs.append(Regression(
                    case_id=r.case_id, tier=r.tier, baseline_verdict=base["verdict"],
                    current_verdict=r.verdict, baseline_score=base["score"],
                    current_score=r.score, reason=reason))
        return regs

    def save_baseline(self, run: EvalRun) -> int:
        """Bless a run's results as the baseline for future regression diffs."""
        for r in run.results:
            self.result_store.save_baseline(
                r.case_id, r.tier, r.score, r.verdict, suite=self.suite, ts=r.ts)
        return len(run.results)
