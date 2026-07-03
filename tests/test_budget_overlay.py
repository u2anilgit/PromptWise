"""Phase 10 WP10.2 — BudgetGuardian reads the governor budget overlay.

Closes the loop opened in Phase 9: the governor's ``AdjustBudgetGuard`` apply writes
a gitignored ``.promptwise/budget.local.yaml``; a freshly constructed
``BudgetGuardian`` must pick that limit up so the action has runtime effect.

Contract:
- Overlay present with a ``limit_usd`` and no explicit ctor arg -> overlay wins.
- No overlay -> the built-in default (10.0).
- Explicit ``BudgetGuardian(limit_usd=X)`` -> X always wins over any overlay.
- Missing/malformed overlay -> no raise from ``__init__``; falls back to default.
- End-to-end: drive the governor's apply (its exact format), then a new
  BudgetGuardian reflects the new limit.

Hermetic: the ``.promptwise`` resolver is monkeypatched to a temp dir — the real
``~/.promptwise`` is never read or written.
"""
from pathlib import Path

import pytest

from promptwise.plugins import budget as budget_mod
from promptwise.plugins.budget import BudgetGuardian


@pytest.fixture
def state_dir(tmp_path, monkeypatch):
    """Point the overlay resolver at a temp ``.promptwise`` dir (the SAME seam the
    governor writes under: ``<root>/.promptwise/``)."""
    d = tmp_path / ".promptwise"
    d.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(budget_mod, "_state_dir", lambda: d)
    return d


def _write_overlay(state_dir: Path, limit: float) -> None:
    # governor's exact written shape (core/governor.write_budget_overlay)
    import time

    payload = {
        "limit_usd": round(float(limit), 4),
        "_managed_by": "promptwise-governor",
        "_ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    if budget_mod.yaml is not None:
        text = budget_mod.yaml.safe_dump(payload, sort_keys=True)
    else:  # pragma: no cover
        import json

        text = json.dumps(payload)
    (state_dir / budget_mod._BUDGET_OVERLAY).write_text(text, encoding="utf-8")


def test_overlay_limit_used_when_no_explicit_arg(state_dir):
    _write_overlay(state_dir, 42.5)
    g = BudgetGuardian()
    assert g.limit_usd == pytest.approx(42.5)
    assert g.get_budget_status()["limit_usd"] == pytest.approx(42.5)


def test_default_used_when_no_overlay(state_dir):
    assert not (state_dir / budget_mod._BUDGET_OVERLAY).exists()
    g = BudgetGuardian()
    assert g.limit_usd == pytest.approx(10.0)


def test_explicit_arg_wins_over_overlay(state_dir):
    _write_overlay(state_dir, 42.5)
    g = BudgetGuardian(limit_usd=7.0)
    assert g.limit_usd == pytest.approx(7.0)


def test_explicit_arg_wins_when_no_overlay(state_dir):
    g = BudgetGuardian(limit_usd=3.0)
    assert g.limit_usd == pytest.approx(3.0)


def test_malformed_overlay_falls_back_to_default(state_dir):
    (state_dir / budget_mod._BUDGET_OVERLAY).write_text(
        "this: : : not valid yaml: [", encoding="utf-8"
    )
    g = BudgetGuardian()  # must not raise
    assert g.limit_usd == pytest.approx(10.0)


def test_overlay_without_limit_key_falls_back(state_dir):
    (state_dir / budget_mod._BUDGET_OVERLAY).write_text(
        "_managed_by: promptwise-governor\n", encoding="utf-8"
    )
    g = BudgetGuardian()
    assert g.limit_usd == pytest.approx(10.0)


def test_read_budget_overlay_helper(state_dir):
    assert budget_mod.read_budget_overlay() is None
    _write_overlay(state_dir, 15.0)
    assert budget_mod.read_budget_overlay() == pytest.approx(15.0)


def test_end_to_end_governor_apply_reflected(tmp_path, monkeypatch):
    """Drive the real governor apply, then a fresh BudgetGuardian reflects it."""
    from promptwise.core.audit_log import AuditLog
    from promptwise.core.governor import Governor

    root = tmp_path
    gov = Governor(root=root, mode="apply", audit_log=AuditLog(tmp_path / "audit.jsonl"))
    rec = {
        "id": "rec-budget-1",
        "category": "budget",
        "message": "raise cap to cover projected spend",
        "evidence": {"kind": "projected_overrun", "projected_usd": 33.0, "limit_usd": 10.0},
    }
    out = gov.run([rec])
    assert out["summary"]["applied"] == ["rec-budget-1"]

    # BudgetGuardian resolves the SAME .promptwise the governor wrote under.
    monkeypatch.setattr(budget_mod, "_state_dir", lambda: root / ".promptwise")
    g = BudgetGuardian()
    assert g.limit_usd == pytest.approx(33.0)
