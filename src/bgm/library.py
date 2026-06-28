from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.errors import AppError
from src.validators.json_validator import load_json


@dataclass(frozen=True)
class BgmTrack:
    track_id: str
    file_path: Path
    title: str
    artist: str
    source: str
    license_type: str
    attribution_required: bool
    attribution_text: str
    mood: str
    intensity: str
    duration_sec: float | None
    bpm: float | None
    loopable: bool
    allowed_platforms: list[str]
    used_count: int = 0
    is_active: bool = True


def load_bgm_manifest(path: Path) -> list[BgmTrack]:
    manifest = load_json(path)
    tracks_raw = manifest.get("tracks")
    if not isinstance(tracks_raw, list):
        raise AppError(
            "BGM manifest must contain a tracks array.",
            location=str(path),
            next_step="Add a top-level tracks list and run import-bgm again.",
        )
    return [_parse_track(item, path.parent, path, index) for index, item in enumerate(tracks_raw, start=1)]


def _parse_track(item: Any, base_dir: Path, manifest_path: Path, index: int) -> BgmTrack:
    if not isinstance(item, dict):
        raise AppError(
            "BGM manifest track must be an object.",
            location=f"{manifest_path}: tracks[{index - 1}]",
            next_step="Replace the track entry with an object containing track_id and file_path.",
        )

    track_id = _required_str(item, "track_id", manifest_path, index)
    file_path = _resolve_audio_path(_required_str(item, "file_path", manifest_path, index), base_dir, manifest_path, track_id)
    return BgmTrack(
        track_id=track_id,
        file_path=file_path,
        title=str(item.get("title") or track_id),
        artist=str(item.get("artist") or ""),
        source=str(item.get("source") or "local_original"),
        license_type=str(item.get("license_type") or ""),
        attribution_required=bool(item.get("attribution_required", False)),
        attribution_text=str(item.get("attribution_text") or ""),
        mood=str(item.get("mood") or "none"),
        intensity=str(item.get("intensity") or "none"),
        duration_sec=_optional_float(item.get("duration_sec")),
        bpm=_optional_float(item.get("bpm")),
        loopable=bool(item.get("loopable", True)),
        allowed_platforms=[str(value) for value in item.get("allowed_platforms", ["youtube_shorts"])],
        used_count=int(item.get("used_count", 0)),
        is_active=bool(item.get("is_active", True)),
    )


def _required_str(item: dict[str, Any], key: str, manifest_path: Path, index: int) -> str:
    value = item.get(key)
    if not isinstance(value, str) or not value.strip():
        raise AppError(
            f"BGM manifest track is missing {key}.",
            location=f"{manifest_path}: tracks[{index - 1}]",
            next_step=f"Set a non-empty string value for {key}.",
        )
    return value


def _resolve_audio_path(value: str, base_dir: Path, manifest_path: Path, track_id: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = base_dir / path
    if not path.is_file():
        raise AppError(
            "BGM audio file was not found.",
            location=str(path),
            next_step=f"Fix file_path for track {track_id} in {manifest_path}.",
        )
    return path.resolve()


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)
