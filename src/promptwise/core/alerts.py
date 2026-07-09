"""core/alerts - opt-in Slack/webhook/email notification when a budget or
security threshold is crossed.

Zero coupling to plugins/budget.py or security/scanner.py: this module is a
pure subscriber over the typed results those modules already return from
their check() calls (BudgetStatus, SecurityResult) - it never imports or
edits their internals. Callers (server.py handlers, hook_bridge.py) pass the
result object they already have to notify_budget()/notify_security().

Off by default (config/alerts.yaml, or the shipped config/alerts.example.yaml
template, both start with enabled: false) - PromptWise never phones home
unless a human explicitly opts in and configures a channel. Stdlib only:
urllib.request for a webhook/Slack POST, smtplib + email.message for mail.
Every send is fail-soft: a bad URL, an unreachable host, or a missing SMTP
config never raises into the caller - it degrades to a no-op result dict.
"""
from __future__ import annotations

import json
import os
import smtplib
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from email.message import EmailMessage
from pathlib import Path

try:  # PyYAML is already a PromptWise dependency (policy/model registry/governor use it)
    import yaml
except Exception:  # pragma: no cover - yaml always present in practice
    yaml = None  # type: ignore

# Env-var overrides so a real deployment never has to commit a channel
# credential to config/alerts.yaml.
_ENV_WEBHOOK_URL = "PROMPTWISE_ALERT_WEBHOOK_URL"
_ENV_SLACK_WEBHOOK_URL = "PROMPTWISE_ALERT_SLACK_WEBHOOK_URL"
_ENV_SMTP_PASS = "PROMPTWISE_ALERT_SMTP_PASS"

_LEVEL_RANK = {"ok": 0, "warn": 1, "critical": 2, "hard_stop": 3}
_DEFAULT_CONFIG_PATH = Path("config") / "alerts.yaml"


@dataclass
class AlertConfig:
    """Parsed config/alerts.yaml. Disabled (all-false) unless a human opts in."""
    enabled: bool = False
    budget_min_level: str = "critical"   # fire at/above this BudgetStatus.alert_level
    security_min_risk: float = 0.7       # fire at/above this SecurityResult.risk_score
    channels: dict = field(default_factory=dict)


def load_alert_config(path: str | Path | None = None) -> AlertConfig:
    """Read config/alerts.yaml. Missing/malformed -> the disabled default,
    never raises (same fail-soft contract as the rest of the config layer)."""
    p = Path(path) if path else _DEFAULT_CONFIG_PATH
    if not p.exists():
        return AlertConfig()
    try:
        text = p.read_text(encoding="utf-8")
        raw = yaml.safe_load(text) if yaml is not None else json.loads(text)
        if not isinstance(raw, dict):
            return AlertConfig()
    except Exception:
        return AlertConfig()
    return AlertConfig(
        enabled=bool(raw.get("enabled", False)),
        budget_min_level=str(raw.get("budget_min_level", "critical")),
        security_min_risk=float(raw.get("security_min_risk", 0.7)),
        channels=dict(raw.get("channels") or {}),
    )


# -- channel resolution: config value, or an env-var override for secrets ----
def _resolve_webhook_url(config: AlertConfig) -> str:
    env_val = os.environ.get(_ENV_WEBHOOK_URL)
    if env_val:
        return env_val
    return str((config.channels.get("webhook") or {}).get("url") or "")


def _resolve_slack_url(config: AlertConfig) -> str:
    env_val = os.environ.get(_ENV_SLACK_WEBHOOK_URL)
    if env_val:
        return env_val
    return str((config.channels.get("slack") or {}).get("webhook_url") or "")


def _resolve_smtp(config: AlertConfig) -> dict:
    smtp_cfg = dict(config.channels.get("email") or {})
    env_val = os.environ.get(_ENV_SMTP_PASS)
    if env_val:
        smtp_cfg["password"] = env_val
    return smtp_cfg


def _channel_enabled(config: AlertConfig, name: str) -> bool:
    return bool((config.channels.get(name) or {}).get("enabled"))


# -- senders: stdlib only, each fails soft (returns False, never raises) -----
def _send_webhook(url: str, payload: dict) -> bool:
    if not url:
        return False
    try:
        req = urllib.request.Request(
            url, data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}, method="POST",
        )
        with urllib.request.urlopen(req, timeout=3) as resp:
            resp.read()
        return True
    except Exception:
        return False


def _send_slack(webhook_url: str, text: str) -> bool:
    """Slack incoming webhooks are a plain POST {"text": ...} - no vendor SDK."""
    return _send_webhook(webhook_url, {"text": text})


