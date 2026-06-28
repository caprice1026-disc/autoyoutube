from __future__ import annotations

import json
import shutil
import wave
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from src.bgm.library import BgmTrack
from src.bgm.selector import select_bgm_track
from src.config import PROJECT_SCHEMA_PATH, RENDERED_SCHEMA_PATH, RENDERS_DIR
from src.db.database import connect, init_db
from src.db.repositories import (
    insert_render_summary,
    list_active_bgm_tracks,
    list_active_media_assets,
    upsert_project,
)
from src.errors import AppError
from src.media.library import MediaAsset
from src.media.selector import select_media_asset
from src.utils.file_hash import sha256_file
from src.validators.json_validator import load_json, validate_json
from src.voice.audio_merge import merge_wav_files
from src.voice.duration import get_wav_duration


class VoiceService(Protocol):
    def synthesize_to_file(
        self,
        text: str,
        speaker: str | int,
        output_path: Path,
        speed_scale: float,
        pitch_scale: float,
        intonation_scale: float,
    ) -> Path: ...


class VideoRenderer(Protocol):
    def render(
        self,
        *,
        render_dir: Path,
        duration_sec: float,
        target: dict[str, Any],
        logs_dir: Path,
        bgm: dict[str, Any] | None = None,
        visuals: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]: ...


