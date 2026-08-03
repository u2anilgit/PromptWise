"""core.preflight -- one combined pass over a user prompt: rewrite advisory,
security scan, task-type classification, model/tier routing, and (opt-in) a
shortlist of the last 2-3 current models for the routed tier.

Designed to be called from hook_bridge.py::userpromptsubmit_policy, which
fires on every prompt today. This module owns the "what to check" logic;
hook_bridge owns "how to surface it" (additionalContext / block / warn).

Every step is independently wrapped so one failing check never suppresses the
others -- same fail-open convention the rest of hook_bridge.py uses.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

from promptwise.config import AppConfig
from promptwise.core.router import Router
from promptwise.core.rewriter import Rewriter
from promptwise.core.text_match import any_keyword
from promptwise.security.scanner import SecurityScanner

# Model-shortlist advisory is opt-in: no sign-off yet on always surfacing it
# (see ROADMAP model-retention entry). Same on/off token convention as
# router.py's _ADAPTIVE_OFF.
_RETENTION_ON = ("1", "on", "true", "yes")

_TASK_TYPE_RULES: list[tuple[str, list[str]]] = [
    ("bugfix", ["bug", "fix", "broken", "error", "crash", "failing", "regression", "traceback"]),
    ("docs", ["document", "documentation", "docstring", "docstrings", "readme",
              "changelog", "comment the", "write docs", "docs"]),
    ("refactor", ["refactor", "clean up", "simplify", "rename", "extract method", "reorganize"]),
    ("enhancement", ["enhance", "improve", "extend", "add support for", "optimize"]),
    ("new_code", ["implement", "build", "create", "add a new", "scaffold", "new feature"]),
]

# Rewrite advisory only surfaces above this saving threshold -- avoid nagging
# on prompts that are already tight.
_REWRITE_SAVING_THRESHOLD = 15.0
# Newest current models to include in the (opt-in) shortlist.
_SHORTLIST_SIZE = 3


def _retention_enabled() -> bool:
    return os.environ.get("PROMPTWISE_MODEL_RETENTION", "off").lower() in _RETENTION_ON


def classify_task_type(text: str) -> str:
    """Heuristic task-type bucket: bugfix / docs / refactor / enhancement /
    new_code / other. Informs (but doesn't replace) Router's own intent
    detection -- mirrors Router._detect_intent's pattern-table style."""
    t = text.lower()
    for task_type, keywords in _TASK_TYPE_RULES:
        if any_keyword(t, keywords):
            return task_type
    return "other"


@dataclass(frozen=True)
class PreflightResult:
    rewritten: str | None = None
    saving_pct: float = 0.0
    security_notes: list[str] = field(default_factory=list)
    blocked: bool = False
    task_type: str = "other"
    recommended_model: str = ""
    model_shortlist: list[str] = field(default_factory=list)
    cross_provider_suggested: bool = False
    cross_provider_note: str = ""
    notes: list[str] = field(default_factory=list)

    @property
    def advisory_text(self) -> str:
        return "; ".join(self.notes)


def run_preflight(prompt: str, *, host: str = "claude-code",
                   config: AppConfig | None = None) -> PreflightResult:
    """Run the combined preflight pass. Never raises -- every step is
    independently guarded; a failing step just contributes no notes."""
    notes: list[str] = []
    blocked = False
    rewritten = None
    saving_pct = 0.0
    security_notes: list[str] = []
    task_type = "other"
    recommended_model = ""
    model_shortlist: list[str] = []
    cross_provider_suggested = False
    cross_provider_note = ""

    if not isinstance(prompt, str) or not prompt.strip():
        return PreflightResult()

    # 1) rewrite advisory
    try:
        rr = Rewriter(config=config).rewrite(prompt)
        if rr.saving_pct > _REWRITE_SAVING_THRESHOLD:
            rewritten = rr.rewritten
            saving_pct = rr.saving_pct
            notes.append(f"rewrite available (~{rr.saving_pct:.0f}% shorter) -- consider deslop/optimize_context")
        if rr.warning:
            notes.append(rr.warning)
    except Exception:
        pass

    # 2) security scan (secrets / injection / PII)
    try:
        res = SecurityScanner().check(prompt)
        violations = res.violations or []
        inj = [v for v in violations if v.get("check") in ("injection", "syntax")]
        if inj:
            security_notes.append(f"possible prompt-injection ({len(inj)} pattern(s))")
        secret_hits = [v for v in violations if v.get("check") == "secrets"]
        if secret_hits:
            security_notes.append(
                f"possible secret/credential pasted into the prompt "
                f"({len(secret_hits)} pattern(s)) -- consider redacting/rotating it")
        notes.extend(security_notes)
    except Exception:
        pass

    # 3) task-type classification (heuristic, no new deps)
    try:
        task_type = classify_task_type(prompt)
    except Exception:
        pass

    # 4) model/tier routing -- reuses existing Router unchanged, task_type is
    # advisory context only, doesn't override Router's own intent detection.
    router = None
    r = None
    try:
        router = Router(config=config)
        r = router.route(text=prompt, intent="auto", stakes="auto", provider="claude")
        recommended_model = r.recommended_model or ""
        if recommended_model and router.registry.tier_of(recommended_model) == "powerful":
            notes.append(
                f"model routing: {task_type}/{r.intent_detected}/{r.stakes_detected} -> "
                f"'{recommended_model}' (powerful tier, ~${r.estimated_input_cost_usd:.4f} est.) "
                f"-- route_request/optimize_context not called this turn; a cheaper tier may suffice")
    except Exception:
        pass

    # 5) model shortlist (opt-in) -- last N current models for the routed tier
    if _retention_enabled() and router is not None and recommended_model:
        try:
            tier = router.registry.tier_of(recommended_model)
            model_shortlist = router.registry.top_n_current(tier, n=_SHORTLIST_SIZE) if tier else []
            if model_shortlist:
                notes.append(f"current {tier}-tier models (newest first): {', '.join(model_shortlist)}")
        except Exception:
            pass

    # 6) cross-provider suggestion -- advisory only, no dispatch (see design
    # doc: transports/http.py's provider calls are simulated stubs today,
    # real dispatch is a separate credential/network-egress decision).
    if router is not None and recommended_model:
        try:
            model_provider = router.registry.provider_of(recommended_model)
            host_provider = "claude" if "claude" in host.lower() or host.lower() in ("claude-code",) else host.lower()
            if model_provider and host_provider and model_provider != host_provider:
                cross_provider_suggested = True
                cross_provider_note = (
                    f"best-fit model '{recommended_model}' is on provider '{model_provider}', "
                    f"different from host provider '{host_provider}' -- advisory only, no auto-dispatch")
                notes.append(cross_provider_note)
        except Exception:
            pass

    # 7) large-prompt advisory (kept from the pre-existing hook_bridge check)
    try:
        approx_count = max(1, len(prompt) // 4)
        if approx_count > 1500:
            notes.append(
                f"large prompt (~{approx_count} est. tokens) -- consider "
                f"optimize_context or compress_prompt before sending")
    except Exception:
        pass

    return PreflightResult(
        rewritten=rewritten,
        saving_pct=saving_pct,
        security_notes=security_notes,
        blocked=blocked,
        task_type=task_type,
        recommended_model=recommended_model,
        model_shortlist=model_shortlist,
        cross_provider_suggested=cross_provider_suggested,
        cross_provider_note=cross_provider_note,
        notes=notes,
    )
