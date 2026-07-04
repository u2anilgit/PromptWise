"""insights — correction trends + a ranked recommendation engine (offline).

Two layers, both pure-stdlib and air-gap safe:

* ``compute_insights`` — the original correction-trend view over the local
  ``LearningStore`` (counts by category/project/month + repeated mistakes).
* ``compute_recommendations`` — a deterministic recommendation engine over the
  local telemetry (``route_outcomes``, ``cost_logs``, ``eval_results`` /
  ``eval_baselines``). It emits structured, ranked, min-sample-gated
  recommendations across four rule families: routing (downgrade/escalate),
  cost (top drivers + spend anomaly), quality (declining met-rate + eval
  regressions), and budget (projected window overrun/underrun).

Design contract (matches ``adaptive_router.py`` / ``eval_harness.py``):

* **Reuse the router's thresholds.** Routing recs read the SAME
  ``min_samples`` / ``meet_bar`` (0.7) / ``fail_bar`` (0.4) and posterior-mean
  estimator as ``AdaptiveRouter`` so a recommendation can never contradict the
  live router.
* **Tiers, never branded ids.** Everything reasons over ``fast -> balanced ->
  powerful``; model *families* (never versioned/branded ids) may appear as cost
  drivers straight from the telemetry.
* **Deterministic + fail-open.** Thin/empty/missing data yields fewer or no
  recommendations — never a crash. Every family is wrapped so one bad table can
  never sink the report.
* **Offline, stdlib only.** Bundled ``sqlite3`` into the local PromptWise DB;
  no server, no network, no new dependency.
"""
from __future__ import annotations

import sqlite3
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from promptwise.core.adaptive_router import AdaptiveRouter, OutcomeStore, TIER_ORDER
from promptwise.core.learning_store import LearningStore

# ── rule-family tunables ─────────────────────────────────────────────────────
# Routing reuses the 7.1 router thresholds directly (see ``_routing_recs``); the
# cost/quality/budget families get their own conservative, min-sample gates.
COST_MIN_EVENTS = 5          # window must hold this many cost events to analyse
COST_DRIVER_SHARE = 0.30     # a driver must own >=30% of window spend to flag
SPEND_ANOMALY_RATIO = 1.5    # recent daily rate >= 1.5x the baseline -> anomaly
QUALITY_MET_DROP = 0.20      # met-rate must fall this much (older->newer) to flag
QUALITY_MIN_PER_HALF = 5     # each half needs this many scored outcomes
EVAL_REGRESSION_SEVERITY = 0.6  # severity for a met->not_met eval regression
BUDGET_MIN_DAYS = 5          # need this many distinct spend-days to project
BUDGET_OVERRUN_MARGIN = 1.10  # projected > 110% of limit -> raise/cut
BUDGET_UNDERRUN_MARGIN = 0.50  # projected < 50% of limit -> lower


def compute_insights(db_path: str | Path | None = None) -> dict:
    store = LearningStore(db_path)
    rows = store.all()
    total = len(rows)
    by_category = Counter(r.category or "uncategorized" for r in rows)
    by_project = Counter(r.project or "unknown" for r in rows)

    # crude monthly bucket from ISO timestamps (YYYY-MM)
    by_month: Counter = Counter()
    for r in rows:
        by_month[(r.ts or "")[:7]] += 1

    # most-repeated mistakes (normalised)
    mistake_counts = Counter((r.mistake or "").strip().lower() for r in rows if r.mistake)
    top_mistakes = [{"mistake": m, "count": c} for m, c in mistake_counts.most_common(5)]

    return {
        "total_learnings": total,
        "fts": store.fts_enabled,
        "by_category": dict(by_category.most_common()),
        "by_project": dict(by_project.most_common()),
        "by_month": dict(sorted(by_month.items())),
        "top_mistakes": top_mistakes,
        "top_category": by_category.most_common(1)[0][0] if by_category else None,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Recommendation engine
# ─────────────────────────────────────────────────────────────────────────────
def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _cutoff_iso(window_days: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=max(1, int(window_days)))).isoformat()


