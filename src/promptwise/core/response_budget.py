"""response_budget -- cap the size of PromptWise's own tool-call responses.

Every optimization tool (rank_context, compress_prompt, optimize_context)
shrinks the prompt going INTO a model call; nothing shrinks PromptWise's own
tool responses coming back to the caller. A large list_tasks/search_trace/
run_security_suite result could return unbounded JSON. This module applies
one global cap at the call_tool choke point, keeping only the first N items
of any list-shaped field and adding a count marker for what was dropped,
rather than string-chopping raw JSON.
"""
from __future__ import annotations

import json
import os

DEFAULT_MAX_ITEMS = 200

# Tools where the full payload is the point -- capping would corrupt the
# artifact (an audit export missing rows is worse than a large one).
EXEMPT_TOOLS = frozenset({
    "export_audit", "get_sbom", "export_compliance_bundle", "export_web_bundle",
})


def _max_items() -> int:
    raw = os.environ.get("PROMPTWISE_MAX_RESPONSE_ITEMS")
    if not raw:
        return DEFAULT_MAX_ITEMS
    try:
        return max(1, int(raw))
    except ValueError:
        return DEFAULT_MAX_ITEMS


def cap_response(name: str, raw_json: str) -> str:
    """Keep only the first N items of any over-limit list-shaped field in a
    tool's JSON response. Fail-open: unparseable JSON or an exempt tool name
    passes through unchanged."""
    if name in EXEMPT_TOOLS:
        return raw_json
    try:
        data = json.loads(raw_json)
    except Exception:
        return raw_json
    limit = _max_items()
    if isinstance(data, list):
        # A bare top-level list has no dict to hang a "{key}_truncated_count"
        # sibling off of, unlike the dict-value case below. Wrap it in an
        # {"items": ..., "items_truncated_count": N} envelope so the marker
        # survives JSON round-tripping -- this only changes the top-level
        # JSON type callers see in the rare case truncation actually fires.
        if len(data) > limit:
            dropped = len(data) - limit
            return json.dumps({"items": data[:limit], "items_truncated_count": dropped})
        return raw_json
    changed = _cap_lists(data, limit)
    if not changed:
        return raw_json
    return json.dumps(data)


def _cap_lists(obj, limit: int) -> bool:
    changed = False
    if isinstance(obj, dict):
        for key, value in list(obj.items()):
            if isinstance(value, list) and len(value) > limit:
                dropped = len(value) - limit
                obj[key] = value[:limit]
                obj[f"{key}_truncated_count"] = dropped
                changed = True
            elif isinstance(value, (dict, list)):
                changed = _cap_lists(value, limit) or changed
    elif isinstance(obj, list):
        for item in obj:
            if isinstance(item, (dict, list)):
                changed = _cap_lists(item, limit) or changed
    return changed
