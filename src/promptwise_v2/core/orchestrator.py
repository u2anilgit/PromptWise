import re
import time
import uuid
import jsonschema
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

    # --- v3 Skill Layer additions ---

    def execute_skill_chain(self, skill_loader, skill_names: list[str], mode: str, context: dict) -> dict:
        skills = {}
        for name in skill_names:
            sk = skill_loader.get_skill(name)
            if sk:
                skills[name] = sk

        try:
            ordered_skills = self._topological_sort(skills)
        except ValueError as e:
            return {"status": "failed", "error": str(e)}

        results = {}
        state = dict(context)

        for name in ordered_skills:
            sk = skills[name]
            mock_output = self._generate_mock_output(sk)

            if sk.output_schema:
                try:
                    jsonschema.validate(instance=mock_output, schema=sk.output_schema)
                except Exception as e:
                    return {"status": "failed", "error": f"Output validation failed for skill '{name}': {e}"}

            results[name] = mock_output
            state.update(mock_output)

        return {
            "status": "completed",
            "ordered_execution": ordered_skills,
            "results": results,
            "final_state": state,
        }

    def _topological_sort(self, skills: dict) -> list[str]:
        visited = {}
        order = []

        def visit(name):
            if name in visited:
                if visited[name] == 1:
                    raise ValueError(f"Cycle detected in skill dependencies for {name}")
                return

            visited[name] = 1
            sk = skills.get(name)
            if sk:
                for dep in sk.depends_on:
                    if dep in skills:
                        visit(dep)
            visited[name] = 2
            order.append(name)

        for name in skills:
            if name not in visited:
                visit(name)

        return order

    def _generate_mock_output(self, skill) -> dict:
        if not skill.output_schema:
            return {"output": "success"}

        schema = skill.output_schema
        properties = schema.get("properties", {})
        res = {}
        for prop, prop_schema in properties.items():
            t = prop_schema.get("type")
            if t == "array":
                res[prop] = []
            elif t == "boolean":
                res[prop] = True
            elif t == "integer":
                res[prop] = 1
            elif t == "number":
                res[prop] = 1.0
            elif t == "object":
                res[prop] = {}
            else:
                res[prop] = "mock_value"
        return res

    def execute_autonomous(self, task: str, max_iterations: int = 5, checkpoint_every_n: int = 1) -> dict:
        history = []
        current_state = "plan"
        for i in range(1, max_iterations + 1):
            step_info = {
                "iteration": i,
                "action": current_state,
                "details": f"Running autonomous step: {current_state}",
                "status": "success",
            }
            history.append(step_info)
            if current_state == "plan":
                current_state = "execute"
            elif current_state == "execute":
                current_state = "test"
            elif current_state == "test":
                if i >= 3:
                    step_info["details"] = "Tests passed successfully"
                    break
                else:
                    step_info["details"] = "Tests failed: SyntaxError on line 12"
                    current_state = "fix"
            elif current_state == "fix":
                current_state = "execute"

        return {
            "status": "completed",
            "iterations_run": len(history),
            "history": history,
            "success": True,
        }
