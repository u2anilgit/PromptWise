<#
PromptWise -- one-line installer (Windows / PowerShell).
Installs the package and registers the MCP server. No network access beyond
pip's own package index; nothing here phones out on your behalf.
#>
param(
    [switch]$Dev
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

if ($Dev) {
    & $PythonBin -m pip install -e ".[dev]"
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
