from __future__ import annotations

import json
import wave
from pathlib import Path
from typing import Any

from src.pipeline.render_project import render_project
import src.pipeline.render_project as render_module


class NullConnection:
    def __enter__(self) -> "NullConnection":
        return self

    def __exit__(self, *args: object) -> None:
        return None


class FakeVideoRenderer:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def render(
        self,
        *,
        render_dir: Path,
        duration_sec: float,
        target: dict[str, Any],
        logs_dir: Path,
    ) -> dict[str, Any]:
        self.calls.append({"render_dir": render_dir, "duration_sec": duration_sec, "target": target, "logs_dir": logs_dir})
        (render_dir / "output.mp4").write_bytes(b"fake mp4")
        (logs_dir / "ffmpeg_command.txt").write_text("ffmpeg fake\n", encoding="utf-8")
        (logs_dir / "ffmpeg_stderr.log").write_text("", encoding="utf-8")
        return {
            "rendered": True,
            "version": "ffmpeg test",
            "command_log_path": str(logs_dir / "ffmpeg_command.txt"),
            "stderr_log_path": str(logs_dir / "ffmpeg_stderr.log"),
        }


def _project() -> dict[str, Any]:
    return {
        "schema_version": "youtube-1.0.0",
        "platform_profile": "youtube_shorts",
        "id": "ffmpeg_test_project",
        "topic": "Deep sea facts",
        "title": "Deep sea facts",
        "hook": "A short hook about the deep sea",
        "target": {
            "duration_sec": 12,
            "aspect_ratio": "9:16",
            "resolution": {"width": 1080, "height": 1920},
            "fps": 30,
            "video_format": {"container": "mp4", "video_codec": "libx264", "audio_codec": "aac", "pix_fmt": "yuv420p"},
        },
        "voice": {"engine": "aivis_speech", "speaker": "Anneli", "speed_scale": 1.0, "pitch_scale": 0.0, "intonation_scale": 1.0, "sentence_gap_ms": 100},
        "bgm": {"enabled": True, "strategy": "youtube_safe_bgm", "mood": "mysterious", "intensity": "low", "volume_db": -26, "fade_in_ms": 500, "fade_out_ms": 1200, "allow_sources": ["youtube_audio_library"], "avoid": ["vocal"]},
        "visual_strategy": {"source_priority": ["local"], "preferred_orientation": "portrait", "fallback": "crop_landscape_to_9_16", "primary_query": "deep ocean", "fallback_queries": ["ocean"], "avoid_keywords": ["toy"]},
        "script": [
            {"index": 1, "text": "First sentence", "visual_query": "ocean", "estimated_duration_sec": 1.0, "caption_style_hint": "normal"},
            {"index": 2, "text": "Second sentence", "visual_query": "submarine", "estimated_duration_sec": 1.0, "caption_style_hint": "emphasis"},
            {"index": 3, "text": "Third sentence", "visual_query": "dark water", "estimated_duration_sec": 1.0, "caption_style_hint": "punchline"},
        ],
        "youtube": {
            "title": "Deep sea facts #Shorts",
            "description": "A short description",
            "hashtags": ["#Shorts"],
            "tags": ["deep sea"],
            "category_hint": "education",
            "privacy_status": "private",
            "made_for_kids": False,
            "contains_synthetic_voice": True,
            "description_sections": {"summary": "Summary", "credits_policy": "include_bgm_credits_only", "disclaimer": "Check facts before publishing."},
            "analytics_hypothesis": {"experiment_group": "ffmpeg_test", "hypothesis": "Short factual narration keeps viewers watching.", "primary_metric": "average_view_percentage", "secondary_metrics": ["views"]},
        },
        "manual_fact_check_required": True,
    }


def test_render_project_uses_video_renderer_and_marks_video_success(tmp_path: Path, monkeypatch) -> None:
    project_path = tmp_path / "project.youtube.json"
    project_path.write_text(json.dumps(_project(), ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(render_module, "RENDERS_DIR", tmp_path / "renders")
    monkeypatch.setattr(render_module, "init_db", lambda: None)
    monkeypatch.setattr(render_module, "connect", lambda: NullConnection())
    monkeypatch.setattr(render_module, "upsert_project", lambda *args: None)
    monkeypatch.setattr(render_module, "insert_render_summary", lambda *args: None)
    renderer = FakeVideoRenderer()

    rendered_path = render_project(project_path, video_renderer=renderer)

    rendered = json.loads(rendered_path.read_text(encoding="utf-8"))
    assert renderer.calls[0]["duration_sec"] == 3.2
    assert (rendered_path.parent / "output.mp4").read_bytes() == b"fake mp4"
    assert rendered["status"] == "success"
    assert rendered["ffmpeg"]["version"] == "ffmpeg test"
    assert rendered["validation"]["warnings"] == [{"code": "DRY_RUN_VOICE", "message": "Silent placeholder WAV files were generated from estimated durations."}]