def _connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


def _sample_factor(n: int, floor: int) -> float:
    """Saturating 0..1 sufficiency factor — more samples -> more confidence,
    bounded so a couple of extra rows never spike confidence to 1."""
    if floor <= 0:
        return 1.0
    return min(1.0, n / (2.0 * floor))


def _mk(rec_id: str, category: str, message: str, evidence: dict,
        estimated_impact: float, confidence: float) -> dict:
    impact = round(max(0.0, float(estimated_impact)), 6)
    conf = round(max(0.0, min(1.0, float(confidence))), 3)
    return {
        "id": rec_id,
        "category": category,
        "message": message,
        "evidence": evidence,
        "estimated_impact": impact,
        "confidence": conf,
        # ranking key: impact x confidence (USD for cost/routing/budget, a 0..1
        # severity for quality/eval). Deterministic; tiebroken by id downstream.
        "score": round(impact * conf, 6),
    }


# ── family 1: routing (downgrade / escalate) ─────────────────────────────────
def _outcome_aggregate(conn: sqlite3.Connection) -> dict:
    """{task_class: {tier: {met, not_met, neutral, n, cost}}} over ALL history.

    Full history (not windowed) so the counts match ``OutcomeStore.stats`` — the
    exact view the live router reasons over — and recs cannot contradict it.
    """
    rows = conn.execute(
        "SELECT task_class, tier, quality_signal, cost FROM route_outcomes"
    ).fetchall()
    agg: dict = defaultdict(lambda: defaultdict(
        lambda: {"met": 0, "not_met": 0, "neutral": 0, "n": 0, "cost": 0.0}))
    for r in rows:
        tier = r["tier"]
        if tier not in TIER_ORDER:
            continue  # only reason over the known tier ladder
        b = agg[r["task_class"]][tier]
        sig = r["quality_signal"] if r["quality_signal"] in ("met", "not_met", "neutral") else "neutral"
        b[sig] += 1
        b["n"] += 1
        b["cost"] += float(r["cost"] or 0.0)
    return agg


def _routing_recs(conn: sqlite3.Connection, router: AdaptiveRouter) -> list[dict]:
    recs: list[dict] = []
    agg = _outcome_aggregate(conn)
    for cls, per_tier in agg.items():
        used = [t for t in TIER_ORDER if per_tier.get(t) and per_tier[t]["n"] > 0]
        if not used:
            continue

        def _pm(t: str) -> tuple[float, int, int, int]:
            d = per_tier[t]
            met, not_met = d["met"], d["not_met"]
            total = met + not_met
            return (router._posterior_mean(met, total) if total else 0.0), met, not_met, total

        # 1) Downgrade: cheapest tier with enough evidence of meeting the bar,
        #    when more-expensive traffic exists that could move down to it.
        target = None
        for t in used:  # TIER_ORDER is cheapest-first
            pm, met, not_met, total = _pm(t)
            if total >= router.min_samples and pm >= router.meet_bar:
                target = t
                break
        if target is not None:
            t_rank = TIER_ORDER.index(target)
            pricier = [t for t in used if TIER_ORDER.index(t) > t_rank]
            if pricier:
                d = per_tier[target]
                avg_target = d["cost"] / d["n"] if d["n"] else 0.0
                saving = 0.0
                moved = 0
                for t in pricier:
                    dt = per_tier[t]
                    avg_t = dt["cost"] / dt["n"] if dt["n"] else 0.0
                    saving += max(0.0, (avg_t - avg_target) * dt["n"])
                    moved += dt["n"]
                pm, met, not_met, total = _pm(target)
                conf = pm * _sample_factor(total, router.min_samples)
                recs.append(_mk(
                    f"routing:downgrade:{cls}", "routing",
                    (f"Class '{cls}' consistently meets the bar at the cheaper "
                     f"'{target}' tier ({met}/{total} met); route it there instead "
                     f"of {', '.join(pricier)} to save."),
                    {"kind": "downgrade", "task_class": cls, "target_tier": target,
                     "from_tiers": pricier, "met": met, "total": total,
                     "moved_calls": moved,
                     "per_tier": {t: dict(per_tier[t]) for t in used}},
                    saving, conf))
                continue  # a class that can downgrade is not also escalating

        # 2) Escalate: the cheapest tier actually in use keeps falling short.
        low = used[0]
        pm, met, not_met, total = _pm(low)
        low_rank = TIER_ORDER.index(low)
        if (total >= router.min_samples and pm <= router.fail_bar
                and low_rank < len(TIER_ORDER) - 1):
            up = TIER_ORDER[low_rank + 1]
            d = per_tier[low]
            avg_low = d["cost"] / d["n"] if d["n"] else 0.0
            waste = not_met * avg_low  # spend on cheap calls that missed the bar
            conf = (1.0 - pm) * _sample_factor(total, router.min_samples)
            recs.append(_mk(
                f"routing:escalate:{cls}", "routing",
                (f"Class '{cls}' is failing at the cheap '{low}' tier "
                 f"({met}/{total} met); escalate to '{up}'."),
                {"kind": "escalate", "task_class": cls, "from_tier": low,
                 "to_tier": up, "met": met, "total": total,
                 "per_tier": {t: dict(per_tier[t]) for t in used}},
                waste, conf))
    return recs


