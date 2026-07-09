# PromptWise statusline badge (Windows) — prints "budget: N% used | last scan: <ago>".
# Works whether or not the package is pip-installed: sets PYTHONPATH relative
# to this script (same convention hooks/*.py already use) and invokes the
# core module directly. Fails silently rather than wedging a shell prompt if
# the plugin isn't bootstrapped yet.
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$env:PYTHONPATH = "$Root\src"
try {
    python -m promptwise.core.statusline 2>$null
} catch {
    # silent — a statusline that errors is worse than one that's briefly blank
}
