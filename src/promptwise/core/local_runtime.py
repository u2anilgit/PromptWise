"""local_runtime — device-aware config and long-output handling for local models.

Targets on-device runtimes exposed over ``localhost`` (an on-device call, not an
air-gap violation). Four concerns, all stdlib and fail-soft — if no daemon is
running the feature is simply dormant and nothing breaks:

  * **Device probe** — cores, RAM, and best-effort VRAM (unknown stays unknown).
  * **Token-config recommender** — a safe ``num_ctx`` / output split for the
    device; conservative when VRAM can't be read.
  * **Discovery** — enumerate a local runtime's models (this is the one place a
    *real* model list is available, unlike a hosted build) to feed the registry.
  * **Long-output continuation** — boundary-aware splitting that never cuts inside
    a sentence or a fenced code block, plus overlap-aware stitching, so a small
    context window can emit a long answer coherently.
"""
from __future__ import annotations

import os
import re

DEFAULT_OLLAMA_URL = "http://localhost:11434"


# ── device probe ─────────────────────────────────────────────────────────────
def _ram_gb():
    try:
        if hasattr(os, "sysconf") and "SC_PHYS_PAGES" in os.sysconf_names:  # unix
            return round(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 1e9, 1)
    except Exception:
        pass
    try:  # windows
        import ctypes

        class _MS(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
        m = _MS()
        m.dwLength = ctypes.sizeof(_MS)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))  # type: ignore[attr-defined]
        return round(m.ullTotalPhys / 1e9, 1)
    except Exception:
        return None


