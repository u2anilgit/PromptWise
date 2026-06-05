import asyncio
from flask import Flask, jsonify, request, render_template_string
from promptwise_v2.plugins.budget_guardian import BudgetGuardian
from promptwise_v2.plugins.roi_tracker import ROITracker

_INDEX_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>PromptWise Supreme — Performance & Cost Dashboard</title>
  <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap">
  <style>
    :root {
      --bg: #07090c;
      --surface: #0f1218;
      --card: #141820;
      --border: rgba(184,255,87,0.18);
      --lime: #b8ff57;
      --cyan: #40e0ff;
      --violet: #a855f7;
      --text: #dde4f0;
      --muted: #5a6680;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background: var(--bg);
      color: var(--text);
      font-family: 'Space Grotesk', sans-serif;
      padding: 2.5rem;
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      gap: 2rem;
    }
    header {
      border-bottom: 1px solid rgba(255,255,255,0.05);
      padding-bottom: 1.5rem;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    h1 {
      font-weight: 700;
      font-size: 2.2rem;
      background: linear-gradient(135deg, var(--lime), var(--cyan));
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
    }
    .badge {
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.8rem;
      padding: 0.3rem 0.8rem;
      border: 1px solid var(--border);
      border-radius: 20px;
      color: var(--lime);
      background: rgba(184,255,87,0.05);
    }
    .grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
      gap: 1.5rem;
    }
    .card {
      background: var(--card);
      border: 1px solid rgba(255,255,255,0.05);
      border-radius: 12px;
      padding: 1.5rem;
      position: relative;
      overflow: hidden;
      transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    }
    .card::before {
      content: '';
      position: absolute;
      top: 0; left: 0; right: 0; height: 3px;
      background: linear-gradient(90deg, var(--lime), var(--cyan));
      opacity: 0.7;
    }
    .card:hover {
      transform: translateY(-5px);
      box-shadow: 0 10px 20px rgba(0, 0, 0, 0.3);
      border-color: rgba(184,255,87,0.3);
    }
    .card-title {
      font-size: 0.9rem;
      text-transform: uppercase;
      letter-spacing: 0.1em;
      color: var(--muted);
      margin-bottom: 0.5rem;
    }
    .card-val {
      font-size: 2.5rem;
      font-weight: 700;
      color: #fff;
    }
    .card-sub {
      font-size: 0.85rem;
      color: var(--muted);
      margin-top: 0.5rem;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      margin-top: 1rem;
    }
    th, td {
      padding: 0.8rem;
      text-align: left;
      border-bottom: 1px solid rgba(255,255,255,0.05);
    }
    th {
      font-size: 0.85rem;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: var(--muted);
      background: rgba(255,255,255,0.02);
    }
    td {
      font-size: 0.95rem;
    }
    .section-title {
      font-size: 1.4rem;
      font-weight: 600;
      margin-bottom: 1rem;
      color: var(--cyan);
    }
  </style>
</head>
<body>
  <header>
    <div>
      <h1>PromptWise Supreme</h1>
      <p style="color: var(--muted); margin-top: 0.3rem;">Real-time Cost &amp; ROI Analytics Dashboard</p>
    </div>
    <span class="badge">v1.0.0</span>
  </header>

  <main class="grid">
    <div class="card">
      <div class="card-title">Total Cost</div>
      <div class="card-val" id="cost">$0.00</div>
      <div class="card-sub">Accrued API spend across all sessions</div>
    </div>
    <div class="card">
      <div class="card-title">Total API Calls</div>
      <div class="card-val" id="calls">0</div>
      <div class="card-sub">Optimization &amp; routing requests logged</div>
    </div>
    <div class="card">
      <div class="card-title">Token Savings</div>
      <div class="card-val" id="savings">0.0%</div>
      <div class="card-sub">Average input tokens trimmed by compaction/rewriter</div>
    </div>
    <div class="card">
      <div class="card-title">Productivity ROI</div>
      <div class="card-val" id="roi">0.00x</div>
      <div class="card-sub">Value of hours saved vs LLM cost</div>
    </div>
  </main>

  <section class="card" style="grid-column: 1 / -1;">
    <h2 class="section-title">Model Energy Efficiency Leaderboard</h2>
    <table>
      <thead>
        <tr>
          <th>Model Name</th>
          <th>Efficiency Score</th>
          <th>Cost Classification</th>
        </tr>
      </thead>
      <tbody id="leaderboard">
        <!-- Rendered dynamically -->
      </tbody>
    </table>
  </section>

  <script>
    async function loadStats() {
      try {
        const res = await fetch('/api/stats');
        const data = await res.json();
        document.getElementById('cost').textContent = '$' + (data.total_cost_usd || 0).toFixed(4);
        document.getElementById('calls').textContent = data.total_calls || 0;
        document.getElementById('savings').textContent = (data.avg_saving_pct || 0).toFixed(1) + '%';
        
        const roiRes = await fetch('/api/roi?total_cost_usd=' + (data.total_cost_usd || 0.01) + '&tokens_saved=' + (data.total_calls * 500));
        const roiData = await roiRes.json();
        document.getElementById('roi').textContent = (roiData.roi_ratio || 0).toFixed(2) + 'x';
      } catch (e) {
        console.error(e);
      }
    }

    async function loadModels() {
      try {
        const res = await fetch('/api/models');
        const data = await res.json();
        const tbody = document.getElementById('leaderboard');
        tbody.innerHTML = data.leaderboard.map(m => `
          <tr>
            <td style="font-weight: 500;">\${m.model}</td>
            <td>
              <div style="display: flex; align-items: center; gap: 0.5rem;">
                <div style="width: 100px; height: 6px; background: rgba(255,255,255,0.05); border-radius: 3px; overflow: hidden;">
                  <div style="width: \${m.energy_score * 100}%; height: 100%; background: var(--lime);"></div>
                </div>
                \${m.energy_score.toFixed(1)}
              </div>
            </td>
            <td><span style="color: \${m.cost_tier === 'fast' ? 'var(--lime)' : m.cost_tier === 'balanced' ? 'var(--cyan)' : 'var(--violet)'}">\${m.cost_tier.toUpperCase()}</span></td>
          </tr>
        `).join('');
      } catch (e) {
        console.error(e);
      }
    }

    loadStats();
    loadModels();
  </script>
</body>
</html>
"""


def create_app(mock_mode: bool = False, stats_service=None, memory_manager=None) -> Flask:
    app = Flask(__name__)
    guardian = BudgetGuardian()
    roi_tracker = ROITracker()

    @app.route("/")
    def index():
        return render_template_string(_INDEX_HTML)

    @app.route("/api/stats")
    def api_stats():
        if stats_service:
            try:
                loop = asyncio.new_event_loop()
                snapshot = loop.run_until_complete(stats_service.snapshot())
                loop.close()
                return jsonify({
                    "total_cost_usd": getattr(snapshot, "total_cost_usd", 0.0),
                    "total_calls": getattr(snapshot, "total_calls", 0),
                    "avg_saving_pct": getattr(snapshot, "avg_saving_pct", 0.0),
                    "cache_hit_rate": getattr(snapshot, "cache_hit_rate", 0.0),
                })
            except Exception as e:
                return jsonify({"error": str(e)})

        if mock_mode:
            return jsonify({
                "total_cost_usd": 0.054,
                "total_calls": 12,
                "avg_saving_pct": 24.5,
                "cache_hit_rate": 0.15,
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
