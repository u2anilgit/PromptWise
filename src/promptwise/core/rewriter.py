import re

from promptwise.config import AppConfig
from promptwise.types import RewriteResult

_FILLER = re.compile(
    r'\b(just|really|basically|actually|simply|literally|very|quite|rather|'
    r'somewhat|kind of|sort of|I was wondering if|you could|please note that)\b\s*', re.I
)

_ROLE_PREFIXES = {
    "developer": "You are a senior software engineer. Provide concise, well-structured code with explanations.",
    "analyst": "You are a data analyst. Provide data-driven insights with clear methodology.",
    "manager": "You are an experienced engineering manager. Focus on clarity, action items, and strategic thinking.",
    "security": "You are a security engineer. Prioritize secure patterns and flag risks.",
    "IT": "You are a DevOps/Infrastructure engineer. Focus on reliability, scalability, and automation.",
    "designer": "You are a UI/UX designer. Focus on user experience, accessibility, and visual design.",
    "writer": "You are a professional writer. Maintain clear narrative flow and consistent tone.",
    "researcher": "You are a research scientist. Be thorough, cite sources, and note limitations.",
    "pm": "You are a product manager. Focus on requirements, stakeholders, and success metrics.",
    "general": "",
}


class Rewriter:
    def __init__(self, config: AppConfig | None = None):
        self.config = config or AppConfig()

    def rewrite(self, text: str, role: str = "general", model: str = "claude-sonnet-4-6") -> RewriteResult:
        if not text:
            return RewriteResult(rewritten="", saving_pct=0.0, raw_tokens=0)

        original_tokens = len(text.split())
        rewritten = _FILLER.sub("", text).strip()
        rewritten = re.sub(r"\s+", " ", rewritten)

        prefix = _ROLE_PREFIXES.get(role, "")
        if role != "general" and prefix:
            rewritten = f"{prefix}\n\n{rewritten}"

        new_tokens = len(rewritten.split())
        saving_pct = round((original_tokens - new_tokens) / original_tokens * 100, 1) if original_tokens else 0.0

        warning = None
        if saving_pct > 50:
            warning = "Large rewrite detected — verify intent preserved"
        elif original_tokens > 50000:
            warning = "Large prompt — consider using optimize_context for better compression"

        return RewriteResult(rewritten=rewritten, saving_pct=saving_pct, warning=warning, raw_tokens=original_tokens)
