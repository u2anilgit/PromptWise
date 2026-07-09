"""Golden-file render tests: freeze each agent's output format so drift is
caught in CI. Regenerate with:  python tests/test_emitter_goldens.py --update
"""
from pathlib import Path

import pytest

from promptwise.core.config_emitter import ConfigEmitter, GovernanceBundle

GOLD_DIR = Path(__file__).parent / "goldens"

# The single fixed bundle every golden is rendered from.
GOLDEN_BUNDLE = GovernanceBundle(
    project="acme-pay",
    method="PromptWise governed agile method",
    policy_summary=["Budget cap $5/day", "Tiers: haiku/sonnet only"],
    packs=["banking", "agile-sm"],
    rules=["No secrets in code"],
)

TARGETS = ["claude", "agents", "cursor", "copilot", "gemini", "cline", "windsurf"]


def _golden_path(target: str) -> Path:
    return GOLD_DIR / f"{target}.golden"


@pytest.mark.parametrize("target", TARGETS)
def test_render_matches_golden(target):
    gp = _golden_path(target)
    assert gp.is_file(), f"missing golden {gp}; run `python tests/test_emitter_goldens.py --update`"
    expected = gp.read_text(encoding="utf-8")
    actual = ConfigEmitter().render(GOLDEN_BUNDLE, target)
    assert actual == expected, f"{target} render drifted from golden"


def _update():
    GOLD_DIR.mkdir(parents=True, exist_ok=True)
    e = ConfigEmitter()
    for t in TARGETS:
        _golden_path(t).write_text(e.render(GOLDEN_BUNDLE, t), encoding="utf-8")
    print(f"wrote {len(TARGETS)} goldens to {GOLD_DIR}")


if __name__ == "__main__":
    import sys
    if "--update" in sys.argv:
        _update()
    else:
        print("pass --update to regenerate goldens")
