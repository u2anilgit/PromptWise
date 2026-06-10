"""Tests for V3 type definitions."""

import pytest
from promptwise_v3.types import (
    RouteResult, RewriteResult, OptimizeResult, CachePlanResult,
    BatchResult, SummarizeResult, CompactResult, SecurityResult,
    CompressionResult, RoleProfile, RoleDetectionResult, OrchestratorResult,
    MemoryEntry, QualityResult, ValidationResult, BudgetStatus,
    ROISnapshot, PluginEvent, ToolRequest, ToolResponse, Skill,
)


def test_route_result():
    r = RouteResult(recommended_model="opus", reason="high stakes", intent_detected="code",
                    stakes_detected="high", estimated_input_cost_usd=0.01, context_window_pct=5.0)
    assert r.recommended_model == "opus"
    assert r.intent_detected == "code"
    assert r.stakes_detected == "high"


def test_route_result_alternatives():
    r = RouteResult(recommended_model="sonnet", reason="test", intent_detected="general",
                    stakes_detected="medium", estimated_input_cost_usd=0.0, context_window_pct=1.0,
                    alternatives=["haiku", "opus"])
    assert len(r.alternatives) == 2


def test_rewrite_result():
    r = RewriteResult(rewritten="hello there", saving_pct=0.0, raw_tokens=2)
    assert r.rewritten == "hello there"


def test_optimize_result():
    r = OptimizeResult(optimized="short", saving_pct=50.0, raw_tokens=100)
    assert r.optimized == "short"
    assert r.saving_pct == 50.0


def test_cache_plan_result():
    r = CachePlanResult(breakpoints=[{"idx": 0}], savings_pct=15.0)
    assert len(r.breakpoints) == 1


def test_batch_result():
    r = BatchResult(batched_prompt="task 1", saving_pct=10.0, individual_tokens=5)
    assert r.saving_pct == 10.0


def test_compact_result():
    r = CompactResult(status="ok", original_tokens=100, compacted_tokens=40, turns_kept=5, turns_dropped=3, saving_pct=60.0)
    assert r.saving_pct == 60.0


def test_security_result():
    r = SecurityResult(passed=True, checks_run=["secrets"], violations=[], risk_score=0.0)
    assert r.passed is True


def test_compression_result():
    r = CompressionResult(original="long text here", compressed="short", tokens_saved=2, saving_pct=50.0, rules_applied=["filler"])
    assert r.saving_pct == 50.0


def test_role_profile():
    r = RoleProfile(role="developer", confidence=0.9, keywords_matched=["code"], recommended_model_tier="balanced", context_hint="code")
    assert r.role == "developer"


def test_role_detection_result():
    r = RoleDetectionResult(primary_role="developer", confidence=0.95, secondary_roles=[], keywords_matched=["code"], rationale="Strong match")
    assert r.primary_role == "developer"


def test_orchestrator_result():
    r = OrchestratorResult(task_id="t1", status="done", steps_total=3, steps_done=3, strategy_used="linear", output="ok", cost_usd=0.01, duration_ms=100)
    assert r.status == "done"
    assert r.steps_done == 3


def test_memory_entry():
    r = MemoryEntry(entry_id="e1", session_id="s1", ts="now", tool="router", summary="test")
    assert r.session_id == "s1"


def test_quality_result():
    r = QualityResult(score=0.95, passed=True, signals=[])
    assert r.passed is True


def test_validation_result():
    r = ValidationResult(valid=True, issues=[], confidence=0.9, checks_run=["syntax"])
    assert r.valid is True


def test_budget_status():
    r = BudgetStatus(used_usd=5.0, limit_usd=10.0, pct_used=50.0, daily_burn_usd=1.0, projected_monthly_usd=30.0, alert_level="ok")
    assert r.alert_level == "ok"


def test_roi_snapshot():
    r = ROISnapshot(session_id="s1", total_cost_usd=1.0, tokens_saved=1000, estimated_time_saved_min=5.0, roi_ratio=10.0, productivity_score=0.8)
    assert r.roi_ratio == 10.0


def test_roi_snapshot_validation():
    with pytest.raises(ValueError):
        ROISnapshot(session_id="s1", total_cost_usd=-1.0, tokens_saved=0, estimated_time_saved_min=0, roi_ratio=0, productivity_score=0.0)


def test_plugin_event():
    r = PluginEvent(plugin_name="budget", trigger="overspend", action_taken="alert")
    assert r.plugin_name == "budget"


def test_tool_request():
    r = ToolRequest(tool_name="route", params={"text": "hello"}, session_id="s1")
    assert r.tool_name == "route"


def test_tool_response():
    r = ToolResponse(result={"model": "sonnet"}, execution_ms=50)
    assert r.success is True


def test_skill():
    r = Skill(name="test", description="desc", triggers=["code"], depends_on=[], output_schema=None, roles=[], model_tier="auto", system_prompt="do stuff", raw_content="---\nname: test\n---\ndo stuff")
    assert r.name == "test"
