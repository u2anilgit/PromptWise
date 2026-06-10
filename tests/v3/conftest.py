"""Shared fixtures for V3 test suite."""

import pytest
from promptwise_v3.config import AppConfigV3, load_config_v3
from promptwise_v3.core.router import Router
from promptwise_v3.core.rewriter import Rewriter
from promptwise_v3.core.optimizer import Optimizer
from promptwise_v3.core.compression import CompressionEngine
from promptwise_v3.core.cache_planner import CachePlanner
from promptwise_v3.core.batcher import Batcher
from promptwise_v3.core.summarizer import Summarizer
from promptwise_v3.core.role_detector import RoleDetector
from promptwise_v3.core.quality import QualityGuard
from promptwise_v3.core.orchestrator import Orchestrator
from promptwise_v3.core.skill_loader import SkillLoader
from promptwise_v3.core.skill_validator import SkillValidator
from promptwise_v3.core.sbom import SBOMGenerator
from promptwise_v3.core.license_checker import LicenseChecker
from promptwise_v3.core.codex_validator import CodexOutputValidator
from promptwise_v3.plugins.budget import BudgetGuardian
from promptwise_v3.plugins.code_validator import CodeValidator
from promptwise_v3.plugins.monitoring import CostMonitor
from promptwise_v3.plugins.roi import ROITracker
from promptwise_v3.security.scanner import SecurityScanner
from promptwise_v3.security.compliance import ComplianceEngine


@pytest.fixture()
def cfg() -> AppConfigV3:
    return AppConfigV3()


@pytest.fixture()
def router(cfg) -> Router:
    return Router(cfg)


@pytest.fixture()
def rewriter() -> Rewriter:
    return Rewriter()


@pytest.fixture()
def role_detector() -> RoleDetector:
    return RoleDetector()


@pytest.fixture()
def quality() -> QualityGuard:
    return QualityGuard(confidence_threshold=0.6)


@pytest.fixture()
def compressor() -> CompressionEngine:
    return CompressionEngine()


@pytest.fixture()
def cache_planner() -> CachePlanner:
    return CachePlanner()


@pytest.fixture()
def batcher() -> Batcher:
    return Batcher()


@pytest.fixture()
def summarizer() -> Summarizer:
    return Summarizer()


@pytest.fixture()
def guardian() -> BudgetGuardian:
    return BudgetGuardian(limit_usd=10.0, team_budget_usd=100.0)


@pytest.fixture()
def roi_tracker() -> ROITracker:
    return ROITracker(dev_hourly_rate_usd=100.0)


@pytest.fixture()
def code_validator() -> CodeValidator:
    return CodeValidator()


@pytest.fixture()
def cost_monitor() -> CostMonitor:
    return CostMonitor()


@pytest.fixture()
def scanner() -> SecurityScanner:
    return SecurityScanner()


@pytest.fixture()
def compliance() -> ComplianceEngine:
    return ComplianceEngine()


@pytest.fixture()
def sbom_gen() -> SBOMGenerator:
    return SBOMGenerator()


@pytest.fixture()
def license_checker() -> LicenseChecker:
    return LicenseChecker()


@pytest.fixture()
def codex_validator() -> CodexOutputValidator:
    return CodexOutputValidator()


@pytest.fixture()
def optimizer() -> Optimizer:
    return Optimizer()


@pytest.fixture()
def skill_validator() -> SkillValidator:
    return SkillValidator()
