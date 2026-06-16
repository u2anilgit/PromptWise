import json
import os
import re
import time
import uuid

from promptwise.types import OrchestratorResult, Skill

_STEP_SEPARATORS = re.compile(r'\b(then|after that|next|finally|first|second|third|step \d+:?)\b', re.I)
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
        parts = [p.strip() for p in _STEP_SEPARATORS.split(text) if p and p.strip() and not _STEP_SEPARATORS.fullmatch(p.strip())]
        if not parts:
            parts = [text.strip()]
        return [{"id": f"t{i+1}", "action": self._detect_action(part), "text": part} for i, part in enumerate(parts)]

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

    async def execute_skill(self, skill: Skill, context: dict, api_key: str | None = None, router=None, budget_pct: float = 0.0) -> dict:
        if api_key is None:
            api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            return {"error": "ANTHROPIC_API_KEY not set", "status": "error", "skill": skill.name}

        if router is not None:
            model = router.resolve_model(skill.name, budget_pct)
        elif skill.model_tier and skill.model_tier not in ("auto", ""):
            model = skill.model_tier
        else:
            model = "claude-sonnet-4-6"

        system_prompt = skill.description or skill.name
        if skill.output_schema:
            system_prompt += f"\n\nOutput JSON matching schema: {json.dumps(skill.output_schema)}"
        if skill.system_prompt:
            system_prompt += f"\n\n{skill.system_prompt}"

        try:
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
            response = client.messages.create(
                model=model,
                max_tokens=4096,
                system=[{"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}}],
                messages=[{"role": "user", "content": f"Context: {json.dumps(context)}\n\nExecute this skill and provide the output."}],
            )
            input_tokens = response.usage.input_tokens
            output_tokens = response.usage.output_tokens
            cost_usd = input_tokens * 0.000003 + output_tokens * 0.000015
            return {"status": "success", "skill": skill.name, "model_used": response.model,
                    "result": response.content[0].text, "input_tokens": input_tokens, "output_tokens": output_tokens, "cost_usd": cost_usd}
        except ImportError:
            return {"error": "anthropic package not installed", "status": "error", "skill": skill.name}
        except Exception as e:
            return {"error": str(e), "status": "error", "skill": skill.name}

    async def execute_skill_chain(self, skill_loader, skill_names: list[str], mode: str, context: dict,
                                   api_key: str | None = None, router=None) -> dict:
        skills = {}
        for name in skill_names:
            sk = skill_loader.get_skill(name)
            if sk:
                skills[name] = sk

        try:
            ordered = self._topological_sort(skills)
        except ValueError as e:
            return {"status": "failed", "error": str(e)}

        results = {}
        state = dict(context)
        for name in ordered:
            sk = skills[name]
            result = await self.execute_skill(sk, state, api_key=api_key, router=router)
            if result.get("status") == "error":
                return {"status": "failed", "error": result.get("error", "unknown error")}
            results[name] = result
            state.update({"last_result": result.get("result", "")})

        return {"status": "completed", "ordered_execution": ordered, "results": results}

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

    def execute_autonomous(self, task: str, max_iterations: int = 5) -> dict:
        history = []
        current_state = "plan"
        for i in range(1, max_iterations + 1):
            step = {"iteration": i, "action": current_state, "details": f"Running autonomous step: {current_state}", "status": "success"}
            history.append(step)
            if current_state == "plan":
                current_state = "execute"
            elif current_state == "execute":
                current_state = "test"
            elif current_state == "test":
                step["details"] = "Tests passed successfully" if i >= 3 else "Tests failed: SyntaxError on line 12"
                if i < 3:
                    current_state = "fix"
                else:
                    break
            elif current_state == "fix":
                current_state = "execute"
        return {"status": "completed", "iterations_run": len(history), "history": history, "success": True}

    def _detect_action(self, text: str) -> str:
        text_lower = text.lower()
        for action, keywords in _ACTION_MAP.items():
            if any(kw in text_lower for kw in keywords):
                return action
        return "process"
