import re
import time
import uuid
from promptwise_v2.types_v2 import OrchestratorResult

_STEP_SEPARATORS = re.compile(
    r'\b(then|after that|next|finally|first|second|third|step \d+:?)\b', re.I
)
_ACTION_MAP = {
    "read": ["read", "open", "load", "fetch"],
    "summarize": ["summarize", "summary", "brief", "tldr"],
    "refactor": ["refactor", "rewrite", "clean", "improve"],
    "test": ["test", "pytest", "verify", "validate"],
    "analyze": ["analyze", "analyse", "review", "inspect"],
    "write": ["write", "create", "draft", "implement"],
}

_STRATEGIES = {"stop", "retry", "fallback", "all"}


class Orchestrator:
    def parse_tasks(self, text: str) -> list[dict]:
        parts = _STEP_SEPARATORS.split(text)
        parts = [p.strip() for p in parts if p and p.strip() and not _STEP_SEPARATORS.fullmatch(p.strip())]
        if not parts:
            parts = [text.strip()]

        tasks = []
        for i, part in enumerate(parts):
            action = self._detect_action(part)
            tasks.append({"id": f"t{i+1}", "action": action, "text": part})
        return tasks

    def build_dag(self, tasks: list[dict]) -> dict:
        dag: dict = {t["id"]: {"task": t, "dependents": []} for t in tasks}
        for t in tasks:
            for dep in t.get("depends_on", []):
                if dep in dag:
                    dag[dep]["dependents"].append(t["id"])
        return dag

    def execute(self, text: str, strategy: str = "fallback") -> OrchestratorResult:
        if strategy not in _STRATEGIES:
            strategy = "fallback"

        start = time.monotonic()
        tasks = self.parse_tasks(text)
        dag = self.build_dag(tasks)

        steps_done = 0
        output_parts: list[str] = []
        error = None

        for node in dag.values():
            task = node["task"]
            try:
                output_parts.append(f"[{task['action']}] {task['text'][:50]}")
                steps_done += 1
            except Exception as exc:
                error = str(exc)
                if strategy == "stop":
                    break
                elif strategy == "retry":
                    try:
                        output_parts.append(f"[retry:{task['action']}]")
                        steps_done += 1
                    except Exception:
                        break

        duration_ms = int((time.monotonic() - start) * 1000)
        status = "completed" if steps_done == len(tasks) else ("partial" if steps_done > 0 else "failed")

        return OrchestratorResult(
            task_id=str(uuid.uuid4())[:8],
            status=status,
            steps_total=len(tasks),
            steps_done=steps_done,
            strategy_used=strategy,
            output="\n".join(output_parts),
            cost_usd=0.0,
            duration_ms=duration_ms,
            error=error,
        )

    def _detect_action(self, text: str) -> str:
        text_lower = text.lower()
        for action, keywords in _ACTION_MAP.items():
            if any(kw in text_lower for kw in keywords):
                return action
        return "process"
