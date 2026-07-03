"""Phase 9 — autonomous governor (policy-gated, reversible, default advise-only).

Acceptance (docs/PHASE9_ROADMAP.md §9):
- ``advise`` (default): proposes actions, applies nothing (overlay + undo-ledger
  unchanged), audits each proposal; the audit chain verifies.
- Policy gate: an action violating an injected policy is blocked, not applied, and
  recorded as blocked with the reason.
- ``apply``: an allowlisted ``AdjustBudgetGuard`` writes the gitignored overlay + a
  ledger entry; ``undo`` restores the exact prior value; re-apply is a no-op.
- An ``advisory-only`` action is never auto-applied in any mode — overlay/live config
  stay untouched even in ``apply``.
- An injected error during apply leaves NO partial state and NO ledger entry
  (fail-safe); a sibling action still applies.
- Everything is offline; the audit chain verifies after a full run.

Every test is hermetic: a temp root for the ``.promptwise`` overlay + ledger, a temp
audit path, and hand-built recommendation dicts (decoupled from the insights engine).
Never touches the real ~/.promptwise or tracked config.
"""
import socket

import pytest

from promptwise.core.audit_log import AuditLog
from promptwise.core.policy import Policy
from promptwise.core.governor import (
    Governor,
    ALLOWLISTED_TYPES,
    read_budget_overlay,
)


# ── recommendation fixtures ──────────────────────────────────────────────────
def _budget_overrun_rec(projected=15.0, limit=10.0):
    return {
        "id": "budget:overrun", "category": "budget",
        "message": f"Projected spend ${projected:.2f} exceeds ${limit:.2f}.",
        "evidence": {"kind": "projected_overrun", "projected_usd": projected,
                     "limit_usd": limit, "spend_so_far_usd": 7.5, "days_observed": 6},
        "estimated_impact": projected - limit, "confidence": 0.8,
        "score": (projected - limit) * 0.8,
    }


def _routing_rec():
    return {
        "id": "routing:downgrade:summarize", "category": "routing",
        "message": "Class 'summarize' meets the bar at the cheaper 'fast' tier.",
        "evidence": {"kind": "downgrade", "task_class": "summarize",
                     "target_tier": "fast", "from_tiers": ["balanced"]},
        "estimated_impact": 0.5, "confidence": 0.9, "score": 0.45,
    }


def _permission_rec():
    return {
        "id": "permission:allow:Bash:git", "category": "permission",
        "message": "Bash:git repeatedly denied but scans clean — consider allow.",
        "evidence": {"kind": "permission_rule", "signature": "Bash:git",
                     "proposed_rule": "alwaysAllow"},
        "estimated_impact": 0.0, "confidence": 0.5, "score": 0.0,
    }


def _mk_governor(tmp_path, mode, *, policy=None, audit=None):
    audit = audit or AuditLog(tmp_path / "audit.jsonl")
    return Governor(root=tmp_path, mode=mode, policy=policy, audit_log=audit), audit


# ── advise (default) ─────────────────────────────────────────────────────────
def test_default_mode_is_advise(monkeypatch, tmp_path):
    monkeypatch.delenv("PROMPTWISE_AUTONOMY", raising=False)
    gov, _ = _mk_governor(tmp_path, mode=None)
    assert gov.mode == "advise"


def test_advise_proposes_but_applies_nothing(tmp_path):
    gov, audit = _mk_governor(tmp_path, mode="advise")
    out = gov.run([_budget_overrun_rec(), _routing_rec()])

    assert out["mode"] == "advise"
    assert len(out["proposals"]) == 2
    assert out["summary"]["applied"] == []
    # nothing changed on disk
    assert read_budget_overlay(tmp_path) is None
    assert not (tmp_path / ".promptwise" / "governor_ledger.json").exists() or gov.ledger_entries() == {}
    # every proposal audited + chain verifies
    ok, msg = audit.verify()
    assert ok, msg
    assert len(audit.records) >= 2  # at least one propose record per action


