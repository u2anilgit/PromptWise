"""Phase 10 alignment guard: the governor's DEFAULT budget-overlay location is the
exact file BudgetGuardian reads, so an applied AdjustBudgetGuard takes runtime effect.

Both sides resolve the ``.promptwise`` state dir via a lazy ``get_db_path()`` call, so
patching ``promptwise.db.models.get_db_path`` redirects both to a temp home.
"""
import promptwise.db.models as models

from promptwise.core import governor as gov
from promptwise.plugins import budget as bud
from promptwise.plugins.budget import BudgetGuardian


def _point_state_dir_at(tmp_path, monkeypatch):
    fake_db = tmp_path / ".promptwise" / "promptwise.db"
    fake_db.parent.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(models, "get_db_path", lambda: fake_db)
    return tmp_path / ".promptwise" / "budget.local.yaml"


def test_governor_default_overlay_path_equals_budget_read_path(tmp_path, monkeypatch):
    expected = _point_state_dir_at(tmp_path, monkeypatch)
    governor_default = gov._budget_overlay_path(gov._default_root())
    guardian_read = bud._overlay_path()
    assert governor_default == guardian_read == expected


def test_overlay_written_at_governor_default_is_read_by_guardian(tmp_path, monkeypatch):
    _point_state_dir_at(tmp_path, monkeypatch)
    # Write at the governor's DEFAULT overlay location (root omitted -> shared home).
    path = gov._budget_overlay_path(gov._default_root())
    path.write_text("limit_usd: 42.0\n", encoding="utf-8")
    # A guardian with no explicit limit reflects the overlay written there.
    assert BudgetGuardian().limit_usd == 42.0
    # An explicit constructor limit still wins over the overlay.
    assert BudgetGuardian(limit_usd=7.0).limit_usd == 7.0


def test_governor_write_overlay_reaches_guardian(tmp_path, monkeypatch):
    """End-to-end: the governor's own overlay write (default root) lands where the
    guardian reads, so an AdjustBudgetGuard apply takes runtime effect."""
    _point_state_dir_at(tmp_path, monkeypatch)
    g = gov.Governor(audit_path=str(tmp_path / "audit.jsonl"))  # root omitted -> shared home
    g.write_budget_overlay(55.0)
    assert BudgetGuardian().limit_usd == 55.0
