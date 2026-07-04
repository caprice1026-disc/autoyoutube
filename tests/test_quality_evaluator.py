from __future__ import annotations

import json
import sys
import wave
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


def _write_wav(
    path: Path,
    samples: list[int],
    *,
    sample_rate: int = 44100,
    channels: int = 1,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(channels)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        frames = b"".join(
            sample.to_bytes(2, "little", signed=True) for sample in samples
        )
        wav.writeframes(frames)


def _write_constant_wav(
    path: Path,
    *,
    duration_sec: float = 3.0,
    sample_rate: int = 44100,
    amplitude: int = 12000,
) -> None:
    frame_count = int(duration_sec * sample_rate)
    _write_wav(path, [amplitude] * frame_count, sample_rate=sample_rate)


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
    _write_constant_wav(render_dir / "audio" / "final_audio.wav")
    rendered_path = render_dir / "rendered.youtube.json"
    rendered_path.write_text(
        json.dumps(_rendered(render_dir), ensure_ascii=False), encoding="utf-8"
    )

    report = evaluate_render(
        rendered_path,
        video_probe=lambda _path: {
            "duration_sec": 3.0,
            "width": 1080,
            "height": 1920,
            "fps": 30.0,
        },
    )

    assert report["project_id"] == "quality_project"
    assert report["render_id"] == "render_quality"
    assert report["status"] == "error"
    assert report["summary"] == {
        "status": "error",
        "error_count": 2,
        "warning_count": 1,
        "info_count": 0,
    }
    assert {check["code"] for check in report["checks"]} == {
        "BGM_CREDIT_MISSING",
        "PEXELS_CREDIT_MISSING",
        "SUBTITLE_TOO_LONG",
    }
    assert report["metrics"]["has_bgm"] is True
    assert report["metrics"]["has_pexels_visual"] is True
    assert report["metrics"]["max_subtitle_chars"] > 32
    assert report["metrics"]["video_duration_sec"] == 3.0
    assert report["metrics"]["video_width"] == 1080
    assert report["metrics"]["video_height"] == 1920
    assert all("auto_fixable" in check for check in report["checks"])
    assert all("codex_hint" in check for check in report["checks"])
    written = json.loads(
        (render_dir / "quality_report.json").read_text(encoding="utf-8")
    )
    assert written == report


def test_evaluate_render_does_not_require_manual_review(tmp_path: Path) -> None:
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
    _write_constant_wav(render_dir / "audio" / "final_audio.wav")
    rendered = _rendered(render_dir)
    del rendered["manual_review"]
    rendered_path = render_dir / "rendered.youtube.json"
    rendered_path.write_text(json.dumps(rendered, ensure_ascii=False), encoding="utf-8")

    report = evaluate_render(
        rendered_path,
        video_probe=lambda _path: {
            "duration_sec": 3.0,
            "width": 1080,
            "height": 1920,
            "fps": 30.0,
        },
    )

    assert "MANUAL_REVIEW_REQUIRED" not in {check["code"] for check in report["checks"]}


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


def test_evaluate_render_reports_invalid_video_dimensions(tmp_path: Path) -> None:
    from src.quality.evaluator import evaluate_render

    render_dir = tmp_path / "render"
    (render_dir / "logs").mkdir(parents=True)
    (render_dir / "output.mp4").write_bytes(b"fake mp4")
    (render_dir / "bgm.mp3").write_bytes(b"fake bgm")
    (render_dir / "video.mp4").write_bytes(b"fake video")
    (render_dir / "subtitle.ass").write_text("subtitle", encoding="utf-8")
    (render_dir / "description.txt").write_text("description", encoding="utf-8")
    (render_dir / "credits.txt").write_text("credits", encoding="utf-8")
    (render_dir / "logs" / "ffmpeg_command.txt").write_text("ffmpeg", encoding="utf-8")
    (render_dir / "logs" / "ffmpeg_stderr.log").write_text("", encoding="utf-8")
    _write_constant_wav(render_dir / "audio" / "final_audio.wav")
    rendered_path = render_dir / "rendered.youtube.json"
    rendered = _rendered(render_dir)
    rendered["credits"]["items"] = [
        {"credit_type": "bgm", "source": "youtube_audio_library", "text": "BGM"},
        {"credit_type": "video", "source": "pexels", "text": "Video"},
    ]
    rendered_path.write_text(json.dumps(rendered, ensure_ascii=False), encoding="utf-8")

    report = evaluate_render(
        rendered_path,
        video_probe=lambda _path: {
            "duration_sec": 3.0,
            "width": 720,
            "height": 1280,
            "fps": 30.0,
        },
    )

    assert "VIDEO_DIMENSION_INVALID" in {check["code"] for check in report["checks"]}
    assert report["status"] == "error"
    assert report["metrics"]["video_width"] == 720
    assert report["metrics"]["video_height"] == 1280


def test_evaluate_render_reports_video_duration_mismatch(tmp_path: Path) -> None:
    from src.quality.evaluator import evaluate_render

    render_dir = tmp_path / "render"
    (render_dir / "logs").mkdir(parents=True)
    (render_dir / "output.mp4").write_bytes(b"fake mp4")
    (render_dir / "bgm.mp3").write_bytes(b"fake bgm")
    (render_dir / "video.mp4").write_bytes(b"fake video")
    (render_dir / "subtitle.ass").write_text("subtitle", encoding="utf-8")
    (render_dir / "description.txt").write_text("description", encoding="utf-8")
    (render_dir / "credits.txt").write_text("credits", encoding="utf-8")
    (render_dir / "logs" / "ffmpeg_command.txt").write_text("ffmpeg", encoding="utf-8")
    (render_dir / "logs" / "ffmpeg_stderr.log").write_text("", encoding="utf-8")
    _write_constant_wav(render_dir / "audio" / "final_audio.wav")
    rendered_path = render_dir / "rendered.youtube.json"
    rendered = _rendered(render_dir)
    rendered["credits"]["items"] = [
        {"credit_type": "bgm", "source": "youtube_audio_library", "text": "BGM"},
        {"credit_type": "video", "source": "pexels", "text": "Video"},
    ]
    rendered_path.write_text(json.dumps(rendered, ensure_ascii=False), encoding="utf-8")

    report = evaluate_render(
        rendered_path,
        video_probe=lambda _path: {
            "duration_sec": 5.2,
            "width": 1080,
            "height": 1920,
            "fps": 30.0,
        },
    )

    assert "VIDEO_DURATION_MISMATCH" in {check["code"] for check in report["checks"]}
    assert report["status"] == "warning"
    assert report["metrics"]["rendered_duration_sec"] == 3.0
    assert report["metrics"]["video_duration_sec"] == 5.2
    assert report["metrics"]["duration_diff_sec"] == 2.2


def test_evaluate_render_reports_shorts_duration_exceeded(tmp_path: Path) -> None:
    from src.quality.evaluator import evaluate_render

    render_dir = tmp_path / "render"
    (render_dir / "logs").mkdir(parents=True)
    (render_dir / "output.mp4").write_bytes(b"fake mp4")
    (render_dir / "bgm.mp3").write_bytes(b"fake bgm")
    (render_dir / "video.mp4").write_bytes(b"fake video")
    (render_dir / "subtitle.ass").write_text("subtitle", encoding="utf-8")
    (render_dir / "description.txt").write_text("description", encoding="utf-8")
    (render_dir / "credits.txt").write_text("credits", encoding="utf-8")
    (render_dir / "logs" / "ffmpeg_command.txt").write_text("ffmpeg", encoding="utf-8")
    (render_dir / "logs" / "ffmpeg_stderr.log").write_text("", encoding="utf-8")
    _write_constant_wav(render_dir / "audio" / "final_audio.wav", duration_sec=65.0)
    rendered_path = render_dir / "rendered.youtube.json"
    rendered = _rendered(render_dir)
    rendered["target"]["actual_duration_sec"] = 65.0
    rendered["audio"]["final_audio_duration_sec"] = 65.0
    rendered["credits"]["items"] = [
        {"credit_type": "bgm", "source": "youtube_audio_library", "text": "BGM"},
        {"credit_type": "video", "source": "pexels", "text": "Video"},
    ]
    rendered_path.write_text(json.dumps(rendered, ensure_ascii=False), encoding="utf-8")

    report = evaluate_render(
        rendered_path,
        video_probe=lambda _path: {
            "duration_sec": 65.0,
            "width": 1080,
            "height": 1920,
            "fps": 30.0,
        },
    )

    checks = {check["code"]: check for check in report["checks"]}
    assert "VIDEO_DURATION_TOO_LONG" in checks
    assert checks["VIDEO_DURATION_TOO_LONG"]["level"] == "warning"
    assert checks["VIDEO_DURATION_TOO_LONG"]["metrics"] == {
        "duration_sec": 65.0,
        "max_duration_sec": 60.0,
    }
    assert checks["VIDEO_DURATION_TOO_LONG"]["auto_fixable"] is True


def test_evaluate_render_counts_wrapped_subtitle_lines(tmp_path: Path) -> None:
    from src.quality.evaluator import evaluate_render

    render_dir = tmp_path / "render"
    (render_dir / "logs").mkdir(parents=True)
    (render_dir / "output.mp4").write_bytes(b"fake mp4")
    (render_dir / "bgm.mp3").write_bytes(b"fake bgm")
    (render_dir / "video.mp4").write_bytes(b"fake video")
    (render_dir / "subtitle.ass").write_text("subtitle", encoding="utf-8")
    (render_dir / "description.txt").write_text("description", encoding="utf-8")
    (render_dir / "credits.txt").write_text("credits", encoding="utf-8")
    (render_dir / "logs" / "ffmpeg_command.txt").write_text("ffmpeg", encoding="utf-8")
    (render_dir / "logs" / "ffmpeg_stderr.log").write_text("", encoding="utf-8")
    rendered_path = render_dir / "rendered.youtube.json"
    rendered = _rendered(render_dir)
    rendered["credits"]["items"] = [
        {"credit_type": "bgm", "source": "youtube_audio_library", "text": "BGM"},
        {"credit_type": "video", "source": "pexels", "text": "Video"},
    ]
    rendered["subtitles"]["items"][0]["text"] = (
        "たとえばチョウチンアンコウは、\\N頭の先にある光で小さな魚を誘います。"
    )
    rendered_path.write_text(json.dumps(rendered, ensure_ascii=False), encoding="utf-8")

    report = evaluate_render(
        rendered_path,
        video_probe=lambda _path: {
            "duration_sec": 3.0,
            "width": 1080,
            "height": 1920,
            "fps": 30.0,
        },
    )

    assert "SUBTITLE_TOO_LONG" not in {check["code"] for check in report["checks"]}
    assert report["metrics"]["max_subtitle_chars"] == 18


def test_evaluate_render_reports_subtitle_speed_and_line_count(
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
    (render_dir / "credits.txt").write_text("credits", encoding="utf-8")
    (render_dir / "logs" / "ffmpeg_command.txt").write_text("ffmpeg", encoding="utf-8")
    (render_dir / "logs" / "ffmpeg_stderr.log").write_text("", encoding="utf-8")
    _write_constant_wav(render_dir / "audio" / "final_audio.wav")
    rendered = _rendered(render_dir)
    rendered["credits"]["items"] = [
        {"credit_type": "bgm", "source": "youtube_audio_library", "text": "BGM"},
        {"credit_type": "video", "source": "pexels", "text": "Video"},
    ]
    rendered["subtitles"]["items"][0]["text"] = "ABCDEFGHIJ\\NKLMNOPQRST\\NUVWXYZABCD"
    rendered["subtitles"]["items"][0]["start_sec"] = 0.0
    rendered["subtitles"]["items"][0]["end_sec"] = 1.0
    rendered_path = render_dir / "rendered.youtube.json"
    rendered_path.write_text(json.dumps(rendered, ensure_ascii=False), encoding="utf-8")

    report = evaluate_render(
        rendered_path,
        video_probe=lambda _path: {
            "duration_sec": 3.0,
            "width": 1080,
            "height": 1920,
            "fps": 30.0,
        },
    )

    checks = {check["code"]: check for check in report["checks"]}
    assert "SUBTITLE_CPS_TOO_HIGH" in checks
    assert checks["SUBTITLE_CPS_TOO_HIGH"]["auto_fixable"] is True
    assert checks["SUBTITLE_CPS_TOO_HIGH"]["metrics"]["chars_per_sec"] == 30.0
    assert "SUBTITLE_TOO_MANY_LINES" in checks
    assert report["metrics"]["max_subtitle_cps"] == 30.0
    assert report["metrics"]["max_subtitle_lines"] == 3


def test_evaluate_render_reports_audio_integrity_issues(tmp_path: Path) -> None:
    from src.quality.evaluator import evaluate_render

    render_dir = tmp_path / "render"
    (render_dir / "logs").mkdir(parents=True)
    (render_dir / "output.mp4").write_bytes(b"fake mp4")
    (render_dir / "bgm.mp3").write_bytes(b"fake bgm")
    (render_dir / "video.mp4").write_bytes(b"fake video")
    (render_dir / "subtitle.ass").write_text("subtitle", encoding="utf-8")
    (render_dir / "description.txt").write_text("description", encoding="utf-8")
    (render_dir / "credits.txt").write_text("credits", encoding="utf-8")
    (render_dir / "logs" / "ffmpeg_command.txt").write_text("ffmpeg", encoding="utf-8")
    (render_dir / "logs" / "ffmpeg_stderr.log").write_text("", encoding="utf-8")
    final_samples = [0] * 24000 + [32767] * 21000
    _write_wav(render_dir / "audio" / "final_audio.wav", final_samples)
    _write_constant_wav(
        render_dir / "audio" / "001.wav", duration_sec=1.0, sample_rate=22050
    )
    rendered = _rendered(render_dir)
    rendered["credits"]["items"] = [
        {"credit_type": "bgm", "source": "youtube_audio_library", "text": "BGM"},
        {"credit_type": "video", "source": "pexels", "text": "Video"},
    ]
    rendered["audio"]["final_audio_duration_sec"] = 1.0
    rendered["audio"]["narration_files"] = [
        {
            "index": 1,
            "text": "sample",
            "path": str(render_dir / "audio" / "001.wav"),
            "estimated_duration_sec": 1.0,
            "actual_duration_sec": 1.0,
            "start_sec": 0.0,
            "end_sec": 1.0,
        }
    ]
    rendered_path = render_dir / "rendered.youtube.json"
    rendered_path.write_text(json.dumps(rendered, ensure_ascii=False), encoding="utf-8")

    report = evaluate_render(
        rendered_path,
        video_probe=lambda _path: {
            "duration_sec": 3.0,
            "width": 1080,
            "height": 1920,
            "fps": 30.0,
        },
    )

    codes = {check["code"] for check in report["checks"]}
    assert "OPENING_NO_AUDIO" in codes
    assert "AUDIO_CLIPPING" in codes
    assert "FINAL_AUDIO_DURATION_MISMATCH" in codes
    assert "AUDIO_SAMPLE_RATE_MISMATCH" in codes
    assert report["metrics"]["final_audio_sample_rate"] == 44100
    assert report["metrics"]["final_audio_peak_dbfs"] == 0.0


def test_evaluate_render_reports_ffmpeg_and_visual_metadata_issues(
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
    (render_dir / "credits.txt").write_text("credits", encoding="utf-8")
    (render_dir / "logs" / "ffmpeg_command.txt").write_text("ffmpeg", encoding="utf-8")
    (render_dir / "logs" / "ffmpeg_stderr.log").write_text(
        "deprecated pixel format used\n"
        "fontselect: (Noto Sans CJK JP, 400, 0) -> ArialMT, 0, ArialMT\n",
        encoding="utf-8",
    )
    _write_constant_wav(render_dir / "audio" / "final_audio.wav")
    rendered = _rendered(render_dir)
    rendered["credits"]["items"] = [
        {"credit_type": "bgm", "source": "youtube_audio_library", "text": "BGM"},
        {"credit_type": "video", "source": "pexels", "text": "Video"},
    ]
    rendered["visuals"][0]["original_width"] = 640
    rendered["visuals"][0]["original_height"] = 360
    rendered["visuals"].append({**rendered["visuals"][0], "index": 2})
    rendered_path = render_dir / "rendered.youtube.json"
    rendered_path.write_text(json.dumps(rendered, ensure_ascii=False), encoding="utf-8")

    report = evaluate_render(
        rendered_path,
        video_probe=lambda _path: {
            "duration_sec": 3.0,
            "width": 1080,
            "height": 1920,
            "fps": 30.0,
        },
    )

    codes = {check["code"] for check in report["checks"]}
    assert "FFMPEG_WARNING_DETECTED" in codes
    assert "FONT_FALLBACK_DETECTED" in codes
    assert "SOURCE_RESOLUTION_TOO_LOW" in codes
    assert "SAME_ASSET_CONSECUTIVE" in codes


def test_evaluate_render_reports_reused_visual_asset_within_render(
    tmp_path: Path,
) -> None:
    from src.quality.evaluator import evaluate_render

    render_dir = tmp_path / "render"
    (render_dir / "logs").mkdir(parents=True)
    (render_dir / "output.mp4").write_bytes(b"fake mp4")
    (render_dir / "bgm.mp3").write_bytes(b"fake bgm")
    (render_dir / "video_a.mp4").write_bytes(b"fake video a")
    (render_dir / "video_b.mp4").write_bytes(b"fake video b")
    (render_dir / "subtitle.ass").write_text("subtitle", encoding="utf-8")
    (render_dir / "description.txt").write_text("description", encoding="utf-8")
    (render_dir / "credits.txt").write_text("credits", encoding="utf-8")
    (render_dir / "logs" / "ffmpeg_command.txt").write_text("ffmpeg", encoding="utf-8")
    (render_dir / "logs" / "ffmpeg_stderr.log").write_text("", encoding="utf-8")
    _write_constant_wav(render_dir / "audio" / "final_audio.wav")
    rendered = _rendered(render_dir)
    rendered["credits"]["items"] = [
        {"credit_type": "bgm", "source": "youtube_audio_library", "text": "BGM"},
        {"credit_type": "video", "source": "pexels", "text": "Video"},
    ]
    rendered["subtitles"]["items"][0]["text"] = "short"
    first_visual = {
        **rendered["visuals"][0],
        "index": 1,
        "asset_id": "pexels_ocean_a",
        "local_file_path": str(render_dir / "video_a.mp4"),
    }
    second_visual = {
        **rendered["visuals"][0],
        "index": 2,
        "script_index": 2,
        "asset_id": "pexels_ocean_b",
        "local_file_path": str(render_dir / "video_b.mp4"),
    }
    third_visual = {
        **rendered["visuals"][0],
        "index": 3,
        "script_index": 3,
        "asset_id": "pexels_ocean_a",
        "local_file_path": str(render_dir / "video_a.mp4"),
    }
    rendered["visuals"] = [first_visual, second_visual, third_visual]
    rendered_path = render_dir / "rendered.youtube.json"
    rendered_path.write_text(json.dumps(rendered, ensure_ascii=False), encoding="utf-8")

    report = evaluate_render(
        rendered_path,
        video_probe=lambda _path: {
            "duration_sec": 3.0,
            "width": 1080,
            "height": 1920,
            "fps": 30.0,
        },
    )

    checks = {check["code"]: check for check in report["checks"]}
    assert "SAME_ASSET_REUSED" in checks
    assert "SAME_ASSET_CONSECUTIVE" not in checks
    assert checks["SAME_ASSET_REUSED"]["metrics"] == {
        "asset_id": "pexels_ocean_a",
        "first_index": 0,
        "current_index": 2,
    }


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
