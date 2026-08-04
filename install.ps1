<#
PromptWise -- one-line installer (Windows / PowerShell).
Installs the package and registers the MCP server. No network access beyond
pip's own package index; nothing here phones out on your behalf.
#>
param(
    [switch]$Dev,
    [switch]$Embeddings
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

$PythonBin = $env:PROMPTWISE_PYTHON
if (-not $PythonBin) {
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if (-not $cmd) { $cmd = Get-Command python3 -ErrorAction SilentlyContinue }
    if (-not $cmd) {
        Write-Error "PromptWise install: python (>=3.10) not found on PATH."
        exit 1
    }
    $PythonBin = $cmd.Source
}

Write-Host "PromptWise install: using $(& $PythonBin --version)"

if ($Embeddings) {
    Write-Host "PromptWise install: embeddings mode. Installing ~300MB of local ML dependencies (fastembed/onnxruntime) for semantic cache + memory search. First real use downloads a small model (~100MB, one time, needs network) then runs fully offline -- nothing is sent to a third party at runtime. To go back to lightweight mode: pip uninstall fastembed onnxruntime."
} else {
    Write-Host "PromptWise install: lightweight mode (no embeddings). Local semantic cache + smarter memory search are available as an optional extra -- re-run with -Embeddings to enable. Adds ~300MB, local and offline after first use. Skipping this changes nothing above."
}

# Extras group selection -- combine [dev] and [embeddings] if both switches
# are passed. Base install (no switches) is unaffected either way.
if ($Dev -and $Embeddings) {
    & $PythonBin -m pip install -e ".[dev,embeddings]"
} elseif ($Dev) {
    & $PythonBin -m pip install -e ".[dev]"
} elseif ($Embeddings) {
    & $PythonBin -m pip install -e ".[embeddings]"
} else {
    & $PythonBin -m pip install -e .
}

$claudeCmd = Get-Command claude -ErrorAction SilentlyContinue
if ($claudeCmd) {
    Write-Host "PromptWise install: Claude Code CLI detected -- registering the plugin."
    try { & claude marketplace add $Root } catch {}
    try { & claude plugin install promptwise } catch {}
    Write-Host "Restart Claude Code and run /mcp to confirm the promptwise tools are loaded."
} else {
    Write-Host "PromptWise install: no 'claude' CLI on PATH -- writing a generic .mcp.json entry instead."
    $targetPath = $env:PROMPTWISE_MCP_JSON_TARGET
    if (-not $targetPath) { $targetPath = Join-Path $Root ".mcp.json" }
    & $PythonBin -m promptwise.core.installer_support --mcp-json $targetPath --project-dir $Root
}

Write-Host ""
Write-Host "Verify:"
Write-Host "  `$env:PYTHONPATH = '$Root\src'; & '$PythonBin' -c `"import promptwise.server as s; print(len(s._TOOL_DEFS), 'tools')`""
