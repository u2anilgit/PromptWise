from promptwise_v2.dashboard.cli_dashboard import CLIDashboard


def test_render_budget_table():
    dash = CLIDashboard()
    table = dash.render_budget(used_usd=3.0, limit_usd=10.0,
                                daily_burn=0.30, projected=9.0, alert="ok")
    assert "Budget" in table
    assert "3.0" in table


def test_render_task_table():
    dash = CLIDashboard()
    tasks = [
        {"id": "t1", "action": "read", "status": "completed", "cost_usd": 0.001},
        {"id": "t2", "action": "summarize", "status": "in_progress", "cost_usd": 0.002},
    ]
    table = dash.render_tasks(tasks)
    assert "t1" in table
    assert "completed" in table


def test_render_plugin_status():
    dash = CLIDashboard()
    plugins = [
        {"name": "monitoring", "active": True},
        {"name": "codereview_bridge", "active": False},
    ]
    output = dash.render_plugins(plugins)
    assert "monitoring" in output
    assert "codereview_bridge" in output


def test_render_burn_rate():
    dash = CLIDashboard()
    output = dash.render_burn_rate(rate_usd_per_min=0.05)
    assert "0.05" in output or "burn" in output.lower()
