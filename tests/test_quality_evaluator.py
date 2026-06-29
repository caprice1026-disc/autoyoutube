from __future__ import annotations

import json
import sys
from pathlib import Path

import src.main as main_module


def _rendered(render_dir: Path) -> dict:
    return {
        "schema_version": "rendered-youtube-1.0.0",
        "platform_profile": "youtube_shorts",
        "project_id": "quality_project",
        "render_id": "render_quality",
        "status": "success",
        "created_at": "2026-06-29T00:00:00Z",
        "completed_at": "2026-06-29T00:00:00Z",
        "input": {
            "project_json_path": "projects/sample/project.youtube.json",
            "project_json_hash": f"sha256:{'a' * 64}",
            "project_schema_path": "schemas/project.youtube.schema.json",
        },
        "output": {
            "video_path": str(render_dir / "output.mp4"),
            "thumbnail_path": str(render_dir / "thumbnail.jpg"),
            "subtitle_ass_path": str(render_dir / "subtitle.ass"),
            "description_path": str(render_dir / "description.txt"),
            "credits_path": str(render_dir / "credits.txt"),
            "rendered_json_path": str(render_dir / "rendered.youtube.json"),
            "logs_dir": str(render_dir / "logs"),
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
        "voice": {
            "engine": "aivis_speech",
            "speaker": "まお",
            "style_id": 888753760,
            "speed_scale": 1.0,
            "pitch_scale": 0.0,
            "intonation_scale": 1.0,
            "sentence_gap_ms": 180,
            "sample_rate": 44100,
            "audio_format": "wav",
        },
        "audio": {
            "narration_files": [],
            "merged_narration_path": str(render_dir / "audio" / "narration.wav"),
            "merged_narration_duration_sec": 3.0,
            "final_audio_path": str(render_dir / "audio" / "final_audio.wav"),
            "final_audio_duration_sec": 3.0,
            "loudness_normalization": {"enabled": False},
        },
        "bgm": {
            "enabled": True,
            "strategy": "youtube_safe_bgm",
            "track_id": "mystery_low",
            "file_path": str(render_dir / "bgm.mp3"),
            "title": "Mystery Low",
            "artist": "Local",
            "source": "youtube_audio_library",
            "license_type": "youtube_audio_library_standard",
            "attribution_required": False,
            "attribution_text": "Music: Mystery Low by Local",
            "mood": "mysterious",
            "intensity": "low",
            "volume_db": -26,
            "fade_in_ms": 500,
            "fade_out_ms": 1200,
            "looped": False,
            "used_start_sec": 0,
            "used_duration_sec": 3.0,
        },
        "visuals": [
            {
                "index": 1,
                "script_index": 1,
                "visual_query": "deep ocean",
                "source": "pexels",
                "asset_id": "pexels_ocean",
                "pexels_id": "12345",
                "photographer": "Ocean Creator",
                "photographer_url": "https://www.pexels.com/@ocean-creator",
                "pexels_url": "https://www.pexels.com/video/deep-ocean-12345/",
                "original_video_url": "https://videos.pexels.com/video-files/12345/hd.mp4",
                "local_file_path": str(render_dir / "video.mp4"),
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
                "used_start_sec": 0,
                "used_duration_sec": 3.0,
                "video_start_sec": 0,
                "video_end_sec": 3.0,
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
                    "text": "これは三十二文字を大きく超える長い字幕テキストです。さらに長くします。",
                    "start_sec": 0.0,
                    "end_sec": 3.0,
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
                "credits_policy": "include_pexels_and_bgm_credits",
                "disclaimer": "Check facts.",
            },
            "analytics_hypothesis": {
                "experiment_group": "sample",
                "hypothesis": "Hook improves retention.",
                "primary_metric": "average_view_percentage",
                "secondary_metrics": ["views"],
            },
            "description_path": str(render_dir / "description.txt"),
            "upload": {"planned": False, "status": "not_uploaded"},
        },
        "thumbnail": {"generated": False},
        "credits": {
            "required": True,
            "items": [],
            "description_text": "",
        },
        "ffmpeg": {
            "version": "ffmpeg version 8",
            "command_log_path": str(render_dir / "logs" / "ffmpeg_command.txt"),
            "stderr_log_path": str(render_dir / "logs" / "ffmpeg_stderr.log"),
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


def test_evaluate_render_writes_quality_report_with_initial_checks(
    tmp_path: Path,
) -> None:
    from src.quality.evaluator import evaluate_render

    render_dir = tmp_path / "render"
    (render_dir / "logs").mkdir(parents=True)
    (render_dir / "output.mp4").write_bytes(b"fake mp4")
    (render_dir / "bgm.mp3").write_bytes(b"fake bgm")
    (render_dir / "video.mp4").write_bytes(b"fake video")
    (render_dir / "subtitle.ass").write_text("subtitle", encoding="utf-8")
    (render_dir / "description.txt").write_text("description", encoding="utf-8")
    (render_dir / "credits.txt").write_text("", encoding="utf-8")
    (render_dir / "logs" / "ffmpeg_command.txt").write_text("ffmpeg", encoding="utf-8")
    (render_dir / "logs" / "ffmpeg_stderr.log").write_text("", encoding="utf-8")
    rendered_path = render_dir / "rendered.youtube.json"
    rendered_path.write_text(
        json.dumps(_rendered(render_dir), ensure_ascii=False), encoding="utf-8"
    )

    report = evaluate_render(rendered_path)

    assert report["project_id"] == "quality_project"
    assert report["render_id"] == "render_quality"
    assert report["status"] == "error"
    assert {check["code"] for check in report["checks"]} == {
        "BGM_CREDIT_MISSING",
        "PEXELS_CREDIT_MISSING",
        "SUBTITLE_TOO_LONG",
    }
    assert report["metrics"]["has_bgm"] is True
    assert report["metrics"]["has_pexels_visual"] is True
    assert report["metrics"]["max_subtitle_chars"] > 32
    written = json.loads(
        (render_dir / "quality_report.json").read_text(encoding="utf-8")
    )
    assert written == report


def test_evaluate_render_reports_missing_and_empty_files(tmp_path: Path) -> None:
    from src.quality.evaluator import evaluate_render

    render_dir = tmp_path / "render"
    render_dir.mkdir()
    (render_dir / "output.mp4").write_bytes(b"")
    rendered = _rendered(render_dir)
    rendered_path = render_dir / "rendered.youtube.json"
    rendered_path.write_text(json.dumps(rendered, ensure_ascii=False), encoding="utf-8")

    report = evaluate_render(rendered_path)

    codes = {check["code"] for check in report["checks"]}
    assert "FILE_MISSING" in codes
    assert "OUTPUT_VIDEO_EMPTY" in codes


def test_evaluate_render_cli_prints_report_path(
    monkeypatch, capsys, tmp_path: Path
) -> None:
    render_dir = tmp_path / "render"
    render_dir.mkdir()
    rendered_path = render_dir / "rendered.youtube.json"
    rendered_path.write_text(
        json.dumps(_rendered(render_dir), ensure_ascii=False), encoding="utf-8"
    )
    monkeypatch.setattr(sys, "argv", ["tsm", "evaluate-render", str(rendered_path)])

    exit_code = main_module.main()

    captured = capsys.readouterr()
    assert exit_code == 0
    assert (
        f"Quality report written: {render_dir / 'quality_report.json'}" in captured.out
    )
