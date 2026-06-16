"""Mermaid validator: accepts valid diagrams, rejects malformed ones."""
from promptwise.core import validate_mermaid


def test_valid_flowchart():
    r = validate_mermaid("flowchart TD\n  A[Start] --> B[End]")
    assert r.valid and r.diagram_type == "flowchart"


def test_valid_er_with_cardinality_not_flagged():
    # '||--o{' contains a brace that must NOT count as structural.
    src = "erDiagram\n  A ||--o{ B : has\n  A {\n    string id PK\n  }"
    r = validate_mermaid(src)
    assert r.valid, r.errors


def test_unbalanced_brackets_rejected():
    r = validate_mermaid("flowchart TD\n  A[Start --> B[End]")
    assert not r.valid
    assert any("bracket" in e.lower() for e in r.errors)


def test_unknown_type_rejected():
    r = validate_mermaid("notadiagram foo\n  A --> B")
    assert not r.valid


def test_strips_mermaid_fence():
    r = validate_mermaid("```mermaid\nsequenceDiagram\n  A->>B: hi\n```")
    assert r.valid and r.diagram_type == "sequenceDiagram"


def test_empty_rejected():
    assert not validate_mermaid("").valid
