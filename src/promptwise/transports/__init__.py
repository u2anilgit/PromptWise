from .base import TransportAdapter, ToolRequest, ToolResponse
from .mcp import MCPAdapter
from .http import HTTPAdapter
from .cli import CLIAdapter

def create_adapter(platform: str, config: dict | None = None) -> TransportAdapter:
    if config is None:
        config = {}
    platform = platform.lower().strip()

    if platform == "mcp":
        return MCPAdapter()
    elif platform == "codex":
        from .http import HTTPAdapter
        api_key = config.get("codex_api_key") or __import__("os").environ.get("CODEX_API_KEY")
        if not api_key:
            raise RuntimeError("Codex API key required. Set CODEX_API_KEY env var.")
        return HTTPAdapter(provider="codex", base_url="https://api.openai.com/v1", api_key=api_key, timeout_s=config.get("timeout_s", 30))
    elif platform == "gemini":
        from .http import HTTPAdapter
        api_key = config.get("gemini_api_key") or __import__("os").environ.get("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("Gemini API key required. Set GEMINI_API_KEY env var.")
        return HTTPAdapter(provider="gemini", base_url="https://generativelanguage.googleapis.com/v1beta/models", api_key=api_key, timeout_s=config.get("timeout_s", 30))
    elif platform == "antigravity":
        from .cli import CLIAdapter
        endpoint = config.get("antigravity_endpoint") or __import__("os").environ.get("ANTIGRAVITY_ENDPOINT")
        if not endpoint:
            raise RuntimeError("Antigravity endpoint required. Set ANTIGRAVITY_ENDPOINT env var.")
        return CLIAdapter(endpoint=endpoint, timeout_s=config.get("timeout_s", 30))
    else:
        raise ValueError(f"Unknown platform: {platform}. Supported: mcp, codex, gemini, antigravity")

def get_default_platform() -> str:
    return __import__("os").environ.get("PROMPTWISE_PLATFORM", "mcp").lower()

def create_default_adapter() -> TransportAdapter:
    return create_adapter(get_default_platform())

__all__ = ["TransportAdapter", "ToolRequest", "ToolResponse", "MCPAdapter", "HTTPAdapter", "CLIAdapter",
           "create_adapter", "get_default_platform", "create_default_adapter"]
