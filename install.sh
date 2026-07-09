#!/usr/bin/env bash
# PromptWise -- one-line installer (POSIX: bash/zsh). Installs the package
# and registers the MCP server. This never pipes a remote script into a
# shell (no curl|bash / wget|sh) -- clone or download the repo first, then
# run this file locally. No network access beyond pip's own package index.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

DEV=0
for arg in "$@"; do
  case "$arg" in
    --dev) DEV=1 ;;
  esac
done

PYTHON_BIN="${PROMPTWISE_PYTHON:-}"
if [ -z "$PYTHON_BIN" ]; then
  if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN=python3
  elif command -v python >/dev/null 2>&1; then
    PYTHON_BIN=python
  else
    echo "PromptWise install: python3 (>=3.10) not found on PATH." >&2
    exit 1
  fi
fi

echo "PromptWise install: using $("$PYTHON_BIN" --version)"

if [ "$DEV" = "1" ]; then
  "$PYTHON_BIN" -m pip install -e ".[dev]"
else
  "$PYTHON_BIN" -m pip install -e .
fi

if command -v claude >/dev/null 2>&1; then
  echo "PromptWise install: Claude Code CLI detected -- registering the plugin."
  claude marketplace add "$ROOT" || true
  claude plugin install promptwise || true
  echo "Restart Claude Code and run /mcp to confirm the promptwise tools are loaded."
else
  echo "PromptWise install: no 'claude' CLI on PATH -- writing a generic .mcp.json entry instead."
  TARGET="${PROMPTWISE_MCP_JSON_TARGET:-$ROOT/.mcp.json}"
  "$PYTHON_BIN" -m promptwise.core.installer_support --mcp-json "$TARGET" --project-dir "$ROOT"
fi

echo
echo "Verify:"
echo "  PYTHONPATH=$ROOT/src $PYTHON_BIN -c \"import promptwise.server as s; print(len(s._TOOL_DEFS), 'tools')\""
