from __future__ import annotations

import json
import wave
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

import src.pipeline.render_project as render_module
from src.pipeline.render_project import render_project
from src.voice.duration import get_wav_duration


class FakeVoiceService:
    def __init__(self, durations: list[float]) -> None:
        self.durations = durations
        self.calls: list[tuple[str, str]] = []

    def synthesize_to_file(
        self,
        text: str,
        speaker: str | int,
        output_path: Path,
        speed_scale: float,
        pitch_scale: float,
        intonation_scale: float,
    ) -> Path:
        self.calls.append((text, str(speaker)))
        duration = self.durations.pop(0)
        _write_silent_wav(output_path, duration)
        return output_path


class NullConnection:
    def __enter__(self) -> "NullConnection":
        return self

    def __exit__(self, *args: object) -> None:
        return None


def _write_silent_wav(
    path: Path, duration_sec: float, *, framerate: int = 8000
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(framerate)
        wav.writeframes(b"\x00" * int(duration_sec * framerate) * 2)


def _project() -> dict[str, Any]:
    return {
        "schema_version": "youtube-1.0.0",
        "platform_profile": "youtube_shorts",
        "id": "voice_test_project",
        "topic": "Deep sea facts",
        "title": "Deep sea facts",
        "hook": "A short hook about the deep sea",
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
        "voice": {
            "engine": "aivis_speech",
            "speaker": "Anneli",
            "speed_scale": 1.0,
            "pitch_scale": 0.0,
            "intonation_scale": 1.0,
            "sentence_gap_ms": 200,
        },
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
            "source_priority": ["local"],
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
                "visual_query": "ocean",
                "estimated_duration_sec": 3.0,
                "caption_style_hint": "normal",
            },
            {
                "index": 2,
                "text": "Second sentence",
                "visual_query": "submarine",
                "estimated_duration_sec": 3.0,
                "caption_style_hint": "emphasis",
            },
            {
                "index": 3,
                "text": "Third sentence",
                "visual_query": "dark water",
                "estimated_duration_sec": 3.0,
                "caption_style_hint": "punchline",
            },
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
            "description_sections": {
                "summary": "Summary",
                "credits_policy": "include_bgm_credits_only",
                "disclaimer": "Check facts before publishing.",
            },
            "analytics_hypothesis": {
                "experiment_group": "voice_test",
                "hypothesis": "Short factual narration keeps viewers watching.",
                "primary_metric": "average_view_percentage",
                "secondary_metrics": ["views"],
            },
        },
        "manual_fact_check_required": True,
    }


def test_render_project_uses_actual_voice_durations_for_audio_and_subtitles(
    tmp_path: Path, monkeypatch
) -> None:
    project_path = tmp_path / "project.youtube.json"
    project_path.write_text(
        json.dumps(_project(), ensure_ascii=False), encoding="utf-8"
    )
    monkeypatch.setattr(render_module, "RENDERS_DIR", tmp_path / "renders")
    monkeypatch.setattr(render_module, "init_db", lambda: None)
    monkeypatch.setattr(render_module, "connect", lambda: NullConnection())
    monkeypatch.setattr(render_module, "list_active_bgm_tracks", lambda connection: [])
    monkeypatch.setattr(
        render_module, "list_active_media_assets", lambda connection: []
    )
    monkeypatch.setattr(render_module, "upsert_project", lambda *args: None)
    monkeypatch.setattr(render_module, "insert_render_summary", lambda *args: None)
    voice_service = FakeVoiceService([1.0, 1.5, 2.0])

    rendered_path = render_project(project_path, voice_service=voice_service)

    rendered = json.loads(rendered_path.read_text(encoding="utf-8"))
    assert voice_service.calls == [
        ("First sentence", "Anneli"),
        ("Second sentence", "Anneli"),
        ("Third sentence", "Anneli"),
    ]
    audio_dir = rendered_path.parent / "audio"
    assert (audio_dir / "001.wav").exists()
    assert get_wav_duration(audio_dir / "narration.wav") == 4.9
    assert [
        item["actual_duration_sec"] for item in rendered["audio"]["narration_files"]
    ] == [1.0, 1.5, 2.0]
    assert [
        (item["start_sec"], item["end_sec"]) for item in rendered["subtitles"]["items"]
    ] == [(0.0, 1.0), (1.2, 2.7), (2.9, 4.9)]
    Draft202012Validator(
        json.loads(
            Path("schemas/rendered.youtube.schema.json").read_text(encoding="utf-8")
        )
    ).validate(rendered)


def test_render_project_prefers_voice_style_id_when_present(
    tmp_path: Path, monkeypatch
) -> None:
    project = _project()
    project["voice"]["style_id"] = 888753760
    project_path = tmp_path / "project.youtube.json"
    project_path.write_text(json.dumps(project, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(render_module, "RENDERS_DIR", tmp_path / "renders")
    monkeypatch.setattr(render_module, "init_db", lambda: None)
    monkeypatch.setattr(render_module, "connect", lambda: NullConnection())
    monkeypatch.setattr(render_module, "list_active_bgm_tracks", lambda connection: [])
    monkeypatch.setattr(
        render_module, "list_active_media_assets", lambda connection: []
    )
    monkeypatch.setattr(render_module, "upsert_project", lambda *args: None)
    monkeypatch.setattr(render_module, "insert_render_summary", lambda *args: None)
    voice_service = FakeVoiceService([1.0, 1.0, 1.0])

    rendered_path = render_project(project_path, voice_service=voice_service)

    rendered = json.loads(rendered_path.read_text(encoding="utf-8"))
    assert voice_service.calls == [
        ("First sentence", "888753760"),
        ("Second sentence", "888753760"),
        ("Third sentence", "888753760"),
    ]
    assert rendered["voice"]["speaker"] == "Anneli"
    assert rendered["voice"]["style_id"] == 888753760
