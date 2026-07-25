from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from src.config import PROJECT_SCHEMA_PATH
from src.validators.json_validator import load_json

Log = Callable[[str], None]


def normalize_project_for_schema(
    project: dict[str, Any],
    *,
    schema_path: Path = PROJECT_SCHEMA_PATH,
    fallback_mood: str = "mysterious",
    log: Log | None = None,
) -> dict[str, Any]:
    """Return a schema-compatible copy without mutating the source project."""

    schema = load_json(schema_path)
    allowed_moods = set(
        schema.get("properties", {})
        .get("bgm", {})
        .get("properties", {})
        .get("mood", {})
        .get("enum", [])
    )
    bgm = project.get("bgm")
    if (
        isinstance(bgm, dict)
        and "mood" in bgm
        and fallback_mood in allowed_moods
        and bgm.get("mood") not in allowed_moods
    ):
        updated = _copy_project(project)
        before = updated["bgm"].get("mood")
        updated["bgm"]["mood"] = fallback_mood
        if log is not None:
            log(f"bgm.mood '{before}' is outside schema; using '{fallback_mood}'")
        return updated
    return project


def project_with_bgm_override(
    project: dict[str, Any], bgm_id: str | None
) -> dict[str, Any]:
    if not bgm_id:
        return project
    updated = _copy_project(project)
    bgm = updated.setdefault("bgm", {})
    if isinstance(bgm, dict):
        bgm["track_id"] = bgm_id
    return updated


def project_with_visual_keywords(
    project: dict[str, Any], keywords: list[str], *, query_mode: str
) -> dict[str, Any]:
    normalized_keywords = unique_non_empty(keywords)
    if not normalized_keywords:
        return project

    updated = _copy_project(project)
    visual_strategy = updated.setdefault("visual_strategy", {})
    if not isinstance(visual_strategy, dict):
        visual_strategy = {}
        updated["visual_strategy"] = visual_strategy

    if query_mode == "override":
        visual_strategy["primary_query"] = normalized_keywords[0]
        visual_strategy["fallback_queries"] = limit_unique_queries(
            normalized_keywords[1:] or [normalized_keywords[0]], 8
        )
        script = updated.get("script", [])
        if isinstance(script, list):
            for index, item in enumerate(script):
                if isinstance(item, dict):
                    item["visual_query"] = normalized_keywords[index % len(normalized_keywords)]
        return updated

    fallback_queries = visual_strategy.get("fallback_queries", [])
    if not isinstance(fallback_queries, list):
        fallback_queries = []
    visual_strategy["fallback_queries"] = limit_unique_queries(
        [str(query) for query in fallback_queries] + normalized_keywords, 8
    )
    return updated


def queries_for_plan(
    project: dict[str, Any], *, query_mode: str, visual_keywords: list[str]
) -> list[str]:
    json_queries: list[str] = []
    visual_strategy = project.get("visual_strategy", {})
    if isinstance(visual_strategy, dict) and visual_strategy.get("primary_query"):
        json_queries.append(str(visual_strategy["primary_query"]))
    for item in project.get("script", []):
        if isinstance(item, dict) and item.get("visual_query"):
            json_queries.append(str(item["visual_query"]))
    if isinstance(visual_strategy, dict):
        for query in visual_strategy.get("fallback_queries", []):
            if query:
                json_queries.append(str(query))

    if query_mode == "override":
        return list(visual_keywords)
    return json_queries + list(visual_keywords)


def unique_non_empty(values: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        normalized = str(value or "").strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        output.append(normalized)
    return output


def limit_unique_queries(values: list[str], limit: int) -> list[str]:
    return unique_non_empty(values)[:limit]


def _copy_project(project: dict[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(project, ensure_ascii=False))