def _vram_gb():
    try:
        import subprocess
        out = subprocess.run(["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
                             capture_output=True, text=True, timeout=3)
        if out.returncode == 0:
            vals = [int(x) for x in re.findall(r"\d+", out.stdout)]
            if vals:
                return round(max(vals) / 1024, 1)  # MiB -> GiB
    except Exception:
        pass
    return None  # unknown (Apple Silicon uses unified RAM; no clean stdlib path)


def probe_device() -> dict:
    """Best-effort device profile. Missing values stay ``None``; never raises."""
    import platform
    return {"cores": os.cpu_count() or 1, "ram_gb": _ram_gb(),
            "vram_gb": _vram_gb(), "platform": platform.system()}


def recommend_token_config(device: dict, model_ctx: int = 8192) -> dict:
    """Recommend num_ctx / output split for a device. VRAM drives it when known;
    otherwise a conservative fraction of RAM, or a floor when nothing is readable.
    Advisory — recommend, never force."""
    vram = device.get("vram_gb")
    ram = device.get("ram_gb")
    if vram:
        budget_gb, basis = vram, "vram"
    elif ram:
        budget_gb, basis = ram * 0.5, "ram"       # leave half for the OS + app
    else:
        budget_gb, basis = None, "conservative-default"
    if budget_gb:
        num_ctx = int(min(model_ctx, max(2048, budget_gb * 4096)))  # ~4k ctx per GB (7B q4 heuristic)
    else:
        num_ctx = min(model_ctx, 4096)
    max_output = min(int(num_ctx * 0.4), 4096)
    return {"num_ctx": num_ctx, "max_output_tokens": max_output, "basis": basis,
            "note": "advisory estimate" + (" (VRAM unreadable — conservative)" if basis != "vram" else "")}


# ── discovery (localhost) ────────────────────────────────────────────────────
def _urllib_get_json(url: str, timeout: float = 3.0):
    import json
    import urllib.request
    with urllib.request.urlopen(url, timeout=timeout) as r:  # noqa: S310 (localhost only)
        return json.loads(r.read().decode("utf-8"))


def discover_ollama(base_url: str = DEFAULT_OLLAMA_URL, http_get=None) -> list[dict]:
    """Enumerate a local runtime's models. ``http_get`` is injected for testing;
    the default reads ``/api/tags`` over localhost. Fail-soft -> ``[]``."""
    getter = http_get or _urllib_get_json
    try:
        data = getter(base_url.rstrip("/") + "/api/tags")
        out = []
        for m in (data or {}).get("models", []) or []:
            alias = m.get("name") or m.get("model") or ""
            if alias:
                out.append({"alias": alias, "size": m.get("size"), "family": "local"})
        return out
    except Exception:
        return []


def to_registry_rows(local_models: list[dict]) -> list[dict]:
    """Convert discovered local models into registry rows (all local, priced $0)."""
    rows = []
    for m in local_models:
        size = m.get("size") or 0
        tier = "powerful" if size and size > 20e9 else ("balanced" if size and size > 5e9 else "fast")
        rows.append({"alias": m["alias"], "family": "local", "tier": tier, "status": "current",
                     "release_date": "", "price": {"input_per_mtok": 0.0, "output_per_mtok": 0.0}})
    return rows


# ── long-output continuation ─────────────────────────────────────────────────
_FENCE = re.compile(r"```.*?```", re.DOTALL)


def _blocks(text: str) -> list[tuple[str, str]]:
    """Split into ('code', ...) fenced blocks and ('text', ...) spans, in order."""
    out: list[tuple[str, str]] = []
    idx = 0
    for m in _FENCE.finditer(text):
        if m.start() > idx:
            out.append(("text", text[idx:m.start()]))
        out.append(("code", m.group(0)))
        idx = m.end()
    if idx < len(text):
        out.append(("text", text[idx:]))
    return out


def _split_text(span: str, max_chars: int) -> list[str]:
    """Split a plain-text span on paragraph, then sentence, then space, then hard."""
    if len(span) <= max_chars:
        return [span]
    pieces: list[str] = []
    rest = span
    while len(rest) > max_chars:
        window = rest[:max_chars]
        cut = window.rfind("\n\n")
        if cut < max_chars * 0.5:
            cut = max((window.rfind(". "), window.rfind("! "), window.rfind("? ")))
            cut = cut + 1 if cut != -1 else -1
        if cut < max_chars * 0.5:
            cut = window.rfind(" ")
        if cut <= 0:
            cut = max_chars  # hard cut (unavoidable, e.g. one long token)
        pieces.append(rest[:cut].rstrip())
        rest = rest[cut:].lstrip()
    if rest:
        pieces.append(rest)
    return pieces


def split_output(text: str, max_chars: int = 2000) -> list[dict]:
    """Split long output into chunks that never cut inside a sentence or a fenced
    code block. Returns ``[{text, kind, oversized}]``. A code fence larger than the
    limit is kept whole (never corrupted) and flagged ``oversized``."""
    if not text or len(text) <= max_chars:
        return [{"text": text or "", "kind": "single", "oversized": False}]
    chunks: list[dict] = []
    buf = ""

    def _flush():
        nonlocal buf
        if buf:
            chunks.append({"text": buf, "kind": "text", "oversized": False})
            buf = ""

    for kind, span in _blocks(text):
        if kind == "code":
            if len(buf) + len(span) > max_chars:
                _flush()
            if len(span) > max_chars:
                _flush()
                chunks.append({"text": span, "kind": "code", "oversized": True})  # keep code intact
            else:
                buf += span
        else:
            for piece in _split_text(span, max_chars):
                if len(buf) + len(piece) > max_chars:
                    _flush()
                buf += piece
    _flush()
    return chunks


def stitch(chunks: list[str], min_overlap: int = 10) -> str:
    """Join continuation chunks, removing a duplicated overlap where a chunk
    re-emitted the tail of the previous one."""
    parts = [c for c in chunks if c]
    if not parts:
        return ""
    result = parts[0]
    for nxt in parts[1:]:
        overlap = 0
        cap = min(len(result), len(nxt), 400)
        for size in range(cap, min_overlap - 1, -1):
            if result[-size:] == nxt[:size]:
                overlap = size
                break
        result += nxt[overlap:]
    return result


def continuation_prompt(previous_tail: str, tail_chars: int = 400) -> str:
    """Re-priming prompt for runtimes without native state passthrough: continue
    exactly, do not repeat. (Ollama's ``/api/generate`` context array is the clean
    path where available; this is the general fallback.)"""
    tail = (previous_tail or "")[-tail_chars:]
    return ("Continue the response from exactly where it stopped. Do not repeat any "
            "text already produced and do not restart. Here is the tail of what you "
            f"have written so far:\n\n{tail}")
