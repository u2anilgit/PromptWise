"""PromptWise — CLI entry point (stats, eval, serve)."""

import argparse
import asyncio
import sys
from pathlib import Path

from promptwise import __version__
from promptwise.config import load_config
from promptwise.db.models import MemoryManager, get_db_path


def _do_stats(config_dir: str | None) -> None:
    cfg = load_config(config_dir)

    from promptwise.plugins.budget import BudgetGuardian
    from promptwise.plugins.roi import ROITracker

    guardian = BudgetGuardian(limit_usd=cfg.policies.budget_hard_stop_usd)
    budget = guardian.get_budget_status()

    roi = ROITracker()
    snapshot = roi.calculate(session_id="stats", total_cost_usd=budget["current_spend_usd"],
                             tokens_saved=0, calls=0)

    db_path = str(get_db_path())

    print(f"PromptWise — {__version__}")
    print(f"Config:  {cfg.version}")
    print(f"DB:      {db_path}")
    print(f"Model:   {cfg.default_model}")
    print()
    print("-- Budget --")
    print(f"  Limit:           ${budget['limit_usd']:.2f}")
    print(f"  Spent:           ${budget['current_spend_usd']:.4f}")
    print(f"  Used:            {budget['pct_used']:.1f}%")
    if budget.get("days_remaining_at_burn_rate"):
        print(f"  Days left:       {budget['days_remaining_at_burn_rate']:.0f}")
    print()
    print("-- ROI --")
    print(f"  Ratio:           {snapshot.roi_ratio:.2f}x")
    print(f"  Productivity:    {snapshot.productivity_score:.1%}")
    print(f"  Time saved:      {snapshot.estimated_time_saved_min:.1f}m")
    print(f"  Cost incurred:   ${snapshot.total_cost_usd:.4f}")


def _run_eval(config_dir: str | None, prompt: str, model: str | None) -> None:
    import time

    from promptwise.core.router import Router
    from promptwise.core.quality import QualityGuard

    cfg = load_config(config_dir)
    router = Router(cfg)
    quality = QualityGuard(cfg)

    t0 = time.perf_counter()
    stakes = "high" if model == "powerful" else "medium"
    result = router.route(text=prompt, stakes=stakes)
    elapsed = time.perf_counter() - t0

    print(f"Prompt:       {prompt[:60]}{'…' if len(prompt) > 60 else ''}")
    print(f"Intent:       {result.intent_detected}")
    print(f"Stakes:       {result.stakes_detected}")
    print(f"Target model: {result.recommended_model}")
    print(f"Est. cost:    ${result.estimated_input_cost_usd:.6f}")
    print(f"Time:         {elapsed*1000:.0f}ms")


def _start_serve(config_dir: str | None, port: int | None, cli_only: bool) -> None:
    cfg = load_config(config_dir)

    if cli_only or not cfg.dashboard.web_enabled:
        from promptwise.dashboard.cli import CLIDashboard
        dash = CLIDashboard(cfg)
        dash.render_all()
        return

    port = port or cfg.dashboard.web_port
    print(f"Starting PromptWise dashboard on http://0.0.0.0:{port}")

    from promptwise.dashboard.web import create_web_app
    app = create_web_app(cfg)
    app.run(host="0.0.0.0", port=port, debug=False)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="promptwise",
        description=f"PromptWise v{__version__} — Token-aware prompt routing",
    )
    parser.add_argument("--config", help="Path to config directory", default=None)

    sub = parser.add_subparsers(dest="command", required=True)

    stats = sub.add_parser("stats", help="Show cost/ROI/session statistics")
    stats.add_argument("--config", help="Config directory", default=None)

    ev = sub.add_parser("eval", help="Evaluate a single prompt")
    ev.add_argument("prompt", help="Prompt text to evaluate")
    ev.add_argument("--model", "-m", help="Model tier override (fast/balanced/powerful)")
    ev.add_argument("--config", help="Config directory", default=None)

    serve = sub.add_parser("serve", help="Start dashboard or CLI monitor")
    serve.add_argument("--port", "-p", type=int, help="Web dashboard port")
    serve.add_argument("--cli", action="store_true", help="Use CLI dashboard instead of web")
    serve.add_argument("--config", help="Config directory", default=None)

    args = parser.parse_args()

    if args.command == "stats":
        _do_stats(args.config)
    elif args.command == "eval":
        _run_eval(args.config, args.prompt, args.model)
    elif args.command == "serve":
        _start_serve(args.config, args.port, getattr(args, "cli", False))


if __name__ == "__main__":
    main()
