"""``run_eval`` used to return hardcoded canned scores keyed only by a
substring match on the model name -- the prompt itself was never evaluated.
It must now derive real, prompt-dependent estimates via BudgetGuardian.predict_cost.
"""
import asyncio
import json
import typing

import promptwise.server as s
from promptwise.plugins.budget import BudgetGuardian


def test_run_eval_scores_depend_on_prompt_length():
    class _FakeCtx:
        budget = BudgetGuardian(limit_usd=10.0)

    ctx = typing.cast(s.ServerContext, _FakeCtx())
    short = json.loads(asyncio.run(s._handle_run_eval(ctx, {"prompt": "hi", "models": ["claude-sonnet-4-6"]})))
    long = json.loads(asyncio.run(s._handle_run_eval(ctx, {"prompt": "word " * 500, "models": ["claude-sonnet-4-6"]})))
    assert short["eval"]["claude-sonnet-4-6"]["estimated_cost_usd"] < long["eval"]["claude-sonnet-4-6"]["estimated_cost_usd"]


def test_run_eval_differentiates_models_by_real_price():
    class _FakeCtx:
        budget = BudgetGuardian(limit_usd=10.0)

    ctx = typing.cast(s.ServerContext, _FakeCtx())
    out = json.loads(asyncio.run(s._handle_run_eval(ctx, {
        "prompt": "explain quicksort", "models": ["claude-haiku-4-5-20251001", "claude-opus-4-7"]})))
    assert out["eval"]["claude-haiku-4-5-20251001"]["estimated_cost_usd"] < out["eval"]["claude-opus-4-7"]["estimated_cost_usd"]
