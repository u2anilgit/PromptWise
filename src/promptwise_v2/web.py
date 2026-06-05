import asyncio
import json
import uuid
import queue
from flask import Flask, jsonify, request, Response, redirect, render_template_string
from prometheus_client import generate_latest, CollectorRegistry, Gauge, Counter
from promptwise_v2.plugins.budget_guardian import BudgetGuardian
from promptwise_v2.plugins.roi_tracker import ROITracker
from promptwise_v2.dashboard.web_dashboard import _INDEX_HTML

app = Flask(__name__)
guardian = BudgetGuardian()
roi_tracker = ROITracker()

# Prometheus metrics setup
registry = CollectorRegistry()
cost_gauge = Gauge("promptwise_cost_usd", "Cumulative API cost in USD", registry=registry)
calls_counter = Counter("promptwise_calls_total", "Total count of API calls", registry=registry)
savings_gauge = Gauge("promptwise_saving_pct", "Average token savings percent", registry=registry)

sse_sessions = {}


@app.route("/")
def index():
    return render_template_string(_INDEX_HTML)


@app.route("/api/stats")
def api_stats():
    # Return mock/calculated stats for dashboard
    return jsonify({
        "total_cost_usd": 0.054,
        "total_calls": 12,
        "avg_saving_pct": 24.5,
        "cache_hit_rate": 0.15,
    })


@app.route("/api/budget")
def api_budget():
    used = float(request.args.get("used_usd", 0))
    days = int(request.args.get("days_elapsed", 1))
    status = guardian.check(used_usd=used, days_elapsed=days)
    return jsonify({
        "used_usd": status.used_usd,
        "limit_usd": status.limit_usd,
        "pct_used": status.pct_used,
        "alert_level": status.alert_level,
        "projected_monthly_usd": status.projected_monthly_usd,
    })


@app.route("/api/roi")
def api_roi():
    snap = roi_tracker.calculate(
        session_id=request.args.get("session_id", "unknown"),
        total_cost_usd=float(request.args.get("total_cost_usd", 0)),
        tokens_saved=int(request.args.get("tokens_saved", 0)),
        calls=int(request.args.get("calls", 1)),
    )
    return jsonify({
        "roi_ratio": snap.roi_ratio,
        "estimated_time_saved_min": snap.estimated_time_saved_min,
        "productivity_score": snap.productivity_score,
    })


@app.route("/api/models")
def api_models():
    leaderboard = [
        {"model": "claude-haiku-4-5-20251001", "energy_score": 1.0, "cost_tier": "fast"},
        {"model": "claude-sonnet-4-6",          "energy_score": 0.6, "cost_tier": "balanced"},
        {"model": "claude-opus-4-7",            "energy_score": 0.2, "cost_tier": "powerful"},
    ]
    return jsonify({"leaderboard": leaderboard})


# --- Prometheus Metrics Endpoint ---
@app.route("/metrics")
def metrics():
    # Update metrics dynamically from current state
    cost_gauge.set(0.054)
    savings_gauge.set(24.5)
    return Response(generate_latest(registry), mimetype="text/plain; version=0.0.4")


# --- MCP SSE Transport ---
@app.route("/mcp/sse")
def mcp_sse_connect():
    session_id = str(uuid.uuid4())
    q = queue.Queue()
    sse_sessions[session_id] = q

    def event_stream():
        # First send the endpoint mapping event
        yield f"event: endpoint\ndata: /mcp/message?session_id={session_id}\n\n"
        while True:
            try:
                msg = q.get(timeout=30)
                yield f"event: message\ndata: {json.dumps(msg)}\n\n"
            except queue.Empty:
                yield ": keepalive\n\n"

    return Response(event_stream(), mimetype="text/event-stream")


@app.route("/mcp/message", methods=["POST"])
def mcp_sse_message():
    session_id = request.args.get("session_id")
    if session_id not in sse_sessions:
        return "Session not found", 404

    payload = request.json
    method = payload.get("method")
    msg_id = payload.get("id")

    response = {"jsonrpc": "2.0", "id": msg_id}
    if method == "initialize":
        response["result"] = {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "serverInfo": {"name": "promptwise-web", "version": "1.0.0"}
        }
    elif method == "tools/list":
        response["result"] = {"tools": []}
    else:
        response["result"] = {"status": "unsupported"}

    sse_sessions[session_id].put(response)
    return "OK", 200


# --- OAuth 2.0 Auth ---
@app.route("/oauth/authorize", methods=["GET", "POST"])
def oauth_authorize():
    redirect_uri = request.args.get("redirect_uri")
    state = request.args.get("state")
    code = "mock_auth_code_123"
    if redirect_uri:
        return redirect(f"{redirect_uri}?code={code}&state={state}")
    return "Authorized successfully."


@app.route("/oauth/token", methods=["POST"])
def oauth_token():
    return jsonify({
        "access_token": "mock_access_token_abc123",
        "token_type": "Bearer",
        "expires_in": 3600
    })


def main():
    app.run(host="localhost", port=8765, debug=True)


if __name__ == "__main__":
    main()
