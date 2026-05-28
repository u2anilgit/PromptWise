import re
from promptwise_v2.types_v2 import CompressionResult

_ARTICLES = re.compile(r'\b(a|an|the)\s+', re.I)
_FILLER = re.compile(
    r'\b(just|really|basically|actually|simply|literally|very|quite|rather|'
    r'somewhat|kind of|sort of|I was wondering if|you could|please note that)\b\s*',
    re.I,
)
_PLEASANTRIES = re.compile(
    r'\b(sure[!,]?\s*|certainly[!,]?\s*|of course[!,]?\s*|happy to help[!,]?\s*|'
    r'great question[!,]?\s*|absolutely[!,]?\s*|no problem[!,]?\s*)\s*',
    re.I,
)
_HEDGING = re.compile(
    r'\b(might|perhaps|possibly|potentially|arguably|it seems|it appears|'
    r'I think|I believe|I guess|probably|likely|maybe)\b\s*',
    re.I,
)
_CODE_BLOCK = re.compile(r'```[\s\S]*?```')


class CompressionEngine:
    def compress(self, text: str) -> CompressionResult:
        if not text:
            return CompressionResult(original="", compressed="", tokens_saved=0,
                                     saving_pct=0.0, rules_applied=[])

        code_blocks: list[str] = []
        placeholder = "\x00CODE{}\x00"

        def _stash(m):
            code_blocks.append(m.group(0))
            return placeholder.format(len(code_blocks) - 1)

        protected = _CODE_BLOCK.sub(_stash, text)

        rules_applied: list[str] = []
        result = protected

        def _apply(pattern, label):
            nonlocal result
            new = pattern.sub("", result)
            if new != result:
                rules_applied.append(label)
            result = new

        _apply(_PLEASANTRIES, "pleasantries")
        _apply(_HEDGING, "hedging")
        _apply(_FILLER, "filler")
        _apply(_ARTICLES, "articles")

        for i, block in enumerate(code_blocks):
            result = result.replace(placeholder.format(i), block)

        result = re.sub(r'  +', ' ', result).strip()

        orig_words = len(text.split())
        new_words = len(result.split())
        saving_pct = round((orig_words - new_words) / orig_words * 100, 1) if orig_words else 0.0
        tokens_saved = max(0, orig_words - new_words)

        return CompressionResult(
            original=text,
            compressed=result,
            tokens_saved=tokens_saved,
            saving_pct=saving_pct,
            rules_applied=rules_applied,
        )
