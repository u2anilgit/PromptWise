"""/api/executive -- the finance/senior-mgmt rollup tab. See
docs/superpowers/specs/2026-07-23-executive-dashboard-design.md.

Reuses build_dashboard_model / ROITracker / BudgetGuardian / governance_summary
against the same cost-log window /api/dashboard already reads -- no new
persistence. These tests lock in the response shape, auth-gating, the
zero-state fail-soft behavior, and the net_savings/budget consistency
guarantee (both must be computed from the same total_cost_usd).
"""
import asyncio

from promptwise.cli import _memory_manager
from promptwise.dashboard.auth import hash_credential
from promptwise.dashboard.web import create_web_app


def test_api_executive_requires_auth_rejects_missing_header(tmp_path):
    cred_path = tmp_path / "dashboard_auth.yaml"
    cred_path.write_text(
        "entries:\n  - credential_hash: \"" + hash_credential("abc") + "\"\n    role: viewer\n",
        encoding="utf-8")
    app = create_web_app(require_auth=True, credentials_path=cred_path)
    r = app.test_client().get("/api/executive")
    assert r.status_code == 401


def test_api_executive_requires_auth_rejects_unknown_credential(tmp_path):
    cred_path = tmp_path / "dashboard_auth.yaml"
    cred_path.write_text(
        "entries:\n  - credential_hash: \"" + hash_credential("abc") + "\"\n    role: viewer\n",
        encoding="utf-8")
    app = create_web_app(require_auth=True, credentials_path=cred_path)
    r = app.test_client().get("/api/executive", headers={"Authorization": "Bearer wrong-value"})
    assert r.status_code == 401


def test_api_executive_accepts_valid_viewer_credential(tmp_path):
    cred_path = tmp_path / "dashboard_auth.yaml"
    cred_path.write_text(
        "entries:\n  - credential_hash: \"" + hash_credential("abc") + "\"\n    role: viewer\n",
        encoding="utf-8")
    app = create_web_app(require_auth=True, credentials_path=cred_path)
    r = app.test_client().get("/api/executive", headers={"Authorization": "Bearer abc"})
    assert r.status_code == 200


def test_api_executive_no_auth_required_by_default():
    app = create_web_app()
    r = app.test_client().get("/api/executive")
    assert r.status_code == 200


def test_api_executive_zero_state_with_no_seeded_logs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    db_path = str(tmp_path / "mem.db")
    mm = asyncio.run(_memory_manager(db_path))
    app = create_web_app(memory_manager=mm)
    r = app.test_client().get("/api/executive")
    body = r.get_json()
    assert r.status_code == 200
    assert body["net_savings_usd"] == 0.0
    assert body["roi"]["roi_ratio"] == 0.0
    assert body["budget"]["used_usd"] == 0.0
    assert body["governance"]["chain_ok"] is True
    assert body["governance"]["audit_records"] == 0


def test_api_executive_response_has_full_shape(tmp_path):
    db_path = str(tmp_path / "mem.db")
    mm = asyncio.run(_memory_manager(db_path))
    app = create_web_app(memory_manager=mm)
    r = app.test_client().get("/api/executive")
    body = r.get_json()
    assert set(body.keys()) == {
        "window_days", "generated_at", "net_savings_usd", "savings_rate_pct",
        "roi", "budget", "governance",
    }
    assert set(body["roi"].keys()) == {"roi_ratio", "estimated_time_saved_hours", "productivity_score"}
    assert set(body["budget"].keys()) == {"used_usd", "limit_usd", "pct_used", "alert_level"}
    assert set(body["governance"].keys()) == {"audit_records", "chain_ok", "denials", "failures"}


def test_api_executive_populated_state_matches_seeded_spend(tmp_path):
    db_path = str(tmp_path / "mem.db")
    mm = asyncio.run(_memory_manager(db_path))
    asyncio.run(mm.record_cost(tool="route_request", session_id="s1", model="m", cost_usd=4.0))
    asyncio.run(mm.record_cost(tool="route_request", session_id="s2", model="m", cost_usd=6.0))

    from promptwise.plugins.budget import BudgetGuardian
    app = create_web_app(memory_manager=mm)
    r = app.test_client().get("/api/executive?days=30")
    body = r.get_json()

    assert r.status_code == 200
    # total_cost_usd for this window is 10.0 (4.0 + 6.0) -- both net_savings'
    # underlying total_cost_usd and budget.used_usd must derive from it.
    assert body["budget"]["used_usd"] == 10.0
    guardian = BudgetGuardian()
    expected_pct = round(10.0 / guardian.limit_usd * 100, 1)
    assert body["budget"]["pct_used"] == expected_pct


def test_api_executive_budget_used_equals_net_savings_cost_basis(tmp_path):
    """Regression guard: net_savings_usd and budget.used_usd must be computed
    from the SAME total_cost_usd for the window -- a bug that read them from
    two different queries/windows would silently desync these two numbers on
    the same page."""
    db_path = str(tmp_path / "mem.db")
    mm = asyncio.run(_memory_manager(db_path))
    asyncio.run(mm.record_cost(tool="route_request", session_id="s1", model="m", cost_usd=7.5))

    app = create_web_app(memory_manager=mm)
    r = app.test_client().get("/api/executive?days=30")
    body = r.get_json()

    assert body["budget"]["used_usd"] == 7.5


def test_index_page_has_two_tab_buttons():
    app = create_web_app()
    r = app.test_client().get("/")
    html = r.get_data(as_text=True)
    assert 'id="tab-btn-ops"' in html
    assert 'id="tab-btn-exec"' in html


def test_index_page_has_two_tab_containers():
    app = create_web_app()
    r = app.test_client().get("/")
    html = r.get_data(as_text=True)
    assert 'id="tab-ops"' in html
    assert 'id="tab-exec"' in html


def test_index_page_executive_tab_fetches_api_executive():
    app = create_web_app()
    r = app.test_client().get("/")
    html = r.get_data(as_text=True)
    assert "/api/executive" in html
