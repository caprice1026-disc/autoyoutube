from __future__ import annotations

import json

from src.media.gemini_keyword_extractor import extract_keywords_for_project


class FakeGeminiTransport:
    def __init__(self, response: dict) -> None:
        self.response = response
        self.calls: list[tuple[str, dict]] = []

    def generate_content(self, model: str, payload: dict) -> dict:
        self.calls.append((model, payload))
        return self.response


def _project() -> dict:
    return {
        "project_id": "gemini-keyword-test",
        "visual_strategy": {
            "primary_query": "technology",
            "fallback_queries": ["generic technology"],
            "avoid_keywords": ["logo"],
        },
        "script": [
            {
                "index": 1,
                "text": "半導体工場ではシリコンウエハーを加工しています。",
                "visual_query": "technology factory",
            }
        ],
    }


def _gemini_response(scenes: list[dict]) -> dict:
    return {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {"text": json.dumps({"scenes": scenes}, ensure_ascii=False)}
                    ]
                }
            }
        ]
    }


def test_extract_keywords_replaces_scene_query_and_records_visual_reason(
    tmp_path,
) -> None:
    transport = FakeGeminiTransport(
        _gemini_response(
            [
                {
                    "index": 1,
                    "primary_keywords": ["silicon wafer", "semiconductor factory"],
                    "secondary_keywords": ["clean room", "microchip production"],
                    "visual_intent": "close-up of silicon wafers in a clean room",
                    "avoid_keywords": ["computer screen", "brand logo"],
                }
            ]
        )
    )

    result = extract_keywords_for_project(
        _project(),
        environ={
            "ENABLE_LLM_KEYWORD_EXTRACTION": "true",
            "GEMINI_API_KEY": "test-key",
            "GEMINI_MODEL": "gemini-test",
        },
        cache_path=tmp_path / "cache.json",
        transport=transport,
    )

    assert result.project["script"][0]["visual_query"] == (
        "silicon wafer semiconductor factory clean room microchip production"
    )
    assert "technology factory" in result.project["visual_strategy"]["fallback_queries"]
    assert "computer screen" in result.project["visual_strategy"]["avoid_keywords"]
    assert result.metadata["status"] == "generated"
    assert result.metadata["scene_plans"]["1"]["visual_intent"].startswith("close-up")
    assert transport.calls[0][0] == "gemini-test"


def test_extract_keywords_uses_original_project_when_gemini_is_unconfigured(
    tmp_path,
) -> None:
    project = _project()

    result = extract_keywords_for_project(
        project,
        environ={"ENABLE_LLM_KEYWORD_EXTRACTION": "true"},
        cache_path=tmp_path / "cache.json",
    )

    assert result.project == project
    assert result.project is not project
    assert result.metadata["status"] == "unavailable"
    assert result.metadata["reason"] == "missing_api_key"


def test_extract_keywords_defaults_to_flash_lite_for_free_tier_usage(tmp_path) -> None:
    result = extract_keywords_for_project(
        _project(),
        environ={"ENABLE_LLM_KEYWORD_EXTRACTION": "true"},
        cache_path=tmp_path / "cache.json",
    )

    assert result.metadata["model"] == "gemini-3.1-flash-lite"


def test_extract_keywords_rejects_a_generated_plan_unrelated_to_visual_query(
    tmp_path,
) -> None:
    project = _project()
    project["script"][0]["visual_query"] = "microwave turntable"
    transport = FakeGeminiTransport(
        _gemini_response(
            [
                {
                    "index": 1,
                    "primary_keywords": ["dandelion seeds", "golden sunlight"],
                    "secondary_keywords": ["grassy meadow"],
                    "visual_intent": "dandelion seeds floating in a field",
                    "avoid_keywords": [],
                }
            ]
        )
    )

    result = extract_keywords_for_project(
        project,
        environ={
            "ENABLE_LLM_KEYWORD_EXTRACTION": "true",
            "GEMINI_API_KEY": "test-key",
        },
        cache_path=tmp_path / "cache.json",
        transport=transport,
    )

    assert result.project == project
    assert result.metadata["status"] == "fallback"
    assert result.metadata["reason"] == "invalid_response"


def test_extract_keywords_falls_back_when_gemini_returns_invalid_json(tmp_path) -> None:
    project = _project()
    transport = FakeGeminiTransport(
        {"candidates": [{"content": {"parts": [{"text": "not json"}]}}]}
    )

    result = extract_keywords_for_project(
        project,
        environ={
            "ENABLE_LLM_KEYWORD_EXTRACTION": "true",
            "GEMINI_API_KEY": "test-key",
        },
        cache_path=tmp_path / "cache.json",
        transport=transport,
    )

    assert result.project == project
    assert result.metadata["status"] == "fallback"
    assert result.metadata["reason"] == "invalid_response"


def test_extract_keywords_falls_back_when_gemini_request_errors(tmp_path) -> None:
    class FailingTransport:
        def generate_content(self, model: str, payload: dict) -> dict:
            raise RuntimeError("Gemini service unavailable")

    project = _project()

    result = extract_keywords_for_project(
        project,
        environ={
            "ENABLE_LLM_KEYWORD_EXTRACTION": "true",
            "GEMINI_API_KEY": "test-key",
        },
        cache_path=tmp_path / "cache.json",
        transport=FailingTransport(),
    )

    assert result.project == project
    assert result.metadata["status"] == "fallback"
    assert result.metadata["reason"] == "request_failed"


def test_extract_keywords_reuses_cached_scene_result_without_a_second_request(
    tmp_path,
) -> None:
    response = _gemini_response(
        [
            {
                "index": 1,
                "primary_keywords": ["silicon wafer"],
                "secondary_keywords": ["clean room"],
                "visual_intent": "silicon wafer close-up",
                "avoid_keywords": [],
            }
        ]
    )
    transport = FakeGeminiTransport(response)
    environ = {
        "ENABLE_LLM_KEYWORD_EXTRACTION": "true",
        "GEMINI_API_KEY": "test-key",
    }
    cache_path = tmp_path / "cache.json"
    project = _project()
    project["script"][0]["visual_query"] = "silicon wafer factory"

    first = extract_keywords_for_project(
        project, environ=environ, cache_path=cache_path, transport=transport
    )
    second = extract_keywords_for_project(
        project, environ=environ, cache_path=cache_path, transport=transport
    )

    assert first.metadata["status"] == "generated"
    assert second.metadata["status"] == "cache_hit"
    assert len(transport.calls) == 1


def test_extract_keywords_uses_visual_intent_when_primary_keywords_are_abstract(
    tmp_path,
) -> None:
    transport = FakeGeminiTransport(
        _gemini_response(
            [
                {
                    "index": 1,
                    "primary_keywords": ["technology", "industry"],
                    "secondary_keywords": [],
                    "visual_intent": "semiconductor clean room silicon wafer close-up",
                    "avoid_keywords": [],
                }
            ]
        )
    )

    project = _project()
    project["script"][0]["visual_query"] = "semiconductor factory"
    result = extract_keywords_for_project(
        project,
        environ={
            "ENABLE_LLM_KEYWORD_EXTRACTION": "true",
            "GEMINI_API_KEY": "test-key",
        },
        cache_path=tmp_path / "cache.json",
        transport=transport,
    )

    assert result.project["script"][0]["visual_query"] == (
        "semiconductor clean room silicon wafer close-up"
    )
