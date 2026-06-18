"""Project context model: intent + role + stack + domain/regulated from text and repo."""
from promptwise.core.context_model import ProjectContextModel, build_context_model


def test_codeish_prompt_intent_is_nonempty():
    m = build_context_model("Write a Python function to parse logs")
    assert isinstance(m.intent, str)
    assert m.intent != ""
    assert m.intent in ("code", "analysis", "extract", "research", "question", "auto")


def test_pyproject_marker_detects_python(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'x'\n", encoding="utf-8")
    m = build_context_model("hello", repo_root=tmp_path)
    assert "python" in m.stack


def test_package_json_marker_detects_node(tmp_path):
    (tmp_path / "package.json").write_text("{}", encoding="utf-8")
    m = build_context_model("hello", repo_root=tmp_path)
    assert "node" in m.stack


def test_empty_repo_has_empty_stack(tmp_path):
    m = build_context_model("hello", repo_root=tmp_path)
    assert m.stack == []


def test_stack_is_sorted_unique(tmp_path):
    (tmp_path / "pyproject.toml").write_text("", encoding="utf-8")
    (tmp_path / "requirements.txt").write_text("", encoding="utf-8")
    (tmp_path / "package.json").write_text("{}", encoding="utf-8")
    m = build_context_model("hello", repo_root=tmp_path)
    assert m.stack == ["node", "python"]


def test_healthcare_domain_is_regulated(tmp_path):
    m = build_context_model("HIPAA compliance for patient records", repo_root=tmp_path)
    assert m.domain == "healthcare"
    assert m.regulated is True


def test_banking_domain_is_regulated(tmp_path):
    m = build_context_model("AML checks for payment processing", repo_root=tmp_path)
    assert m.domain == "banking"
    assert m.regulated is True


def test_neutral_text_has_no_domain(tmp_path):
    m = build_context_model("plan a birthday party", repo_root=tmp_path)
    assert m.domain is None
    assert m.regulated is False


def test_role_is_str_or_none(tmp_path):
    m = build_context_model("refactor and debug this API code", repo_root=tmp_path)
    assert m.role is None or isinstance(m.role, str)


def test_never_raises_on_missing_repo_root(tmp_path):
    missing = tmp_path / "does_not_exist"
    m = build_context_model("hello world", repo_root=missing)
    assert isinstance(m, ProjectContextModel)
    assert m.stack == []


def test_fields_exact_names():
    m = build_context_model("hello")
    assert set(vars(m).keys()) == {"intent", "role", "stack", "domain", "regulated"}