def _send_email(smtp_cfg: dict, *, subject: str, body: str) -> bool:
    host = smtp_cfg.get("smtp_host")
    to_addrs = smtp_cfg.get("to_addrs") or []
    if not host or not to_addrs:
        return False
    try:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = smtp_cfg.get("from_addr") or ""
        msg["To"] = ", ".join(to_addrs)
        msg.set_content(body)
        port = int(smtp_cfg.get("smtp_port", 587))
        with smtplib.SMTP(host, port, timeout=5) as server:
            if smtp_cfg.get("use_tls", True):
                server.starttls()
            user = smtp_cfg.get("username")
            pw = smtp_cfg.get("password")
            if user and pw:
                server.login(user, pw)
            server.send_message(msg)
        return True
    except Exception:
        return False


def _dispatch(config: AlertConfig, *, subject: str, text: str, extra: dict) -> dict:
    """Fan out to every enabled+configured channel; best-effort per channel."""
    fired: list[str] = []
    if _channel_enabled(config, "webhook"):
        url = _resolve_webhook_url(config)
        if url and _send_webhook(url, {**extra, "message": text}):
            fired.append("webhook")
    if _channel_enabled(config, "slack"):
        url = _resolve_slack_url(config)
        if url and _send_slack(url, text):
            fired.append("slack")
    if _channel_enabled(config, "email"):
        smtp_cfg = _resolve_smtp(config)
        if _send_email(smtp_cfg, subject=subject, body=text):
            fired.append("email")
    return {"sent": bool(fired), "channels": fired}


# -- public entry points: subscribe to an ALREADY-COMPUTED result ------------
def notify_budget(status, *, config: AlertConfig | None = None) -> dict:
    """Fire configured channels when a BudgetStatus crosses budget_min_level.

    ``status`` is whatever ``BudgetGuardian.check()`` already returned - this
    function never calls BudgetGuardian itself. Fail-soft: any error during
    dispatch is caught and reported in the result, never raised.
    """
    config = config or load_alert_config()
    if not config.enabled:
        return {"sent": False, "reason": "disabled", "channels": []}
    level = getattr(status, "alert_level", "ok")
    threshold = _LEVEL_RANK.get(config.budget_min_level, _LEVEL_RANK["critical"])
    if _LEVEL_RANK.get(level, 0) < threshold:
        return {"sent": False, "reason": "below_threshold", "channels": []}
    try:
        text = (f"PromptWise budget alert: {level.upper()} - "
                f"${status.used_usd:.2f}/${status.limit_usd:.2f} ({status.pct_used}% used).")
        result = _dispatch(
            config, subject="PromptWise budget alert", text=text,
            extra={"kind": "budget", "alert_level": level, "pct_used": status.pct_used,
                   "used_usd": status.used_usd, "limit_usd": status.limit_usd},
        )
        if not result["sent"]:
            result.setdefault("reason", "no_channel_configured")
        return result
    except Exception as e:  # fail-soft: alerting must never break the caller
        return {"sent": False, "reason": "send_error", "error": f"{type(e).__name__}: {e}", "channels": []}


def notify_security(result, *, config: AlertConfig | None = None) -> dict:
    """Fire configured channels when a SecurityResult is blocked or its
    risk_score crosses security_min_risk. Same fail-soft contract as
    notify_budget(); never edits security/scanner.py's SecurityResult."""
    config = config or load_alert_config()
    if not config.enabled:
        return {"sent": False, "reason": "disabled", "channels": []}
    blocked = bool(getattr(result, "blocked", False))
    risk = float(getattr(result, "risk_score", 0.0) or 0.0)
    if not blocked and risk < config.security_min_risk:
        return {"sent": False, "reason": "below_threshold", "channels": []}
    try:
        checks = sorted({v.get("check", "?") for v in (getattr(result, "violations", None) or [])})
        text = (f"PromptWise security alert: risk {risk} "
                f"({'blocked' if blocked else 'flagged'}) - {', '.join(checks) or 'no detail'}.")
        out = _dispatch(
            config, subject="PromptWise security alert", text=text,
            extra={"kind": "security", "blocked": blocked, "risk_score": risk, "checks": checks},
        )
        if not out["sent"]:
            out.setdefault("reason", "no_channel_configured")
        return out
    except Exception as e:  # fail-soft
        return {"sent": False, "reason": "send_error", "error": f"{type(e).__name__}: {e}", "channels": []}
