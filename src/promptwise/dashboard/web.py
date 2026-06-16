from flask import Flask, jsonify, request, render_template_string

_INDEX_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>PromptWise — Dashboard</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { background: #07090c; color: #dde4f0; font-family: -apple-system, sans-serif; padding: 2rem; }
    h1 { font-size: 2rem; color: #b8ff57; margin-bottom: 1.5rem; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 1rem; }
    .card { background: #141820; border: 1px solid rgba(255,255,255,0.05); border-radius: 8px; padding: 1.5rem; }
    .card-title { font-size: 0.85rem; text-transform: uppercase; color: #5a6680; margin-bottom: 0.5rem; }
    .card-val { font-size: 2rem; font-weight: 700; color: #fff; }
    .card-sub { font-size: 0.8rem; color: #5a6680; margin-top: 0.5rem; }
    table { width: 100%; border-collapse: collapse; margin-top: 1rem; }
    th, td { padding: 0.7rem; text-align: left; border-bottom: 1px solid rgba(255,255,255,0.05); }
    th { color: #5a6680; font-size: 0.8rem; text-transform: uppercase; }
    .section-title { color: #40e0ff; font-size: 1.2rem; margin: 1.5rem 0 0.5rem; }
  </style>
</head>
<body>
  <h1>PromptWise</h1>
  <div class="grid">
    <div class="card"><div class="card-title">Total Cost</div><div class="card-val" id="cost">$0.00</div><div class="card-sub">API spend across all sessions</div></div>
    <div class="card"><div class="card-title">API Calls</div><div class="card-val" id="calls">0</div><div class="card-sub">Requests logged</div></div>
    <div class="card"><div class="card-title">Token Savings</div><div class="card-val" id="savings">0.0%</div><div class="card-sub">Avg tokens trimmed</div></div>
    <div class="card"><div class="card-title">Productivity ROI</div><div class="card-val" id="roi">0.00x</div><div class="card-sub">Value vs cost</div></div>
  </div>

  <h2 class="section-title">Model Energy Efficiency</h2>
  <table>
    <thead><tr><th>Model</th><th>Score</th><th>Tier</th></tr></thead>
    <tbody id="leaderboard"></tbody>
  </table>

  <script>
    async function load() {
      try {
        const s = await (await fetch('/api/stats')).json();
        document.getElementById('cost').textContent = '$' + (s.total_cost_usd || 0).toFixed(4);
        document.getElementById('calls').textContent = s.total_calls || 0;
        document.getElementById('savings').textContent = (s.avg_saving_pct || 0).toFixed(1) + '%';
        const r = await (await fetch('/api/roi?total_cost_usd=' + (s.total_cost_usd || 0.01) + '&tokens_saved=' + ((s.total_calls || 1) * 500))).json();
        document.getElementById('roi').textContent = (r.roi_ratio || 0).toFixed(2) + 'x';
        const m = await (await fetch('/api/models')).json();
        document.getElementById('leaderboard').innerHTML = (m.leaderboard || []).map(x => '<tr><td>' + x.model + '</td><td>' + (x.energy_score || 0).toFixed(1) + '</td><td>' + (x.cost_tier || '').toUpperCase() + '</td></tr>').join('');
      } catch(e) { console.error(e); }
    }
    load();
  </script>
</body>
</html>"""


def create_web_app(stats_service=None, memory_manager=None) -> Flask:
    app = Flask(__name__)

    @app.route("/")
    def index():
        return render_template_string(_INDEX_HTML)

    @app.route("/api/stats")
    def api_stats():
        if stats_service:
            try:
                import asyncio
                loop = asyncio.new_event_loop()
                snap = loop.run_until_complete(stats_service.snapshot())
                loop.close()
                return jsonify({"total_cost_usd": snap.get("total_cost_usd", 0), "total_calls": snap.get("total_calls", 0),
                                "avg_saving_pct": snap.get("avg_saving_pct", 0), "cache_hit_rate": snap.get("cache_hit_rate", 0)})
            except Exception as e:
                return jsonify({"error": str(e)})
        return jsonify({"total_cost_usd": 0.054, "total_calls": 12, "avg_saving_pct": 24.5, "cache_hit_rate": 0.15})

    @app.route("/api/budget")
    def api_budget():
        from promptwise.plugins.budget import BudgetGuardian
        g = BudgetGuardian()
        s = g.check(used_usd=float(request.args.get("used_usd", 0)), days_elapsed=int(request.args.get("days_elapsed", 1)))
        return jsonify({"used_usd": s.used_usd, "limit_usd": s.limit_usd, "pct_used": s.pct_used, "alert_level": s.alert_level})

    @app.route("/api/roi")
    def api_roi():
        from promptwise.plugins.roi import ROITracker
        r = ROITracker().calculate(session_id=request.args.get("session_id", "unknown"),
                                    total_cost_usd=float(request.args.get("total_cost_usd", 0)),
                                    tokens_saved=int(request.args.get("tokens_saved", 0)),
                                    calls=int(request.args.get("calls", 1)))
        return jsonify({"roi_ratio": r.roi_ratio, "estimated_time_saved_min": r.estimated_time_saved_min, "productivity_score": r.productivity_score})

    @app.route("/api/models")
    def api_models():
        return jsonify({"leaderboard": [
            {"model": "claude-haiku-4-5-20251001", "energy_score": 1.0, "cost_tier": "fast"},
            {"model": "claude-sonnet-4-6", "energy_score": 0.6, "cost_tier": "balanced"},
            {"model": "claude-opus-4-7", "energy_score": 0.2, "cost_tier": "powerful"},
        ]})

    @app.route("/metrics")
    def metrics():
        from prometheus_client import generate_latest, CollectorRegistry, Gauge
        reg = CollectorRegistry()
        Gauge("promptwise_cost_usd", "", registry=reg).set(0.054)
        from flask import Response
        return Response(generate_latest(reg), mimetype="text/plain; version=0.0.4")

    return app
