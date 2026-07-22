"""handlers -- per-category MCP tool handler modules.

Each submodule registers its tools into promptwise.core.tool_registry's
_registry via the @tool decorator at import time. server.py imports every
submodule listed in its _HANDLER_MODULES, in isolation (one category
failing to import does not affect the others) -- see
docs/superpowers/specs/2026-07-22-handlers-package-split-design.md.
"""
