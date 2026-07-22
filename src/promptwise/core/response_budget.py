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
        kept, dropped, item_changed = _trim_list(data, limit)
        if dropped:
            return json.dumps({"items": kept, "items_truncated_count": dropped})
        if item_changed:
            return json.dumps(kept)
        return raw_json
    changed = _cap_lists(data, limit)
    if not changed:
        return raw_json
    return json.dumps(data)


def _trim_list(value: list, limit: int) -> tuple[list, int, bool]:
    """Trim `value` to `limit` items, then recurse into every surviving item
    to cap ITS own nested lists too.

    Trimming and recursing into the survivors are done together, in this one
    function, on purpose: every list truncation in this module -- top-level,
    dict-value, or list-nested-in-a-list -- routes through here, so a
    surviving item's own oversized lists can never be left uncapped just
    because the list holding it happened to be trimmed by a different code
    path.

    Returns (kept_items, dropped_count, changed) where `changed` is True if
    anything -- the trim itself, or a nested cap inside a surviving item --
    happened.
    """
    dropped = 0
    changed = False
    if len(value) > limit:
        dropped = len(value) - limit
        value = value[:limit]
        changed = True
    for item in value:
        if isinstance(item, (dict, list)):
            if _cap_lists(item, limit):
                changed = True
    return value, dropped, changed


def _cap_lists(obj, limit: int) -> bool:
    """Recursively cap every list-shaped field found within obj, in place.

    Any list this finds -- whether it's a dict's value or an item inside
    another list -- is trimmed and has its survivors recursed into via the
    single shared `_trim_list` path above. Returns whether anything changed.
    """
    changed = False
    if isinstance(obj, dict):
        for key, value in list(obj.items()):
            if isinstance(value, list):
                kept, dropped, item_changed = _trim_list(value, limit)
                obj[key] = kept
                if dropped:
                    obj[f"{key}_truncated_count"] = dropped
                if dropped or item_changed:
                    changed = True
            elif isinstance(value, dict):
                if _cap_lists(value, limit):
                    changed = True
    elif isinstance(obj, list):
        for item in obj:
            if isinstance(item, (dict, list)):
                if _cap_lists(item, limit):
                    changed = True
    return changed
