"""Phase 6 WP10 — intent-aware scaffolding (options + interactive page + diagram)."""
from promptwise.core import scaffold as S
from promptwise.core.mermaid import validate_mermaid


# ── classification ───────────────────────────────────────────────────────────
def test_classify_build():
    assert S.classify_request("Build a new invoicing feature from scratch")["mode"] == "build"


def test_classify_reengineer():
    assert S.classify_request("Refactor the legacy billing module and pay down tech debt")["mode"] == "reengineer"


def test_classify_rearchitect():
    assert S.classify_request("Re-architect the monolith into a different layout")["mode"] == "rearchitect"


def test_classify_diagram_and_kind():
    c = S.classify_request("Draw a sequence diagram of the checkout call flow")
    assert c["mode"] == "diagram"
    assert c["diagram_kind"] == "sequence"


def test_classify_underspecified_defaults_to_build():
    assert S.classify_request("do the thing")["mode"] == "build"


# ── options ──────────────────────────────────────────────────────────────────
def test_options_have_required_shape():
    for mode in S.MODES:
        opts = S.propose_options("some request", mode)
        assert 2 <= len(opts) <= 4
        for o in opts:
            assert {"title", "approach", "tradeoffs", "effort", "best_for"} <= set(o)


# ── diagrams (must be valid Mermaid) ─────────────────────────────────────────
def test_mermaid_flow_is_valid():
    src = S.mermaid_diagram("read the file, then process it, then write output", "flow")
    assert validate_mermaid(src).valid
    assert src.startswith("flowchart")


def test_mermaid_all_kinds_valid():
    for kind in ("flow", "sequence", "architecture", "er"):
        src = S.mermaid_diagram("user submits order then service charges then db stores", kind)
        assert validate_mermaid(src).valid, f"{kind} produced invalid mermaid"


def _no_external_assets(doc: str) -> bool:
    low = doc.lower()
    # the SVG xmlns URI is a namespace, not a fetch; real external assets would
    # appear as a CDN link, a <link>, or an http(s) src/href.
    return ("cdn" not in low and "<link" not in low
            and 'src="http' not in low and 'href="http' not in low)


def test_flow_svg_is_self_contained():
    svg = S.flow_svg(["Login", "Validate", "Redirect"])
    assert svg.startswith("<svg") and "</svg>" in svg
    assert _no_external_assets(svg)
    assert "Login" in svg


# ── spec page ────────────────────────────────────────────────────────────────
def test_spec_page_is_self_contained_and_interactive():
    r = S.scaffold("Build a new dashboard, then wire the API, then add auth")
    page = r["page_html"]
    assert page.startswith("<!DOCTYPE html>")
    assert _no_external_assets(page)     # no CDN / external CSS / JS / fonts
    assert "pick(this)" in page          # clickable option selection
    assert r["mode"] in S.MODES
    assert "<svg" in page


def test_scaffold_returns_all_parts():
    r = S.scaffold("Re-architect the service into event-driven components")
    assert set(r) >= {"mode", "options", "mermaid", "flow_svg", "page_html", "context"}
    assert r["mode"] == "rearchitect"
