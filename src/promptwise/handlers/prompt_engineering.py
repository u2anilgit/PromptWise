"""handlers.prompt_engineering -- prompt-engineering technique MCP tool
handlers (moved verbatim from server.py's "Prompt Engineering" section
during the handlers/ package split; see
docs/superpowers/specs/2026-07-22-handlers-package-split-design.md)."""
from __future__ import annotations

import json

from promptwise.core.tool_registry import ServerContext, tool


@tool(name="suggest_technique", description="Auto-detect best prompting technique: CRAFT, Few-Shot, Chain-of-Thought, or Chaining. Blends the static heuristic pick with learned outcome history for this task class (fails open to the heuristic pick when history is thin). Returns technique_id -- pass it to validate_output/run_quality_gate's technique_id param so a later verdict teaches this decision.",
         schema={"type": "object", "properties": {"prompt": {"type": "string"}}, "required": ["prompt"]})
async def _handle_suggest_technique(ctx: ServerContext, arguments: dict) -> str:
    prompt = arguments.get("prompt", "")
    pl = prompt.lower()
    if "example" in pl:
        tech, conf, reason = "Few-Shot", 0.85, "Prompt contains 'example'"
    elif any(kw in pl for kw in ("step", "reason", "explain why")):
        tech, conf, reason = "Chain-of-Thought", 0.85, "Prompt requests step-wise reasoning"
    elif len(prompt) > 200 and len(prompt.split(".")) > 3:
        tech, conf, reason = "Chaining", 0.75, "Complex multi-sentence task"
    else:
        tech, conf, reason = "CRAFT", 0.80, "Short prompt; add Context/Role/Action/Format/Tone"

    technique_id = None
    try:
        from promptwise.core.technique_adapter import TechniqueAdapter
        from promptwise.core.technique_recorder import record_technique_decision
        task_class = ctx.router.detect_intent(prompt)
        adapted, adapt_reason = TechniqueAdapter().adapt(task_class, tech)
        if adapted != tech:
            tech = adapted
            reason = f"{reason} | adaptive: {adapt_reason}"
        technique_id = record_technique_decision(task_class, tech)
    except Exception:
        pass  # fail-open: heuristic pick above stands unchanged

    return json.dumps({"technique": tech, "confidence": conf, "rationale": reason, "technique_id": technique_id})


@tool(name="apply_craft", description="Analyze prompt against CRAFT axes (Context/Role/Action/Format/Tone) and rebuild",
         schema={"type": "object", "properties": {"prompt": {"type": "string"}}, "required": ["prompt"]})
async def _handle_apply_craft(ctx: ServerContext, arguments: dict) -> str:
    prompt = arguments.get("prompt", "")
    pl = prompt.lower()
    axes = {"context": any(kw in pl for kw in ["context", "background", "given"]),
            "role": any(kw in pl for kw in ["you are", "act as", "as a"]),
            "action": any(kw in pl for kw in ["write", "generate", "analyze", "summarize", "create", "explain"]),
            "format": any(kw in pl for kw in ["format", "bullet", "markdown", "json", "table"]),
            "tone": any(kw in pl for kw in ["tone", "formal", "casual", "professional"])}
    score = sum(20 for v in axes.values() if v)
    missing = [ax for ax, v in axes.items() if not v]
    adds = []
    if not axes["context"]: adds.append("Context: [Describe background]")
    if not axes["role"]: adds.append("Role: You are a helpful expert assistant.")
    if not axes["format"]: adds.append("Format: Respond in clear, structured paragraphs.")
    if not axes["tone"]: adds.append("Tone: Professional and concise.")
    improved = "\n".join(adds) + ("\n\n" if adds else "") + prompt
    return json.dumps({"axes": axes, "score": score, "missing_axes": missing, "improved_prompt": improved})


@tool(name="inject_few_shot", description="Enhance prompt with few-shot examples",
         schema={"type": "object", "properties": {"prompt": {"type": "string"}, "examples": {"type": "array", "items": {"type": "object"}, "default": []}}, "required": ["prompt"]})
async def _handle_inject_few_shot(ctx: ServerContext, arguments: dict) -> str:
    prompt = arguments.get("prompt", "")
    examples = arguments.get("examples", [])
    if examples:
        formatted = "\n".join(f"Example {i+1}:\nInput: {ex.get('input', '')}\nOutput: {ex.get('output', '')}" for i, ex in enumerate(examples))
        enhanced = formatted + "\n\n" + prompt
        return json.dumps({"enhanced_prompt": enhanced, "example_count": len(examples)})
    return json.dumps({"enhanced_prompt": "[INSERT EXAMPLES HERE]\n\n" + prompt, "example_count": 0})


