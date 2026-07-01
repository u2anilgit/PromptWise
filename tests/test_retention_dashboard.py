"""Phase 6 WP7 — dashboard retention + metric model + windowed endpoint.

Pure retention logic is unit-tested; the Flask endpoint is smoke-tested with a
stub data source. Local, no external services.
"""
from promptwise.dashboard import retention as R


# ── window clamping (raw <=90, archive <=365) ────────────────────────────────
def test_clamp_raw_caps_at_90():
    assert R.clamp_window(120, raw=True) == 90
    assert R.clamp_window(30, raw=True) == 30


def test_clamp_archive_caps_at_365():
    assert R.clamp_window(400, raw=False) == 365
    assert R.clamp_window(180, raw=False) == 180


def test_clamp_garbage_defaults():
    assert R.clamp_window("abc", raw=True) == R.DEFAULT_WINDOW


def test_window_cutoff_is_before_now():
    now = "2026-07-01T00:00:00+00:00"
    cut = R.window_cutoff(30, now)
    assert cut < now
    assert cut.startswith("2026-06-01")


# ── rollup ───────────────────────────────────────────────────────────────────
def test_rollup_aggregates_by_day_and_model():
    logs = [
        {"ts": "2026-06-01T10:00:00", "model": "m-a", "cost_usd": 1.0, "input_tokens": 100, "output_tokens": 50, "saving_pct": 20},
        {"ts": "2026-06-01T12:00:00", "model": "m-a", "cost_usd": 2.0, "input_tokens": 100, "output_tokens": 50, "saving_pct": 40},
        {"ts": "2026-06-02T09:00:00", "model": "m-b", "cost_usd": 0.5, "input_tokens": 10, "output_tokens": 5},
    ]
    rows = R.rollup(logs)
    a = [r for r in rows if r["day"] == "2026-06-01" and r["model"] == "m-a"][0]
    assert a["calls"] == 2
    assert a["cost_usd"] == 3.0
    assert a["avg_saving_pct"] == 30.0
    assert len(rows) == 2


# ── metric model + North Star ────────────────────────────────────────────────
def _logs():
    return [
        {"ts": "2026-06-01T10:00:00", "model": "cheap", "session_id": "s1", "tool": "route_request",
         "cost_usd": 0.10, "input_tokens": 1_000_000, "output_tokens": 0, "saving_pct": 25, "lines": 40},
        {"ts": "2026-06-02T10:00:00", "model": "cheap", "session_id": "s2", "tool": "summarize_thread",
         "cost_usd": 0.05, "input_tokens": 500_000, "output_tokens": 0, "saving_pct": 15, "lines": 10},
    ]


def test_dashboard_model_net_savings_vs_top_tier():
    m = R.build_dashboard_model(_logs(), window_days=30, now_iso="2026-07-01T00:00:00+00:00",
                                top_tier_price={"input_per_mtok": 15.0, "output_per_mtok": 75.0})
    h = m["headline"]
    # baseline = 1.5M input tok * $15/Mtok = $22.5; actual = $0.15 -> big net savings
    assert h["net_savings_usd"] > 20
    assert 0 < h["savings_rate_pct"] <= 100
    assert h["total_cost_usd"] == 0.15
    assert h["lines_changed"] == 50
    assert h["cost_per_task_usd"] == 0.075  # 0.15 / 2 sessions


def test_dashboard_model_without_price_degrades_to_zero_net():
    m = R.build_dashboard_model(_logs(), window_days=30, now_iso="2026-07-01T00:00:00+00:00",
                                top_tier_price=None)
    assert m["headline"]["net_savings_usd"] == 0.0


def test_dashboard_breakdowns_and_trends():
    m = R.build_dashboard_model(_logs(), window_days=30, now_iso="2026-07-01T00:00:00+00:00")
    assert m["breakdowns"]["by_model"][0]["key"] == "cheap"
    assert set(m["trends"]["spend_by_day"].keys()) == {"2026-06-01", "2026-06-02"}


# ── governance summary from state dir ────────────────────────────────────────
def test_governance_summary_counts(tmp_path):
    d = tmp_path / ".promptwise"
    d.mkdir()
    (d / "audit.jsonl").write_text('{"task":"Write a.py"}\n{"task":"failure:Bash"}\n', encoding="utf-8")
    (d / "denials.jsonl").write_text('{"tool_name":"Bash"}\n', encoding="utf-8")
    g = R.governance_summary(d)
    assert g["audit_records"] == 2
    assert g["failures"] == 1
    assert g["denials"] == 1


# ── windowed endpoint (Flask smoke) ──────────────────────────────────────────
class _StubMemory:
    async def raw_cost_logs(self, since=None):
        return _logs()


def test_dashboard_endpoint_returns_model():
    from promptwise.dashboard.web import create_web_app
    app = create_web_app(memory_manager=_StubMemory())
    client = app.test_client()
    r = client.get("/api/dashboard?days=30")
    assert r.status_code == 200
    body = r.get_json()
    assert "headline" in body and "governance" in body
    assert body["window_days"] == 30


def test_dashboard_endpoint_clamps_archive_window():
    from promptwise.dashboard.web import create_web_app
    app = create_web_app(memory_manager=_StubMemory())
    r = app.test_client().get("/api/dashboard?days=400")
    assert r.status_code == 200
    assert r.get_json()["window_days"] == 365  # 1-year archive cap


def test_index_page_renders():
    from promptwise.dashboard.web import create_web_app
    app = create_web_app()
    r = app.test_client().get("/")
    assert r.status_code == 200
    assert b"PromptWise" in r.data
