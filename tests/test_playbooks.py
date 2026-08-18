"""WP3 -- YAML playbook loader + execution engine. Reuses core/governor.py's
exact autonomy-gating pattern (PROMPTWISE_AUTONOMY env var, advise/dry_run/
apply, per-call mode override, conservative fallback on unknown value) --
NOT a new mechanism. dry-run (the default) never executes; apply requires
explicit opt-in matching run_governor's posture.
"""
import os

import pytest

from promptwise.core.playbooks import (
    Playbook, PlaybookStep, PlaybookRun, StepResult, load_playbook, run_playbook,
)


def _sample_playbook():
    return Playbook(
        name="test_playbook", description="test",
        steps=[
            PlaybookStep(name="contain", action="quarantine_actor", params={"actor": "alice"}),
            PlaybookStep(name="notify", action="send_alert", params={"channel": "security"}),
        ])


def test_load_playbook_from_yaml(tmp_path):
    yaml_text = """
name: test_playbook
description: A test playbook
steps:
  - name: contain
    action: quarantine_actor
    params:
      actor: alice
  - name: notify
    action: send_alert
    params:
      channel: security
    on_failure: continue
"""
    path = tmp_path / "test.yaml"
    path.write_text(yaml_text, encoding="utf-8")
    pb = load_playbook(path)
    assert pb.name == "test_playbook"
    assert len(pb.steps) == 2
    assert pb.steps[0].action == "quarantine_actor"
    assert pb.steps[0].on_failure == "halt"  # default
    assert pb.steps[1].on_failure == "continue"


def test_run_playbook_advise_mode_never_executes(monkeypatch):
    monkeypatch.delenv("PROMPTWISE_AUTONOMY", raising=False)
    calls = []
    run = run_playbook(_sample_playbook(), executor=lambda step: calls.append(step.name) or True)
    assert calls == []  # advise (default) -- executor never invoked
    assert run.mode == "advise"
    assert all(r.status == "would_apply" for r in run.results)


def test_run_playbook_dry_run_mode_never_executes():
    calls = []
    run = run_playbook(_sample_playbook(), mode="dry_run", executor=lambda step: calls.append(step.name) or True)
    assert calls == []
    assert run.mode == "dry_run"
    assert all(r.status == "would_apply" for r in run.results)


def test_run_playbook_apply_mode_executes_via_injected_executor():
    calls = []
    run = run_playbook(_sample_playbook(), mode="apply", executor=lambda step: calls.append(step.name) or True)
    assert calls == ["contain", "notify"]
    assert run.mode == "apply"
    assert all(r.status == "applied" for r in run.results)


def test_run_playbook_apply_mode_env_var_override(monkeypatch):
    monkeypatch.setenv("PROMPTWISE_AUTONOMY", "apply")
    calls = []
    run = run_playbook(_sample_playbook(), executor=lambda step: calls.append(step.name) or True)  # no explicit mode
    assert calls == ["contain", "notify"]
    assert run.mode == "apply"


def test_run_playbook_unknown_mode_falls_back_to_advise():
    calls = []
    run = run_playbook(_sample_playbook(), mode="bogus", executor=lambda step: calls.append(step.name) or True)
    assert calls == []
    assert run.mode == "advise"


def test_run_playbook_step_failure_halts_by_default():
    pb = Playbook(name="p", description="", steps=[
        PlaybookStep(name="a", action="x", params={}),           # on_failure=halt (default)
        PlaybookStep(name="b", action="y", params={}),
    ])
    run = run_playbook(pb, mode="apply", executor=lambda step: step.name != "a")  # step "a" fails
    assert run.halted_at == "a"
    assert len(run.results) == 1
    assert run.results[0].status == "failed"


def test_run_playbook_step_failure_continues_when_configured():
    pb = Playbook(name="p", description="", steps=[
        PlaybookStep(name="a", action="x", params={}, on_failure="continue"),
        PlaybookStep(name="b", action="y", params={}),
    ])
    run = run_playbook(pb, mode="apply", executor=lambda step: step.name != "a")
    assert run.halted_at is None
    assert len(run.results) == 2
    assert run.results[0].status == "failed"
    assert run.results[1].status == "applied"


def test_playbook_run_to_dict():
    run = run_playbook(_sample_playbook())
    d = run.to_dict()
    assert set(d) >= {"playbook_name", "mode", "results", "halted_at"}
    assert isinstance(d["results"][0], dict)
