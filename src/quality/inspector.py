from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from src.errors import AppError
from src.validators.json_validator import load_json


DEFAULT_SCREENSHOT_NAMES = ("opening", "middle", "ending")


def inspect_render(rendered_path: Path, *, ffmpeg_path: str | Path | None = None) -> dict[str, Any]:
    """Extract render inspection images for human/Codex review."""
    rendered_path = rendered_path.resolve()
    if not rendered_path.is_file():
        raise AppError(
            "rendered JSON was not found.",
            location=str(rendered_path),
            next_step="Run render first, then pass the generated rendered.youtube.json.",
        )

    rendered = load_json(rendered_path)
    video_path = _resolve_path(rendered["output"]["video_path"])
    if not video_path.is_file() or video_path.stat().st_size == 0:
        raise AppError(
            "output video was not found or is empty.",
            location=str(video_path),
            next_step="Run render with --video-mode ffmpeg before inspect-render.",
        )

    ffmpeg = _find_ffmpeg(ffmpeg_path)
    inspect_dir = rendered_path.parent / "inspect"
    inspect_dir.mkdir(parents=True, exist_ok=True)

    duration_sec = _duration_for_sampling(rendered)
    screenshot_paths = _extract_summary_screenshots(
        ffmpeg,
        video_path,
        inspect_dir,
        duration_sec,
    )
    subtitle_frame_paths = _extract_subtitle_frames(
        ffmpeg,
        video_path,
        inspect_dir,
        rendered.get("subtitles", {}).get("items", []),
        duration_sec,
    )

    report = {
        "render_id": rendered["render_id"],
        "project_id": rendered["project_id"],
        "inspect_dir": _rel(inspect_dir),
        "screenshot_paths": [_rel(path) for path in screenshot_paths],
        "subtitle_frame_paths": [_rel(path) for path in subtitle_frame_paths],
    }
    (inspect_dir / "inspect_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return report


def _extract_summary_screenshots(
    ffmpeg_path: Path,
    video_path: Path,
    inspect_dir: Path,
    duration_sec: float,
) -> list[Path]:
    sample_points = {
        "opening": _clamp_time(1.0, duration_sec),
        "middle": _clamp_time(duration_sec / 2, duration_sec),
        "ending": _clamp_time(max(0.0, duration_sec - 1.0), duration_sec),
    }
    paths: list[Path] = []
    for name in DEFAULT_SCREENSHOT_NAMES:
        output_path = inspect_dir / f"{name}.png"
        _extract_frame(ffmpeg_path, video_path, sample_points[name], output_path)
        paths.append(output_path)
    return paths


def _extract_subtitle_frames(
    ffmpeg_path: Path,
    video_path: Path,
    inspect_dir: Path,
    subtitle_items: list[dict[str, Any]],
    duration_sec: float,
) -> list[Path]:
    paths: list[Path] = []
    for item in subtitle_items:
        index = int(item.get("index") or len(paths) + 1)
        start_sec = _float_or_none(item.get("start_sec"))
        end_sec = _float_or_none(item.get("end_sec"))
        if start_sec is None or end_sec is None:
            continue
        midpoint = _clamp_time((start_sec + end_sec) / 2, duration_sec)
        output_path = inspect_dir / f"subtitle_{index:03d}.png"
        _extract_frame(ffmpeg_path, video_path, midpoint, output_path)
        paths.append(output_path)
    return paths


def _extract_frame(
    ffmpeg_path: Path,
    video_path: Path,
    timestamp_sec: float,
    output_path: Path,
) -> None:
    completed = subprocess.run(
        [
            str(ffmpeg_path),
            "-y",
            "-ss",
            f"{timestamp_sec:.3f}",
            "-i",
            str(video_path),
            "-frames:v",
            "1",
            "-q:v",
            "2",
            str(output_path),
        ],
        capture_output=True,
        check=False,
        text=True,
    )
    if completed.returncode != 0:
        raise AppError(
            "FFmpeg frame extraction failed.",
            location=str(output_path),
            details=completed.stderr[-2000:] or completed.stdout[-2000:],
            next_step="Confirm output.mp4 is readable and ffmpeg can extract PNG frames.",
        )
    if not output_path.is_file() or output_path.stat().st_size == 0:
        raise AppError(
            "FFmpeg did not create a screenshot.",
            location=str(output_path),
            next_step="Inspect the ffmpeg command and output video duration.",
        )


def _duration_for_sampling(rendered: dict[str, Any]) -> float:
    duration = _float_or_none(rendered.get("target", {}).get("actual_duration_sec"))
    if duration is None or duration <= 0:
        duration = _float_or_none(rendered.get("target", {}).get("planned_duration_sec"))
    return max(0.001, float(duration or 0.001))


def _clamp_time(timestamp_sec: float, duration_sec: float) -> float:
    if duration_sec <= 0.1:
        return 0.0
    return min(max(0.0, timestamp_sec), max(0.0, duration_sec - 0.05))


def _find_ffmpeg(explicit_path: str | Path | None) -> Path:
    if explicit_path is not None:
        candidate = Path(explicit_path)
        if candidate.is_file():
            return candidate
        raise AppError(
            "FFmpeg executable was not found.",
            location=str(candidate),
            next_step="Install FFmpeg or pass --ffmpeg-path with the full path to ffmpeg.exe.",
        )
    found = shutil.which("ffmpeg")
    if found:
        return Path(found)
    raise AppError(
        "FFmpeg executable was not found.",
        location="ffmpeg",
        next_step="Install FFmpeg or pass --ffmpeg-path with the full path to ffmpeg.exe.",
    )


def _resolve_path(path_text: str) -> Path:
    path = Path(path_text)
    if path.is_absolute():
        return path
    return Path.cwd() / path


def _rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(Path.cwd().resolve()))
    except ValueError:
        return str(path)


def _float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
