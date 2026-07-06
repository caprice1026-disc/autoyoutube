from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.errors import AppError
from src.utils.file_hash import sha256_file
from src.validators.json_validator import load_json


@dataclass(frozen=True)
class MediaAsset:
    asset_id: str
    source: str
    local_file_path: Path
    original_width: int | None
    original_height: int | None
    original_duration_sec: float | None
    orientation: str
    selected_quality: str
    query: str
    tags: list[str]
    pexels_id: str | None = None
    photographer: str | None = None
    photographer_url: str | None = None
    pexels_url: str | None = None
    original_video_url: str | None = None
    used_count: int = 0
    is_active: bool = True


def load_media_manifest(path: Path) -> list[MediaAsset]:
    manifest = load_json(path)
    assets_raw = manifest.get("assets")
    if not isinstance(assets_raw, list):
        raise AppError(
            "Media manifest must contain an assets array.",
            location=str(path),
            next_step="Add a top-level assets list and run import-media again.",
        )
    return [
        _parse_asset(item, path.parent, path, index)
        for index, item in enumerate(assets_raw, start=1)
    ]


def media_asset_source_key(asset: MediaAsset) -> str:
    if asset.source == "pexels":
        if asset.pexels_id:
            return f"pexels:{asset.pexels_id}"
        if asset.original_video_url:
            return f"pexels-url:{asset.original_video_url}"

    if asset.local_file_path.is_file():
        try:
            return sha256_file(asset.local_file_path)
        except OSError:
            pass

    try:
        return f"path:{asset.local_file_path.resolve()}"
    except OSError:
        return f"path:{asset.local_file_path.as_posix()}"


def _parse_asset(
    item: Any, base_dir: Path, manifest_path: Path, index: int
) -> MediaAsset:
    if not isinstance(item, dict):
        raise AppError(
            "Media manifest asset must be an object.",
            location=f"{manifest_path}: assets[{index - 1}]",
            next_step="Replace the asset entry with an object containing asset_id and local_file_path.",
        )
    asset_id = _required_str(item, "asset_id", manifest_path, index)
    local_file_path = _resolve_media_path(
        _required_str(item, "local_file_path", manifest_path, index),
        base_dir,
        manifest_path,
        asset_id,
    )
    tags = item.get("tags", [])
    if not isinstance(tags, list):
        raise AppError(
            "Media asset tags must be an array.",
            location=f"{manifest_path}: assets[{index - 1}]",
            next_step="Set tags to a list of short strings.",
        )
    return MediaAsset(
        asset_id=asset_id,
        source=str(item.get("source") or "local"),
        local_file_path=local_file_path,
        original_width=_optional_int(item.get("original_width")),
        original_height=_optional_int(item.get("original_height")),
        original_duration_sec=_optional_float(item.get("original_duration_sec")),
        orientation=str(
            item.get("orientation")
            or _infer_orientation(
                item.get("original_width"), item.get("original_height")
            )
        ),
        selected_quality=str(item.get("selected_quality") or "unknown"),
        query=str(item.get("query") or ""),
        tags=[str(tag) for tag in tags],
        pexels_id=_optional_str(item.get("pexels_id")),
        photographer=_optional_str(item.get("photographer")),
        photographer_url=_optional_str(item.get("photographer_url")),
        pexels_url=_optional_str(item.get("pexels_url")),
        original_video_url=_optional_str(item.get("original_video_url")),
        used_count=int(item.get("used_count", 0)),
        is_active=bool(item.get("is_active", True)),
    )


def _required_str(
    item: dict[str, Any], key: str, manifest_path: Path, index: int
) -> str:
    value = item.get(key)
    if not isinstance(value, str) or not value.strip():
        raise AppError(
            f"Media manifest asset is missing {key}.",
            location=f"{manifest_path}: assets[{index - 1}]",
            next_step=f"Set a non-empty string value for {key}.",
        )
    return value


def _resolve_media_path(
    value: str, base_dir: Path, manifest_path: Path, asset_id: str
) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = base_dir / path
    if not path.is_file():
        raise AppError(
            "Media file was not found.",
            location=str(path),
            next_step=f"Fix local_file_path for asset {asset_id} in {manifest_path}.",
        )
    return path.resolve()


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text else None


def _infer_orientation(width: Any, height: Any) -> str:
    if width is None or height is None:
        return "unknown"
    width_int = int(width)
    height_int = int(height)
    if height_int > width_int:
        return "portrait"
    if width_int > height_int:
        return "landscape"
    return "square"
