"""Tests for the additive agile-method + governance modules.

Run with:  python -m pytest tests/test_agile_governance.py -q
These import only the new modules; they do not touch existing PromptWise code.
"""
from __future__ import annotations

from promptwise.core.doc_sharder import DocSharder
from promptwise.core.story_context import StoryContextBuilder
from promptwise.core.quality_gate import QualityGate, PASS, CONCERNS, FAIL, WAIVED
from promptwise.core.policy import Policy
from promptwise.core.audit_log import AuditLog
from promptwise.core.config_emitter import ConfigEmitter, GovernanceBundle, TARGETS


PRD = """# Payments PRD
Intro text.

## Epic 1 Onboarding
Onboard merchants with KYC.

## Epic 2 Reconciliation
Reconcile ledgers nightly. FINRA relevant.

### Detail
Edge cases here.
"""


# ---------- doc_sharder ----------
def test_shard_splits_on_level_2():
    shards = DocSharder().shard(PRD, by_level=2)
    titles = [s.title for s in shards]
    assert "Payments PRD" in titles
    assert "Epic 1 Onboarding" in titles
    assert "Epic 2 Reconciliation" in titles
    # the '### Detail' stays inside Epic 2's shard
    epic2 = [s for s in shards if s.title == "Epic 2 Reconciliation"][0]
    assert "Edge cases" in epic2.body


def test_shards_for_epic_matches_numeric():
    shards = DocSharder().shard(PRD)
    hits = DocSharder().shards_for_epic(shards, "E2")
    assert any("Reconciliation" in s.title for s in hits)


# ---------- story_context ----------
def test_story_embeds_context_and_compliance():
    shards = DocSharder().shard(PRD)
    arch = DocSharder().shards_for_epic(shards, "E2")
    story = StoryContextBuilder().build(
        story_id="S2.1",
        title="Nightly ledger reconciliation",
        epic_id="E2",
        acceptance_criteria=["Balances match to the cent"],
        arch_shards=arch,
        files_to_touch=["recon/job.py"],
        compliance_rules=["FINRA 3110 audit log retained"],
        tasks=["write job", "write tests"],
    )
    d = story.to_dict()
    assert d["status"] == "Draft"
    assert d["dev_notes"]["compliance_rules"] == ["FINRA 3110 audit log retained"]
    assert d["dev_notes"]["relevant_architecture"]  # not empty -> self-contained
    assert "Reconciliation" in story.to_markdown()


# ---------- quality_gate ----------
def test_gate_pass_concerns_fail_waived():
    g = QualityGate(concerns_threshold=40)
    assert g.evaluate("S1", findings=[]).decision == PASS
    assert g.evaluate("S1", findings=[{"severity": "medium"}]).decision == CONCERNS
    assert g.evaluate("S1", risk_score=55).decision == CONCERNS
    assert g.evaluate("S1", findings=[{"severity": "high"}]).decision == FAIL
    w = g.evaluate("S1", findings=[{"severity": "high"}], waiver_reason="risk accepted by CISO")
    assert w.decision == WAIVED and w.waiver_reason


# ---------- policy ----------
def test_policy_blocks_and_allows():
    p = Policy.from_dict({
        "budget_cap_usd": 1.00,
        "allowed_model_tiers": ["haiku", "sonnet"],
        "banned_operations": ["force_push"],
        "required_gates": ["quality"],
    })
    ok = p.evaluate_action(model_tier="sonnet", estimated_cost=0.2, spent_so_far=0.1,
                           operation="commit", gates_passed=["quality"])
    assert ok.allowed and not ok.violations

    bad = p.evaluate_action(model_tier="opus", estimated_cost=2.0, spent_so_far=0.0,
                            operation="force_push", gates_passed=[])
    assert not bad.allowed
    assert len(bad.violations) == 4  # tier + budget + banned op + missing gate


def test_policy_warns_near_cap():
    p = Policy.from_dict({"budget_cap_usd": 1.0})
    d = p.evaluate_action(estimated_cost=0.95, spent_so_far=0.0)
    assert d.allowed and d.warnings


# ---------- audit_log ----------
def test_audit_chain_verifies_and_detects_tamper():
    log = AuditLog()
    log.append("draft story S2.1", agent="claude-code", model="sonnet",
               cost_usd=0.01, gate_decision="PASS", rules_applied=["banking"])
    log.append("implement S2.1", agent="cursor", model="sonnet", cost_usd=0.02,
               gate_decision="CONCERNS")
    ok, msg = log.verify()
    assert ok, msg
    # tamper: mutate a stored field, hash no longer matches
    log.records[0].cost_usd = 9.99
    ok2, _ = log.verify()
    assert not ok2


def test_audit_persists_jsonl(tmp_path):
    path = tmp_path / "audit.jsonl"
    log = AuditLog(path)
    log.append("task one", agent="codex")
    reloaded = AuditLog(path)
    assert len(reloaded.records) == 1
    ok, _ = reloaded.verify()
    assert ok


# ---------- config_emitter ----------
def test_emitter_renders_all_targets(tmp_path):
    bundle = GovernanceBundle(
        project="acme-payments",
        policy_summary=["Budget cap $5/day", "Tiers: haiku/sonnet only"],
        packs=["banking", "agile-sm", "agile-qa"],
        rules=["No secrets in code"],
    )
    res = ConfigEmitter().sync(bundle, tmp_path)
    assert set(res) == set(TARGETS.values())
    assert all(v == "written" for v in res.values())
    # cross-agent parity: the policy line appears in each generated file
    for rel in TARGETS.values():
        text = (tmp_path / rel).read_text(encoding="utf-8")
        assert "Budget cap $5/day" in text
        assert "agile-sm" in text