@tool(name="add_chain_of_thought", description="Wrap prompt with Chain-of-Thought scaffold",
         schema={"type": "object", "properties": {"prompt": {"type": "string"}, "style": {"type": "string", "enum": ["standard", "step-by-step", "tree-of-thought"], "default": "step-by-step"}}, "required": ["prompt"]})
async def _handle_add_chain_of_thought(ctx: ServerContext, arguments: dict) -> str:
    prompt = arguments.get("prompt", "")
    style = arguments.get("style", "step-by-step")
    cot = {"standard": "Think step by step.", "tree-of-thought": "Consider multiple approaches before answering.",
           "step-by-step": "Let's approach this step by step:\n1. First, understand the problem.\n2. Then, work through each part.\n3. Finally, synthesize the answer."}.get(style, "Think step by step.")
    return json.dumps({"wrapped_prompt": prompt + "\n\n" + cot, "technique_applied": style})


@tool(name="chain_prompts", description="Decompose complex task into sequential prompt chain",
         schema={"type": "object", "properties": {"task": {"type": "string"}, "steps": {"type": "integer", "default": 3}}, "required": ["task"]})
async def _handle_chain_prompts(ctx: ServerContext, arguments: dict) -> str:
    task = arguments.get("task", "")
    steps = int(arguments.get("steps", 3))
    sents = [s.strip() for s in task.split(".") if s.strip()]
    chain = [{"step": i+1, "prompt": f"Step {i+1}: {(sents[i] if i < len(sents) else f'Continue step {i+1}')}.",
              "input_from": f"step_{i}" if i > 0 else "user", "output_to": f"step_{i+2}" if i < steps-1 else "final_output"} for i in range(steps)]
    return json.dumps({"chain": chain, "handoff_instructions": "Pass output of each step as input to the next."})


@tool(name="eval_prompt_across_models", description="Estimate cost and recommend model tier across Haiku/Sonnet/Opus",
         schema={"type": "object", "properties": {"prompt": {"type": "string"}, "task_type": {"type": "string", "default": "general"}}, "required": ["prompt"]})
async def _handle_eval_prompt_across_models(ctx: ServerContext, arguments: dict) -> str:
    prompt = arguments.get("prompt", "")
    inp = max(1, len(prompt) // 4)
    out = inp * 2
    tiers = {"haiku": {"cost_usd": round(inp*0.0000008+out*0.000004, 8), "quality": "good for simple tasks"},
             "sonnet": {"cost_usd": round(inp*0.000003+out*0.000015, 8), "quality": "best balance"},
             "opus": {"cost_usd": round(inp*0.000015+out*0.000075, 8), "quality": "highest quality"}}
    rec, reason = ("haiku", "Short prompt") if inp < 200 else ("sonnet", "Medium complexity") if inp < 1000 else ("opus", "Long/complex")
    return json.dumps({"recommendation": rec, "tiers": tiers, "rationale": reason, "estimated_input_tokens": inp})


@tool(name="audit_system_prompt", description="Score system prompt on clarity, role, constraints, and jailbreak resistance",
         schema={"type": "object", "properties": {"system_prompt": {"type": "string"}}, "required": ["system_prompt"]})
async def _handle_audit_system_prompt(ctx: ServerContext, arguments: dict) -> str:
    sp = arguments.get("system_prompt", "")
    spl = sp.lower()
    issues = []
    score = 0
    if any(kw in spl for kw in ("you are", "act as", "your role")):
        score += 20
    else:
        issues.append("Missing role definition")
    if any(kw in spl for kw in ("do not", "never", "must not", "avoid")):
        score += 20
    else:
        issues.append("Missing constraints")
    if any(kw in spl for kw in ("format", "output", "respond in")):
        score += 20
    else:
        issues.append("Missing output format")
    if not any(p in spl for p in ["ignore previous", "disregard", "override"]):
        score += 20
    else:
        issues.append("Injection pattern detected")
    if len(sp) > 50:
        score += 20
    else:
        issues.append("Too short, unclear task")
    adds = []
    if "Missing role" in " ".join(issues):
        adds.append("You are a helpful, knowledgeable assistant.")
    if "Missing constraints" in " ".join(issues):
        adds.append("Do not discuss topics outside your defined scope.")
    if "Missing output format" in " ".join(issues):
        adds.append("Respond in clear, structured paragraphs.")
    return json.dumps({"score": score, "issues": issues, "improved_prompt": "\n".join(adds) + ("\n\n" if adds else "") + sp})
