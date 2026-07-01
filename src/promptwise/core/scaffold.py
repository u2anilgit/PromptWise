"""scaffold — intent-aware solution scaffolding.

From a request, decide the *shape* of work (new build / re-engineer / re-architect
/ diagram), offer a small set of concrete approach **options** with trade-offs,
and produce two artifacts with zero infrastructure:

  * a self-contained **interactive spec page** (HTML, no CDN) the user can open
    and click through — options as cards, context chips, an inline flow diagram;
  * a validated **Mermaid diagram** seeded from the request (flowchart / sequence
    / architecture / ER), plus a dependency-free inline-SVG flow render.

Reuses the existing engines (context model, Mermaid validator). Pure stdlib.
"""
from __future__ import annotations

import html
import re

from promptwise.core.context_model import build_context_model
from promptwise.core.mermaid import validate_mermaid

MODES = ("build", "reengineer", "rearchitect", "diagram")

_DIAGRAM_HINTS = ("diagram", "flowchart", "flow chart", "sequence", "architecture",
                  "chart", "visualize", "visualise", "draw", "wireframe", "er diagram",
                  "data model", "state machine")
_REARCH_HINTS = ("re-architect", "rearchitect", "redesign", "new architecture",
                 "different layout", "restructure", "re-structure", "different architecture",
                 "microservice", "monolith", "decouple", "re-platform", "replatform")
_REENG_HINTS = ("refactor", "re-engineer", "reengineer", "modernize", "modernise",
                "rewrite", "clean up", "improve existing", "optimize existing",
                "tech debt", "technical debt", "migrate")
_BUILD_HINTS = ("build", "create", "implement", "add", "new feature", "greenfield",
                "from scratch", "prototype", "develop")


def classify_request(text: str, repo_root: str = ".") -> dict:
    """Classify the shape of work and gather context. Never raises."""
    low = (text or "").lower()
    try:
        ctx = build_context_model(text, repo_root)
        context = {"intent": ctx.intent, "role": ctx.role, "stack": ctx.stack,
                   "domain": ctx.domain, "regulated": ctx.regulated}
    except Exception:
        context = {"intent": "auto", "role": None, "stack": [], "domain": None, "regulated": False}

    def _hit(hints):
        return [h for h in hints if h in low]

    diagram_hits = _hit(_DIAGRAM_HINTS)
    if diagram_hits:
        mode = "diagram"
    elif _hit(_REARCH_HINTS):
        mode = "rearchitect"
    elif _hit(_REENG_HINTS):
        mode = "reengineer"
    elif _hit(_BUILD_HINTS):
        mode = "build"
    else:
        mode = "build"  # default for an under-specified request

    diagram_kind = _diagram_kind(low) if mode == "diagram" else None
    return {"mode": mode, "diagram_kind": diagram_kind, "context": context,
            "signals": {"diagram": diagram_hits}}


def _diagram_kind(low: str) -> str:
    if any(k in low for k in ("sequence", "interaction", "message", "call flow")):
        return "sequence"
    if any(k in low for k in ("architecture", "component", "system design", "service")):
        return "architecture"
    if any(k in low for k in ("er ", "entity", "data model", "schema", "database")):
        return "er"
    return "flow"


_OPTIONS = {
    "build": [
        ("MVP vertical slice", "Ship one thin end-to-end slice first, then widen.",
         "Fastest feedback; some early code gets reworked as scope grows.", "S", "validating an idea fast"),
        ("Foundation first", "Lock the data model and interfaces before feature work.",
         "Fewer rewrites later; slower to first demo.", "M", "a known, long-lived system"),
        ("Spike then build", "Throwaway prototype to de-risk the unknowns, then build for real.",
         "Retires technical risk early; the spike itself is discarded effort.", "M", "novel or uncertain tech"),
    ],
    "reengineer": [
        ("Strangler-fig", "Wrap the old path and replace it piece by piece behind the wrapper.",
         "Safe and reversible; slower, and the wrapper lingers a while.", "M", "a live system that can't stop"),
        ("Branch by abstraction", "Introduce a seam, build the new behind it, then flip.",
         "Main stays releasable throughout; needs a clean seam to exist.", "M", "continuous delivery"),
        ("Contained rewrite", "Rewrite a bounded module wholesale with tests as the contract.",
         "Fast for a small surface; risky if the surface is large or fuzzy.", "S", "a small, well-tested module"),
    ],
    "rearchitect": [
        ("Modular monolith", "One deployable, hard module boundaries inside it.",
         "Simplest ops; boundaries are convention, not enforced by the network.", "M", "most teams, most of the time"),
        ("Service extraction", "Split by bounded context into independent services.",
         "Independent scaling and deploys; real ops and distributed-systems cost.", "L", "clear domains + platform maturity"),
        ("Event-driven", "Decouple components through an event log / queue.",
         "Resilient and loosely coupled; harder to trace and debug end-to-end.", "L", "async, spiky, or fan-out workloads"),
        ("Ports and adapters", "Isolate the core domain from IO behind ports.",
         "Highly testable, swappable IO; more upfront indirection.", "M", "long-lived core logic"),
    ],
    "diagram": [
        ("Flowchart", "Steps and decisions as a top-down flow.", "Best for process / logic.", "S", "a process or algorithm"),
        ("Sequence", "Actors exchanging messages over time.", "Best for interactions.", "S", "an API or call flow"),
        ("Architecture", "Components and their connections.", "Best for system shape.", "S", "a system overview"),
        ("Entity relationship", "Entities and their relationships.", "Best for data.", "S", "a data model"),
    ],
}


