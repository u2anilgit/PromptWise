#!/usr/bin/env python3
"""Install PromptWise MCP plugin."""

import configparser
import json
import os
import subprocess
import sys
from pathlib import Path

VERSION = "1.1.0"


def configure_pip_trusted_hosts() -> None:
    """Write pip trusted-host config for corporate proxy environments.

    Corporate SSL inspection breaks pip's isolated build subprocess even when
    --trusted-host is passed on the outer call. Persistent pip.ini fixes both.
    """
    if sys.platform == "win32":
        pip_ini = Path(os.environ.get("APPDATA", Path.home())) / "pip" / "pip.ini"
    else:
        pip_ini = Path.home() / ".config" / "pip" / "pip.conf"

    trusted_hosts = ["pypi.org", "files.pythonhosted.org", "pypi.python.org"]

    config = configparser.RawConfigParser()
    if pip_ini.exists():
        config.read(pip_ini, encoding="utf-8")

    if not config.has_section("global"):
        config.add_section("global")

    existing_raw = config.get("global", "trusted-host", fallback="")
    existing = [h.strip() for h in existing_raw.splitlines() if h.strip()]
    merged = existing + [h for h in trusted_hosts if h not in existing]

    if merged == existing and pip_ini.exists():
        print("    OK - already configured")
        return

    config.set("global", "trusted-host", "\n\t".join(merged))
    pip_ini.parent.mkdir(parents=True, exist_ok=True)

    with open(pip_ini, "w", encoding="utf-8", newline="\n") as f:
        config.write(f)

    print(f"    OK - configured in {pip_ini}")


def install_package() -> bool:
    """Install promptwise package in editable mode."""
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-e", ".", "--quiet"],
        capture_output=True,
        text=True,
        cwd=Path(__file__).parent,
    )
    if result.returncode != 0:
        print(f"    ERROR: {result.stderr.strip()}")
        return False
    print("    OK")
    return True


def register_with_claude_cli() -> bool:
    """Register plugin via claude mcp add."""
    plugin_path = Path(__file__).parent / "plugin.json"
    for cmd in ["chubb-claude", "claude"]:
        try:
            result = subprocess.run(
                [cmd, "mcp", "add", str(plugin_path)],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                print(f"    OK - registered via {cmd} mcp add")
                return True
        except FileNotFoundError:
            continue
    return False


def register_via_settings_json() -> bool:
    """Fallback: patch ~/.claude/settings.json directly."""
    settings_path = Path.home() / ".claude" / "settings.json"
    plugin_path = Path(__file__).parent / "plugin.json"

    if settings_path.exists():
        try:
            with open(settings_path) as f:
                settings = json.load(f)
        except json.JSONDecodeError:
            settings = {}
    else:
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        settings = {}

    if "mcpServers" not in settings:
        settings["mcpServers"] = {}

    with open(plugin_path) as f:
        plugin = json.load(f)

    if "mcpServers" in plugin:
        for name, config in plugin["mcpServers"].items():
            settings["mcpServers"][name] = config

    with open(settings_path, "w") as f:
        json.dump(settings, f, indent=2)

    print(f"    OK - registered in {settings_path}")
    return True


def verify_install() -> bool:
    """Verify server module loads and lists tools."""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from promptwise.server import list_tools; import asyncio; "
            "tools=asyncio.run(list_tools()); print(f'    OK - {len(tools)} tools loaded')",
        ],
        capture_output=False,
        text=True,
        cwd=Path(__file__).parent,
    )
    return result.returncode == 0


def main() -> None:
    print(f"PromptWise v{VERSION} - Install")
    print("=" * 30)

    print("\n[1/3] Configuring pip trusted hosts...")
    configure_pip_trusted_hosts()

    print("\n[2/3] Installing package...")
    if not install_package():
        sys.exit(1)

    print("\n[3/3] Registering MCP server...")
    if not register_with_claude_cli():
        print("    claude CLI not found - patching settings.json...")
        if not register_via_settings_json():
            print("    ERROR: registration failed. Check ~/.claude/settings.json manually.")
            sys.exit(1)

    print("\nVerifying install...")
    verify_install()

    print(
        "\nDone. Restart Claude Code then run /mcp to confirm PromptWise tools appear.\n"
        "\nAvailable tools:\n"
        "  route_request         - pick right model tier\n"
        "  compare_providers     - cross-provider cost comparison\n"
        "  rewrite_prompt        - strip filler, apply role framing\n"
        "  optimize_context      - compress doc to token budget\n"
        "  plan_cache            - design cache breakpoints\n"
        "  batch_prompts         - merge 2-5 tasks into one prompt\n"
        "  summarize_thread      - compress conversation for handoff\n"
        "  get_session_stats     - cost and savings accounting\n"
        "  reload_config         - reload YAML configs without restart\n"
        "  ping_session          - record user activity\n"
        "  check_session_timeout - idle timeout status\n"
        "  clear_history         - delete records older than N days\n"
        "  export_stats          - export stats to JSON or CSV\n"
        "  auto_compact          - automatic context compaction"
    )


if __name__ == "__main__":
    main()
