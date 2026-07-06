from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from src.bgm.library import BgmTrack
from src.media.library import MediaAsset
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
        bgm: dict[str, Any] | None = None,
        visuals: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        self.calls.append(
            {
                "render_dir": render_dir,
                "duration_sec": duration_sec,
                "target": target,
                "logs_dir": logs_dir,
                "bgm": bgm,
                "visuals": visuals,
            }
        )
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
            "sentence_gap_ms": 100,
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
                "estimated_duration_sec": 1.0,
                "caption_style_hint": "normal",
            },
            {
                "index": 2,
                "text": "Second sentence",
                "visual_query": "submarine",
                "estimated_duration_sec": 1.0,
                "caption_style_hint": "emphasis",
            },
            {
                "index": 3,
                "text": "Third sentence",
                "visual_query": "dark water",
                "estimated_duration_sec": 1.0,
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
                "experiment_group": "ffmpeg_test",
                "hypothesis": "Short factual narration keeps viewers watching.",
                "primary_metric": "average_view_percentage",
                "secondary_metrics": ["views"],
            },
        },
        "manual_fact_check_required": True,
    }


def test_render_project_uses_video_renderer_and_marks_video_success(
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
    renderer = FakeVideoRenderer()

    rendered_path = render_project(project_path, video_renderer=renderer)

    rendered = json.loads(rendered_path.read_text(encoding="utf-8"))
    assert renderer.calls[0]["duration_sec"] == 3.2
    assert (rendered_path.parent / "output.mp4").read_bytes() == b"fake mp4"
    assert rendered["status"] == "success"
    assert "manual_review" not in rendered
    assert rendered["ffmpeg"]["version"] == "ffmpeg test"
    assert rendered["validation"]["warnings"] == [
        {
            "code": "DRY_RUN_VOICE",
            "message": "Silent placeholder WAV files were generated from estimated durations.",
        }
    ]


def test_render_project_saves_each_render_in_timestamped_title_directory(
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
    renderer = FakeVideoRenderer()

    rendered_path = render_project(project_path, video_renderer=renderer)

    assert rendered_path.name == "rendered.youtube.json"
    assert rendered_path.parent.parent == tmp_path / "renders"
    assert re.fullmatch(r"\d{12}-Deep sea facts", rendered_path.parent.name)
    rendered = json.loads(rendered_path.read_text(encoding="utf-8"))
    assert (
        rendered["output"]["rendered_json_path"]
        .replace("\\", "/")
        .endswith(f"{rendered_path.parent.name}/rendered.youtube.json")
    )


def test_render_project_can_write_to_explicit_render_directory(
    tmp_path: Path, monkeypatch
) -> None:
    project_path = tmp_path / "project.youtube.json"
    project_path.write_text(
        json.dumps(_project(), ensure_ascii=False), encoding="utf-8"
    )
    explicit_render_dir = tmp_path / "run" / "attempts" / "attempt_001"
    monkeypatch.setattr(render_module, "RENDERS_DIR", tmp_path / "renders")
    monkeypatch.setattr(render_module, "init_db", lambda: None)
    monkeypatch.setattr(render_module, "connect", lambda: NullConnection())
    monkeypatch.setattr(render_module, "list_active_bgm_tracks", lambda connection: [])
    monkeypatch.setattr(
        render_module, "list_active_media_assets", lambda connection: []
    )
    monkeypatch.setattr(render_module, "upsert_project", lambda *args: None)
    monkeypatch.setattr(render_module, "insert_render_summary", lambda *args: None)
    renderer = FakeVideoRenderer()

    rendered_path = render_project(
        project_path,
        video_renderer=renderer,
        render_dir=explicit_render_dir,
    )

    assert rendered_path == explicit_render_dir / "rendered.youtube.json"
    assert renderer.calls[0]["render_dir"] == explicit_render_dir
    rendered = json.loads(rendered_path.read_text(encoding="utf-8"))
    assert (
        rendered["output"]["video_path"]
        .replace("\\", "/")
        .endswith("run/attempts/attempt_001/output.mp4")
    )


def test_render_project_selects_bgm_and_passes_it_to_video_renderer(
    tmp_path: Path, monkeypatch
) -> None:
    project = _project()
    project["bgm"]["strategy"] = "local_safe_bgm"
    project["bgm"]["allow_sources"] = ["local_original"]
    project_path = tmp_path / "project.youtube.json"
    project_path.write_text(json.dumps(project, ensure_ascii=False), encoding="utf-8")
    bgm_path = tmp_path / "mystery.wav"
    bgm_path.write_bytes(b"fake wav")
    track = BgmTrack(
        track_id="mystery_low",
        file_path=bgm_path,
        title="Mystery Low",
        artist="Local",
        source="local_original",
        license_type="local_safe",
        attribution_required=True,
        attribution_text="BGM: Mystery Low by Local",
        mood="mysterious",
        intensity="low",
        duration_sec=20,
        bpm=90,
        loopable=True,
        allowed_platforms=["youtube_shorts"],
        used_count=0,
        is_active=True,
    )
    monkeypatch.setattr(render_module, "RENDERS_DIR", tmp_path / "renders")
    monkeypatch.setattr(render_module, "init_db", lambda: None)
    monkeypatch.setattr(render_module, "connect", lambda: NullConnection())
    monkeypatch.setattr(
        render_module, "list_active_bgm_tracks", lambda connection: [track]
    )
    monkeypatch.setattr(
        render_module, "list_active_media_assets", lambda connection: []
    )
    monkeypatch.setattr(render_module, "upsert_project", lambda *args: None)
    monkeypatch.setattr(render_module, "insert_render_summary", lambda *args: None)
    renderer = FakeVideoRenderer()

    rendered_path = render_project(project_path, video_renderer=renderer)

    rendered = json.loads(rendered_path.read_text(encoding="utf-8"))
    assert renderer.calls[0]["bgm"]["track_id"] == "mystery_low"
    assert renderer.calls[0]["bgm"]["file_path"] == str(bgm_path)
    assert renderer.calls[0]["bgm"]["volume_db"] == -26
    assert rendered["bgm"]["enabled"] is True
    assert rendered["bgm"]["track_id"] == "mystery_low"
    assert rendered["bgm"]["looped"] is False
    assert rendered["credits"]["required"] is True
    assert rendered["credits"]["items"] == [
        {
            "credit_type": "bgm",
            "source": "local_original",
            "text": "BGM: Mystery Low by Local",
            "url": None,
        }
    ]


def test_render_project_adds_pexels_video_credit_once_with_bgm_credit(
    tmp_path: Path, monkeypatch
) -> None:
    project = _project()
    project["visual_strategy"]["source_priority"] = ["pexels"]
    project_path = tmp_path / "project.youtube.json"
    project_path.write_text(json.dumps(project, ensure_ascii=False), encoding="utf-8")
    bgm_path = tmp_path / "mystery.wav"
    bgm_path.write_bytes(b"fake wav")
    video_path = tmp_path / "pexels_ocean.mp4"
    video_path.write_bytes(b"fake mp4")
    track = BgmTrack(
        track_id="mystery_low",
        file_path=bgm_path,
        title="Mystery Low",
        artist="Local",
        source="youtube_audio_library",
        license_type="youtube_audio_library_standard",
        attribution_required=False,
        attribution_text="Music: Mystery Low by Local from YouTube Audio Library",
        mood="mysterious",
        intensity="low",
        duration_sec=20,
        bpm=None,
        loopable=True,
        allowed_platforms=["youtube_shorts"],
        used_count=0,
        is_active=True,
    )
    asset = MediaAsset(
        asset_id="pexels_ocean",
        source="pexels",
        local_file_path=video_path,
        pexels_id="12345",
        photographer="Ocean Creator",
        photographer_url="https://www.pexels.com/@ocean-creator",
        pexels_url="https://www.pexels.com/video/deep-ocean-12345/",
        original_video_url="https://videos.pexels.com/video-files/12345/hd.mp4",
        original_width=1080,
        original_height=1920,
        original_duration_sec=8.0,
        orientation="portrait",
        selected_quality="hd",
        query="ocean",
        tags=["ocean"],
        used_count=0,
        is_active=True,
    )
    monkeypatch.setattr(render_module, "RENDERS_DIR", tmp_path / "renders")
    monkeypatch.setattr(render_module, "init_db", lambda: None)
    monkeypatch.setattr(render_module, "connect", lambda: NullConnection())
    monkeypatch.setattr(
        render_module, "list_active_bgm_tracks", lambda connection: [track]
    )
    monkeypatch.setattr(
        render_module, "list_active_media_assets", lambda connection: [asset]
    )
    monkeypatch.setattr(render_module, "upsert_project", lambda *args: None)
    monkeypatch.setattr(render_module, "insert_render_summary", lambda *args: None)
    renderer = FakeVideoRenderer()

    rendered_path = render_project(project_path, video_renderer=renderer)

    rendered = json.loads(rendered_path.read_text(encoding="utf-8"))
    assert rendered["credits"]["items"] == [
        {
            "credit_type": "bgm",
            "source": "youtube_audio_library",
            "text": "Music: Mystery Low by Local from YouTube Audio Library",
            "url": None,
        },
        {
            "credit_type": "video",
            "source": "pexels",
            "text": "Video by Ocean Creator on Pexels",
            "url": "https://www.pexels.com/video/deep-ocean-12345/",
        },
    ]
    assert rendered["credits"]["description_text"].count("Video by Ocean Creator") == 1
    credits_text = (rendered_path.parent / "credits.txt").read_text(encoding="utf-8")
    assert "Music: Mystery Low by Local from YouTube Audio Library" in credits_text
    assert "Video: Video by Ocean Creator on Pexels" in credits_text
    assert "https://www.pexels.com/video/deep-ocean-12345/" in credits_text


def test_render_project_selects_local_media_and_passes_visuals_to_video_renderer(
    tmp_path: Path, monkeypatch
) -> None:
    project_path = tmp_path / "project.youtube.json"
    project_path.write_text(
        json.dumps(_project(), ensure_ascii=False), encoding="utf-8"
    )
    media_path = tmp_path / "ocean.mp4"
    media_path.write_bytes(b"fake mp4")
    asset = MediaAsset(
        asset_id="ocean_portrait",
        source="local",
        local_file_path=media_path,
        original_width=1080,
        original_height=1920,
        original_duration_sec=8.0,
        orientation="portrait",
        selected_quality="hd",
        query="dark ocean",
        tags=["ocean"],
        used_count=0,
        is_active=True,
    )
    monkeypatch.setattr(render_module, "RENDERS_DIR", tmp_path / "renders")
    monkeypatch.setattr(render_module, "init_db", lambda: None)
    monkeypatch.setattr(render_module, "connect", lambda: NullConnection())
    monkeypatch.setattr(render_module, "list_active_bgm_tracks", lambda connection: [])
    monkeypatch.setattr(
        render_module, "list_active_media_assets", lambda connection: [asset]
    )
    monkeypatch.setattr(render_module, "upsert_project", lambda *args: None)
    monkeypatch.setattr(render_module, "insert_render_summary", lambda *args: None)
    renderer = FakeVideoRenderer()

    rendered_path = render_project(project_path, video_renderer=renderer)

    rendered = json.loads(rendered_path.read_text(encoding="utf-8"))
    first_visual = rendered["visuals"][0]
    assert first_visual["asset_id"] == "ocean_portrait"
    assert first_visual["local_file_path"] == str(media_path)
    assert first_visual["source"] == "local"
    assert renderer.calls[0]["visuals"][0]["asset_id"] == "ocean_portrait"


def test_render_project_avoids_reusing_same_media_asset_in_one_render(
    tmp_path: Path, monkeypatch
) -> None:
    project = _project()
    project["script"][0]["visual_query"] = "ocean"
    project["script"][1]["visual_query"] = "ocean"
    project["script"][2]["visual_query"] = "ocean"
    project_path = tmp_path / "project.youtube.json"
    project_path.write_text(json.dumps(project, ensure_ascii=False), encoding="utf-8")
    first_path = tmp_path / "ocean_a.mp4"
    second_path = tmp_path / "ocean_b.mp4"
    first_path.write_bytes(b"fake mp4")
    second_path.write_bytes(b"fake mp4 b")
    first_asset = MediaAsset(
        asset_id="ocean_a",
        source="local",
        local_file_path=first_path,
        original_width=1080,
        original_height=1920,
        original_duration_sec=8.0,
        orientation="portrait",
        selected_quality="hd",
        query="ocean",
        tags=["ocean"],
        used_count=0,
        is_active=True,
    )
    second_asset = MediaAsset(
        asset_id="ocean_b",
        source="local",
        local_file_path=second_path,
        original_width=1080,
        original_height=1920,
        original_duration_sec=8.0,
        orientation="portrait",
        selected_quality="hd",
        query="ocean",
        tags=["ocean"],
        used_count=0,
        is_active=True,
    )
    monkeypatch.setattr(render_module, "RENDERS_DIR", tmp_path / "renders")
    monkeypatch.setattr(render_module, "init_db", lambda: None)
    monkeypatch.setattr(render_module, "connect", lambda: NullConnection())
    monkeypatch.setattr(render_module, "list_active_bgm_tracks", lambda connection: [])
    monkeypatch.setattr(
        render_module,
        "list_active_media_assets",
        lambda connection: [first_asset, second_asset],
    )
    monkeypatch.setattr(render_module, "upsert_project", lambda *args: None)
    monkeypatch.setattr(render_module, "insert_render_summary", lambda *args: None)
    renderer = FakeVideoRenderer()

    rendered_path = render_project(project_path, video_renderer=renderer)

    rendered = json.loads(rendered_path.read_text(encoding="utf-8"))
    asset_ids = [visual.get("asset_id") for visual in rendered["visuals"]]
    assert asset_ids == ["ocean_a", "ocean_b", None]


def test_render_project_avoids_reusing_same_visual_source_with_different_asset_ids(
    tmp_path: Path, monkeypatch
) -> None:
    project = _project()
    project["script"][0]["visual_query"] = "ocean"
    project["script"][1]["visual_query"] = "ocean"
    project["script"][2]["visual_query"] = "ocean"
    project_path = tmp_path / "project.youtube.json"
    project_path.write_text(json.dumps(project, ensure_ascii=False), encoding="utf-8")
    shared_path = tmp_path / "shared_ocean.mp4"
    shared_path.write_bytes(b"fake mp4")
    first_asset = MediaAsset(
        asset_id="ocean_a",
        source="local",
        local_file_path=shared_path,
        original_width=1080,
        original_height=1920,
        original_duration_sec=8.0,
        orientation="portrait",
        selected_quality="hd",
        query="ocean",
        tags=["ocean"],
        used_count=0,
        is_active=True,
    )
    second_asset = MediaAsset(
        asset_id="ocean_b",
        source="local",
        local_file_path=shared_path,
        original_width=1080,
        original_height=1920,
        original_duration_sec=8.0,
        orientation="portrait",
        selected_quality="hd",
        query="ocean",
        tags=["ocean"],
        used_count=0,
        is_active=True,
    )
    monkeypatch.setattr(render_module, "RENDERS_DIR", tmp_path / "renders")
    monkeypatch.setattr(render_module, "init_db", lambda: None)
    monkeypatch.setattr(render_module, "connect", lambda: NullConnection())
    monkeypatch.setattr(render_module, "list_active_bgm_tracks", lambda connection: [])
    monkeypatch.setattr(
        render_module,
        "list_active_media_assets",
        lambda connection: [first_asset, second_asset],
    )
    monkeypatch.setattr(render_module, "upsert_project", lambda *args: None)
    monkeypatch.setattr(render_module, "insert_render_summary", lambda *args: None)
    renderer = FakeVideoRenderer()

    rendered_path = render_project(project_path, video_renderer=renderer)

    rendered = json.loads(rendered_path.read_text(encoding="utf-8"))
    asset_ids = [visual.get("asset_id") for visual in rendered["visuals"]]
    assert asset_ids == ["ocean_a", None, None]


def test_render_project_does_not_reuse_available_media_when_query_has_no_match(
    tmp_path: Path, monkeypatch
) -> None:
    project = _project()
    project["script"][0]["visual_query"] = "ocean"
    project["script"][1]["visual_query"] = "seismic graph"
    project["script"][2]["visual_query"] = "submarine"
    project_path = tmp_path / "project.youtube.json"
    project_path.write_text(json.dumps(project, ensure_ascii=False), encoding="utf-8")
    media_path = tmp_path / "ocean.mp4"
    media_path.write_bytes(b"fake mp4")
    asset = MediaAsset(
        asset_id="ocean_portrait",
        source="local",
        local_file_path=media_path,
        original_width=1080,
        original_height=1920,
        original_duration_sec=8.0,
        orientation="portrait",
        selected_quality="hd",
        query="ocean",
        tags=["ocean"],
        used_count=0,
        is_active=True,
    )
    monkeypatch.setattr(render_module, "RENDERS_DIR", tmp_path / "renders")
    monkeypatch.setattr(render_module, "init_db", lambda: None)
    monkeypatch.setattr(render_module, "connect", lambda: NullConnection())
    monkeypatch.setattr(render_module, "list_active_bgm_tracks", lambda connection: [])
    monkeypatch.setattr(
        render_module, "list_active_media_assets", lambda connection: [asset]
    )
    monkeypatch.setattr(render_module, "upsert_project", lambda *args: None)
    monkeypatch.setattr(render_module, "insert_render_summary", lambda *args: None)
    renderer = FakeVideoRenderer()

    rendered_path = render_project(project_path, video_renderer=renderer)

    rendered = json.loads(rendered_path.read_text(encoding="utf-8"))
    fallback_visual = rendered["visuals"][1]
    assert fallback_visual["visual_query"] == "seismic graph"
    assert fallback_visual.get("asset_id") is None
    assert (
        fallback_visual["local_file_path"]
        .replace("\\", "/")
        .endswith("/video/material_002.mp4")
    )
    assert renderer.calls[0]["visuals"][1].get("asset_id") is None


def test_render_project_wraps_long_subtitle_lines(tmp_path: Path, monkeypatch) -> None:
    project = _project()
    original_text = "たとえばチョウチンアンコウは、頭の先にある光で小さな魚を誘います。"
    project["script"][0]["text"] = original_text
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
    renderer = FakeVideoRenderer()

    rendered_path = render_project(project_path, video_renderer=renderer)

    rendered = json.loads(rendered_path.read_text(encoding="utf-8"))
    assert rendered["audio"]["narration_files"][0]["text"] == original_text
    assert "\\N" in rendered["subtitles"]["items"][0]["text"]
    subtitle_ass = (rendered_path.parent / "subtitle.ass").read_text(encoding="utf-8")
    assert "\\N" in subtitle_ass


def test_render_project_keeps_safe_subtitle_sentence_on_one_line(
    tmp_path: Path, monkeypatch
) -> None:
    project = _project()
    safe_text = "ここで問題になるのが、マグマに含まれるガスです。"
    project["script"][0]["text"] = safe_text
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
    renderer = FakeVideoRenderer()

    rendered_path = render_project(project_path, video_renderer=renderer)

    rendered = json.loads(rendered_path.read_text(encoding="utf-8"))
    assert rendered["subtitles"]["items"][0]["text"] == safe_text
    subtitle_ass = (rendered_path.parent / "subtitle.ass").read_text(encoding="utf-8")
    assert "\\N" not in subtitle_ass