# ── family 2: cost (top drivers + spend anomaly) ─────────────────────────────
def _cost_rows(conn: sqlite3.Connection, cutoff: str) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT ts, tool, model, cost_usd FROM cost_logs WHERE ts >= ?",
        (cutoff,)).fetchall()


def _cost_recs(conn: sqlite3.Connection, window_days: int, cutoff: str) -> list[dict]:
    rows = _cost_rows(conn, cutoff)
    if len(rows) < COST_MIN_EVENTS:
        return []
    total = sum(float(r["cost_usd"] or 0.0) for r in rows)
    if total <= 0:
        return []

    recs: list[dict] = []
    dims: dict[str, dict[str, float]] = {
        "model": {},
        "skill": {},
    }
    for r in rows:
        model_key = r["model"] or "unknown"
        skill_key = r["tool"] or "unknown"
        dims["model"][model_key] = dims["model"].get(model_key, 0.0) + float(r["cost_usd"] or 0.0)
        dims["skill"][skill_key] = dims["skill"].get(skill_key, 0.0) + float(r["cost_usd"] or 0.0)

    for dim, spend_by_key in dims.items():
        if not spend_by_key:
            continue
        key, spend = max(spend_by_key.items(), key=lambda kv: kv[1])
        share = spend / total if total else 0.0
        if share < COST_DRIVER_SHARE:
            continue
        conf = min(0.99, share) * _sample_factor(len(rows), COST_MIN_EVENTS)
        recs.append(_mk(
            f"cost:driver:{dim}:{key}", "cost",
            (f"Top cost driver by {dim}: '{key}' accounts for "
             f"${spend:.4f} ({share * 100:.0f}%) of the last {window_days}-day spend."),
            {"kind": "top_driver", "dimension": dim, "key": key,
             "spend_usd": round(spend, 6), "share": round(share, 3),
             "window_spend_usd": round(total, 6), "events": len(rows)},
            spend, conf))

    # spend anomaly: recent 7-day daily rate vs. the rest of the window.
    if window_days > 7:
        recent_cut = _cutoff_iso(7)
        recent = sum(float(r["cost_usd"] or 0.0) for r in rows if r["ts"] >= recent_cut)
        prior = total - recent
        prior_days = max(1, window_days - 7)
        recent_daily = recent / 7.0
        prior_daily = prior / prior_days
        if prior_daily > 0 and recent_daily >= SPEND_ANOMALY_RATIO * prior_daily:
            ratio = recent_daily / prior_daily
            impact = max(0.0, (recent_daily - prior_daily) * window_days)
            conf = min(0.95, (ratio - 1.0) / 2.0) * _sample_factor(len(rows), COST_MIN_EVENTS)
            recs.append(_mk(
                "cost:anomaly:spend", "cost",
                (f"Spend anomaly: the last 7 days run ${recent_daily:.4f}/day vs. "
                 f"${prior_daily:.4f}/day baseline ({ratio:.1f}x)."),
                {"kind": "spend_anomaly", "recent_daily_usd": round(recent_daily, 6),
                 "baseline_daily_usd": round(prior_daily, 6), "ratio": round(ratio, 2),
                 "events": len(rows)},
                impact, conf))
    return recs


