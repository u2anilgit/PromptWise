"""response_budget -- cap the size of PromptWise's own tool-call responses.

Every optimization tool (rank_context, compress_prompt, optimize_context)
shrinks the prompt going INTO a model call; nothing shrinks PromptWise's own
tool responses coming back to the caller. A large list_tasks/search_trace/
run_security_suite result could return unbounded JSON. This module applies
one global cap at the call_tool choke point, keeping only the first N items
of any list-shaped field and adding a count marker for what was dropped,
rather than string-chopping raw JSON.

Design note: earlier versions of this module had three separate call sites
for "trim a list" (top-level, dict-value, list-item), and only some of them
recursed into survivors -- every patch closed one shape-specific gap and a
review kept finding the next one (top-level list, list-in-dict-value,
list-in-list-item, ...). This version replaces all of that with a single
generic recursive walker, `_process`, that treats "a list found at the
document root", "a list found as a dict value", and "a list found as an item
inside another list" identically: trim to `limit`, record what was dropped,
then recurse into every surviving element regardless of where the list was
found. There is exactly one trimming code path (`_process_list`) and one
recursion code path (`_process`).
"""
from __future__ import annotations

import json
import os
from typing import Any

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
    new_data, changed = _process(data, limit)
    if not changed:
        return raw_json
    return json.dumps(new_data)


def _process(obj: Any, limit: int) -> tuple[Any, bool]:
    """Generic recursive walker: cap every list-shaped field within `obj`,
    no matter whether it sits at the document root, as a dict value, or as
    an item inside another list -- one code path handles all three.

    Returns (possibly-new obj, changed).
    """
    if isinstance(obj, dict):
        changed = False
        for key, value in list(obj.items()):
            if isinstance(value, list):
                kept, dropped, item_changed = _process_list(value, limit)
                obj[key] = kept
                if dropped:
                    obj[f"{key}_truncated_count"] = dropped
                if dropped or item_changed:
                    changed = True
            elif isinstance(value, dict):
                _, value_changed = _process(value, limit)
                if value_changed:
                    changed = True
        return obj, changed

    if isinstance(obj, list):
        kept, dropped, item_changed = _process_list(obj, limit)
        if dropped:
            # No dict key (or document root) exists here to hang a
            # "{key}_truncated_count" sibling off of -- wrap the trimmed
            # list in the same {"items": ..., "items_truncated_count": N}
            # envelope used for an over-limit top-level list, so the count
            # is always discoverable and never silently dropped, whether
            # this list is the document root or sitting inside another list.
            return {"items": kept, "items_truncated_count": dropped}, True
        return kept, item_changed

    return obj, False


def _process_list(value: list, limit: int) -> tuple[list, int, bool]:
    """Trim `value` to `limit` items, then recurse into every surviving item
    to cap its own nested lists too. This is the ONE trimming code path in
    the module; every list, regardless of where it was found, goes through
    it.

    Returns (kept_items, dropped_count, changed) where `changed` is True if
    anything -- the trim itself, or a nested cap inside a surviving item --
    happened.
    """
    dropped = 0
    if len(value) > limit:
        dropped = len(value) - limit
        value = value[:limit]
    changed = dropped > 0
    kept = []
    for item in value:
        new_item, item_changed = _process(item, limit)
        kept.append(new_item)
        if item_changed:
            changed = True
    return kept, dropped, changed
