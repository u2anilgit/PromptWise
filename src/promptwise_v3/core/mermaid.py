"""Mermaid validator — lightweight, deterministic, self-contained.

Lints Mermaid diagram source (the text format produced by the diagram skill packs) so
generated diagrams actually render on GitHub / docs. No external renderer or network.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_DIAGRAM_TYPES = (
    "graph", "flowchart", "sequenceDiagram", "classDiagram", "stateDiagram",
    "stateDiagram-v2", "erDiagram", "journey", "gantt", "pie", "mindmap",
    "timeline", "C4Context", "C4Container", "C4Component",
)


@dataclass
class MermaidReport:
    valid: bool
    diagram_type: str = ""
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    node_count: int = 0


def validate_mermaid(source: str) -> MermaidReport:
    errors: list[str] = []
    warnings: list[str] = []

    text = (source or "").strip()
    # Strip a ```mermaid fence if present.
    fence = re.match(r"^```+\s*mermaid\s*\n(.*?)\n```+\s*$", text, re.DOTALL | re.IGNORECASE)
    if fence:
        text = fence.group(1).strip()
    elif text.startswith("```"):
        warnings.append("Unclosed or non-mermaid code fence detected.")
        text = re.sub(r"^```+[a-zA-Z]*\s*", "", text).strip()

    if not text:
        return MermaidReport(valid=False, errors=["Empty diagram source."])

    first = text.splitlines()[0].strip()
    diagram_type = next((d for d in _DIAGRAM_TYPES if first.startswith(d)), "")
    if not diagram_type:
        errors.append(f"First line does not declare a known Mermaid diagram type: {first!r}")

    # Bracket / quote balance. Strip relationship operators first so ER cardinality
    # tokens (||--o{, }o--o{, |{, etc.) don't count as structural braces.
    balance_text = re.sub(r"[|}{o]*--[|}{o]*", " ", text) if diagram_type == "erDiagram" else text
    for open_c, close_c, label in (("[", "]", "square"), ("(", ")", "round"), ("{", "}", "curly")):
        if balance_text.count(open_c) != balance_text.count(close_c):
            errors.append(f"Unbalanced {label} brackets: {balance_text.count(open_c)} '{open_c}' vs {balance_text.count(close_c)} '{close_c}'.")
    if text.count('"') % 2 != 0:
        errors.append("Unbalanced double quotes.")

    # Rough node/edge sanity.
    node_count = len(re.findall(r"[A-Za-z0-9_]+\s*(?:\[|\(|\{|-->|---|==>|-\.->)", text))
    if diagram_type in ("graph", "flowchart") and "-->" not in text and "---" not in text and "-.->" not in text:
        warnings.append("Flowchart has no edges (no '-->' / '---').")
    if diagram_type == "erDiagram" and "||" not in text and "}o" not in text and "}|" not in text:
        warnings.append("erDiagram has no relationship cardinality markers.")

    return MermaidReport(
        valid=not errors,
        diagram_type=diagram_type,
        errors=errors,
        warnings=warnings,
        node_count=node_count,
    )