# ── family 3: quality (declining met-rate + eval regressions) ────────────────
def _quality_recs(conn: sqlite3.Connection, cutoff: str) -> list[dict]:
    recs: list[dict] = []

    # A) per-class declining met-rate (older half vs. newer half, windowed).
    rows = conn.execute(
        "SELECT task_class, quality_signal, ts FROM route_outcomes "
        "WHERE ts >= ? ORDER BY ts", (cutoff,)).fetchall()
    by_class: dict = defaultdict(list)
    for r in rows:
        if r["quality_signal"] in ("met", "not_met"):
            by_class[r["task_class"]].append(1 if r["quality_signal"] == "met" else 0)
    for cls, seq in by_class.items():
        if len(seq) < 2 * QUALITY_MIN_PER_HALF:
            continue
        mid = len(seq) // 2
        older, newer = seq[:mid], seq[mid:]
        old_rate = sum(older) / len(older)
        new_rate = sum(newer) / len(newer)
        drop = old_rate - new_rate
        if drop >= QUALITY_MET_DROP:
            conf = min(1.0, drop) * _sample_factor(len(seq), 2 * QUALITY_MIN_PER_HALF)
            recs.append(_mk(
                f"quality:decline:{cls}", "quality",
                (f"Class '{cls}' met-rate is declining: "
                 f"{old_rate * 100:.0f}% -> {new_rate * 100:.0f}% over the window."),
                {"kind": "met_rate_decline", "task_class": cls,
                 "old_met_rate": round(old_rate, 3), "new_met_rate": round(new_rate, 3),
                 "drop": round(drop, 3), "samples": len(seq)},
                round(drop, 4), conf))

    # B) standing eval regressions vs. the blessed baseline (latest per case/tier).
    try:
        eresults = conn.execute(
            "SELECT suite, case_id, tier, score, verdict, ts FROM eval_results "
            "ORDER BY ts").fetchall()
    except sqlite3.OperationalError:
        eresults = []
    latest: dict = {}
    for r in eresults:
        latest[(r["suite"], r["case_id"], r["tier"])] = r
    for (suite, case_id, tier), r in latest.items():
        try:
            base = conn.execute(
                "SELECT score, verdict FROM eval_baselines "
                "WHERE suite = ? AND case_id = ? AND tier = ?",
                (suite, case_id, tier)).fetchone()
        except sqlite3.OperationalError:
            base = None
        if not base:
            continue
        severity = 0.0
        reason = ""
        if base["verdict"] == "met" and r["verdict"] == "not_met":
            severity = EVAL_REGRESSION_SEVERITY
            reason = "verdict regressed met -> not_met"
        elif r["score"] < base["score"] - 1e-9:
            severity = min(1.0, base["score"] - r["score"])
            reason = f"score dropped {base['score']:.2f} -> {r['score']:.2f}"
        if severity > 0:
            recs.append(_mk(
                f"quality:eval:{suite}:{case_id}:{tier}", "quality",
                (f"Eval regression: case '{case_id}' at '{tier}' ({suite}) {reason}."),
                {"kind": "eval_regression", "suite": suite, "case_id": case_id,
                 "tier": tier, "baseline_score": round(base["score"], 4),
                 "current_score": round(r["score"], 4), "reason": reason},
                severity, 0.9))
    return recs


