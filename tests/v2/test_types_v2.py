from promptwise_v2.types_v2 import (
    SecurityResult, ContextFile, OrchestratorResult,
    CompressionResult, MemoryEntry, RoleProfile,
    PluginEvent, BudgetStatus, ValidationResult, ROISnapshot,
)

def test_security_result_fields():
    r = SecurityResult(passed=True, checks_run=["syntax"], violations=[], risk_score=0.0)
    assert r.passed is True
    assert r.risk_score == 0.0

def test_orchestrator_result_fields():
    r = OrchestratorResult(
        task_id="t1", status="completed", steps_total=3,
        steps_done=3, strategy_used="fallback", output="done",
        cost_usd=0.001, duration_ms=120,
    )
    assert r.status == "completed"

def test_compression_result_fields():
    r = CompressionResult(original="hello world", compressed="hello world",
                          tokens_saved=0, saving_pct=0.0, rules_applied=[])
    assert r.saving_pct == 0.0

def test_role_profile_fields():
    r = RoleProfile(role="developer", confidence=0.85, keywords_matched=["def", "class"],
                    recommended_model_tier="balanced", context_hint="code-heavy")
    assert r.role == "developer"
    assert r.confidence == 0.85

def test_budget_status_fields():
    b = BudgetStatus(used_usd=5.0, limit_usd=10.0, pct_used=50.0,
                     daily_burn_usd=1.0, projected_monthly_usd=30.0,
                     alert_level="ok")
    assert b.alert_level == "ok"

def test_validation_result_fields():
    v = ValidationResult(valid=True, issues=[], confidence=1.0, checks_run=["syntax"])
    assert v.valid is True
