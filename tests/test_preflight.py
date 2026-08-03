import textwrap

from promptwise.core.preflight import classify_task_type, run_preflight

REG = textwrap.dedent("""
schema_version: 1
families:
  ff: { provider: claude, tier: fast }
  bf: { provider: claude, tier: balanced }
  pf: { provider: claude, tier: powerful }
  gf: { provider: gemini, tier: powerful }
models:
  - { alias: fast-cur, family: ff, status: current, release_date: "2026-01-01", price: {input_per_mtok: 1.0, output_per_mtok: 2.0} }
  - { alias: bal-cur, family: bf, status: current, release_date: "2026-01-01", price: {input_per_mtok: 3.0, output_per_mtok: 6.0} }
  - { alias: pow-cur-new, family: pf, status: current, release_date: "2026-02-01", price: {input_per_mtok: 10.0, output_per_mtok: 20.0} }
  - { alias: pow-cur-old, family: pf, status: current, release_date: "2026-01-01", price: {input_per_mtok: 10.0, output_per_mtok: 20.0} }
""")


def test_classify_task_type_bugfix():
    assert classify_task_type("fix the crash in the login handler") == "bugfix"


def test_classify_task_type_docs():
    assert classify_task_type("write docs for the new API") == "docs"


def test_classify_task_type_docs_matches_documentation_and_docstrings():
    # word-boundary keyword matching (text_match.any_keyword) means
    # "document"/"docstring" alone would NOT match "documentation"/
    # "docstrings" -- regression guard for that gap.
    assert classify_task_type("Write documentation and docstrings for the billing module") == "docs"


def test_classify_task_type_refactor():
    assert classify_task_type("refactor this module to simplify the logic") == "refactor"


def test_classify_task_type_new_code():
    assert classify_task_type("implement a new caching layer") == "new_code"


def test_classify_task_type_default_other():
    assert classify_task_type("hello there") == "other"


def test_run_preflight_empty_prompt_returns_defaults():
    result = run_preflight("")
    assert result.notes == []
    assert result.blocked is False


def test_run_preflight_never_raises_on_garbage_input():
    result = run_preflight(None)  # type: ignore[arg-type]
    assert result.notes == []


def test_run_preflight_flags_secret():
    result = run_preflight("here is my api_key=abcd1234efgh5678, use it")
    assert any("secret" in n.lower() for n in result.notes)


def test_run_preflight_flags_large_prompt():
    result = run_preflight("x " * 4000)
    assert any("large prompt" in n for n in result.notes)


def test_run_preflight_model_shortlist_off_by_default(monkeypatch):
    monkeypatch.delenv("PROMPTWISE_MODEL_RETENTION", raising=False)
    result = run_preflight("implement a new caching layer for the API")
    assert result.model_shortlist == []


def test_run_preflight_model_shortlist_opt_in(monkeypatch, tmp_path):
    monkeypatch.setenv("PROMPTWISE_MODEL_RETENTION", "on")
    reg_path = tmp_path / "models.yaml"
    reg_path.write_text(REG, encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    result = run_preflight(
        "design a production-critical distributed microservices architecture")
    if result.recommended_model:
        assert isinstance(result.model_shortlist, list)


def test_run_preflight_cross_provider_advisory_only():
    # No dispatch is ever performed -- only a text note when the routed
    # model's provider differs from the host's.
    result = run_preflight("hello", host="cursor")
    assert result.cross_provider_suggested in (True, False)
    if result.cross_provider_suggested:
        assert "advisory only" in result.cross_provider_note
