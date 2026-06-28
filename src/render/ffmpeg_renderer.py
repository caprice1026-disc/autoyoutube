from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from src.errors import AppError


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
    bgm_path: Path | None = None
    bgm_volume_db: float = -26
    bgm_fade_in_sec: float = 0.5
    bgm_fade_out_sec: float = 1.2


def build_ffmpeg_command(request: FfmpegRenderRequest, ffmpeg_path: Path) -> list[str]:
    command = [
        str(ffmpeg_path),
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"color=c=0x07111f:s={request.width}x{request.height}:r={request.fps}:d={request.duration_sec:.3f}",
        "-i",
        _relative_arg(request.audio_path, request.render_dir),
    ]
    if request.bgm_path is not None:
        command.extend(["-stream_loop", "-1", "-i", _relative_arg(request.bgm_path, request.render_dir)])
    command.extend(["-vf", f"subtitles={_relative_arg(request.subtitle_path, request.render_dir)}"])
    if request.bgm_path is not None:
        command.extend(["-filter_complex", _bgm_filter(request), "-shortest", "-c:v", request.video_codec, "-pix_fmt", request.pix_fmt, "-r", str(request.fps), "-c:a", request.audio_codec, "-map", "0:v", "-map", "[aout]"])
    else:
        command.extend(["-shortest", "-c:v", request.video_codec, "-pix_fmt", request.pix_fmt, "-r", str(request.fps), "-c:a", request.audio_codec])
    command.append(_relative_arg(request.output_path, request.render_dir))
    return command


def find_ffmpeg_executable(explicit_path: str | Path | None = None) -> Path:
    candidates: list[Path] = []
    if explicit_path:
        candidate = Path(explicit_path)
        if candidate.is_file():
            return candidate
        raise AppError(
            "FFmpeg executable was not found.",
            location=str(candidate),
            next_step="Install FFmpeg or pass --ffmpeg-path with the full path to ffmpeg.exe.",
        )
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
    raise AppError(
        "FFmpeg executable was not found.",
        location="ffmpeg",
        next_step="Install FFmpeg or pass --ffmpeg-path with the full path to ffmpeg.exe.",
    )


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
        bgm: dict | None = None,
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
            bgm_path=Path(bgm["file_path"]) if bgm else None,
            bgm_volume_db=float(bgm["volume_db"]) if bgm else -26,
            bgm_fade_in_sec=float(bgm["fade_in_ms"]) / 1000 if bgm else 0.5,
            bgm_fade_out_sec=float(bgm["fade_out_ms"]) / 1000 if bgm else 1.2,
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
            raise AppError(
                "FFmpeg render failed.",
                location=str(stderr_log_path),
                details=f"exit code {result.returncode}: {tail}",
                next_step="Open the stderr log, fix the input paths or FFmpeg options, and run render again.",
            )

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
        return path.resolve().as_posix()


def _bgm_filter(request: FfmpegRenderRequest) -> str:
    volume = 10 ** (request.bgm_volume_db / 20)
    fade_out_start = max(0.0, request.duration_sec - request.bgm_fade_out_sec)
    return (
        f"[1:a]volume=1.0[narr];"
        f"[2:a]volume={volume:.6f},"
        f"afade=t=in:st=0:d={request.bgm_fade_in_sec:.3f},"
        f"afade=t=out:st={fade_out_start:.3f}:d={request.bgm_fade_out_sec:.3f}[bgm];"
        "[narr][bgm]amix=inputs=2:duration=first:dropout_transition=0[aout]"
    )


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
