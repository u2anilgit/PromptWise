"""Phase 13.2 — indirect prompt-injection canary (Rebuff-style).

A canary token is embedded in content that flows through tool output / RAG; if
that token comes back in the model's output, the injected content leaked back
out (an indirect-injection / exfiltration signal). Wired into scan_response.
"""
import asyncio
import json
import typing

from promptwise.security.scanner import SecurityScanner
from promptwise import server as srv


class _Ctx:
    def __init__(self):
        self.security = SecurityScanner()


def _call(name, arguments):
    # _Ctx is a lightweight stand-in: this handler only reads ctx.security,
    # not the full ServerContext shape. Cast documents the intentional gap.
    ctx = typing.cast(srv.ServerContext, _Ctx())
    coro = typing.cast(
        "typing.Coroutine[typing.Any, typing.Any, str]", srv._HANDLERS[name](ctx, arguments)
    )
    return asyncio.run(coro)


def test_issue_canary_is_unique_and_nonempty():
    s = SecurityScanner()
    a, b = s.issue_canary(), s.issue_canary()
    assert a and b and a != b


def test_embed_canary_hides_token_in_content():
    s = SecurityScanner()
    tok = s.issue_canary()
    wrapped = s.embed_canary("Here is the retrieved document body.", tok)
    assert tok in wrapped
    assert "Here is the retrieved document body." in wrapped


def test_check_canary_leak_detects_and_ignores():
    s = SecurityScanner()
    tok = s.issue_canary()
    assert s.check_canary_leak(f"...the answer is {tok} oops", tok) is True
    assert s.check_canary_leak("a clean response with nothing hidden", tok) is False
    assert s.check_canary_leak("anything", "") is False


def test_scan_response_flags_canary_leak():
    s = SecurityScanner()
    tok = s.issue_canary()
    out = json.loads(_call("scan_response", {
        "response": f"Sure, here is what the source said: {tok}",
        "canary": tok}))
    assert out["canary_leak"] is True
    assert out["safe"] is False


def test_scan_response_no_canary_is_backward_compatible():
    out = json.loads(_call("scan_response", {"response": "A perfectly clean answer."}))
    # New key is present but false; existing keys are unchanged.
    assert out["canary_leak"] is False
    assert out["safe"] is True
    assert {"pii_found", "injection_echo", "system_leak", "responsible_ai"} <= set(out)
