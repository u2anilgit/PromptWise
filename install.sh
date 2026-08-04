#!/usr/bin/env bash
# PromptWise -- one-line installer (POSIX: bash/zsh). Installs the package
# and registers the MCP server. This never pipes a remote script into a
# shell (no curl|bash / wget|sh) -- clone or download the repo first, then
# run this file locally. No network access beyond pip's own package index.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

DEV=0
EMBEDDINGS=0
for arg in "$@"; do
  case "$arg" in
    --dev) DEV=1 ;;
    --embeddings) EMBEDDINGS=1 ;;
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

# Extras group selection -- combine [dev] and [embeddings] if both flags
# are passed. Base install (no flags) is unaffected either way: this
# only ever adds to the pip install target, never changes the default.
EXTRAS=""
if [ "$DEV" = "1" ] && [ "$EMBEDDINGS" = "1" ]; then
  EXTRAS="[dev,embeddings]"
elif [ "$DEV" = "1" ]; then
  EXTRAS="[dev]"
elif [ "$EMBEDDINGS" = "1" ]; then
  EXTRAS="[embeddings]"
fi

if [ "$EMBEDDINGS" = "1" ]; then
  echo "PromptWise install: embeddings mode. Installing ~300MB of local ML dependencies (fastembed/onnxruntime) for semantic cache + memory search. First real use downloads a small model (~100MB, one time, needs network) then runs fully offline -- nothing is sent to a third party at runtime. To go back to lightweight mode: pip uninstall fastembed onnxruntime."
else
  echo "PromptWise install: lightweight mode (no embeddings). Local semantic cache + smarter memory search are available as an optional extra -- re-run with --embeddings to enable. Adds ~300MB, local and offline after first use. Skipping this changes nothing above."
fi

if [ -n "$EXTRAS" ]; then
  "$PYTHON_BIN" -m pip install -e ".$EXTRAS"
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
