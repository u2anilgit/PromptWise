"""doc_sharder — split a PRD / architecture markdown document into focused shards.

Self-contained: stdlib only, no imports from the rest of PromptWise, no network.
Deterministic and snapshot-testable, matching the repo's existing module style.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*$")
_WORD = re.compile(r"[^a-z0-9]+")


def _slug(text: str) -> str:
    return _WORD.sub("-", text.lower()).strip("-") or "section"


@dataclass
class Shard:
    """A focused section of a larger document."""
    anchor: str          # url-safe slug, e.g. "epic-2-payments"
    title: str           # heading text
    level: int           # heading depth (1=#, 2=##, ...)
    body: str            # full section text including its heading


class DocSharder:
    """Split markdown into shards at heading boundaries.

    `by_level=2` starts a new shard at every heading whose level is <= 2
    (i.e. '#' and '##'). Deeper headings stay inside their parent shard.
    """

    def shard(self, markdown: str, by_level: int = 2) -> list[Shard]:
        lines = (markdown or "").splitlines()
        shards: list[Shard] = []
        cur_title = ""
        cur_level = 0
        cur_lines: list[str] = []

        def flush() -> None:
            if not cur_lines and not cur_title:
                return
            body = "\n".join(cur_lines).strip("\n")
            if not body.strip():
                return
            shards.append(
                Shard(
                    anchor=_slug(cur_title) if cur_title else f"section-{len(shards) + 1}",
                    title=cur_title or "(preamble)",
                    level=cur_level or 1,
                    body=body,
                )
            )

        for line in lines:
            m = _HEADING.match(line)
            if m and len(m.group(1)) <= by_level:
                flush()
                cur_title = m.group(2).strip()
                cur_level = len(m.group(1))
                cur_lines = [line]
            else:
                cur_lines.append(line)
        flush()
        return shards

    def shards_for_epic(self, shards: list[Shard], epic_id: str) -> list[Shard]:
        """Return shards relevant to an epic id (e.g. 'E2' or 'Epic 2').

        Matches the id in the title or body, case-insensitively. Returns an
        empty list if nothing matches (caller decides the fallback).
        """
        needle = (epic_id or "").lower().strip()
        if not needle:
            return []
        # also try the numeric form: "E2" -> "epic 2"
        alt = ""
        m = re.match(r"e\s*0*(\d+)$", needle)
        if m:
            alt = f"epic {m.group(1)}"
        out: list[Shard] = []
        for s in shards:
            hay = f"{s.title}\n{s.body}".lower()
            if needle in hay or (alt and alt in hay):
                out.append(s)
        return out
