from __future__ import annotations

import subprocess
from pathlib import Path

from src.errors import AppError
from src.render.ffmpeg_renderer import find_ffmpeg_executable


def remove_audio_track(
    input_path: Path,
    output_path: Path,
    *,
    ffmpeg_path: str | Path | None = None,
) -> Path:
    """Write a video-only copy of *input_path*.

    Generated-video services may include dialogue, music, or ambient audio.  The
    project narration and BGM are mixed separately, so this helper removes every
    input audio stream before the clip enters the render timeline.
    """

    source = input_path.resolve()
    destination = output_path.resolve()
    if not source.is_file():
        raise AppError(
            "Generated intro video was not found.",
            location=str(source),
            next_step="Place the generated MP4 beside project.youtube.json or use the stock fallback.",
        )

    destination.parent.mkdir(parents=True, exist_ok=True)
    executable = find_ffmpeg_executable(ffmpeg_path)
    command = [
        str(executable),
        "-y",
        "-i",
        str(source),
        "-map",
        "0:v:0",
        "-c:v",
        "copy",
        "-an",
        str(destination),
    ]
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        raise AppError(
            "Failed to remove audio from generated intro video.",
            location=str(source),
            details=f"exit code {result.returncode}: {result.stderr[-2000:]}",
            next_step="Confirm the file is a readable video and that FFmpeg is available.",
        )
    if not destination.is_file():
        raise AppError(
            "Muted generated intro video was not created.",
            location=str(destination),
            next_step="Inspect the FFmpeg installation and retry.",
        )
    return destination