def propose_options(text: str, mode: str) -> list[dict]:
    rows = _OPTIONS.get(mode, _OPTIONS["build"])
    return [{"title": t, "approach": a, "tradeoffs": tr, "effort": e, "best_for": bf}
            for (t, a, tr, e, bf) in rows]


def _extract_steps(text: str, limit: int = 8) -> list[str]:
    """Pull short step labels from a request (separators + verbs)."""
    parts = re.split(r"\b(?:then|next|after that|finally|first|second|third|,|;|\.|->|→)\b",
                     text or "", flags=re.I)
    steps = []
    for p in parts:
        p = p.strip(" .\t")
        if len(p) >= 3:
            steps.append(p[:48])
        if len(steps) >= limit:
            break
    return steps or ["Start", "Process", "Done"]


def _node_id(i: int) -> str:
    return "N" + str(i)


def mermaid_diagram(text: str, kind: str = "flow") -> str:
    """Seed a validated Mermaid diagram from the request. Falls back to a minimal
    valid diagram if seeding produces something invalid."""
    steps = _extract_steps(text)
    if kind == "sequence":
        actors = steps[:4]
        lines = ["sequenceDiagram"]
        for i in range(len(actors) - 1):
            lines.append(f"    {_safe(actors[i])}->>+{_safe(actors[i+1])}: step {i+1}")
        src = "\n".join(lines) if len(actors) > 1 else "sequenceDiagram\n    A->>B: message"
    elif kind == "architecture":
        lines = ["flowchart LR"]
        for i, s in enumerate(steps[:6]):
            lines.append(f"    {_node_id(i)}[{_bracket(s)}]")
        for i in range(min(len(steps), 6) - 1):
            lines.append(f"    {_node_id(i)} --> {_node_id(i+1)}")
        src = "\n".join(lines)
    elif kind == "er":
        ents = [re.sub(r"[^A-Za-z0-9_]", "", s.title().replace(" ", "")) or f"Entity{i}"
                for i, s in enumerate(steps[:4])]
        lines = ["erDiagram"]
        for i in range(len(ents) - 1):
            lines.append(f"    {ents[i]} ||--o{{ {ents[i+1]} : has")
        src = "\n".join(lines) if len(ents) > 1 else "erDiagram\n    A ||--o{ B : has"
    else:  # flow
        lines = ["flowchart TD"]
        for i, s in enumerate(steps):
            lines.append(f"    {_node_id(i)}[{_bracket(s)}]")
        for i in range(len(steps) - 1):
            lines.append(f"    {_node_id(i)} --> {_node_id(i+1)}")
        src = "\n".join(lines)

    if not validate_mermaid(src).valid:
        src = "flowchart TD\n    N0[Start] --> N1[Process] --> N2[Done]"
    return src


def _safe(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9 ]", "", s).strip().replace(" ", "_")[:20] or "step"


def _bracket(s: str) -> str:
    return re.sub(r"[\[\]{}()\"|]", "", s).strip()[:40] or "step"


def flow_svg(steps: list[str]) -> str:
    """Dependency-free inline SVG flow (boxes + arrows). Self-contained, no CDN."""
    steps = steps[:8] or ["Start", "Done"]
    bw, bh, gap, pad = 260, 52, 34, 20
    w = bw + pad * 2
    h = pad * 2 + len(steps) * bh + (len(steps) - 1) * gap
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">',
           '<defs><marker id="arw" markerWidth="9" markerHeight="9" refX="7" refY="3" orient="auto">'
           '<path d="M0,0 L7,3 L0,6 Z" fill="#818cf8"/></marker></defs>']
    y = pad
    cx = pad + bw // 2
    for i, s in enumerate(steps):
        out.append(f'<rect x="{pad}" y="{y}" width="{bw}" height="{bh}" rx="9" '
                   f'fill="#141820" stroke="#2a3350"/>')
        out.append(f'<text x="{cx}" y="{y + bh // 2 + 5}" fill="#e7e9f0" font-size="14" '
                   f'font-family="sans-serif" text-anchor="middle">{html.escape(s[:36])}</text>')
        if i < len(steps) - 1:
            y2 = y + bh
            out.append(f'<line x1="{cx}" y1="{y2}" x2="{cx}" y2="{y2 + gap}" '
                       f'stroke="#818cf8" stroke-width="2" marker-end="url(#arw)"/>')
        y += bh + gap
    out.append("</svg>")
    return "".join(out)


