import re

_PLUGIN_RULES: list[tuple[str, list[str]]] = [
    ("monitoring",        ["cost", "burn", "budget", "overspend", "track"]),
    ("codereview_bridge", [r"\.py\b", r"\.js\b", r"\.go\b", "code review", "review.*file"]),
    ("playwright_bridge", [r"\.jsx\b", r"\.tsx\b", r"\.html\b", "visual test", "react component",
                           "frontend"]),
]

_ALL_MODELS = [
    "claude-opus-4-7",
    "claude-sonnet-4-6",
    "claude-haiku-4-5-20251001",
]


class RouterV2:
    def route_for_plugin(self, text: str) -> str | None:
        text_lower = text.lower()
        for plugin_name, patterns in _PLUGIN_RULES:
            for pat in patterns:
                if re.search(pat, text_lower):
                    return plugin_name
        return None

    def fallback_models(self, current: str) -> list[str]:
        return [m for m in _ALL_MODELS if m != current]
