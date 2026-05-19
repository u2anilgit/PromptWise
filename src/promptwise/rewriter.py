"""Prompt rewriting with role framing and filler removal."""

import re

from promptwise.config import AppConfig
from promptwise.tokenizer import count_tokens
from promptwise.types import RewriteResult


class Rewriter:
    """Rewrite prompts with role framing and filler removal."""

    def __init__(self, config: AppConfig):
        """Initialize rewriter with config.

        Args:
            config: AppConfig with roles and pricing
        """
        self.config = config
        self.preamble_phrases = [
            p.lower() for p in config.roles.preamble_phrases
        ]
        self.filler_words = set(config.roles.filler_words)

    def rewrite(
        self, text: str, role: str = "general", model: str = "claude-sonnet-4-6"
    ) -> RewriteResult:
        """Rewrite text with role framing and filler removal.

        Args:
            text: Original prompt text
            role: Role name from roles.yaml
            model: Model for token counting

        Returns:
            RewriteResult with rewritten text and stats
        """
        original_count = count_tokens(text, model)

        working_text = text.strip()

        for preamble in self.preamble_phrases:
            if working_text.lower().startswith(preamble):
                working_text = working_text[len(preamble) :].strip()
                break

        working_text = self._remove_filler_words(working_text)

        role_obj = self.config.roles.roles.get(role)
        if not role_obj:
            role_obj = self.config.roles.roles.get("general")
            role = "general"

        prefix = role_obj.prefix
        if prefix:
            working_text = f"{prefix}{working_text}"

        rewritten_count = count_tokens(working_text, model)

        saving_pct = (
            (original_count.value - rewritten_count.value) / original_count.value * 100
            if original_count.value > 0
            else 0.0
        )

        warning = None
        if rewritten_count.value < 8 and original_count.value > 8:
            warning = "rewrite collapsed prompt to near-empty; consider expanding"

        return RewriteResult(
            original=text,
            rewritten=working_text,
            role=role,
            raw_tokens=original_count.value,
            rewritten_tokens=rewritten_count.value,
            saving_pct=saving_pct,
            model_used_for_count=model,
            warning=warning,
        )

    def _remove_filler_words(self, text: str) -> str:
        """Remove filler words from text.

        Args:
            text: Text to clean

        Returns:
            Text with filler words removed
        """
        words = text.split()
        filtered = [
            w for w in words if w.lower().strip(",.!?;:") not in self.filler_words
        ]
        return " ".join(filtered)
