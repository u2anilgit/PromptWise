"""PromptWise: Token-aware prompt routing and cost optimization for Claude Code."""

import sys

if sys.version_info < (3, 10):
    raise RuntimeError(
        f"PromptWise requires Python 3.10+. "
        f"You are running Python {sys.version_info.major}.{sys.version_info.minor}. "
        f"Upgrade: https://www.python.org/downloads/"
    )

__version__ = "1.1.0"
