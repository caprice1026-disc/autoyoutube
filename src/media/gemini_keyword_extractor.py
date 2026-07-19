"""Optional Gemini-powered visual keyword extraction for video projects."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


DEFAULT_GEMINI_MODEL = "gemini-2.0-flash"
PROMPT_VERSION = "visual-keyword-extraction-v1"
DEFAULT_CACHE_PATH = Path("data/llm_keyword_cache.json")
_MAX_FALLBACK_QUERIES = 8
_MAX_KEYWORDS = 8
_GENERIC_KEYWORDS = {
    "analysis",
    "business",
    "concept",
    "economy",
    "history",
    "industry",
    "news",
    "politics",
    "science",
    "technology",
    "world",
}


class GeminiTransport(Protocol):
    def generate_content(
        self, model: str, payload: dict[str, Any]
    ) -> dict[str, Any]: ...


class GeminiRequestError(RuntimeError):
    """Raised when Gemini cannot provide a usable response."""


class UrlLibGeminiTransport:
    """Small Gemini REST transport that avoids an extra SDK dependency."""

    def __init__(self, api_key: str, timeout_sec: float = 20.0) -> None:
        self.api_key = api_key
        self.timeout_sec = timeout_sec

    def generate_content(self, model: str, payload: dict[str, Any]) -> dict[str, Any]:
        endpoint = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{quote(model, safe='.-_')}:generateContent?key={quote(self.api_key, safe='')}"
        )
        request = Request(
            endpoint,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout_sec) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            raise GeminiRequestError(f"http_{exc.code}") from exc
        except (URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise GeminiRequestError("transport_error") from exc


@dataclass(frozen=True)
class KeywordExtractionResult:
    project: dict[str, Any]
    metadata: dict[str, Any]


def extract_keywords_for_project(
    project: Mapping[str, Any],
    *,
    environ: Mapping[str, str] | None = None,
    cache_path: Path | None = None,
    transport: GeminiTransport | None = None,
) -> KeywordExtractionResult:
    """Return a project enriched with Gemini visual terms or an unchanged safe fallback."""

    environment = os.environ if environ is None else environ
    project_copy = copy.deepcopy(dict(project))
    model = (
        environment.get("GEMINI_MODEL", DEFAULT_GEMINI_MODEL).strip()
        or DEFAULT_GEMINI_MODEL
    )
    base_metadata = {
        "enabled": _is_enabled(environment.get("ENABLE_LLM_KEYWORD_EXTRACTION", "")),
        "model": model,
        "scene_plans": {},
    }
    if not base_metadata["enabled"]:
        return KeywordExtractionResult(
            project_copy,
            {**base_metadata, "status": "disabled", "reason": "feature_disabled"},
        )

    api_key = environment.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        return KeywordExtractionResult(
            project_copy,
            {**base_metadata, "status": "unavailable", "reason": "missing_api_key"},
        )

    scenes = _project_scenes(project_copy)
    if not scenes:
        return KeywordExtractionResult(
            project_copy,
            {**base_metadata, "status": "unavailable", "reason": "no_scenes"},
        )

    cache_file = cache_path or DEFAULT_CACHE_PATH
    cache_key = _cache_key(model, scenes)
    cached_plans = _read_cache(cache_file).get(cache_key)
    if cached_plans is not None:
        enhanced, scene_plans = _apply_scene_plans(project_copy, cached_plans)
        return KeywordExtractionResult(
            enhanced,
            {**base_metadata, "status": "cache_hit", "scene_plans": scene_plans},
        )

    request_transport = transport or UrlLibGeminiTransport(api_key)
    try:
        response = request_transport.generate_content(model, _request_payload(scenes))
        scene_plans = _parse_response(response, scenes)
    except Exception as exc:
        return KeywordExtractionResult(
            project_copy,
            {
                **base_metadata,
                "status": "fallback",
                "reason": _failure_reason(exc),
            },
        )

    _write_cache(cache_file, cache_key, scene_plans)
    enhanced, normalized_plans = _apply_scene_plans(project_copy, scene_plans)
    return KeywordExtractionResult(
        enhanced,
        {**base_metadata, "status": "generated", "scene_plans": normalized_plans},
    )


def _is_enabled(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _project_scenes(project: Mapping[str, Any]) -> list[dict[str, Any]]:
    scenes: list[dict[str, Any]] = []
    for item in project.get("script", []):
        if not isinstance(item, Mapping):
            continue
        index = item.get("index")
        text = item.get("text")
        if isinstance(index, int) and isinstance(text, str) and text.strip():
            scenes.append({"index": index, "text": text.strip()})
    return scenes


def _request_payload(scenes: list[dict[str, Any]]) -> dict[str, Any]:
    scene_lines = "\n".join(
        f"- index: {scene['index']}; narration: {scene['text']}" for scene in scenes
    )
    prompt = f"""You create concise English search terms for stock-video selection.
Return JSON only, with this exact top-level shape:
{{"scenes":[{{"index":1,"primary_keywords":["..."],"secondary_keywords":["..."],"visual_intent":"...","avoid_keywords":["..."]}}]}}

For every input scene, provide concrete, visual English terms. primary_keywords must name the main visible subject or action. secondary_keywords may add setting or motion. visual_intent must describe a specific footage shot and must replace abstract terms such as technology, history, economy, or politics when those are not directly filmable. avoid_keywords lists misleading footage to exclude. Do not include brand names. Translate Japanese narration to English. Keep every array to at most {_MAX_KEYWORDS} short phrases.

