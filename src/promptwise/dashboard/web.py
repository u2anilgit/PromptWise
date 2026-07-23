from flask import Flask, jsonify, request, render_template_string

from promptwise.dashboard.auth import load_credentials, find_identity, role_satisfies

_INDEX_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>PromptWise — Governance & Cost Dashboard</title>
  <style>
    :root { --bg:#0a0c10; --card:#141820; --line:rgba(255,255,255,.06);
            --ink:#e7e9f0; --mut:#7a869e; --accent:#818cf8; --good:#34d399; --warn:#fbbf24; --bad:#fb7185; }
    * { box-sizing:border-box; margin:0; padding:0; }
    body { background:var(--bg); color:var(--ink); font-family:-apple-system,Segoe UI,Roboto,sans-serif; padding:2rem; line-height:1.5; }
    header { display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:1rem; margin-bottom:1.5rem; }
    h1 { font-size:1.6rem; letter-spacing:-.02em; }
    h1 small { color:var(--mut); font-weight:400; font-size:.9rem; margin-left:.5rem; }
    select { background:var(--card); color:var(--ink); border:1px solid var(--line); border-radius:8px; padding:.5rem .8rem; font-size:.9rem; }
    .hero { background:linear-gradient(135deg,rgba(129,140,248,.14),transparent); border:1px solid var(--line); border-radius:14px; padding:1.6rem 1.8rem; margin-bottom:1.2rem; }
    .hero .lbl { font-size:.8rem; text-transform:uppercase; letter-spacing:.08em; color:var(--mut); }
    .hero .val { font-size:2.6rem; font-weight:700; color:var(--good); }
    .hero .sub { color:var(--mut); font-size:.9rem; }
    .grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(200px,1fr)); gap:1rem; margin-bottom:1.4rem; }
    .card { background:var(--card); border:1px solid var(--line); border-radius:10px; padding:1.2rem 1.4rem; }
    .card .t { font-size:.75rem; text-transform:uppercase; letter-spacing:.06em; color:var(--mut); margin-bottom:.4rem; }
    .card .v { font-size:1.7rem; font-weight:700; }
    .card .s { font-size:.78rem; color:var(--mut); margin-top:.3rem; }
    .sect { color:var(--accent); font-size:1.05rem; margin:1.4rem 0 .6rem; letter-spacing:-.01em; }
    table { width:100%; border-collapse:collapse; background:var(--card); border:1px solid var(--line); border-radius:10px; overflow:hidden; }
    th,td { padding:.65rem .9rem; text-align:left; border-bottom:1px solid var(--line); font-size:.88rem; }
    th { color:var(--mut); font-size:.72rem; text-transform:uppercase; letter-spacing:.05em; }
    tr:last-child td { border-bottom:none; }
    .gov { display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:.8rem; }
    .pill { background:var(--card); border:1px solid var(--line); border-radius:10px; padding:.9rem 1rem; }
    .pill .v { font-size:1.4rem; font-weight:700; }
    .ok { color:var(--good); } .no { color:var(--bad); }
    .bars { display:flex; gap:3px; align-items:flex-end; height:60px; margin-top:.5rem; }
    .bars .b { flex:1; background:var(--accent); border-radius:2px 2px 0 0; min-height:2px; opacity:.85; }
    .muted { color:var(--mut); font-size:.82rem; }
  </style>