def test_advise_marks_safe_actions_would_apply(tmp_path):
    gov, _ = _mk_governor(tmp_path, mode="advise")
    out = gov.run([_budget_overrun_rec()])
    p = out["proposals"][0]
    assert p["type"] == "AdjustBudgetGuard"
    assert p["blast_radius"] == "safe"
    assert p["status"] == "would_apply"
    assert p["id"] in out["summary"]["would_apply"]


# ── policy gate ──────────────────────────────────────────────────────────────
def test_policy_violation_blocks_action(tmp_path):
    policy = Policy.from_dict({"banned_operations": ["adjust_budget"]})
    gov, audit = _mk_governor(tmp_path, mode="apply", policy=policy)
    out = gov.run([_budget_overrun_rec()])

    p = out["proposals"][0]
    assert p["status"] == "blocked"
    assert p["verdict"]["allowed"] is False
    assert any("banned" in v for v in p["verdict"]["violations"])
    # blocked => not applied, no state change, no ledger entry
    assert read_budget_overlay(tmp_path) is None
    assert gov.ledger_entries() == {}
    assert p["id"] in [b["action_id"] for b in out["summary"]["blocked"]]
    ok, _ = audit.verify()
    assert ok


def test_policy_warning_does_not_block(tmp_path):
    # cap not exceeded (actions cost 0) but a warning-style policy still allows.
    policy = Policy.from_dict({"budget_cap_usd": 100.0})
    gov, _ = _mk_governor(tmp_path, mode="apply", policy=policy)
    out = gov.run([_budget_overrun_rec()])
    assert out["proposals"][0]["status"] == "applied"


# ── apply + undo + idempotency ───────────────────────────────────────────────
def test_apply_writes_overlay_and_ledger(tmp_path):
    gov, audit = _mk_governor(tmp_path, mode="apply")
    out = gov.run([_budget_overrun_rec(projected=15.0, limit=10.0)])

    p = out["proposals"][0]
    assert p["status"] == "applied"
    assert read_budget_overlay(tmp_path) == pytest.approx(15.0)
    entries = gov.ledger_entries()
    assert "budget:overrun" in entries
    e = entries["budget:overrun"]
    assert e["type"] == "AdjustBudgetGuard"
    assert e["prior_state"]["limit_usd"] is None      # overlay did not exist before
    assert e["new_state"]["limit_usd"] == pytest.approx(15.0)
    ok, _ = audit.verify()
    assert ok


def test_undo_restores_exact_prior_value(tmp_path):
    gov, audit = _mk_governor(tmp_path, mode="apply")
    # seed an existing overlay so prior is a concrete value, not absence
    gov.write_budget_overlay(8.0)
    gov.run([_budget_overrun_rec(projected=20.0, limit=10.0)])
    assert read_budget_overlay(tmp_path) == pytest.approx(20.0)

    res = gov.undo("budget:overrun")
    assert res["status"] == "undone"
    assert read_budget_overlay(tmp_path) == pytest.approx(8.0)   # exact prior
    assert "budget:overrun" not in gov.ledger_entries()
    ok, _ = audit.verify()
    assert ok


def test_reapply_is_a_noop(tmp_path):
    gov, _ = _mk_governor(tmp_path, mode="apply")
    rec = _budget_overrun_rec(projected=15.0, limit=10.0)
    gov.run([rec])
    entries_before = dict(gov.ledger_entries())

    out2 = gov.run([rec])   # identical action, already applied
    assert out2["proposals"][0]["status"] == "noop"
    assert gov.ledger_entries() == entries_before
    assert read_budget_overlay(tmp_path) == pytest.approx(15.0)


def test_undo_missing_action_is_safe(tmp_path):
    gov, _ = _mk_governor(tmp_path, mode="apply")
    res = gov.undo("does-not-exist")
    assert res["status"] == "noop"


