"""
Adapter factory for multi-platform PromptWise.

Instantiates the correct TransportAdapter based on platform.
"""

import os
from typing import Dict, Any, Optional

from .transports import TransportAdapter
from .transports.mcp_adapter import MCPAdapter
from .transports.http_adapter import HTTPAdapter
from .transports.cli_adapter import CLIAdapter
from .transports.claude_api_adapter import ClaudeAPIAdapter
from .transports.collaboration_adapter import CollaborationAdapter


def create_adapter(platform: str, config: Optional[Dict[str, Any]] = None) -> TransportAdapter:
    """
    Factory function to create the appropriate adapter.

    Args:
        platform: Platform name (mcp, codex, gemini, antigravity, claude-api, collaboration, claude-chat)
        config: Optional configuration dict with:
            - codex_api_key: API key for Codex
            - gemini_api_key: API key for Gemini
            - anthropic_api_key: API key for Claude API
            - team_id: Team ID for collaboration
            - workspace_id: Workspace ID for collaboration
            - antigravity_endpoint: Endpoint for Antigravity
            - timeout_s: Request timeout (default 30)

    Returns:
        TransportAdapter instance

    Raises:
        ValueError: If platform is unknown
        RuntimeError: If required config is missing
    """
    if config is None:
        config = {}

    platform = platform.lower().strip()

    if platform == "mcp":
        return _create_mcp_adapter()

    elif platform == "codex":
        return _create_codex_adapter(config)

    elif platform == "gemini":
        return _create_gemini_adapter(config)

    elif platform == "claude-api" or platform == "claude-chat":
        return _create_claude_api_adapter(config)

    elif platform == "collaboration":
        return _create_collaboration_adapter(config)

    elif platform == "antigravity":
        return _create_antigravity_adapter(config)

    else:
        raise ValueError(
            f"Unknown platform: {platform}. "
            f"Supported platforms: mcp, codex, gemini, antigravity, claude-api, claude-chat, collaboration"
        )


def _create_mcp_adapter() -> MCPAdapter:
    """Create MCP adapter for Claude Code."""
    return MCPAdapter()


def _create_codex_adapter(config: Dict[str, Any]) -> HTTPAdapter:
    """
    Create HTTP adapter for Codex 5.5.

    Args:
        config: Configuration dict

    Returns:
        HTTPAdapter configured for Codex

    Raises:
        RuntimeError: If API key is missing
    """
    api_key = config.get("codex_api_key") or os.getenv("CODEX_API_KEY")

    if not api_key:
        raise RuntimeError(
            "Codex API key required. "
            "Set CODEX_API_KEY env var or pass codex_api_key in config"
        )

    timeout_s = config.get("timeout_s", 30)

    adapter = HTTPAdapter(
        provider="codex",
        base_url="https://api.openai.com/v1",
        api_key=api_key,
        timeout_s=timeout_s
    )

    return adapter


def _create_gemini_adapter(config: Dict[str, Any]) -> HTTPAdapter:
    """
    Create HTTP adapter for Google Gemini.

    Args:
        config: Configuration dict

    Returns:
        HTTPAdapter configured for Gemini

    Raises:
        RuntimeError: If API key is missing
    """
    api_key = config.get("gemini_api_key") or os.getenv("GEMINI_API_KEY")

    if not api_key:
        raise RuntimeError(
            "Gemini API key required. "
            "Set GEMINI_API_KEY env var or pass gemini_api_key in config"
        )

    timeout_s = config.get("timeout_s", 30)

    adapter = HTTPAdapter(
        provider="gemini",
        base_url="https://generativelanguage.googleapis.com/v1beta/models",
        api_key=api_key,
        timeout_s=timeout_s
    )

    return adapter


