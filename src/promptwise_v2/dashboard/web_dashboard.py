from flask import Flask, jsonify, request, render_template_string
from promptwise_v2.plugins.budget_guardian import BudgetGuardian
from promptwise_v2.plugins.roi_tracker import ROITracker

_INDEX_HTML = """<!DOCTYPE html>
<html><head><title>PromptWise v2 Dashboard</title>
<style>
body{font-family:monospace;background:#0d1117;color:#e6edf3;padding:2rem;}
h1{color:#58a6ff;}
table{width:100%;border-collapse:collapse;}
th,td{padding:0.5rem;border:1px solid #30363d;text-align:left;}
th{background:#161b22;}
</style></head>
<body>
<h1>PromptWise v2.0 — Cost &amp; ROI Dashboard</h1>
<p>Real-time model cost tracking, burn-rate monitoring, and ROI analytics.</p>
<div id="stats">Loading...</div>
<script>
async function load(){
  const r=await fetch('/api/stats');
  const d=await r.json();
  document.getElementById('stats').innerHTML=
    '<table><tr><th>Metric</th><th>Value</th></tr>'+
    '<tr><td>Total Cost</td><td>$'+d.total_cost_usd+'</td></tr>'+
    '<tr><td>Total Calls</td><td>'+d.total_calls+'</td></tr>'+
    '<tr><td>Avg Saving %</td><td>'+d.avg_saving_pct+'%</td></tr>'+
    '</table>';
}
load();
</script>
</body></html>"""


def create_app(mock_mode: bool = False) -> Flask:
    app = Flask(__name__)
    guardian = BudgetGuardian()
    roi_tracker = ROITracker()

    @app.route("/")
    def index():
        return render_template_string(_INDEX_HTML)

    @app.route("/api/stats")
    def api_stats():
        if mock_mode:
            return jsonify({
                "total_cost_usd": 0.0,
                "total_calls": 0,
                "avg_saving_pct": 0.0,
                "cache_hit_rate": 0.0,
                "cost_by_model": {},
                "calls_by_tool": {},
            })
        return jsonify({"error": "live mode requires stats service"})

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

    return app
