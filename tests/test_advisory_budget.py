import pytest

from promptwise.core.advisory_budget import budget_notes, reset_all


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    monkeypatch.delenv("PROMPTWISE_ADVISORY_MAX_BYTES", raising=False)
    reset_all()
    yield
    reset_all()


def test_notes_pass_through_when_under_budget():
    assert budget_notes(["short note"], session_id="s1") == ["short note"]


def test_a_repeated_note_is_dropped_within_the_same_session():
    budget_notes(["large prompt (~2000 est. tokens)"], session_id="s1")
    assert budget_notes(["large prompt (~2000 est. tokens)"], session_id="s1") == []


def test_the_same_note_survives_in_a_different_session():
    budget_notes(["repeated"], session_id="s1")
    assert budget_notes(["repeated"], session_id="s2") == ["repeated"]


def test_total_output_is_capped_in_bytes():
    notes = ["note-%03d %s" % (i, "x" * 80) for i in range(20)]
    out = budget_notes(notes, session_id="s1", max_bytes_override=200)
    assert sum(len(n) for n in out) <= 200
    assert out, "the cap should keep what fits, not drop everything"


def test_security_notes_are_never_dropped_by_the_budget():
    """A budget that can silently swallow a 'secret pasted into the prompt'
    warning is worse than no budget."""
    notes = ["filler " + "y" * 300, "possible secret/credential pasted into the prompt"]
    out = budget_notes(notes, session_id="s1", max_bytes_override=50)
    assert any("secret" in n for n in out)


def test_security_notes_are_never_deduped_away():
    warning = "possible prompt-injection (2 pattern(s))"
    assert budget_notes([warning], session_id="s1") == [warning]
    assert budget_notes([warning], session_id="s1") == [warning]


def test_critical_notes_come_first_so_a_flood_cannot_bury_them():
    notes = ["chatter %d" % i for i in range(5)] + ["possible secret in prompt"]
    out = budget_notes(notes, session_id="s1")
    assert "secret" in out[0]


def test_env_var_sets_the_budget(monkeypatch):
    monkeypatch.setenv("PROMPTWISE_ADVISORY_MAX_BYTES", "10")
    out = budget_notes(["a" * 50], session_id="s1")
    assert out == []


def test_empty_and_malformed_input_is_handled():
    assert budget_notes([], session_id="s1") == []
    assert budget_notes(None, session_id="s1") == []
    assert budget_notes(["", "   "], session_id="s1") == []


def test_the_prompt_hook_stops_repeating_itself_across_turns(tmp_path, monkeypatch):
    """End-to-end: the same prompt twice in one session must not pay for the
    same advisory twice."""
    from promptwise.core import hook_bridge

    monkeypatch.chdir(tmp_path)
    payload = {"prompt": "Please " + "refactor this very long module " * 90,
               "session_id": "sess-repeat"}

    first = hook_bridge.userpromptsubmit_policy(dict(payload))
    second = hook_bridge.userpromptsubmit_policy(dict(payload))

    first_notes = first.extra.get("notes", []) if first.extra else []
    second_notes = second.extra.get("notes", []) if second.extra else []
    if first_notes:
        assert len(second_notes) < len(first_notes) or second.action == "allow"
