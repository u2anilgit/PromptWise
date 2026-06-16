from promptwise.config import AppConfig
from promptwise.types import OptimizeResult


class Optimizer:
    def __init__(self, config: AppConfig | None = None):
        self.config = config or AppConfig()

    def optimize(self, context: str, token_budget: int = 2000, model: str = "claude-sonnet-4-6") -> OptimizeResult:
        if not context:
            return OptimizeResult(optimized="", saving_pct=0.0, raw_tokens=0)

        raw_tokens = len(context.split())
        if raw_tokens <= token_budget:
            return OptimizeResult(optimized=context, saving_pct=0.0, raw_tokens=raw_tokens)

        sentences = [s.strip() for s in context.replace("\n", " ").split(". ") if s.strip()]
        sentences.sort(key=len, reverse=True)

        optimized = []
        kept_tokens = 0
        chunks_dropped = 0

        for sent in sentences:
            tokens = len(sent.split())
            if kept_tokens + tokens <= token_budget:
                optimized.append(sent)
                kept_tokens += tokens
            else:
                room = token_budget - kept_tokens
                if room > 5:
                    words = sent.split()
                    optimized.append(" ".join(words[:room]))
                    kept_tokens += room
                chunks_dropped += 1

        result = ". ".join(optimized) + "."
        result = result.replace("..", ".")
        saving_pct = round((raw_tokens - kept_tokens) / raw_tokens * 100, 1)

        return OptimizeResult(optimized=result, saving_pct=saving_pct, chunks_dropped=chunks_dropped, raw_tokens=raw_tokens)
