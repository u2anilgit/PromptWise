"""Model-aware token counting for PromptWise."""

from promptwise.types import TokenCount

try:
    import tiktoken

    TIKTOKEN_AVAILABLE = True
except ImportError:
    TIKTOKEN_AVAILABLE = False


TIKTOKEN_BY_MODEL = {
    "claude-opus-4-7": "cl100k_base",
    "claude-opus-4-6": "cl100k_base",
    "claude-sonnet-4-6": "cl100k_base",
    "claude-haiku-4-5-20251001": "cl100k_base",
}

OPUS_47_INFLATION = 1.20


def count_tokens(text: str, model: str = "claude-sonnet-4-6") -> TokenCount:
    """Count tokens in text with model-aware adjustment.

    Args:
        text: Text to count tokens for
        model: Model ID (default: claude-sonnet-4-6)

    Returns:
        TokenCount with value, method, and model
    """
    encoding_name = TIKTOKEN_BY_MODEL.get(model, "cl100k_base")
    inflation = OPUS_47_INFLATION if model == "claude-opus-4-7" else 1.0

    if TIKTOKEN_AVAILABLE:
        try:
            encoding = tiktoken.get_encoding(encoding_name)
            token_count = len(encoding.encode(text))
            adjusted_count = int(token_count * inflation)
            return TokenCount(
                value=adjusted_count, method="tiktoken", model=model
            )
        except Exception:
            pass

    fallback_count = int(len(text) / 4)
    adjusted_count = int(fallback_count * inflation)
    return TokenCount(value=adjusted_count, method="char_estimate", model=model)


def count_tokens_batch(
    texts: list[str], model: str = "claude-sonnet-4-6"
) -> list[TokenCount]:
    """Count tokens for multiple texts efficiently.

    Args:
        texts: List of texts to count tokens for
        model: Model ID (default: claude-sonnet-4-6)

    Returns:
        List of TokenCount objects
    """
    return [count_tokens(text, model) for text in texts]
