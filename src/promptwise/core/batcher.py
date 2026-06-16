from promptwise.config import AppConfig
from promptwise.types import BatchResult

_TEMPLATE = (
    "I have multiple tasks to complete. Please address each one thoroughly:\n\n"
    "{tasks_text}\n\n"
    "Provide clear answers for each numbered task, keeping them well-organized."
)


class Batcher:
    def __init__(self, config: AppConfig | None = None):
        self.config = config or AppConfig()

    def batch(self, tasks: list[str], role: str = "general", model: str = "claude-sonnet-4-6") -> BatchResult:
        if not tasks or len(tasks) < 2:
            text = tasks[0] if tasks else ""
            return BatchResult(batched_prompt=text, saving_pct=0.0, individual_tokens=len(text.split()))

        individual_tokens = sum(len(t.split()) for t in tasks)
        tasks_text = "\n\n".join(f"{i + 1}. {t}" for i, t in enumerate(tasks))

        batched = _TEMPLATE.format(tasks_text=tasks_text) if len(tasks) > 1 else tasks_text
        batched_tokens = len(batched.split())

        individual_with_overhead = sum(len(t.split()) + 20 for t in tasks)
        saving_pct = round((individual_with_overhead - batched_tokens) / individual_with_overhead * 100, 1) if individual_with_overhead else 0.0

        return BatchResult(batched_prompt=batched, saving_pct=saving_pct, individual_tokens=individual_tokens)