</head>
<body>
  <header>
    <h1>PromptWise <small id="win-lbl">last 30 days</small></h1>
    <select id="win" onchange="load()">
      <option value="7">Last 7 days</option>
      <option value="30" selected>Last 30 days</option>
      <option value="60">Last 60 days</option>
      <option value="90">Last 90 days</option>
      <option value="180">Last 180 days (archive)</option>
      <option value="365">Last 1 year (archive)</option>
    </select>
  </header>

  <div class="hero">
    <div class="lbl">Net savings this window &mdash; North Star</div>
    <div class="val" id="net">$0.00</div>
    <div class="sub" id="net-sub">vs. running every call on the top tier</div>
  </div>

  <div class="grid" id="cards"></div>

  <div class="sect">Spend trend</div>
  <div class="bars" id="trend"></div>
  <div class="muted" id="trend-lbl"></div>

  <div class="sect">By model <span class="muted">(deprecated retained)</span></div>
  <table><thead><tr><th>Model</th><th>Calls</th><th>Cost</th></tr></thead><tbody id="by-model"></tbody></table>

  <div class="sect">By skill</div>
  <table><thead><tr><th>Skill / tool</th><th>Calls</th><th>Cost</th></tr></thead><tbody id="by-skill"></tbody></table>

  <div class="sect">Recommendations <span class="muted">(ranked · offline · min-sample gated)</span></div>
  <table><thead><tr><th>Category</th><th>Recommendation</th><th>Impact</th><th>Confidence</th></tr></thead><tbody id="recs"></tbody></table>

  <div class="sect">Governance &mdash; is it working?</div>
  <div class="gov" id="gov"></div>

  <div class="sect">Governor actions <span class="muted">(Phase 9 &middot; policy-gated &middot; reversible &middot; default advise-only)</span></div>
  <div class="muted" id="gov-mode"></div>
  <table><thead><tr><th>Type</th><th>Blast radius</th><th>Action</th><th>Policy</th><th>Status</th></tr></thead><tbody id="gov-actions"></tbody></table>

  <script>
    function money(x){ return '$' + (Number(x)||0).toFixed(Math.abs(x)<1?4:2); }
    async function load(){
      const days = document.getElementById('win').value;
      document.getElementById('win-lbl').textContent = 'last ' + days + ' days';
      let d;
      try { d = await (await fetch('/api/dashboard?days=' + days)).json(); }
      catch(e){ console.error(e); return; }
      const h = d.headline || {};
      document.getElementById('net').textContent = money(h.net_savings_usd);
      document.getElementById('net-sub').textContent = (h.savings_rate_pct||0) + '% saved vs. top-tier baseline';
      document.getElementById('cards').innerHTML = [
        ['Total cost', money(h.total_cost_usd), (h.total_calls||0)+' calls'],
        ['Tokens saved', (h.tokens_saved_pct||0)+'%', 'compression + caching'],
        ['Cost per task', money(h.cost_per_task_usd), 'per session'],
        ['Lines changed', (h.lines_changed||0), 'audited edits'],
      ].map(c=>`<div class="card"><div class="t">${c[0]}</div><div class="v">${c[1]}</div><div class="s">${c[2]}</div></div>`).join('');
      const spend = (d.trends&&d.trends.spend_by_day)||{};
      const days_sorted = Object.keys(spend).sort();
      const max = Math.max(0.0001, ...days_sorted.map(k=>spend[k]));
      document.getElementById('trend').innerHTML = days_sorted.map(k=>`<div class="b" style="height:${Math.round(spend[k]/max*100)}%" title="${k}: ${money(spend[k])}"></div>`).join('') || '<span class="muted">no data yet</span>';
      document.getElementById('trend-lbl').textContent = days_sorted.length ? (days_sorted[0]+' → '+days_sorted[days_sorted.length-1]) : '';
      const bm = (d.breakdowns&&d.breakdowns.by_model)||[];
      document.getElementById('by-model').innerHTML = bm.map(r=>`<tr><td>${r.key}</td><td>${r.calls}</td><td>${money(r.cost_usd)}</td></tr>`).join('') || '<tr><td colspan=3 class="muted">no data</td></tr>';
      const bs = (d.breakdowns&&d.breakdowns.by_skill)||[];
      document.getElementById('by-skill').innerHTML = bs.map(r=>`<tr><td>${r.key}</td><td>${r.calls}</td><td>${money(r.cost_usd)}</td></tr>`).join('') || '<tr><td colspan=3 class="muted">no data</td></tr>';
      try {
        const ir = await (await fetch('/api/insights?days=' + days)).json();
        const recs = (ir.recommendations||[]);
        const cat = {routing:'#818cf8', cost:'#fbbf24', quality:'#fb7185', budget:'#34d399'};
        document.getElementById('recs').innerHTML = recs.map(r=>{
          const usd = (r.category!=='quality');
          const imp = usd ? money(r.estimated_impact) : (Number(r.estimated_impact)||0).toFixed(2);
          const c = cat[r.category]||'#7a869e';
          return `<tr><td><span style="color:${c};text-transform:capitalize">${r.category}</span></td>`+
                 `<td>${r.message}</td><td>${imp}</td><td>${Math.round((r.confidence||0)*100)}%</td></tr>`;
        }).join('') || '<tr><td colspan=4 class="muted">no recommendations yet</td></tr>';
      } catch(e){ document.getElementById('recs').innerHTML = '<tr><td colspan=4 class="muted">no data</td></tr>'; }
      const g = d.governance || {};
      document.getElementById('gov').innerHTML = [
        ['Audit records', g.audit_records||0, ''],
        ['Chain', g.chain_ok===false?'BROKEN':'OK', g.chain_ok===false?'no':'ok'],
        ['Denials logged', g.denials||0, ''],
        ['Failures captured', g.failures||0, ''],
      ].map(p=>`<div class="pill"><div class="t muted">${p[0]}</div><div class="v ${p[2]}">${p[1]}</div></div>`).join('');
      try {
        const gv = await (await fetch('/api/governor')).json();
        const props = (gv.proposals||[]);
        document.getElementById('gov-mode').textContent = props.length
          ? ('mode: ' + (gv.mode||'advise') + ' · ' + props.length + ' proposal(s)')
          : 'No governor run recorded yet (advise-only by default).';
        const scol = {applied:'#34d399', would_apply:'#818cf8', advisory:'#7a869e',
                      blocked:'#fb7185', noop:'#7a869e', failed:'#fb7185'};
        document.getElementById('gov-actions').innerHTML = props.map(p=>{
          const v = p.verdict||{}; const pol = (v.allowed===false)?'BLOCK':'OK';
          const pc = (v.allowed===false)?'#fb7185':'#34d399';
          const sc = scol[p.status]||'#7a869e';
          const br = (p.blast_radius==='safe')?'#34d399':'#fbbf24';
          return `<tr><td>${p.type||''}</td>`+
                 `<td><span style="color:${br}">${p.blast_radius||''}</span></td>`+
                 `<td>${p.description||''}</td>`+
                 `<td><span style="color:${pc}">${pol}</span></td>`+
                 `<td><span style="color:${sc}">${p.status||''}</span></td></tr>`;
        }).join('') || '<tr><td colspan=5 class="muted">no governor proposals yet</td></tr>';
      } catch(e){ document.getElementById('gov-actions').innerHTML = '<tr><td colspan=5 class="muted">no data</td></tr>'; }
    }
    load();
  </script>
