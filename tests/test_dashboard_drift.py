from promptwise.dashboard.cli import CLIDashboard


def test_render_drift_returns_str_with_paths():
    dash = CLIDashboard()
    results = {
        "a/config.json": "in-sync",
        "b/config.json": "drift",
        "c/config.json": "conflict: both changed",
    }
    out = dash.render_drift(results)
    assert isinstance(out, str)
    for path in results:
        assert path in out


def test_render_drift_status_markers():
    dash = CLIDashboard()
    results = {
        "ok.json": "in-sync",
        "drifted.json": "drift",
        "clash.json": "conflict: diverged",
    }
    out = dash.render_drift(results)
    assert "[OK]" in out
    assert "[DRIFT]" in out
    assert "[CONFLICT]" in out


def test_render_drift_summary_differs():
    dash = CLIDashboard()
    in_sync = dash.render_drift({"a.json": "in-sync", "b.json": "in-sync"})
    needs_attention = dash.render_drift({"a.json": "in-sync", "b.json": "drift"})
    assert "all in sync" in in_sync
    assert "all in sync" not in needs_attention
    assert in_sync != needs_attention


def test_render_drift_needs_attention_count():
    dash = CLIDashboard()
    out = dash.render_drift({
        "a.json": "drift",
        "b.json": "conflict: x",
        "c.json": "in-sync",
    })
    assert "2 file(s) need attention" in out


def test_render_drift_empty_dict_all_in_sync():
    dash = CLIDashboard()
    out = dash.render_drift({})
    assert isinstance(out, str)
    assert "all in sync" in out


def test_render_drift_unknown_status_marker():
    dash = CLIDashboard()
    out = dash.render_drift({"weird.json": "written"})
    assert "[?]" in out


def test_render_drift_has_title():
    dash = CLIDashboard()
    out = dash.render_drift({"a.json": "in-sync"})
    assert "Config Drift" in out