def render_project(
    project_path: Path,
    voice_service: VoiceService | None = None,
    video_renderer: VideoRenderer | None = None,
) -> Path:
    init_db()
    project_path = project_path.resolve()
    project = load_json(project_path)
    project_schema = load_json(PROJECT_SCHEMA_PATH)
    project_errors = validate_json(project, project_schema)
    if project_errors:
        joined = "\n".join(error.to_text() for error in project_errors)
        raise AppError(
            "project JSON validation failed.",
            location=str(project_path),
            details=joined,
            next_step="Fix project JSON schema errors and run validation again.",
        )

    project_hash = sha256_file(project_path)
    render_dir = RENDERS_DIR / project["id"]
    (render_dir / "audio").mkdir(parents=True, exist_ok=True)
    (render_dir / "video").mkdir(parents=True, exist_ok=True)
    logs_dir = render_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    narration_files, subtitle_items, visuals, actual_duration, sample_rate = (
        _generate_voice_and_timing(
            project,
            render_dir,
            voice_service,
        )
    )
    selected_bgm = _select_render_bgm(project["bgm"])
    bgm_render = _build_bgm_render(project["bgm"], selected_bgm, actual_duration)
    visuals = _select_render_visuals(project, visuals)

    now = datetime.now(timezone.utc)
    render_id = f"render_{now.strftime('%Y%m%d_%H%M%S')}"
    description = _build_description(project)
    credits_required, credits_items, credits = _build_credits(selected_bgm)
    subtitle = _build_subtitle(subtitle_items)
    (render_dir / "description.txt").write_text(description, encoding="utf-8")
    (render_dir / "credits.txt").write_text(credits, encoding="utf-8")
    (render_dir / "subtitle.ass").write_text(subtitle, encoding="utf-8")
    video_result = _render_video(
        video_renderer,
        render_dir,
        actual_duration,
        project["target"],
        logs_dir,
        bgm_render,
        visuals,
    )

    rendered_path = render_dir / "rendered.youtube.json"
    rendered = _build_rendered(
        project,
        project_path,
        project_hash,
        render_id,
        now,
        render_dir,
        logs_dir,
        description,
        credits,
        credits_required,
        credits_items,
        bgm_render,
        narration_files,
        subtitle_items,
        visuals,
        actual_duration,
        sample_rate,
        voice_service is None,
        video_result,
    )
    rendered_schema = load_json(RENDERED_SCHEMA_PATH)
    render_errors = validate_json(rendered, rendered_schema)
    rendered["validation"]["rendered_json_valid"] = not render_errors
    rendered["validation"]["errors"] = [
        {
            "code": "RENDER_SCHEMA_ERROR",
            "message": error.to_text(),
            "details": {"path": error.path},
        }
        for error in render_errors
    ]
    rendered_path.write_text(
        json.dumps(rendered, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    with connect() as connection:
        upsert_project(connection, project, _rel(project_path), project_hash)
        insert_render_summary(connection, rendered)
    return rendered_path


def _generate_voice_and_timing(
    project: dict[str, Any],
    render_dir: Path,
    voice_service: VoiceService | None,
) -> tuple[
    list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], float, int
]:
    audio_dir = render_dir / "audio"
    video_dir = render_dir / "video"
    voice = project["voice"]
    wav_paths: list[Path] = []
    durations: list[float] = []

    for item in project["script"]:
        wav_path = audio_dir / f"{item['index']:03d}.wav"
        if voice_service is None:
            _write_silent_wav(wav_path, float(item["estimated_duration_sec"]))
        else:
            voice_service.synthesize_to_file(
                item["text"],
                voice.get("style_id", voice["speaker"]),
                wav_path,
                voice["speed_scale"],
                voice["pitch_scale"],
                voice["intonation_scale"],
            )
        wav_paths.append(wav_path)
        durations.append(round(get_wav_duration(wav_path), 3))

    narration_path = audio_dir / "narration.wav"
    actual_duration = round(
        merge_wav_files(wav_paths, narration_path, voice["sentence_gap_ms"]), 3
    )
    shutil.copyfile(narration_path, audio_dir / "final_audio.wav")

    gap = voice["sentence_gap_ms"] / 1000
    cursor = 0.0
    narration_files: list[dict[str, Any]] = []
    subtitle_items: list[dict[str, Any]] = []
    visuals: list[dict[str, Any]] = []
    for item, duration in zip(project["script"], durations):
        start = round(cursor, 3)
        end = round(cursor + duration, 3)
        narration_files.append(
            {
                "index": item["index"],
                "text": item["text"],
                "path": _rel(audio_dir / f"{item['index']:03d}.wav"),
                "estimated_duration_sec": float(item["estimated_duration_sec"]),
                "actual_duration_sec": duration,
                "start_sec": start,
                "end_sec": end,
            }
        )
        subtitle_items.append(
            {
                "index": item["index"],
                "text": item["text"],
                "start_sec": start,
                "end_sec": end,
                "caption_style_hint": item["caption_style_hint"],
            }
        )
        visuals.append(
            {
                "index": item["index"],
                "script_index": item["index"],
                "visual_query": item["visual_query"],
                "source": "local",
                "local_file_path": _rel(
                    video_dir / f"material_{item['index']:03d}.mp4"
                ),
                "original_width": 1080,
                "original_height": 1920,
                "original_duration_sec": duration,
                "orientation": "portrait",
                "selected_quality": "unknown",
                "transform": {
                    "type": "none",
                    "scale_width": 1080,
                    "scale_height": 1920,
                },
                "used_start_sec": 0,
                "used_duration_sec": duration,
                "video_start_sec": start,
                "video_end_sec": end,
            }
        )
        cursor = end + gap
    return (
        narration_files,
        subtitle_items,
        visuals,
        actual_duration,
        _wav_sample_rate(narration_path),
    )


def _build_rendered(
    project: dict[str, Any],
    project_path: Path,
    project_hash: str,
    render_id: str,
    now: datetime,
    render_dir: Path,
    logs_dir: Path,
    description: str,
    credits: str,
    credits_required: bool,
    credits_items: list[dict[str, Any]],
    bgm_render: dict[str, Any] | None,
    narration_files: list[dict[str, Any]],
    subtitle_items: list[dict[str, Any]],
    visuals: list[dict[str, Any]],
    actual_duration: float,
    sample_rate: int,
    dry_run_voice: bool,
    video_result: dict[str, Any],
) -> dict[str, Any]:
    iso = now.isoformat().replace("+00:00", "Z")
    warnings = []
    if not video_result["rendered"]:
        warnings.append(
            {
                "code": "VIDEO_NOT_RENDERED",
                "message": "FFmpeg was not executed for this render.",
            }
        )
    if dry_run_voice:
        warnings.append(
            {
                "code": "DRY_RUN_VOICE",
                "message": "Silent placeholder WAV files were generated from estimated durations.",
            }
        )

    return {
        "schema_version": "rendered-youtube-1.0.0",
        "platform_profile": "youtube_shorts",
        "project_id": project["id"],
        "render_id": render_id,
        "status": "success" if video_result["rendered"] else "partial_success",
        "created_at": iso,
        "completed_at": iso,
        "input": {
            "project_json_path": _rel(project_path),
            "project_json_hash": project_hash,
            "project_schema_path": _rel(PROJECT_SCHEMA_PATH),
        },
        "output": {
            "video_path": _rel(render_dir / "output.mp4"),
            "thumbnail_path": _rel(render_dir / "thumbnail.jpg"),
            "subtitle_ass_path": _rel(render_dir / "subtitle.ass"),
            "description_path": _rel(render_dir / "description.txt"),
            "credits_path": _rel(render_dir / "credits.txt"),
            "rendered_json_path": _rel(render_dir / "rendered.youtube.json"),
            "logs_dir": _rel(logs_dir),
        },
        "target": {
            "planned_duration_sec": project["target"]["duration_sec"],
            "actual_duration_sec": actual_duration,
            "aspect_ratio": "9:16",
            "resolution": project["target"]["resolution"],
            "fps": project["target"]["fps"],
            "video_format": project["target"]["video_format"],
        },
        "voice": {
            **project["voice"],
            "sample_rate": sample_rate,
            "audio_format": "wav",
        },
        "audio": {
            "narration_files": narration_files,
            "merged_narration_path": _rel(render_dir / "audio" / "narration.wav"),
            "merged_narration_duration_sec": actual_duration,
            "final_audio_path": _rel(render_dir / "audio" / "final_audio.wav"),
            "final_audio_duration_sec": actual_duration,
            "loudness_normalization": {"enabled": False},
        },
        "bgm": bgm_render
        if bgm_render is not None
        else {
            "enabled": False,
            "strategy": "none",
            "source": "none",
            "mood": "none",
            "intensity": "none",
        },
        "visuals": visuals,
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
            "items": subtitle_items,
        },
        "youtube": {
            **project["youtube"],
            "description": description,
            "description_path": _rel(render_dir / "description.txt"),
            "upload": {"planned": False, "status": "not_uploaded"},
        },
        "thumbnail": {"generated": False},
        "credits": {
            "required": credits_required,
            "items": credits_items,
            "description_text": credits,
        },
        "ffmpeg": {
            "version": video_result["version"],
            "command_log_path": _rel(Path(video_result["command_log_path"])),
            "stderr_log_path": _rel(Path(video_result["stderr_log_path"])),
            "video_codec": project["target"]["video_format"]["video_codec"],
            "audio_codec": "aac",
            "pix_fmt": "yuv420p",
            "preset": "medium",
            "crf": 20,
        },
        "validation": {
            "project_json_valid": True,
            "rendered_json_valid": True,
            "warnings": warnings,
            "errors": [],
        },
        "manual_review": {
            "required": True,
            "fact_check_required": project["manual_fact_check_required"],
            "checked": False,
            "publish_ready": False,
            "notes": "Manual fact check and quality review are required before publishing.",
        },
    }


