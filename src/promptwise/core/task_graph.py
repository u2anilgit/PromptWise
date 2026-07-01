"""task_graph — decide which tasks are *safe* to run in parallel.

The one thing an agent harness cannot decide for itself: given a set of tasks
with dependencies, which ones may run concurrently without corrupting shared
state. This module answers that and emits an ordered list of **waves** (each wave
= tasks that can run at once), leaving the actual concurrent dispatch to the
harness. Pure stdlib, additive, no execution, no infrastructure.

Safety rails baked in:
  * **Dependency order** via Kahn's algorithm (topological layering).
  * **Cycle detection for free** — any task left unscheduled is in a cycle and
    is reported, never silently misordered.
  * **Shared-file serialization** — two tasks that write the same target never
    land in the same wave (prevents parallel writers to one file).
  * **Fan-out cap** — a wave is capped so parallelism can't blow the budget;
    overflow spills to the next wave.
"""
from __future__ import annotations

DEFAULT_FAN_OUT = 8


def plan_waves(tasks: list[dict], fan_out_cap: int = DEFAULT_FAN_OUT) -> dict:
    """Return an execution plan: ordered waves of task ids safe to run together.

    Each task is ``{"id": str, "depends_on": [ids], "file": optional target}``
    (``target`` is accepted as an alias for ``file``). Unknown deps are ignored.
    """
    fan_out_cap = max(1, int(fan_out_cap))
    ids = [t["id"] for t in tasks]
    idset = set(ids)
    deps = {t["id"]: {d for d in (t.get("depends_on") or []) if d in idset and d != t["id"]}
            for t in tasks}
    files = {t["id"]: (t.get("file") or t.get("target") or "") for t in tasks}
    dependents: dict[str, list[str]] = {i: [] for i in ids}
    for i in ids:
        for d in deps[i]:
            dependents[d].append(i)
    indeg = {i: len(deps[i]) for i in ids}

    remaining = set(ids)
    waves: list[list[str]] = []
    serialized: set[str] = set()
    capped_any = False

    while True:
        ready = [i for i in ids if i in remaining and indeg[i] == 0]
        if not ready:
            break
        wave: list[str] = []
        used_files: set[str] = set()
        for i in ready:
            f = files[i]
            if f and f in used_files:
                serialized.add(i)          # same file target -> hold for a later wave
                continue
            if f:
                used_files.add(f)
            wave.append(i)
        if len(wave) > fan_out_cap:
            capped_any = True
            wave = wave[:fan_out_cap]      # overflow stays in `remaining` for next wave
        if not wave:
            break                          # defensive: never spin without progress
        waves.append(wave)
        for i in wave:
            remaining.discard(i)
            for dep in dependents[i]:
                indeg[dep] -= 1

    cycle = sorted(remaining)              # anything unscheduled is in a dependency cycle
    return {
        "waves": waves,
        "wave_count": len(waves),
        "max_parallel": max((len(w) for w in waves), default=0),
        "cycle": cycle,
        "has_cycle": bool(cycle),
        "serialized": sorted(serialized),
        "fan_out_cap": fan_out_cap,
        "capped": capped_any,
    }


def summarize_plan(plan: dict) -> str:
    """One-line human summary for logs / the orchestrate tool."""
    if plan.get("has_cycle"):
        return f"cycle detected among {plan['cycle']} — cannot schedule; break the dependency loop"
    parts = [f"{plan['wave_count']} wave(s)", f"max {plan['max_parallel']} parallel"]
    if plan.get("serialized"):
        parts.append(f"{len(plan['serialized'])} serialized on shared files")
    if plan.get("capped"):
        parts.append(f"fan-out capped at {plan['fan_out_cap']}")
    return "; ".join(parts)
