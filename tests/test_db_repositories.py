from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from src.db.database import init_db
from src.db.repositories import insert_render_summary, upsert_project


def _project(style_id: int | None = 888753760) -> dict[str, Any]:
    voice: dict[str, Any] = {
        "engine": "aivis_speech",
        "speaker": "まお",
        "speed_scale": 1.0,
        "pitch_scale": 0.0,
        "intonation_scale": 1.0,
        "sentence_gap_ms": 180,
    }
    if style_id is not None:
        voice["style_id"] = style_id
    return {
        "schema_version": "youtube-1.0.0",
        "platform_profile": "youtube_shorts",
        "id": "db_voice_project",
        "topic": "Deep sea facts",
        "title": "Deep sea facts",
        "hook": "A short hook",
        "target": {
            "duration_sec": 12,
            "aspect_ratio": "9:16",
            "resolution": {"width": 1080, "height": 1920},
            "fps": 30,
            "video_format": {
                "container": "mp4",
                "video_codec": "libx264",
                "audio_codec": "aac",
                "pix_fmt": "yuv420p",
            },
        },
        "voice": voice,
        "bgm": {
            "enabled": True,
            "strategy": "youtube_safe_bgm",
            "mood": "mysterious",
            "intensity": "low",
            "volume_db": -26,
            "fade_in_ms": 500,
            "fade_out_ms": 1200,
            "allow_sources": ["youtube_audio_library"],
            "avoid": ["vocal"],
        },
        "visual_strategy": {
            "source_priority": ["pexels"],
            "preferred_orientation": "portrait",
            "fallback": "crop_landscape_to_9_16",
            "primary_query": "deep ocean",
            "fallback_queries": ["ocean"],
            "avoid_keywords": ["toy"],
        },
        "script": [
            {
                "index": 1,
                "text": "First sentence",
                "visual_query": "deep ocean",
                "estimated_duration_sec": 3.0,
                "caption_style_hint": "normal",
            }
        ],
        "youtube": {
            "title": "Deep sea facts #Shorts",
            "description": "Description",
            "hashtags": ["#Shorts"],
            "tags": ["deep sea"],
            "category_hint": "education",
            "privacy_status": "private",
            "made_for_kids": False,
            "contains_synthetic_voice": True,
            "description_sections": {
                "summary": "Summary",
                "credits_policy": "include_pexels_and_bgm_credits",
                "disclaimer": "Check facts.",
            },
            "analytics_hypothesis": {
                "experiment_group": "db_test",
                "hypothesis": "Hook improves retention.",
                "primary_metric": "average_view_percentage",
                "secondary_metrics": ["views"],
            },
        },
        "manual_fact_check_required": True,
    }


def _rendered(project: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "rendered-youtube-1.0.0",
        "platform_profile": "youtube_shorts",
        "project_id": project["id"],
        "render_id": "render_db_voice",
        "status": "success",
        "created_at": "2026-06-29T00:00:00Z",
        "completed_at": "2026-06-29T00:00:00Z",
        "input": {
            "project_json_path": "projects/sample/project.youtube.json",
            "project_json_hash": f"sha256:{'a' * 64}",
            "project_schema_path": "schemas/project.youtube.schema.json",
        },
        "output": {
            "video_path": "renders/sample/output.mp4",
            "thumbnail_path": "renders/sample/thumbnail.jpg",
            "subtitle_ass_path": "renders/sample/subtitle.ass",
            "description_path": "renders/sample/description.txt",
            "credits_path": "renders/sample/credits.txt",
            "rendered_json_path": "renders/sample/rendered.youtube.json",
            "logs_dir": "renders/sample/logs",
        },
        "target": {
            "planned_duration_sec": 12,
            "actual_duration_sec": 3.0,
            "aspect_ratio": "9:16",
            "resolution": {"width": 1080, "height": 1920},
            "fps": 30,
            "video_format": {
                "container": "mp4",
                "video_codec": "libx264",
                "audio_codec": "aac",
                "pix_fmt": "yuv420p",
            },
        },
        "voice": {**project["voice"], "sample_rate": 44100, "audio_format": "wav"},
        "audio": {
            "narration_files": [],
            "merged_narration_path": "renders/sample/audio/narration.wav",
            "merged_narration_duration_sec": 3.0,
            "final_audio_path": "renders/sample/audio/final_audio.wav",
            "final_audio_duration_sec": 3.0,
            "loudness_normalization": {"enabled": False},
        },
        "bgm": {"enabled": False, "strategy": "none", "source": "none"},
        "visuals": [],
        "subtitles": {"format": "ass", "style": {}, "items": []},
        "youtube": {
            **project["youtube"],
            "description_path": "renders/sample/description.txt",
            "upload": {"planned": False, "status": "not_uploaded"},
        },
        "thumbnail": {"generated": False},
        "credits": {"required": False, "items": [], "description_text": ""},
        "ffmpeg": {
            "version": "ffmpeg version 8",
            "command_log_path": "renders/sample/logs/ffmpeg_command.txt",
            "stderr_log_path": "renders/sample/logs/ffmpeg_stderr.log",
            "video_codec": "libx264",
            "audio_codec": "aac",
            "pix_fmt": "yuv420p",
            "preset": "medium",
            "crf": 20,
        },
        "validation": {
            "project_json_valid": True,
            "rendered_json_valid": True,
            "warnings": [],
            "errors": [],
        },
        "manual_review": {
            "required": True,
            "fact_check_required": True,
            "checked": False,
            "publish_ready": False,
            "notes": "Manual review required.",
        },
    }


def test_upsert_project_saves_optional_voice_style_id(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    init_db(db_path)
    project = _project(style_id=888753760)

    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        upsert_project(
            connection, project, "projects/sample/project.youtube.json", "hash"
        )
        row = connection.execute(
            "SELECT voice_speaker, voice_style_id FROM youtube_projects WHERE id = ?",
            (project["id"],),
        ).fetchone()

    assert dict(row) == {"voice_speaker": "まお", "voice_style_id": 888753760}


def test_upsert_project_allows_missing_voice_style_id(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    init_db(db_path)
    project = _project(style_id=None)

    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        upsert_project(
            connection, project, "projects/sample/project.youtube.json", "hash"
        )
        row = connection.execute(
            "SELECT voice_style_id FROM youtube_projects WHERE id = ?",
            (project["id"],),
        ).fetchone()

    assert row["voice_style_id"] is None


def test_insert_render_summary_saves_voice_style_id(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    init_db(db_path)
    project = _project(style_id=888753760)
    rendered = _rendered(project)

    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        upsert_project(
            connection, project, "projects/sample/project.youtube.json", "hash"
        )
        insert_render_summary(connection, rendered)
        row = connection.execute(
            "SELECT speaker, voice_style_id FROM render_voice_settings WHERE render_id = ?",
            (rendered["render_id"],),
        ).fetchone()

    assert dict(row) == {"speaker": "まお", "voice_style_id": 888753760}