def _create_claude_api_adapter(config: Dict[str, Any]) -> ClaudeAPIAdapter:
    """
    Create Claude API adapter for direct API integration.

    Args:
        config: Configuration dict with:
            - anthropic_api_key: API key for Claude API
            - model: Model name (default: claude-opus-4-7)
            - timeout_s: Request timeout (default 30)

    Returns:
        ClaudeAPIAdapter instance

    Raises:
        RuntimeError: If API key is missing
    """
    api_key = config.get("anthropic_api_key") or os.getenv("ANTHROPIC_API_KEY")

    if not api_key:
        raise RuntimeError(
            "Anthropic API key required. "
            "Set ANTHROPIC_API_KEY env var or pass anthropic_api_key in config"
        )

    model = config.get("model", "claude-opus-4-7")
    timeout_s = config.get("timeout_s", 30)

    return ClaudeAPIAdapter(api_key=api_key, timeout_s=timeout_s, model=model)


def _create_collaboration_adapter(config: Dict[str, Any]) -> CollaborationAdapter:
    """
    Create Collaboration adapter for team/workspace features.

    Args:
        config: Configuration dict with:
            - anthropic_api_key: API key for Claude API
            - team_id: Team ID for collaboration
            - workspace_id: Workspace ID for collaboration
            - timeout_s: Request timeout (default 30)

    Returns:
        CollaborationAdapter instance

    Raises:
        RuntimeError: If required keys are missing
    """
    api_key = config.get("anthropic_api_key") or os.getenv("ANTHROPIC_API_KEY")
    team_id = config.get("team_id") or os.getenv("ANTHROPIC_TEAM_ID", "")
    workspace_id = config.get("workspace_id") or os.getenv("ANTHROPIC_WORKSPACE_ID", "")

    if not api_key:
        raise RuntimeError(
            "Anthropic API key required. "
            "Set ANTHROPIC_API_KEY env var or pass anthropic_api_key in config"
        )

    timeout_s = config.get("timeout_s", 30)

    return CollaborationAdapter(
        api_key=api_key,
        team_id=team_id,
        workspace_id=workspace_id,
        timeout_s=timeout_s
    )


def _create_antigravity_adapter(config: Dict[str, Any]) -> CLIAdapter:
    """
    Create CLI adapter for Antigravity.

    Args:
        config: Configuration dict with:
            - antigravity_endpoint: Endpoint (e.g., "localhost:5000" or "socket:/tmp/antigravity.sock")

    Returns:
        CLIAdapter configured for Antigravity

    Raises:
        RuntimeError: If endpoint is missing
    """
    endpoint = config.get("antigravity_endpoint") or os.getenv("ANTIGRAVITY_ENDPOINT")

    if not endpoint:
        raise RuntimeError(
            "Antigravity endpoint required. "
            "Set ANTIGRAVITY_ENDPOINT env var or pass antigravity_endpoint in config"
        )

    timeout_s = config.get("timeout_s", 30)

    # Convert shorthand endpoint formats to full protocol:target format
    if endpoint.startswith("/"):
        # Unix socket path
        endpoint = f"socket:{endpoint}"
    elif ":" not in endpoint or endpoint.count(":") == 1 and not endpoint.startswith("socket:"):
        # TCP endpoint (host:port or just port)
        if ":" in endpoint:
            host, port = endpoint.split(":")
        else:
            host, port = "localhost", endpoint
        endpoint = f"socket:{host}:{port}"

    adapter = CLIAdapter(endpoint=endpoint, timeout_s=timeout_s)

    return adapter


def get_default_platform() -> str:
    """
    Get default platform from environment or config.

    Returns:
        Platform name (default: "mcp")
    """
    return os.getenv("PROMPTWISE_PLATFORM", "mcp").lower()


def create_default_adapter() -> TransportAdapter:
    """
    Create adapter using default platform and env config.

    Returns:
        TransportAdapter instance
    """
    platform = get_default_platform()
    return create_adapter(platform)


__all__ = [
    "create_adapter",
    "get_default_platform",
    "create_default_adapter",
]
