"""host_detector -- which coding agent is running us *right now*.

agent_detector.py answers a different question: which agents this repo is
*configured* for (marker files on disk). Routing needs the running host: a repo
carrying CLAUDE.md, GEMINI.md and .cursorrules tells you nothing about which of
the three is executing this call, and routing a Gemini CLI session to a Claude
alias it cannot call is a wrong answer delivered confidently.

Precedence runs from "the host said so" down to "the repo hints at it", and
bottoms out at today's behavior (provider="claude") so nothing regresses when no
signal exists at all.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

# Host key -> the provider whose models that host calls by default.
#
# Several hosts are model-agnostic in principle (Cursor, Cline and Windsurf all
# let a user pick any provider). The mapping records the default a fresh install
# ships with; a user who has changed it sets PROMPTWISE_HOST or supplies a local
# override rather than being silently mis-routed.
HOST_PROVIDERS: dict[str, str] = {
    "claude": "claude",
    "codex": "openai",
    "copilot": "openai",
    "cursor": "claude",
    "cline": "claude",
    "windsurf": "claude",
    "gemini": "gemini",
    "antigravity": "gemini",
    "jetbrains": "claude",
    "aider": "claude",
    "goose": "claude",
    "openhands": "claude",
    "grok": "xai",
    "unknown": "claude",
}

# env var -> host key. Checked in this order; first hit wins.
_ENV_SIGNALS: tuple[tuple[str, str], ...] = (
    ("CLAUDECODE", "claude"),
    ("CLAUDE_CODE_ENTRYPOINT", "claude"),
    ("CURSOR_TRACE_ID", "cursor"),
    ("CODEX_SANDBOX", "codex"),
    ("CODEX_HOME", "codex"),
    ("GEMINI_CLI", "gemini"),
    ("GEMINI_SYSTEM_MD", "gemini"),
    ("WINDSURF_USER", "windsurf"),
    ("AIDER_MODEL", "aider"),
    ("GOOSE_MODE", "goose"),
    ("OPENHANDS_WORKSPACE_BASE", "openhands"),
)

# Substring of a lowercased MCP clientInfo.name -> host key. Ordered: the first
# match wins, so more specific names must precede substrings of themselves.
_CLIENT_NAME_SIGNALS: tuple[tuple[str, str], ...] = (
    ("claude", "claude"),
    ("cursor", "cursor"),
    ("codex", "codex"),
    ("copilot", "copilot"),
    ("cline", "cline"),
    ("windsurf", "windsurf"),
    ("antigravity", "antigravity"),
    ("gemini", "gemini"),
    ("jetbrains", "jetbrains"),
    ("intellij", "jetbrains"),
    ("aider", "aider"),
    ("goose", "goose"),
    ("openhands", "openhands"),
    ("grok", "grok"),
)

_ENV_OVERRIDE = "PROMPTWISE_HOST"

# A repo marker says which agent the repo is set up for, not which one is
# running, so it can never outrank a live signal however confident the scan is.
_REPO_SCAN_CAP = 0.6

_CLIENT_INFO: dict | None = None


def set_client_info(info: dict | None) -> None:
    """Record the MCP initialize handshake's clientInfo (process-global)."""
    global _CLIENT_INFO
    _CLIENT_INFO = dict(info) if isinstance(info, dict) else None


def get_client_info() -> dict | None:
    return dict(_CLIENT_INFO) if _CLIENT_INFO else None


@dataclass(frozen=True)
class HostInfo:
    key: str
    provider: str
    confidence: float
    evidence: str


def _info(key: str, confidence: float, evidence: str) -> HostInfo:
    return HostInfo(key=key, provider=HOST_PROVIDERS.get(key, "claude"),
                    confidence=confidence, evidence=evidence)


def detect_host(repo_root: str | Path = ".",
                client_info: dict | None = None) -> HostInfo:
    """Best available identification of the running agent. Never raises."""
    try:
        override = os.environ.get(_ENV_OVERRIDE, "").strip().lower()
        if override:
            return _info(override, 1.0, "%s=%s" % (_ENV_OVERRIDE, override))

        ci = client_info if client_info is not None else _CLIENT_INFO
        name = str((ci or {}).get("name") or "").lower()
        if name:
            for needle, key in _CLIENT_NAME_SIGNALS:
                if needle in name:
                    return _info(key, 0.95, "MCP clientInfo.name=%s" % name)

        for var, key in _ENV_SIGNALS:
            if os.environ.get(var, "").strip():
                return _info(key, 0.9, "env %s" % var)

        from promptwise.core.agent_detector import detect_agents
        result = detect_agents(repo_root)
        if result.targets:
            key = result.targets[0]
            conf = min(_REPO_SCAN_CAP, float(result.confidence.get(key, 0.0)))
            return _info(key, conf, "repo scan: %s" % ", ".join(result.fingerprints.get(key, [])))
    except Exception:
        pass
    return _info("unknown", 0.0, "no host signal")
