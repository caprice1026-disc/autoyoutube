from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT_DIR = Path(__file__).resolve().parent.parent
PROJECT_SCHEMA_PATH = ROOT_DIR / "schemas" / "project.youtube.schema.json"
RENDERED_SCHEMA_PATH = ROOT_DIR / "schemas" / "rendered.youtube.schema.json"
SAMPLE_PROJECT_PATH = (
    ROOT_DIR / "projects" / "trivia_submarine_black_001" / "project.youtube.json"
)


def _load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as file:
        return json.load(file)


def test_youtube_schema_files_are_valid_draft_2020_12() -> None:
    """YouTube用JSON Schema自体がDraft 2020-12として有効であることを確認する。"""
    for schema_path in [PROJECT_SCHEMA_PATH, RENDERED_SCHEMA_PATH]:
        Draft202012Validator.check_schema(_load_json(schema_path))


def test_sample_project_matches_project_schema() -> None:
    """同梱サンプルのproject.youtube.jsonが整形済みスキーマで検証できることを確認する。"""
    schema = _load_json(PROJECT_SCHEMA_PATH)
    project = _load_json(SAMPLE_PROJECT_PATH)

    Draft202012Validator(schema).validate(project)


def test_project_schema_rejects_unexpected_property() -> None:
    """additionalProperties=falseの制約が期待どおり余分な項目を拒否することを確認する。"""
    schema = _load_json(PROJECT_SCHEMA_PATH)
    project = _load_json(SAMPLE_PROJECT_PATH)
    project["unexpected_field"] = "許可されていない項目です"

    errors = list(Draft202012Validator(schema).iter_errors(project))

    assert errors
    assert any(error.validator == "additionalProperties" for error in errors)


def test_project_schema_accepts_optional_voice_style_id() -> None:
    schema = _load_json(PROJECT_SCHEMA_PATH)
    project = _load_json(SAMPLE_PROJECT_PATH)
    project["voice"]["style_id"] = 888753760

    Draft202012Validator(schema).validate(project)


def test_rendered_schema_requires_narration_file_fields() -> None:
    schema = _load_json(RENDERED_SCHEMA_PATH)
    rendered = _valid_rendered_json()
    del rendered["audio"]["narration_files"][0]["actual_duration_sec"]

    errors = list(Draft202012Validator(schema).iter_errors(rendered))

    assert errors
    assert any("actual_duration_sec" in error.message for error in errors)


def test_rendered_schema_requires_visual_fields() -> None:
    schema = _load_json(RENDERED_SCHEMA_PATH)
    rendered = _valid_rendered_json()
    del rendered["visuals"][0]["transform"]

    errors = list(Draft202012Validator(schema).iter_errors(rendered))

    assert errors
    assert any("transform" in error.message for error in errors)


def test_rendered_schema_requires_pexels_metadata_for_pexels_visuals() -> None:
    schema = _load_json(RENDERED_SCHEMA_PATH)
    rendered = _valid_rendered_json()
    rendered["visuals"][0]["source"] = "pexels"
    rendered["visuals"][0].update(
        {
            "pexels_id": "20349819",
            "photographer": "Pexels Creator",
            "photographer_url": "https://www.pexels.com/@creator",
            "pexels_url": "https://www.pexels.com/video/deep-ocean-20349819/",
            "original_video_url": "https://videos.pexels.com/video-files/hd.mp4",
        }
    )
    del rendered["visuals"][0]["pexels_id"]

    errors = list(Draft202012Validator(schema).iter_errors(rendered))

    assert errors
    assert any("pexels_id" in error.message for error in errors)


def test_rendered_schema_rejects_credit_type_alias() -> None:
    schema = _load_json(RENDERED_SCHEMA_PATH)
    rendered = _valid_rendered_json()
    rendered["credits"]["items"][0] = {
        "type": "bgm",
        "source": "local_original",
        "text": "BGM credit",
        "url": None,
    }

    errors = list(Draft202012Validator(schema).iter_errors(rendered))

    assert errors
    assert any(error.validator == "additionalProperties" for error in errors)


def test_rendered_schema_requires_validation_message_code_and_message() -> None:
    schema = _load_json(RENDERED_SCHEMA_PATH)
    rendered = _valid_rendered_json()
    rendered["validation"]["warnings"] = [{"code": "DRY_RUN_VOICE"}]

    errors = list(Draft202012Validator(schema).iter_errors(rendered))

    assert errors
    assert any("message" in error.message for error in errors)


def test_rendered_schema_allows_private_upload_without_manual_review() -> None:
    schema = _load_json(RENDERED_SCHEMA_PATH)
    rendered = _valid_rendered_json()
    del rendered["manual_review"]

    errors = list(Draft202012Validator(schema).iter_errors(rendered))

    assert errors == []