def _build_description(project: dict[str, Any]) -> str:
    yt = project["youtube"]
    sections = yt["description_sections"]
    return (
        "\n".join(
            [
                yt["description"],
                "",
                sections["summary"],
                "",
                " ".join(yt["hashtags"]),
                "",
                sections["disclaimer"],
            ]
        ).strip()
        + "\n"
    )


def _render_video(
    video_renderer: VideoRenderer | None,
    render_dir: Path,
    actual_duration: float,
    target: dict[str, Any],
    logs_dir: Path,
    bgm_render: dict[str, Any] | None,
    visuals: list[dict[str, Any]],
) -> dict[str, Any]:
    if video_renderer is None:
        command_log_path = logs_dir / "ffmpeg_command.txt"
        stderr_log_path = logs_dir / "ffmpeg_stderr.log"
        command_log_path.write_text(
            "FFmpeg was not executed for this render.\n", encoding="utf-8"
        )
        stderr_log_path.write_text("", encoding="utf-8")
        return {
            "rendered": False,
            "version": "not_executed",
            "command_log_path": str(command_log_path),
            "stderr_log_path": str(stderr_log_path),
        }
    return video_renderer.render(
        render_dir=render_dir,
        duration_sec=actual_duration,
        target=target,
        logs_dir=logs_dir,
        bgm=bgm_render,
        visuals=visuals,
    )