Scenes:
{scene_lines}
"""
    return {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json"},
    }


def _parse_response(
    response: Mapping[str, Any], scenes: list[dict[str, Any]]
) -> dict[str, dict[str, Any]]:
    candidates = response.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        raise ValueError("invalid_response")
    content = (
        candidates[0].get("content", {}) if isinstance(candidates[0], Mapping) else {}
    )
    parts = content.get("parts", []) if isinstance(content, Mapping) else []
    text = parts[0].get("text") if parts and isinstance(parts[0], Mapping) else None
    if not isinstance(text, str):
        raise ValueError("invalid_response")
    try:
        data = json.loads(_json_object(text))
    except json.JSONDecodeError as exc:
        raise ValueError("invalid_response") from exc
    raw_scenes = data.get("scenes") if isinstance(data, Mapping) else None
    if not isinstance(raw_scenes, list):
        raise ValueError("invalid_response")

    expected_indices = {scene["index"] for scene in scenes}
    normalized: dict[str, dict[str, Any]] = {}
    for raw in raw_scenes:
        plan = _normalize_scene_plan(raw)
        if plan is not None and plan["index"] in expected_indices:
            normalized[str(plan["index"])] = plan
    if set(int(index) for index in normalized) != expected_indices:
        raise ValueError("invalid_response")
    return normalized


def _json_object(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(
            r"^```(?:json)?\s*|\s*```$", "", stripped, flags=re.IGNORECASE
        )
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start < 0 or end < start:
        raise ValueError("invalid_response")
    return stripped[start : end + 1]


def _normalize_scene_plan(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, Mapping) or not isinstance(raw.get("index"), int):
        return None
    primary = _phrases(raw.get("primary_keywords"))
    secondary = _phrases(raw.get("secondary_keywords"))
    visual_intent = _phrase(raw.get("visual_intent"))
    avoid = _phrases(raw.get("avoid_keywords"))
    if not primary and not visual_intent:
        return None
    return {
        "index": raw["index"],
        "primary_keywords": primary,
        "secondary_keywords": secondary,
        "visual_intent": visual_intent,
        "avoid_keywords": avoid,
    }


def _phrases(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        phrase = _phrase(item)
        if phrase and phrase not in result:
            result.append(phrase)
        if len(result) >= _MAX_KEYWORDS:
            break
    return result


def _phrase(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.split())[:120]


def _apply_scene_plans(
    project: dict[str, Any], scene_plans: Mapping[str, Mapping[str, Any]]
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    strategy = project.setdefault("visual_strategy", {})
    original_fallbacks = strategy.get("fallback_queries", [])
    fallbacks = [
        item for item in original_fallbacks if isinstance(item, str) and item.strip()
    ]
    original_avoid = strategy.get("avoid_keywords", [])
    avoid_keywords = [
        item for item in original_avoid if isinstance(item, str) and item.strip()
    ]
    normalized_plans: dict[str, dict[str, Any]] = {}
    first_query = ""

    for script in project.get("script", []):
        if not isinstance(script, dict):
            continue
        key = str(script.get("index"))
        plan = scene_plans.get(key)
        if plan is None:
            continue
        original_query = _phrase(script.get("visual_query"))
        query = _compose_visual_query(plan)
        if not query:
            continue
        script["visual_query"] = query
        if not first_query:
            first_query = query
        if original_query:
            fallbacks.append(original_query)
        if plan.get("visual_intent"):
            fallbacks.append(plan["visual_intent"])
        avoid_keywords.extend(plan.get("avoid_keywords", []))
        normalized_plans[key] = {
            **dict(plan),
            "original_visual_query": original_query,
            "search_query": query,
        }

    if first_query:
        strategy["primary_query"] = first_query
    strategy["fallback_queries"] = _unique_phrases(fallbacks, _MAX_FALLBACK_QUERIES)
    strategy["avoid_keywords"] = _unique_phrases(avoid_keywords, _MAX_KEYWORDS * 3)
    return project, normalized_plans


def _compose_visual_query(plan: Mapping[str, Any]) -> str:
    primary = [
        phrase for phrase in plan.get("primary_keywords", []) if isinstance(phrase, str)
    ]
    secondary = [
        phrase
        for phrase in plan.get("secondary_keywords", [])
        if isinstance(phrase, str)
    ]
    all_primary_generic = bool(primary) and all(
        phrase.lower() in _GENERIC_KEYWORDS for phrase in primary
    )
    if all_primary_generic and isinstance(plan.get("visual_intent"), str):
        return plan["visual_intent"]
    return " ".join(_unique_phrases(primary + secondary, _MAX_KEYWORDS))


def _unique_phrases(values: list[str], limit: int) -> list[str]:
    result: list[str] = []
    for value in values:
        phrase = _phrase(value)
        if phrase and phrase not in result:
            result.append(phrase)
        if len(result) >= limit:
            break
    return result


def _cache_key(model: str, scenes: list[dict[str, Any]]) -> str:
    material = json.dumps(
        {"version": PROMPT_VERSION, "model": model, "scenes": scenes},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _read_cache(path: Path) -> dict[str, dict[str, dict[str, Any]]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        entries = data.get("entries", {})
        return entries if isinstance(entries, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _write_cache(
    path: Path, cache_key: str, scene_plans: Mapping[str, Mapping[str, Any]]
) -> None:
    try:
        entries = _read_cache(path)
        entries[cache_key] = dict(scene_plans)
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", delete=False, dir=path.parent, suffix=".tmp"
        ) as handle:
            json.dump(
                {"version": 1, "entries": entries}, handle, ensure_ascii=False, indent=2
            )
            temporary_path = Path(handle.name)
        temporary_path.replace(path)
    except OSError:
        return


def _failure_reason(exc: Exception) -> str:
    if isinstance(exc, GeminiRequestError):
        return "rate_limited" if "429" in str(exc) else "request_failed"
    if isinstance(exc, (KeyError, TypeError, ValueError, json.JSONDecodeError)):
        return "invalid_response"
    return "request_failed"
