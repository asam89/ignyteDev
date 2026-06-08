"""
Requirements Decomposer — takes a vision document (text + images) and
breaks it down into an ordered backlog of development tasks.

Uses LLM to analyze uploaded requirements (mockups, colour palettes,
feature specs, PRDs) and produces a structured list of tasks that can
be queued for autonomous execution.
"""

import json
import logging

from bot.core.llm import call_llm

log = logging.getLogger(__name__)

DECOMPOSE_SYSTEM = """You are a senior technical product manager and architect.
You analyze product requirements — text descriptions, mockups, colour palettes,
wireframes, and design files — and break them into an ordered backlog of
concrete, implementable development tasks.

Each task must be self-contained enough for an AI developer to implement in
a single PR. Tasks should be ordered so dependencies come first.

Respond ONLY with valid JSON."""

DECOMPOSE_PROMPT = """Analyze the following requirements and decompose them into
an ordered backlog of development tasks.

For each task, provide:
- "title": Short task title (max 80 chars)
- "description": Detailed implementation description with specifics
  (colors, layout, components, APIs, etc.)
- "priority": "high", "normal", or "low"
- "category": one of "setup", "frontend", "backend", "design", "integration", "testing"
- "depends_on": list of task indices (0-based) this task depends on

Also provide:
- "project_summary": A 2-3 sentence summary of the overall vision
- "tech_recommendations": Suggested tech stack if not already specified

--- Requirements ---
{requirements_text}

--- Additional Context ---
{extra_context}

Respond with JSON:
{{
  "project_summary": "...",
  "tech_recommendations": "...",
  "tasks": [
    {{
      "title": "...",
      "description": "...",
      "priority": "high|normal|low",
      "category": "setup|frontend|backend|design|integration|testing",
      "depends_on": []
    }}
  ]
}}"""


def decompose_requirements(
    requirements_text: str,
    extra_context: str = "",
    llm_provider: str = "auto",
    images: list[dict] | None = None,
) -> dict:
    """
    Decompose requirements into an ordered task backlog.

    Args:
        requirements_text: The main requirements text (from uploaded docs + user input).
        extra_context: Additional context (repo structure, existing code, etc.).
        llm_provider: Which LLM to use.
        images: Optional list of {"data": bytes, "mime_type": str} for vision.

    Returns:
        Dict with "project_summary", "tech_recommendations", and "tasks" list.
    """
    prompt = DECOMPOSE_PROMPT.format(
        requirements_text=requirements_text,
        extra_context=extra_context or "None provided",
    )

    try:
        raw = call_llm(
            prompt=prompt,
            system=DECOMPOSE_SYSTEM,
            provider=llm_provider,
            max_tokens=8192,
            images=images,
        )

        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.lstrip("`").lstrip("json").strip()
        if cleaned.endswith("```"):
            cleaned = cleaned[: cleaned.rfind("```")].strip()

        result = json.loads(cleaned)

        # Validate structure
        if "tasks" not in result or not isinstance(result["tasks"], list):
            raise ValueError("Response missing 'tasks' list")

        for i, task in enumerate(result["tasks"]):
            task.setdefault("title", f"Task {i + 1}")
            task.setdefault("description", "")
            task.setdefault("priority", "normal")
            task.setdefault("category", "frontend")
            task.setdefault("depends_on", [])

        log.info(
            f"Decomposed requirements into {len(result['tasks'])} tasks"
        )
        return result

    except json.JSONDecodeError as e:
        log.error(f"LLM returned invalid JSON during decomposition: {e}")
        return {
            "project_summary": "Failed to parse requirements",
            "tech_recommendations": "",
            "tasks": [],
            "error": f"LLM returned invalid JSON: {e}",
        }
    except Exception as e:
        log.error(f"Requirements decomposition failed: {e}")
        return {
            "project_summary": "Decomposition failed",
            "tech_recommendations": "",
            "tasks": [],
            "error": str(e),
        }
