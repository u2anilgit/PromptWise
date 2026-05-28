from pathlib import Path
import pytest
from promptwise_v2.config_v2 import load_config_v2, AppConfigV2
from promptwise_v2.types_v2 import ROISnapshot

CONFIG_DIR = Path(__file__).parents[2] / "config"

def test_load_config_v2():
    cfg = load_config_v2(CONFIG_DIR)
    assert cfg.version == "2.0"
    assert cfg.core.max_context_tokens == 150000
    assert cfg.security.checks == ["syntax", "secrets", "destructive", "supply_chain", "permissions"]
    assert cfg.policies.budget_hard_stop_usd == 10.0
    assert cfg.memory.retention_weeks == 4
    assert cfg.orchestration.max_retries == 2
    assert "monitoring" in cfg.plugins.enabled

def test_config_compression_defaults():
    cfg = load_config_v2(CONFIG_DIR)
    assert cfg.compression.enabled is True
    assert cfg.compression.auto_compress_threshold_usd_per_min == 0.01

def test_load_config_missing_file():
    with pytest.raises(FileNotFoundError):
        load_config_v2(Path("/nonexistent/dir"))

def test_roi_snapshot_negative_cost_raises():
    with pytest.raises(ValueError):
        ROISnapshot(session_id="s", total_cost_usd=-1.0, tokens_saved=0,
                    estimated_time_saved_min=0, roi_ratio=0, productivity_score=0.5)

def test_roi_snapshot_invalid_productivity_score_raises():
    with pytest.raises(ValueError):
        ROISnapshot(session_id="s", total_cost_usd=0, tokens_saved=0,
                    estimated_time_saved_min=0, roi_ratio=0, productivity_score=1.5)