def render_spec_page(request: str, mode: str, options: list[dict],
                     diagram_mermaid: str, flow_svg_str: str, context: dict) -> str:
    """Self-contained interactive HTML spec page (no CDN, no external assets)."""
    chips = "".join(
        f'<span class="chip">{html.escape(str(k))}: {html.escape(str(v))}</span>'
        for k, v in context.items() if v)
    cards = "".join(
        f'''<div class="opt" onclick="pick(this)">
              <div class="ot">{html.escape(o["title"])} <span class="eff">{html.escape(o["effort"])}</span></div>
              <div class="oa">{html.escape(o["approach"])}</div>
              <div class="otr"><b>Trade-off:</b> {html.escape(o["tradeoffs"])}</div>
              <div class="obf">Best for: {html.escape(o["best_for"])}</div>
            </div>''' for o in options)
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>PromptWise — Solution Scaffold</title>
<style>
 :root{{--bg:#0a0c10;--card:#141820;--line:rgba(255,255,255,.07);--ink:#e7e9f0;--mut:#7a869e;--accent:#818cf8;--good:#34d399;}}
 *{{box-sizing:border-box;margin:0;padding:0}} body{{background:var(--bg);color:var(--ink);font-family:-apple-system,Segoe UI,Roboto,sans-serif;padding:2rem;line-height:1.55}}
 h1{{font-size:1.5rem;letter-spacing:-.02em}} .mode{{color:var(--accent);text-transform:uppercase;font-size:.75rem;letter-spacing:.1em;margin-bottom:.4rem}}
 .req{{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:1rem 1.2rem;margin:1rem 0;color:var(--mut)}}
 .chips{{display:flex;gap:.5rem;flex-wrap:wrap;margin:1rem 0}} .chip{{background:var(--card);border:1px solid var(--line);border-radius:20px;padding:.25rem .7rem;font-size:.78rem;color:var(--mut)}}
 h2{{font-size:1rem;color:var(--accent);margin:1.5rem 0 .7rem}}
 .opts{{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:1rem}}
 .opt{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:1.1rem;cursor:pointer;transition:.15s}}
 .opt:hover{{border-color:var(--accent)}} .opt.sel{{border-color:var(--good);box-shadow:0 0 0 1px var(--good)}}
 .ot{{font-weight:700;margin-bottom:.4rem}} .eff{{float:right;font-size:.7rem;color:var(--mut);border:1px solid var(--line);border-radius:5px;padding:1px 6px}}
 .oa{{font-size:.9rem;margin-bottom:.5rem}} .otr,.obf{{font-size:.8rem;color:var(--mut);margin-top:.3rem}}
 .diagram{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:1.2rem;margin-top:.6rem;display:flex;gap:2rem;flex-wrap:wrap;align-items:flex-start}}
 pre{{background:#0c0e14;border:1px solid var(--line);border-radius:8px;padding:1rem;overflow:auto;font-size:.8rem;color:#cdd3e0;flex:1;min-width:280px}}
 .hint{{color:var(--mut);font-size:.8rem;margin-top:.5rem}}
</style></head><body>
 <div class="mode">{html.escape(mode)} scaffold</div>
 <h1>Solution options &amp; diagram</h1>
 <div class="req">{html.escape(request[:600])}</div>
 <div class="chips">{chips}</div>
 <h2>Approach options <span class="hint">(click to select)</span></h2>
 <div class="opts">{cards}</div>
 <h2>Diagram</h2>
 <div class="diagram">
   <div>{flow_svg_str}</div>
   <pre><code>{html.escape(diagram_mermaid)}</code></pre>
 </div>
 <div class="hint">The SVG renders anywhere with no dependencies; the Mermaid source drops into any Mermaid renderer.</div>
 <script>function pick(el){{document.querySelectorAll('.opt').forEach(o=>o.classList.remove('sel'));el.classList.add('sel');}}</script>
</body></html>"""


def scaffold(text: str, repo_root: str = ".") -> dict:
    """End-to-end: classify -> options -> diagram -> interactive page (as a string)."""
    cls = classify_request(text, repo_root)
    mode = cls["mode"]
    options = propose_options(text, mode)
    kind = cls["diagram_kind"] or "flow"
    diagram = mermaid_diagram(text, kind)
    steps = _extract_steps(text)
    svg = flow_svg(steps)
    page = render_spec_page(text, mode, options, diagram, svg, cls["context"])
    return {"mode": mode, "diagram_kind": kind, "context": cls["context"],
            "options": options, "mermaid": diagram, "flow_svg": svg, "page_html": page}
