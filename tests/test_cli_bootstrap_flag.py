import subprocess
import sys


def test_bootstrap_help_lists_sync_agents_flag():
    result = subprocess.run(
        [sys.executable, "-m", "promptwise", "bootstrap", "--help"],
        capture_output=True, text=True, check=True,
    )
    assert "--sync-agents" in result.stdout


def test_bootstrap_cli_runs_with_sync_agents_flag(tmp_path):
    result = subprocess.run(
        [sys.executable, "-m", "promptwise", "bootstrap", "--sync-agents"],
        capture_output=True, text=True, cwd=str(tmp_path),
    )
    assert result.returncode == 0
    assert "Bootstrapped state at" in result.stdout