# ── family 4: budget (projected window overrun / underrun) ───────────────────
def _budget_recs(conn: sqlite3.Connection, window_days: int, cutoff: str,
                 budget_usd: float | None) -> list[dict]:
    limit = budget_usd
    if limit is None:
        try:
            from promptwise.plugins.budget import BudgetGuardian
            limit = float(BudgetGuardian().limit_usd)
        except Exception:
            return []
    if not limit or limit <= 0:
        return []

    rows = _cost_rows(conn, cutoff)
    if not rows:
        return []
    days = {str(r["ts"])[:10] for r in rows if r["ts"]}
    if len(days) < BUDGET_MIN_DAYS:
        return []  # too little coverage to project a window total honestly
    spend = sum(float(r["cost_usd"] or 0.0) for r in rows)
    daily = spend / len(days)
    projected = daily * window_days
    coverage = min(1.0, len(days) / float(window_days))

    if projected > limit * BUDGET_OVERRUN_MARGIN:
        impact = projected - limit
        return [_mk(
            "budget:overrun", "budget",
            (f"Projected {window_days}-day spend ${projected:.2f} exceeds the "
             f"${limit:.2f} budget; raise the limit or cut spend."),
            {"kind": "projected_overrun", "projected_usd": round(projected, 4),
             "limit_usd": round(limit, 4), "spend_so_far_usd": round(spend, 4),
             "days_observed": len(days)},
            impact, coverage)]
    if projected < limit * BUDGET_UNDERRUN_MARGIN:
        impact = limit - projected
        return [_mk(
            "budget:underrun", "budget",
            (f"Projected {window_days}-day spend ${projected:.2f} is well under the "
             f"${limit:.2f} budget; consider lowering it."),
            {"kind": "projected_underrun", "projected_usd": round(projected, 4),
             "limit_usd": round(limit, 4), "spend_so_far_usd": round(spend, 4),
             "days_observed": len(days)},
            impact, coverage)]
    return []


# ── orchestrator ─────────────────────────────────────────────────────────────
def compute_recommendations(db_path: str | Path | None = None, window_days: int = 30,
                            budget_usd: float | None = None) -> list[dict]:
    """Ranked, min-sample-gated recommendations over the local telemetry.

    Deterministic and offline. Each recommendation dict carries ``id``,
    ``category``, ``message``, ``evidence``, ``estimated_impact``, ``confidence``
    and a derived ``score`` (impact x confidence). Routing recs reuse the 7.1
    router thresholds; cost/quality/budget use the module gates above. Fail-open:
    thin/empty/missing data yields fewer or no recs, never a crash.
    """
    window_days = max(1, int(window_days or 30))
    # Resolve the DB path via OutcomeStore (shares the router's default), which
    # also guarantees the route_outcomes table exists.
    store = OutcomeStore(db_path)
    router = AdaptiveRouter(store=store)
    cutoff = _cutoff_iso(window_days)

    recs: list[dict] = []
    conn = _connect(store.db_path)
    try:
        for fn in (
            lambda: _routing_recs(conn, router),
            lambda: _cost_recs(conn, window_days, cutoff),
            lambda: _quality_recs(conn, cutoff),
            lambda: _budget_recs(conn, window_days, cutoff, budget_usd),
        ):
            try:
                recs.extend(fn())
            except sqlite3.OperationalError:
                continue  # a missing table for one family is fine (fail-open)
            except Exception:
                continue
    finally:
        conn.close()

    # Rank by impact x confidence (desc), tiebroken by id for determinism.
    recs.sort(key=lambda r: (-r["score"], r["id"]))
    return recs
