import json
from promptwise_v2.dashboard.web_dashboard import create_app


def test_index_returns_200():
    app = create_app(mock_mode=True)
    client = app.test_client()
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"PromptWise" in resp.data


def test_api_stats_returns_json():
    app = create_app(mock_mode=True)
    client = app.test_client()
    resp = client.get("/api/stats")
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert "total_cost_usd" in data


def test_api_budget_returns_json():
    app = create_app(mock_mode=True)
    client = app.test_client()
    resp = client.get("/api/budget?used_usd=3.0&days_elapsed=10")
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert "alert_level" in data


def test_api_roi_returns_json():
    app = create_app(mock_mode=True)
    client = app.test_client()
    resp = client.get("/api/roi?session_id=s1&total_cost_usd=1.0&tokens_saved=5000&calls=10")
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert "roi_ratio" in data


def test_api_models_returns_leaderboard():
    app = create_app(mock_mode=True)
    client = app.test_client()
    resp = client.get("/api/models")
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert "leaderboard" in data
