"""skill_optimizer — offline reflect -> patch -> validate -> accept loop for packs.

Treats the corrections accumulated in the Phase 2 LearningStore as training data
and folds the relevant ones into a SKILL.md as a stamped, reversible managed
block ("Learned rules"). A patch is accepted ONLY when:

  1. the patched file still parses (valid frontmatter + name), and
  2. its heuristic quality score (optimizer_validate.score_skill) strictly improves.

Fully offline and deterministic — the "reflection" is a rule-extraction over stored
corrections, not an LLM call, so it works with no network and no API key. An LLM
endpoint can be layered on later behind the same accept gate, but is never required.
"""
from __future__ import annotations

from pathlib import Path

from promptwise.core.config_emitter import MANAGED_START, MANAGED_END
import hashlib
import re

from promptwise.core.optimizer_validate import score_skill, validate_skill, parse_skill
from promptwise.core.learning_store import LearningStore

_MANAGED_REGION = re.compile(
    re.escape("<!-- promptwise:managed:start").replace("\\ ", " ")
    + r".*?" + re.escape(MANAGED_END), re.DOTALL)
_START_ANY = re.compile(r"<!-- promptwise:managed:start[^>]*-->")

_SECTION_TITLE = "## Learned rules (PromptWise-managed)"


def _managed_block(rules: list[tuple[str, str]]) -> str:
    body_lines = [_SECTION_TITLE,
                  "<!-- Auto-folded from captured corrections. Safe to delete; regenerated on demand. -->"]
    for mistake, correction in rules:
        body_lines.append(f"- {mistake} -> {correction}")
    body = "\n".join(body_lines)
    h = hashlib.sha256(body.encode("utf-8")).hexdigest()[:8]
    return f"{MANAGED_START.format(h=h)}\n{body}\n{MANAGED_END}"


def _merge_skill_block(content: str, block: str) -> str:
    """Append-or-replace PromptWise's managed region at the END of a SKILL.md,
    preserving frontmatter and all hand-written prose. Reversible: delete the
    region between the markers and the original file is back."""
    if _START_ANY.search(content) and MANAGED_END in content:
        return _MANAGED_REGION.sub(block, content, count=1)
    sep = "" if content.endswith("\n") else "\n"
    return f"{content}{sep}\n{block}\n"


def _relevant_rules(store: LearningStore, skill_name: str, body: str,
                    project: str | None, max_rules: int) -> list[tuple[str, str]]:
    # Query the store by the pack's name/topic; fall back to recent corrections.
    query = f"{skill_name} {body[:200]}"
    hits = store.search(query, k=max_rules, project=project)
    if not hits:
        hits = store.recent(k=max_rules, project=project)
    seen = set()
    rules: list[tuple[str, str]] = []
    for l in hits:
        key = (l.mistake.strip().lower(), l.correction.strip().lower())
        if not l.mistake.strip() or not l.correction.strip() or key in seen:
            continue
        seen.add(key)
        rules.append((l.mistake.strip(), l.correction.strip()))
    return rules[:max_rules]


def optimize_skill_pack(skill_path: str | Path, project: str | None = None,
                        db_path: str | Path | None = None, max_rules: int = 8,
                        dry_run: bool = False) -> dict:
    path = Path(skill_path)
    if not path.exists():
        return {"accepted": False, "reason": f"skill not found: {path}"}
    content = path.read_text(encoding="utf-8")

    ok, why = validate_skill(content)
    if not ok:
        return {"accepted": False, "reason": f"target SKILL.md invalid: {why}"}

    meta, body = parse_skill(content)
    skill_name = str(meta.get("name", path.stem))

    store = LearningStore(db_path)
    rules = _relevant_rules(store, skill_name, body, project, max_rules)
    if not rules:
        return {"accepted": False, "reason": "no corrections available to learn from",
                "skill": skill_name}

    before = score_skill(content)
    candidate = _merge_skill_block(content, _managed_block(rules))
    cand_valid, cand_why = validate_skill(candidate)
    after = score_skill(candidate)

    accepted = bool(cand_valid and after.score > before.score)
    written = False
    if accepted and not dry_run:
        path.write_text(candidate, encoding="utf-8")
        written = True

    return {
        "skill": skill_name,
        "path": str(path),
        "accepted": accepted,
        "written": written,
        "dry_run": dry_run,
        "rules_folded": len(rules),
        "score_before": before.score,
        "score_after": after.score,
        "candidate_valid": cand_valid,
        "reason": "" if accepted else (cand_why if not cand_valid else "score did not strictly improve"),
        "learned_rules": [f"{m} -> {c}" for m, c in rules],
    }
