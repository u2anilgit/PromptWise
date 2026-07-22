"""PromptWise — Unified token-aware prompt routing and cost optimization."""

import sys

if sys.version_info < (3, 10):
    raise RuntimeError(f"PromptWise requires Python 3.10+ (running {sys.version_info.major}.{sys.version_info.minor})")

__version__ = "1.3.0"
