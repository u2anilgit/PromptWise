"""Batch multiple tasks into single prompt."""

from promptwise.config import AppConfig
from promptwise.rewriter import Rewriter
from promptwise.tokenizer import count_tokens
from promptwise.types import BatchResult


class Batcher:
    """Batch multiple tasks into one prompt."""

    CONNECTIVES = ["Also,", "Then,", "Additionally,", "Next,", "Finally,"]

    def __init__(self, config: AppConfig):
        """Initialize batcher with config.

        Args:
            config: AppConfig
        """
        self.config = config
        self.rewriter = Rewriter(config)

    def batch(
        self,
        tasks: list[str],
        role: str = "general",
        model: str = "claude-sonnet-4-6",
    ) -> BatchResult:
        """Batch multiple tasks into single prompt.

        Args:
            tasks: List of task strings (2-5 tasks)
            role: Role for prefix
            model: Model for token counting

        Returns:
            BatchResult with batched prompt and savings
        """
        if len(tasks) < 2 or len(tasks) > 5:
            raise ValueError("tasks must be 2-5 items")

        if any(not t.strip() for t in tasks):
            raise ValueError("no empty tasks allowed")

        individual_tokens = sum(count_tokens(t, model).value for t in tasks)

        batched_lines = []
        for i, task in enumerate(tasks):
            connector = self.CONNECTIVES[i] if i > 0 else ""
            batched_lines.append(f"{connector} {task}".strip())

        batched_text = " ".join(batched_lines)

        role_obj = self.config.roles.roles.get(role)
        if not role_obj:
            role_obj = self.config.roles.roles.get("general")

        prefix = role_obj.prefix
        if prefix:
            batched_text = f"{prefix}{batched_text}"

        batched_tokens = count_tokens(batched_text, model).value

        reload_reduction_tokens = (len(tasks) - 1) * 500

        total_without_batch = individual_tokens + reload_reduction_tokens
        saving_pct = (
            (total_without_batch - batched_tokens) / total_without_batch * 100
            if total_without_batch > 0
            else 0.0
        )

        return BatchResult(
            batched_prompt=batched_text,
            tasks=tasks,
            individual_tokens=individual_tokens,
            batched_tokens=batched_tokens,
            reload_reduction_tokens=reload_reduction_tokens,
            saving_pct=saving_pct,
            model_used_for_count=model,
        )