def test_rendered_schema_validates_legacy_manual_review_when_present() -> None:
    schema = _load_json(RENDERED_SCHEMA_PATH)
    rendered = _valid_rendered_json()
    del rendered["manual_review"]["publish_ready"]

    errors = list(Draft202012Validator(schema).iter_errors(rendered))

    assert errors
    assert any("publish_ready" in error.message for error in errors)


def _valid_rendered_json() -> dict:
    return {
        "schema_version": "rendered-youtube-1.0.0",
        "platform_profile": "youtube_shorts",
        "project_id": "sample_project",
        "render_id": "render_20260628_000000",
        "status": "success",
        "created_at": "2026-06-28T00:00:00Z",
        "completed_at": "2026-06-28T00:00:00Z",
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
            "actual_duration_sec": 10.5,
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
        "voice": {
            "engine": "aivis_speech",
            "speaker": "Anneli",
            "style_id": 888753760,
            "speed_scale": 1.0,
            "pitch_scale": 0.0,
            "intonation_scale": 1.0,
            "sentence_gap_ms": 180,
            "sample_rate": 44100,
            "audio_format": "wav",
        },
        "audio": {
            "narration_files": [
                {
                    "index": 1,
                    "text": "First sentence",
                    "path": "renders/sample/audio/001.wav",
                    "estimated_duration_sec": 3.0,
                    "actual_duration_sec": 2.9,
                    "start_sec": 0.0,
                    "end_sec": 2.9,
                }
            ],
            "merged_narration_path": "renders/sample/audio/narration.wav",
            "merged_narration_duration_sec": 10.5,
            "final_audio_path": "renders/sample/audio/final_audio.wav",
            "final_audio_duration_sec": 10.5,
            "loudness_normalization": {"enabled": False},
        },
        "bgm": {
            "enabled": True,
            "strategy": "youtube_safe_bgm",
            "track_id": "mystery_low",
            "file_path": "assets/bgm/mystery_low.wav",
            "title": "Mystery Low",
            "artist": "Local",
            "source": "local_original",
            "license_type": "local_safe",
            "attribution_required": True,
            "attribution_text": "BGM credit",
            "mood": "mysterious",
            "intensity": "low",
            "volume_db": -26,
            "fade_in_ms": 500,
            "fade_out_ms": 1200,
            "looped": False,
            "used_start_sec": 0,
            "used_duration_sec": 10.5,
        },
        "visuals": [
            {
                "index": 1,
                "script_index": 1,
                "visual_query": "deep ocean",
                "source": "local",
                "asset_id": "local_ocean",
                "local_file_path": "assets/local_media/ocean.mp4",
                "original_width": 1080,
                "original_height": 1920,
                "original_duration_sec": 8.0,
                "orientation": "portrait",
                "selected_quality": "hd",
                "transform": {
                    "type": "none",
                    "scale_width": 1080,
                    "scale_height": 1920,
                },
                "used_start_sec": 0.0,
                "used_duration_sec": 2.9,
                "video_start_sec": 0.0,
                "video_end_sec": 2.9,
            }
        ],
        "subtitles": {
            "format": "ass",
            "style": {
                "font_name": "Noto Sans CJK JP",
                "font_size": 72,
                "primary_color": "FFFFFF",
                "outline_color": "000000",
                "outline": 5,
                "shadow": 1,
                "alignment": "bottom_center",
                "margin_v": 220,
            },
            "items": [
                {
                    "index": 1,
                    "text": "First sentence",
                    "start_sec": 0.0,
                    "end_sec": 2.9,
                    "caption_style_hint": "normal",
                }
            ],
        },
        "youtube": {
            "title": "Sample #Shorts",
            "description": "Description",
            "hashtags": ["#Shorts"],
            "tags": ["sample"],
            "category_hint": "education",
            "privacy_status": "private",
            "made_for_kids": False,
            "contains_synthetic_voice": True,
            "description_sections": {
                "summary": "Summary",
                "credits_policy": "include_bgm_credits_only",
                "disclaimer": "Check facts.",
            },
            "analytics_hypothesis": {
                "experiment_group": "sample",
                "hypothesis": "Hook improves retention.",
                "primary_metric": "average_view_percentage",
                "secondary_metrics": ["views"],
            },
            "description_path": "renders/sample/description.txt",
            "upload": {
                "planned": False,
                "status": "not_uploaded",
            },
        },
        "thumbnail": {"generated": False},
        "credits": {
            "required": True,
            "items": [
                {
                    "credit_type": "bgm",
                    "source": "local_original",
                    "text": "BGM credit",
                    "url": None,
                }
            ],
            "description_text": "BGM credit\n",
        },
        "ffmpeg": {
            "version": "ffmpeg version 7",
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
            "warnings": [
                {
                    "code": "DRY_RUN_VOICE",
                    "message": "Silent placeholder WAV files were generated from estimated durations.",
                    "details": {},
                }
            ],
            "errors": [],
        },
        "manual_review": {
            "required": True,
            "fact_check_required": True,
            "checked": False,
            "publish_ready": False,
            "notes": "Manual fact check and quality review are required before publishing.",
        },
    }