</body>
</html>"""


def _run_async(coro):
    import asyncio
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def create_web_app(stats_service=None, memory_manager=None, require_auth: bool = False,
                    credentials_path: str = "config/dashboard_auth.yaml") -> Flask:
    app = Flask(__name__)
    credentials = load_credentials(credentials_path) if require_auth else []

    def require_role(minimum: str):
        def decorator(fn):
            from functools import wraps

            @wraps(fn)
            def wrapper(*args, **kwargs):
                if not require_auth:
                    return fn(*args, **kwargs)
                auth_header = request.headers.get("Authorization", "")
                if not auth_header.startswith("Bearer "):
                    return jsonify({"error": "missing credential"}), 401
                identity = find_identity(auth_header[len("Bearer "):], credentials)
                if identity is None:
                    return jsonify({"error": "invalid credential"}), 401
                if not role_satisfies(identity.role, minimum):
                    return jsonify({"error": "insufficient role"}), 403
                return fn(*args, **kwargs)
            return wrapper
        return decorator

    @app.route("/")
    def index():
        return render_template_string(_INDEX_HTML)

    @app.route("/api/dashboard")
    @require_role("viewer")
    def api_dashboard():
        """Windowed metric model: headline (net savings), trends, breakdowns,
        governance. Raw granularity is capped at 90 days; archive views run to
        1 year. Filtering is pushed into the query, never done in the browser."""
        from promptwise.dashboard import retention as R
        raw = str(request.args.get("days", R.DEFAULT_WINDOW))
        is_archive = int(raw) > R.HOT_MAX_DAYS if raw.isdigit() else False
        days = R.clamp_window(raw, raw=not is_archive)
        now = R.utc_now_iso()
        cutoff = R.window_cutoff(days, now)

        logs = []
        if memory_manager is not None and hasattr(memory_manager, "raw_cost_logs"):
            try:
                logs = _run_async(memory_manager.raw_cost_logs(since=cutoff))
            except Exception:
                logs = []

        top_price = None
        try:
            from promptwise.core.model_registry import ModelRegistry
            reg = ModelRegistry()
            top_price = reg.price(reg.resolve("powerful") or "")
        except Exception:
            top_price = None

        gov = {}
        try:
            from pathlib import Path
            gov = R.governance_summary(Path.cwd() / ".promptwise")
        except Exception:
            gov = {}

        model = R.build_dashboard_model(logs, window_days=days, now_iso=now,
                                        top_tier_price=top_price, governance=gov)
        model["archive"] = is_archive
        return jsonify(model)

    @app.route("/api/insights")
    @require_role("viewer")
    def api_insights():
        """Ranked recommendations (routing/cost/quality/budget) over the local
        telemetry. Deterministic, offline, fail-open — any error yields []."""
        from promptwise.core.insights import compute_recommendations
        raw = str(request.args.get("days", 30))
        days = int(raw) if raw.isdigit() else 30
        try:
            recs = compute_recommendations(window_days=days)
        except Exception:
            recs = []
        return jsonify({"recommendations": recs[:8], "count": len(recs)})

    @app.route("/api/governor")
    @require_role("viewer")
    def api_governor():
        """Most recent governor proposals + verdicts + apply state, read from the
        local advisory artifact the governor writes (`.promptwise/governor_proposals.json`).
        Read-only, offline, fail-open — never triggers an autonomy run."""
        import json as _json
        from pathlib import Path
        p = Path.cwd() / ".promptwise" / "governor_proposals.json"
        try:
            data = _json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
        except Exception:
            data = {}
        return jsonify({"mode": data.get("mode", "advise"),
                        "proposals": data.get("proposals", []),
                        "summary": data.get("summary", {})})

    @app.route("/api/stats")
    @require_role("viewer")
    def api_stats():
        if stats_service:
            try:
                snap = _run_async(stats_service.snapshot())
                return jsonify({"total_cost_usd": snap.get("total_cost_usd", 0), "total_calls": snap.get("total_calls", 0),
                                "avg_saving_pct": snap.get("avg_saving_pct", 0), "cache_hit_rate": snap.get("cache_hit_rate", 0)})
            except Exception as e:
                return jsonify({"error": str(e)})
        return jsonify({"total_cost_usd": 0.0, "total_calls": 0, "avg_saving_pct": 0.0, "cache_hit_rate": 0.0})

    @app.route("/api/budget")
    @require_role("viewer")
    def api_budget():
        from promptwise.plugins.budget import BudgetGuardian
        g = BudgetGuardian()
        s = g.check(used_usd=float(request.args.get("used_usd", 0)), days_elapsed=int(request.args.get("days_elapsed", 1)))
        return jsonify({"used_usd": s.used_usd, "limit_usd": s.limit_usd, "pct_used": s.pct_used, "alert_level": s.alert_level})

    @app.route("/api/roi")
    @require_role("viewer")
    def api_roi():
        from promptwise.plugins.roi import ROITracker
        r = ROITracker().calculate(session_id=request.args.get("session_id", "unknown"),
                                    total_cost_usd=float(request.args.get("total_cost_usd", 0)),
                                    tokens_saved=int(request.args.get("tokens_saved", 0)),
                                    calls=int(request.args.get("calls", 1)))
        return jsonify({"roi_ratio": r.roi_ratio, "estimated_time_saved_min": r.estimated_time_saved_min, "productivity_score": r.productivity_score})

    @app.route("/api/models")
    @require_role("viewer")
    def api_models():
        """Current selectable models from the registry (deprecated excluded from
        selection but still resolvable elsewhere for history)."""
        try:
            from promptwise.core.model_registry import ModelRegistry
            reg = ModelRegistry()
            tiers = {"fast": "fast", "balanced": "balanced", "powerful": "powerful"}
            board = []
            for tier in tiers:
                alias = reg.resolve(tier)
                if alias:
                    board.append({"model": alias, "cost_tier": tier})
            if board:
                return jsonify({"leaderboard": board})
        except Exception:
            pass
        return jsonify({"leaderboard": []})

    @app.route("/api/executive")
    @require_role("viewer")
    def api_executive():
        """One-page, jargon-free rollup for finance/senior-mgmt: net savings,
        ROI, budget burn vs. cap, governance status. Reuses the same window
        computation /api/dashboard performs -- no new persistence, no new
        data model. Every number degrades to zero/empty on missing data
        rather than raising (same fail-soft posture as /api/dashboard)."""
        from promptwise.dashboard import retention as R
        raw = str(request.args.get("days", R.DEFAULT_WINDOW))
        days = R.clamp_window(raw, raw=True)
        now = R.utc_now_iso()
        cutoff = R.window_cutoff(days, now)

        logs = []
        if memory_manager is not None and hasattr(memory_manager, "raw_cost_logs"):
            try:
                logs = _run_async(memory_manager.raw_cost_logs(since=cutoff))
            except Exception:
                logs = []

        top_price = None
        try:
            from promptwise.core.model_registry import ModelRegistry
            reg = ModelRegistry()
            top_price = reg.price(reg.resolve("powerful") or "")
        except Exception:
            top_price = None

        model = R.build_dashboard_model(logs, window_days=days, now_iso=now, top_tier_price=top_price)
        h = model["headline"]

        total_in = sum(float(l.get("input_tokens", 0) or 0) for l in logs)
        total_out = sum(float(l.get("output_tokens", 0) or 0) for l in logs)
        tokens_saved_estimate = int((total_in + total_out) * (h["tokens_saved_pct"] / 100))

        from promptwise.plugins.roi import ROITracker
        roi = ROITracker().calculate(
            session_id="executive-rollup",
            total_cost_usd=h["total_cost_usd"],
            tokens_saved=tokens_saved_estimate,
            calls=h["total_calls"],
        )

        from promptwise.plugins.budget import BudgetGuardian
        budget_status = BudgetGuardian().check(used_usd=h["total_cost_usd"], days_elapsed=days)

        gov = {}
        if h["total_cost_usd"] > 0:
            try:
                from pathlib import Path
                gov = R.governance_summary(Path.cwd() / ".promptwise")
            except Exception:
                gov = {}

        return jsonify({
            "window_days": days,
            "generated_at": now,
            "net_savings_usd": h["net_savings_usd"],
            "savings_rate_pct": h["savings_rate_pct"],
            "roi": {
                "roi_ratio": roi.roi_ratio,
                "estimated_time_saved_hours": round(roi.estimated_time_saved_min / 60, 2),
                "productivity_score": roi.productivity_score,
            },
            "budget": {
                "used_usd": budget_status.used_usd,
                "limit_usd": budget_status.limit_usd,
                "pct_used": budget_status.pct_used,
                "alert_level": budget_status.alert_level,
            },
            "governance": gov or {"audit_records": 0, "chain_ok": True, "denials": 0, "failures": 0},
        })

    return app