def _select_render_bgm(project_bgm: dict[str, Any]) -> BgmTrack | None:
    if not project_bgm.get("enabled") or project_bgm.get("strategy") == "none":
        return None
    with connect() as connection:
        tracks = list_active_bgm_tracks(connection)
    if not tracks:
        return None
    return select_bgm_track(project_bgm, tracks)


def _select_render_visuals(
    project: dict[str, Any], visuals: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    with connect() as connection:
        assets = list_active_media_assets(connection)
    if not assets:
        return visuals

    selected_visuals: list[dict[str, Any]] = []
    for visual in visuals:
        asset = select_media_asset(
            {"visual_query": visual["visual_query"]}, project["visual_strategy"], assets
        )
        selected_visuals.append(
            _build_visual_from_asset(visual, asset) if asset is not None else visual
        )
    return selected_visuals


def _build_visual_from_asset(
    visual: dict[str, Any], asset: MediaAsset
) -> dict[str, Any]:
    transform_type = (
        "none" if asset.orientation == "portrait" else "crop_landscape_to_9_16"
    )
    return {
        **visual,
        "asset_id": asset.asset_id,
        "source": asset.source,
        "pexels_id": asset.pexels_id,
        "photographer": asset.photographer,
        "photographer_url": asset.photographer_url,
        "pexels_url": asset.pexels_url,
        "original_video_url": asset.original_video_url,
        "local_file_path": str(asset.local_file_path),
        "original_width": asset.original_width or visual["original_width"],
        "original_height": asset.original_height or visual["original_height"],
        "original_duration_sec": asset.original_duration_sec
        or visual["used_duration_sec"],
        "orientation": asset.orientation,
        "selected_quality": asset.selected_quality,
        "transform": {
            "type": transform_type,
            "scale_width": 1080,
            "scale_height": 1920,
        },
    }


def _build_bgm_render(
    project_bgm: dict[str, Any], track: BgmTrack | None, actual_duration: float
) -> dict[str, Any] | None:
    if track is None:
        return None
    return {
        "enabled": True,
        "strategy": project_bgm["strategy"],
        "track_id": track.track_id,
        "file_path": str(track.file_path),
        "title": track.title,
        "artist": track.artist,
        "source": track.source,
        "license_type": track.license_type,
        "attribution_required": track.attribution_required,
        "attribution_text": track.attribution_text,
        "mood": track.mood,
        "intensity": track.intensity,
        "volume_db": project_bgm["volume_db"],
        "fade_in_ms": project_bgm["fade_in_ms"],
        "fade_out_ms": project_bgm["fade_out_ms"],
        "looped": bool(
            track.loopable
            and track.duration_sec is not None
            and track.duration_sec < actual_duration
        ),
        "used_start_sec": 0,
        "used_duration_sec": actual_duration,
    }


def _build_credits(track: BgmTrack | None) -> tuple[bool, list[dict[str, Any]], str]:
    if track is None:
        return (
            False,
            [],
            "Dry-run render: external visual media and BGM were not used.\n",
        )
    text = track.attribution_text or f"BGM: {track.title} by {track.artist}".strip()
    item = {"credit_type": "bgm", "source": track.source, "text": text, "url": None}
    return track.attribution_required, [item], text + "\n"


def _build_subtitle(subtitle_items: list[dict[str, Any]]) -> str:
    lines = [
        "[Script Info]",
        "ScriptType: v4.00+",
        "PlayResX: 1080",
        "PlayResY: 1920",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        "Style: Default,Noto Sans CJK JP,72,&H00FFFFFF,&H00000000,1,5,1,2,80,80,220,1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    for item in subtitle_items:
        lines.append(
            f"Dialogue: 0,{_ass_time(item['start_sec'])},{_ass_time(item['end_sec'])},Default,,0,0,0,,{item['text']}"
        )
    return "\n".join(lines) + "\n"


def _ass_time(seconds: float) -> str:
    centis = int(round(seconds * 100))
    s, cs = divmod(centis, 100)
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(Path.cwd().resolve()))
    except ValueError:
        return str(path)


def _write_silent_wav(
    path: Path, duration_sec: float, *, framerate: int = 44100
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame_count = max(1, round(duration_sec * framerate))
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(framerate)
        wav.writeframes(b"\x00" * frame_count * 2)


def _wav_sample_rate(path: Path) -> int:
    with wave.open(str(path), "rb") as wav:
        return wav.getframerate()
