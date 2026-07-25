from __future__ import annotations

from pathlib import Path
from typing import Any

from src.pipeline.project_normalization import (
    normalize_project_for_schema,
    project_with_bgm_override,
    project_with_visual_keywords,
    queries_for_plan,
)
from src.pipeline.render_metadata import (
    build_bgm_render,
    build_credits,
    build_description,
    build_subtitle,
)
from src.repair.logs import (
    append_quality_failure,
    check_summaries,
    empty_failure_log,
    empty_repair_log,
    exit_code_from_failure,
)
from src.youtube.analytics_presentation import format_console_summary


def _project() -> dict[str, Any]:
    return {
        "id": "boundary-test",
        "youtube": {
            "description": "Description",
            "hashtags": ["#Shorts"],
            "description_sections": {
                "summary": "Summary",
                "disclaimer": "Disclaimer",
            },
        },
        "bgm": {"enabled": True, "mood": "unknown", "volume_db": -30, "strategy": "youtube_safe_bgm", "fade_in_ms": 100, "fade_out_ms": 200},
        "visual_strategy": {"primary_query": "ocean", "fallback_queries": ["ocean", "water"]},
        "script": [{"visual_query": "waves"}, {"visual_query": "ocean"}],
    }


def test_project_normalization_uses_copy_and_unknown_mood_fallback() -> None:
    project = _project()
    messages: list[str] = []

    normalized = normalize_project_for_schema(project, log=messages.append)

    assert normalized is not project
    assert normalized["bgm"]["mood"] == "mysterious"
    assert project["bgm"]["mood"] == "unknown"
    assert "mysterious" in messages[0]


def test_project_mutators_and_queries_are_deterministic() -> None:
    project = _project()
    overridden = project_with_bgm_override(project, "custom-track")
    updated = project_with_visual_keywords(
        overridden,
        ["glass close up", "glass close up", "handheld glass"],
        query_mode="override",
    )

    assert project["bgm"].get("track_id") is None
    assert updated["bgm"]["track_id"] == "custom-track"
    assert updated["visual_strategy"]["primary_query"] == "glass close up"
    assert [item["visual_query"] for item in updated["script"]] == [
        "glass close up",
        "handheld glass",
    ]
    assert queries_for_plan(updated, query_mode="append", visual_keywords=[]) == [
        "glass close up",
        "glass close up",
        "handheld glass",
        "handheld glass",
    ]


def test_render_metadata_builders_keep_output_contract() -> None:
    description = build_description(_project())
    assert description == "Description\n\nSummary\n\n#Shorts\n\nDisclaimer\n"

    required, credits, text = build_credits(
        None,
        [
            {
                "source": "pexels",
                "pexels_url": "https://pexels.example/video/1",
                "photographer": "Creator",
            },
            {
                "source": "pexels",
                "pexels_url": "https://pexels.example/video/1",
                "photographer": "Creator",
            },
        ],
    )
    assert required is True
    assert len(credits) == 1
    assert text.count("pexels.example/video/1") == 1

    subtitle = build_subtitle([{"start_sec": 0, "end_sec": 1.25, "text": "A long subtitle"}])
    assert "Dialogue: 0,0:00:00.00,0:00:01.25" in subtitle


def test_bgm_render_builder_applies_volume_floor() -> None:
    track = type(
        "Track",
        (),
        {
            "track_id": "track",
            "file_path": Path("assets/bgm/track.mp3"),
            "title": "Track",
            "artist": "Artist",
            "source": "youtube_audio_library",
            "license_type": "standard",
            "attribution_required": False,
            "attribution_text": "Music: Track by Artist",
            "mood": "mysterious",
            "intensity": "low",
            "loopable": True,
            "duration_sec": 2.0,
        },
    )()
    result = build_bgm_render(_project()["bgm"], track, 5.0)
    assert result["volume_db"] == -22
    assert result["looped"] is True
    assert result["used_duration_sec"] == 5.0


def test_repair_log_helpers_preserve_schema_and_failure_mapping() -> None:
    repair = empty_repair_log({"id": "project"}, seed=7, max_attempts=2)
    failure = empty_failure_log()
    append_quality_failure(
        failure,
        2,
        [{"code": "VIDEO_BAD", "message": "bad", "auto_fixable": False}],
    )
    assert repair["schema_version"] == "repair-log-1.0.0"
    assert failure["failures"][0]["attempt"] == 2
    assert exit_code_from_failure({"category": "encoding_error"}) == 70
    assert check_summaries([{"code": "A", "level": "warning", "auto_fixable": 1}]) == [
        {"code": "A", "level": "warning", "auto_fixable": True, "target": None}
    ]


def test_analytics_presentation_keeps_console_contract() -> None:
    lines = format_console_summary(
        {
            "analyzed_video_count": 1,
            "video_count": 1,
            "start_date": "2026-07-01",
            "end_date": "2026-07-28",
            "totals": {"views": 42, "likes": 3, "comments": 1, "shares": 0, "estimated_minutes_watched": 1.5},
            "weighted_averages": {"average_view_duration": 2.5, "average_view_percentage": 50.0},
        }
    )
    assert lines[0] == "Analyzed videos: 1 / 1"
    assert "views=42" in lines[2]
