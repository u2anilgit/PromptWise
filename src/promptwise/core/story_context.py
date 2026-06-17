"""story_context — assemble a self-contained, implementation-ready story.

This is the method's signature mechanic: the architecture context, constraints,
and (for regulated work) the compliance rules are embedded *into* the story so a
downstream dev executor needs no external lookup. Stdlib only, no network.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Imported lazily-friendly: type only, no hard dependency required at runtime.
try:  # pragma: no cover - import convenience
    from promptwise.core.doc_sharder import Shard
except Exception:  # pragma: no cover
    Shard = Any  # type: ignore


_STATUSES = ("Draft", "Approved", "InProgress", "Review", "Done")


@dataclass
class StoryContext:
    id: str
    title: str
    epic_id: str = ""
    status: str = "Draft"
    as_a: str = ""
    i_want: str = ""
    so_that: str = ""
    acceptance_criteria: list[str] = field(default_factory=list)
    dev_notes: dict = field(default_factory=dict)
    tasks: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "epic_id": self.epic_id,
            "title": self.title,
            "status": self.status,
            "as_a": self.as_a,
            "i_want": self.i_want,
            "so_that": self.so_that,
            "acceptance_criteria": list(self.acceptance_criteria),
            "dev_notes": dict(self.dev_notes),
            "tasks": list(self.tasks),
        }

    def to_markdown(self) -> str:
        ac = "\n".join(f"- {c}" for c in self.acceptance_criteria) or "- (none)"
        tasks = "\n".join(f"- [ ] {t}" for t in self.tasks) or "- [ ] (none)"
        arch = self.dev_notes.get("relevant_architecture", [])
        arch_md = "\n\n".join(arch) if arch else "_none captured_"
        files = ", ".join(self.dev_notes.get("files_to_touch", [])) or "_tbd_"
        cons = "\n".join(f"- {c}" for c in self.dev_notes.get("constraints", [])) or "- none"
        comp = self.dev_notes.get("compliance_rules", [])
        comp_md = "\n".join(f"- {c}" for c in comp) if comp else "- none"
        story_line = ""
        if self.as_a or self.i_want or self.so_that:
            story_line = f"\n**As a** {self.as_a} **I want** {self.i_want} **so that** {self.so_that}\n"
        return (
            f"# Story {self.id} — {self.title}\n"
            f"**Epic:** {self.epic_id or '-'} · **Status:** {self.status}\n"
            f"{story_line}\n"
            f"## Acceptance criteria\n{ac}\n\n"
            f"## Dev notes (self-contained context)\n"
            f"**Files likely touched:** {files}\n\n"
            f"**Constraints:**\n{cons}\n\n"
            f"**Compliance rules:**\n{comp_md}\n\n"
            f"**Relevant architecture:**\n\n{arch_md}\n\n"
            f"## Tasks\n{tasks}\n"
        )


class StoryContextBuilder:
    """Build a StoryContext, embedding the supplied context inline."""

    def build(
        self,
        *,
        story_id: str,
        title: str,
        epic_id: str = "",
        as_a: str = "",
        i_want: str = "",
        so_that: str = "",
        acceptance_criteria: list[str] | None = None,
        arch_shards: list | None = None,
        files_to_touch: list[str] | None = None,
        constraints: list[str] | None = None,
        compliance_rules: list[str] | None = None,
        tasks: list[str] | None = None,
        status: str = "Draft",
        max_shard_chars: int = 1200,
    ) -> StoryContext:
        if status not in _STATUSES:
            status = "Draft"
        embedded: list[str] = []
        for s in arch_shards or []:
            title_attr = getattr(s, "title", None)
            body_attr = getattr(s, "body", None)
            if title_attr is not None and body_attr is not None:
                body = body_attr if len(body_attr) <= max_shard_chars else body_attr[:max_shard_chars] + " …"
                embedded.append(f"### {title_attr}\n{body}")
            else:  # accept plain strings too
                text = str(s)
                embedded.append(text if len(text) <= max_shard_chars else text[:max_shard_chars] + " …")

        dev_notes = {
            "relevant_architecture": embedded,
            "files_to_touch": list(files_to_touch or []),
            "constraints": list(constraints or []),
            "compliance_rules": list(compliance_rules or []),
        }
        return StoryContext(
            id=story_id,
            title=title,
            epic_id=epic_id,
            status=status,
            as_a=as_a,
            i_want=i_want,
            so_that=so_that,
            acceptance_criteria=list(acceptance_criteria or []),
            dev_notes=dev_notes,
            tasks=list(tasks or []),
        )
