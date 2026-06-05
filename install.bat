@echo off
setlocal

echo PromptWise v1.0.0 - Install
echo ============================

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found. Install Python 3.10+ and add to PATH.
    exit /b 1
)

REM Configure pip for corporate proxy (self-signed SSL certs)
echo.
echo [1/3] Configuring pip trusted hosts...
python -c "from install import configure_pip_trusted_hosts; configure_pip_trusted_hosts()"

REM Install package
echo.
echo [2/3] Installing package...
python -m pip install -e . --quiet
if errorlevel 1 (
    echo ERROR: pip install failed.
    exit /b 1
)
echo     OK

REM Register MCP server
echo.
echo [3/3] Registering MCP server...
set PLUGIN_PATH=%~dp0plugin.json

chubb-claude mcp add "%PLUGIN_PATH%" >nul 2>&1
if not errorlevel 1 (
    echo     OK - registered via chubb-claude mcp add
    goto verify
)

claude mcp add "%PLUGIN_PATH%" >nul 2>&1
if not errorlevel 1 (
    echo     OK - registered via claude mcp add
    goto verify
)

REM Fallback: patch settings.json directly
echo     claude CLI not found - patching settings.json...
python -c "from install import register_via_settings_json; import sys; sys.exit(0 if register_via_settings_json() else 1)"
if errorlevel 1 (
    echo ERROR: registration failed. Check ~/.claude/settings.json manually.
    exit /b 1
)

:verify
echo.
echo Verifying install...
python -c "from promptwise.server import list_tools; import asyncio; tools=asyncio.run(list_tools()); print(f'    OK - {len(tools)} tools loaded')"
if errorlevel 1 (
    echo ERROR: server module import failed. Check src/promptwise/ and dependencies.
    exit /b 1
)

echo.
echo Done. Restart Claude Code then run /mcp to confirm PromptWise tools appear.
echo.
echo Available tools:
echo   route_request         - pick right model tier
echo   compare_providers     - cross-provider cost comparison
echo   rewrite_prompt        - strip filler, apply role framing
echo   optimize_context      - compress doc to token budget
echo   plan_cache            - design cache breakpoints
echo   batch_prompts         - merge 2-5 tasks into one prompt
echo   summarize_thread      - compress conversation for handoff
echo   get_session_stats     - cost and savings accounting
echo   reload_config         - reload YAML configs without restart
echo   ping_session          - record user activity
echo   check_session_timeout - idle timeout status
echo   clear_history         - delete records older than N days
echo   export_stats          - export stats to JSON or CSV
echo   auto_compact          - automatic context compaction

endlocal