# ── advisory-only never auto-applies ─────────────────────────────────────────
def test_advisory_only_never_applied_even_in_apply(tmp_path):
    gov, audit = _mk_governor(tmp_path, mode="apply")
    out = gov.run([_permission_rec()])

    p = out["proposals"][0]
    assert p["blast_radius"] == "advisory-only"
    assert p["type"] not in ALLOWLISTED_TYPES
    assert p["status"] == "advisory"
    # no state, no ledger entry, no live-config edit
    assert gov.ledger_entries() == {}
    assert read_budget_overlay(tmp_path) is None
    assert p["id"] in out["summary"]["advisory"]
    ok, _ = audit.verify()
    assert ok


# ── fail-safe ────────────────────────────────────────────────────────────────
def test_injected_error_leaves_no_partial_state_no_ledger(tmp_path, monkeypatch):
    gov, audit = _mk_governor(tmp_path, mode="apply")

    def boom(action):
        if action.type == "AdjustBudgetGuard":
            raise RuntimeError("injected fault")

    # seam invoked after the state write, before ledger/audit-applied
    monkeypatch.setattr(gov, "_post_write_verify", boom)

    out = gov.run([_budget_overrun_rec(), _routing_rec()])
    by_id = {p["id"]: p for p in out["proposals"]}

    # the faulted budget action: no partial overlay, no ledger entry
    assert by_id["budget:overrun"]["status"] == "failed"
    assert read_budget_overlay(tmp_path) is None
    assert "budget:overrun" not in gov.ledger_entries()

    # the sibling routing note still applied
    assert by_id["routing:downgrade:summarize"]["status"] == "applied"
    assert "routing:downgrade:summarize" in gov.ledger_entries()

    ok, _ = audit.verify()
    assert ok


def test_failsafe_restores_preexisting_overlay(tmp_path, monkeypatch):
    gov, _ = _mk_governor(tmp_path, mode="apply")
    gov.write_budget_overlay(9.0)   # pre-existing value must survive a fault

    monkeypatch.setattr(gov, "_post_write_verify",
                        lambda a: (_ for _ in ()).throw(RuntimeError("x")))
    gov.run([_budget_overrun_rec(projected=30.0, limit=10.0)])
    assert read_budget_overlay(tmp_path) == pytest.approx(9.0)


# ── dry_run ──────────────────────────────────────────────────────────────────
def test_dry_run_simulates_without_applying(tmp_path):
    gov, audit = _mk_governor(tmp_path, mode="dry_run")
    out = gov.run([_budget_overrun_rec()])
    assert out["mode"] == "dry_run"
    assert out["proposals"][0]["status"] == "would_apply"
    assert read_budget_overlay(tmp_path) is None
    assert gov.ledger_entries() == {}
    ok, _ = audit.verify()
    assert ok


# ── offline ──────────────────────────────────────────────────────────────────
def test_full_run_is_offline(tmp_path, monkeypatch):
    def _no_net(*a, **k):
        raise AssertionError("network access attempted")

    monkeypatch.setattr(socket, "socket", _no_net)
    gov, audit = _mk_governor(tmp_path, mode="apply")
    gov.run([_budget_overrun_rec(), _routing_rec(), _permission_rec()])
    ok, msg = audit.verify()
    assert ok, msg


# ── env-driven mode ──────────────────────────────────────────────────────────
def test_env_apply_enables_state_change(tmp_path, monkeypatch):
    monkeypatch.setenv("PROMPTWISE_AUTONOMY", "apply")
    gov, _ = _mk_governor(tmp_path, mode=None)
    assert gov.mode == "apply"
    gov.run([_budget_overrun_rec(projected=12.0, limit=10.0)])
    assert read_budget_overlay(tmp_path) == pytest.approx(12.0)


def test_unknown_env_mode_falls_back_to_advise(tmp_path, monkeypatch):
    monkeypatch.setenv("PROMPTWISE_AUTONOMY", "yolo")
    gov, _ = _mk_governor(tmp_path, mode=None)
    assert gov.mode == "advise"
