from promptwise_v3.config import AppConfigV3
from promptwise_v3.types import SummarizeResult

_RESET_PROMPT = (
    "Continue the conversation. The assistant has summarized the preceding discussion above. "
    "If the conversation's context is insufficient, ask clarifying questions."
)


class Summarizer:
    def __init__(self, config: AppConfigV3 | None = None):
        self.config = config or AppConfigV3()

    def summarize(self, conversation: str, max_tokens: int = 500, model: str = "claude-sonnet-4-6") -> SummarizeResult:
        if not conversation:
            return SummarizeResult(summary="", saving_pct=100.0, original_tokens=0, summary_tokens=0)

        original_tokens = len(conversation.split())
        sentences = [s.strip() for s in conversation.replace("\n", " ").split(". ") if s.strip()]

        summary_sentences = sentences[:max(3, len(sentences) // 3)]
        summary = ". ".join(summary_sentences) + "."
        summary_tokens = len(summary.split())
        saving_pct = round((original_tokens - summary_tokens) / original_tokens * 100, 1)

        return SummarizeResult(
            summary=summary,
            reset_prompt=_RESET_PROMPT,
            saving_pct=saving_pct,
            original_tokens=original_tokens,
            summary_tokens=summary_tokens,
        )
