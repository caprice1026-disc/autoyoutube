from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class FfmpegRenderRequest:
    render_dir: Path
    duration_sec: float
    width: int
    height: int
    fps: int
    audio_path: Path
    subtitle_path: Path
    output_path: Path
    logs_dir: Path
    video_codec: str
    audio_codec: str
    pix_fmt: str


def build_ffmpeg_command(request: FfmpegRenderRequest, ffmpeg_path: Path) -> list[str]:
    return [
        str(ffmpeg_path),
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"color=c=0x07111f:s={request.width}x{request.height}:r={request.fps}:d={request.duration_sec:.3f}",
        "-i",
        _relative_arg(request.audio_path, request.render_dir),
        "-vf",
        f"subtitles={_relative_arg(request.subtitle_path, request.render_dir)}",
        "-shortest",
        "-c:v",
        request.video_codec,
        "-pix_fmt",
        request.pix_fmt,
        "-r",
        str(request.fps),
        "-c:a",
        request.audio_codec,
        _relative_arg(request.output_path, request.render_dir),
    ]


def find_ffmpeg_executable(explicit_path: str | Path | None = None) -> Path:
    candidates: list[Path] = []
    if explicit_path:
        candidates.append(Path(explicit_path))
    env_path = os.environ.get("FFMPEG_PATH")
    if env_path:
        candidates.append(Path(env_path))
    found = shutil.which("ffmpeg")
    if found:
        candidates.append(Path(found))
    candidates.extend(_winget_ffmpeg_candidates())

    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise FileNotFoundError("ffmpeg executable was not found. Pass --ffmpeg-path or set FFMPEG_PATH.")


class FfmpegVideoRenderer:
    def __init__(self, ffmpeg_path: str | Path | None = None) -> None:
        self.ffmpeg_path = find_ffmpeg_executable(ffmpeg_path)

    def render(
        self,
        *,
        render_dir: Path,
        duration_sec: float,
        target: dict,
        logs_dir: Path,
    ) -> dict[str, str | bool]:
        video_format = target["video_format"]
        resolution = target["resolution"]
        request = FfmpegRenderRequest(
            render_dir=render_dir,
            duration_sec=duration_sec,
            width=resolution["width"],
            height=resolution["height"],
            fps=target["fps"],
            audio_path=render_dir / "audio" / "final_audio.wav",
            subtitle_path=render_dir / "subtitle.ass",
            output_path=render_dir / "output.mp4",
            logs_dir=logs_dir,
            video_codec=video_format["video_codec"],
            audio_codec=video_format["audio_codec"],
            pix_fmt=video_format["pix_fmt"],
        )
        logs_dir.mkdir(parents=True, exist_ok=True)
        command = build_ffmpeg_command(request, self.ffmpeg_path)
        command_log_path = logs_dir / "ffmpeg_command.txt"
        stderr_log_path = logs_dir / "ffmpeg_stderr.log"
        command_log_path.write_text(" ".join(command) + "\n", encoding="utf-8")

        result = subprocess.run(command, cwd=render_dir, capture_output=True, text=True)
        stderr_log_path.write_text(result.stderr, encoding="utf-8")
        if result.returncode != 0:
            tail = result.stderr[-2000:]
            raise RuntimeError(f"FFmpeg failed with exit code {result.returncode}: {tail}")

        return {
            "rendered": True,
            "version": _ffmpeg_version(self.ffmpeg_path),
            "command_log_path": str(command_log_path),
            "stderr_log_path": str(stderr_log_path),
        }


def _relative_arg(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _winget_ffmpeg_candidates() -> list[Path]:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if not local_app_data:
        return []
    package_root = Path(local_app_data) / "Microsoft" / "WinGet" / "Packages"
    if not package_root.exists():
        return []
    return list(package_root.glob("Gyan.FFmpeg_*/*/bin/ffmpeg.exe"))


def _ffmpeg_version(ffmpeg_path: Path) -> str:
    result = subprocess.run([str(ffmpeg_path), "-version"], capture_output=True, text=True)
    if result.returncode != 0:
        return "unknown"
    return result.stdout.splitlines()[0] if result.stdout else "unknown"
