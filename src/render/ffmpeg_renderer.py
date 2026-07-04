from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.defaults import (
    DEFAULT_BGM_FADE_IN_MS,
    DEFAULT_BGM_FADE_OUT_MS,
    DEFAULT_BGM_VOLUME_DB,
)
from src.errors import AppError


@dataclass(frozen=True)
class FfmpegVideoSegment:
    path: Path
    duration_sec: float


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
    background_video_path: Path | None = None
    background_video_segments: list[FfmpegVideoSegment] | None = None
    bgm_path: Path | None = None
    bgm_volume_db: float = DEFAULT_BGM_VOLUME_DB
    bgm_fade_in_sec: float = DEFAULT_BGM_FADE_IN_MS / 1000
    bgm_fade_out_sec: float = DEFAULT_BGM_FADE_OUT_MS / 1000


@dataclass(frozen=True)
class VisualSegment:
    index: int
    input_path: Path
    output_path: Path
    start_sec: float
    duration_sec: float
    used_start_sec: float = 0.0


def build_ffmpeg_command(request: FfmpegRenderRequest, ffmpeg_path: Path) -> list[str]:
    command = [str(ffmpeg_path), "-y"]
    video_segments = list(request.background_video_segments or [])
    if video_segments:
        for segment in video_segments:
            command.extend(
                [
                    "-stream_loop",
                    "-1",
                    "-i",
                    _relative_arg(segment.path, request.render_dir),
                ]
            )
    elif request.background_video_path is not None:
        command.extend(
            [
                "-stream_loop",
                "-1",
                "-i",
                _relative_arg(request.background_video_path, request.render_dir),
            ]
        )
    else:
        command.extend(
            [
                "-f",
                "lavfi",
                "-i",
                f"color=c=0x07111f:s={request.width}x{request.height}:r={request.fps}:d={request.duration_sec:.3f}",
            ]
        )

    command.extend(["-i", _relative_arg(request.audio_path, request.render_dir)])
    narration_input_index = len(video_segments) if video_segments else 1
    if request.bgm_path is not None:
        command.extend(
            [
                "-stream_loop",
                "-1",
                "-i",
                _relative_arg(request.bgm_path, request.render_dir),
            ]
        )

    if video_segments:
        filters = [_video_timeline_filter(request, video_segments)]
        if request.bgm_path is not None:
            filters.append(
                _bgm_filter(
                    request,
                    narration_input_index=narration_input_index,
                    bgm_input_index=narration_input_index + 1,
                )
            )
        command.extend(["-filter_complex", ";".join(filters)])
        command.extend(
            _timeline_output_options(
                request,
                narration_input_index=narration_input_index,
                has_bgm=request.bgm_path is not None,
            )
        )
    else:
        command.extend(["-vf", _video_filter(request)])
        if request.bgm_path is not None:
            command.extend(
                [
                    "-filter_complex",
                    _bgm_filter(request),
                    "-shortest",
                    "-t",
                    f"{request.duration_sec:.3f}",
                    "-c:v",
                    request.video_codec,
                    "-pix_fmt",
                    request.pix_fmt,
                    "-r",
                    str(request.fps),
                    "-c:a",
                    request.audio_codec,
                    "-map",
                    "0:v",
                    "-map",
                    "[aout]",
                ]
            )
        else:
            command.extend(
                [
                    "-shortest",
                    "-t",
                    f"{request.duration_sec:.3f}",
                    "-c:v",
                    request.video_codec,
                    "-pix_fmt",
                    request.pix_fmt,
                    "-r",
                    str(request.fps),
                    "-c:a",
                    request.audio_codec,
                ]
            )
    command.append(_relative_arg(request.output_path, request.render_dir))
    return command


def build_segment_command(
    segment: VisualSegment,
    request: FfmpegRenderRequest,
    ffmpeg_path: Path,
) -> list[str]:
    return [
        str(ffmpeg_path),
        "-y",
        "-stream_loop",
        "-1",
        "-ss",
        f"{segment.used_start_sec:.3f}",
        "-i",
        _relative_arg(segment.input_path, request.render_dir),
        "-t",
        f"{segment.duration_sec:.3f}",
        "-vf",
        _segment_video_filter(request),
        "-an",
        "-c:v",
        request.video_codec,
        "-pix_fmt",
        request.pix_fmt,
        "-r",
        str(request.fps),
        _relative_arg(segment.output_path, request.render_dir),
    ]


def build_concat_command(
    concat_list_path: Path,
    output_path: Path,
    request: FfmpegRenderRequest,
    ffmpeg_path: Path,
) -> list[str]:
    return [
        str(ffmpeg_path),
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        _relative_arg(concat_list_path, request.render_dir),
        "-c",
        "copy",
        _relative_arg(output_path, request.render_dir),
    ]


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
        visuals: list[dict] | None = None,
    ) -> dict[str, str | bool]:
        video_format = target["video_format"]
        resolution = target["resolution"]
        video_segments = _visual_background_segments(visuals)
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
            background_video_path=video_segments[0].path
            if len(video_segments) == 1
            else None,
            background_video_segments=video_segments if len(video_segments) > 1 else None,
            bgm_path=Path(bgm["file_path"]) if bgm else None,
            bgm_volume_db=float(bgm["volume_db"]) if bgm else DEFAULT_BGM_VOLUME_DB,
            bgm_fade_in_sec=float(bgm["fade_in_ms"]) / 1000
            if bgm
            else DEFAULT_BGM_FADE_IN_MS / 1000,
            bgm_fade_out_sec=float(bgm["fade_out_ms"]) / 1000
            if bgm
            else DEFAULT_BGM_FADE_OUT_MS / 1000,
        )
        background_path, timeline_commands = _prepare_background_video(
            visuals,
            base_request,
            self.ffmpeg_path,
        )
        request = FfmpegRenderRequest(
            **{
                **base_request.__dict__,
                "background_video_path": background_path,
            }
        )
        command = build_ffmpeg_command(request, self.ffmpeg_path)
        command_log_path = logs_dir / "ffmpeg_command.txt"
        stderr_log_path = logs_dir / "ffmpeg_stderr.log"
        command_log_path.write_text(
            _format_command_log(timeline_commands + [command]), encoding="utf-8"
        )

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


def _prepare_background_video(
    visuals: list[dict[str, Any]] | None,
    request: FfmpegRenderRequest,
    ffmpeg_path: Path,
) -> tuple[Path | None, list[list[str]]]:
    visual_segments = _visual_segments(visuals, request)
    if len(visual_segments) <= 1:
        return _visual_background_path(visuals), []

    commands: list[list[str]] = []
    for segment in visual_segments:
        command = build_segment_command(segment, request, ffmpeg_path)
        _run_timeline_command(command, request.render_dir, request.logs_dir, segment.output_path)
        commands.append(command)

    concat_list_path = request.render_dir / "video_segments" / "concat.txt"
    _write_concat_list(concat_list_path, [segment.output_path for segment in visual_segments])
    background_path = request.render_dir / "video" / "background_timeline.mp4"
    concat_command = build_concat_command(
        concat_list_path,
        background_path,
        request,
        ffmpeg_path,
    )
    _run_timeline_command(concat_command, request.render_dir, request.logs_dir, background_path)
    commands.append(concat_command)
    return background_path, commands


def _visual_segments(
    visuals: list[dict[str, Any]] | None,
    request: FfmpegRenderRequest,
) -> list[VisualSegment]:
    if not visuals:
        return []
    segments: list[VisualSegment] = []
    segments_dir = request.render_dir / "video_segments"
    for visual in sorted(
        visuals,
        key=lambda item: float(item.get("video_start_sec") or item.get("index") or 0),
    ):
        if not visual.get("asset_id"):
            continue
        input_path = Path(str(visual["local_file_path"]))
        if not input_path.is_file():
            raise AppError(
                "Media segment file was not found.",
                location=str(input_path),
                next_step="Run fetch-visuals/import-media again or fix visual local_file_path.",
            )
        start_sec = float(visual.get("video_start_sec") or 0.0)
        duration_sec = _segment_duration(visual)
        if duration_sec <= 0:
            continue
        index = int(visual.get("index") or len(segments) + 1)
        segments.append(
            VisualSegment(
                index=index,
                input_path=input_path,
                output_path=segments_dir / f"segment_{index:03d}.mp4",
                start_sec=start_sec,
                duration_sec=duration_sec,
                used_start_sec=float(visual.get("used_start_sec") or 0.0),
            )
        )
    return segments


def _segment_duration(visual: dict[str, Any]) -> float:
    if visual.get("used_duration_sec") is not None:
        return float(visual["used_duration_sec"])
    start = float(visual.get("video_start_sec") or 0.0)
    end = float(visual.get("video_end_sec") or 0.0)
    return max(0.0, end - start)


def _run_timeline_command(
    command: list[str], render_dir: Path, logs_dir: Path, output_path: Path
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(command, cwd=render_dir, capture_output=True, text=True)
    log_path = logs_dir / f"{output_path.stem}_stderr.log"
    log_path.write_text(result.stderr, encoding="utf-8")
    if result.returncode != 0:
        tail = result.stderr[-2000:]
        raise AppError(
            "FFmpeg visual timeline step failed.",
            location=str(log_path),
            details=f"exit code {result.returncode}: {tail}",
            next_step="Check visual media files, segment durations, and FFmpeg timeline logs.",
        )


def _write_concat_list(concat_list_path: Path, paths: list[Path]) -> None:
    concat_list_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"file '{_concat_path(path)}'" for path in paths]
    concat_list_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _concat_path(path: Path) -> str:
    return path.resolve().as_posix().replace("'", "'\\''")


def _format_command_log(commands: list[list[str]]) -> str:
    return "\n\n".join(" ".join(command) for command in commands) + "\n"


def _relative_arg(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _video_filter(request: FfmpegRenderRequest) -> str:
    subtitle_filter = (
        f"subtitles={_relative_arg(request.subtitle_path, request.render_dir)}"
    )
    if request.background_video_path is None:
        return subtitle_filter
    return (
        f"scale={request.width}:{request.height}:force_original_aspect_ratio=increase,"
        f"crop={request.width}:{request.height},"
        f"{subtitle_filter}"
    )


def _video_timeline_filter(
    request: FfmpegRenderRequest, segments: list[FfmpegVideoSegment]
) -> str:
    filters: list[str] = []
    for index, segment in enumerate(segments):
        filters.append(
            f"[{index}:v]"
            f"trim=duration={segment.duration_sec:.3f},"
            "setpts=PTS-STARTPTS,"
            f"scale={request.width}:{request.height}:force_original_aspect_ratio=increase,"
            f"crop={request.width}:{request.height},"
            f"fps={request.fps},"
            "setsar=1"
            f"[v{index}]"
        )
    inputs = "".join(f"[v{index}]" for index in range(len(segments)))
    filters.append(f"{inputs}concat=n={len(segments)}:v=1:a=0[vcat]")
    filters.append(
        f"[vcat]subtitles={_relative_arg(request.subtitle_path, request.render_dir)}[vout]"
    )
    return ";".join(filters)


def _timeline_output_options(
    request: FfmpegRenderRequest, *, narration_input_index: int, has_bgm: bool
) -> list[str]:
    return [
        "-shortest",
        "-t",
        f"{request.duration_sec:.3f}",
        "-c:v",
        request.video_codec,
        "-pix_fmt",
        request.pix_fmt,
        "-r",
        str(request.fps),
        "-c:a",
        request.audio_codec,
        "-map",
        "[vout]",
        "-map",
        "[aout]" if has_bgm else f"{narration_input_index}:a",
    ]


def _visual_background_segments(visuals: list[dict] | None) -> list[FfmpegVideoSegment]:
    if not visuals:
        return []
    valid_visuals = [visual for visual in visuals if visual.get("asset_id")]
    segments: list[FfmpegVideoSegment] = []
    for index, visual in enumerate(valid_visuals):
        path = Path(visual["local_file_path"])
        if not path.is_file():
            raise AppError(
                "Media background file was not found.",
                location=str(path),
                next_step="Re-import the media manifest or fix the asset local_file_path.",
            )
        start_sec = float(visual.get("video_start_sec") or 0.0)
        if index + 1 < len(valid_visuals):
            next_start_sec = float(
                valid_visuals[index + 1].get("video_start_sec") or start_sec
            )
            duration_sec = next_start_sec - start_sec
        else:
            duration_sec = _visual_duration_sec(visual)
        if duration_sec <= 0:
            duration_sec = _visual_duration_sec(visual)
        segments.append(
            FfmpegVideoSegment(path=path, duration_sec=round(duration_sec, 3))
        )
    return segments


def _visual_duration_sec(visual: dict) -> float:
    used_duration = visual.get("used_duration_sec")
    if used_duration is not None:
        return float(used_duration)
    return float(visual["video_end_sec"]) - float(visual["video_start_sec"])


def _visual_background_path(visuals: list[dict] | None) -> Path | None:
    if not visuals:
        return None
    for visual in visuals:
        if not visual.get("asset_id"):
            continue
        path = Path(visual["local_file_path"])
        if path.is_file():
            return path
        raise AppError(
            "Media background file was not found.",
            location=str(path),
            next_step="Re-import the media manifest or fix the asset local_file_path.",
        )
    return None


def _bgm_filter(
    request: FfmpegRenderRequest,
    *,
    narration_input_index: int = 1,
    bgm_input_index: int = 2,
) -> str:
    volume = 10 ** (request.bgm_volume_db / 20)
    fade_out_start = max(0.0, request.duration_sec - request.bgm_fade_out_sec)
    return (
        f"[{narration_input_index}:a]volume=1.0[narr];"
        f"[{bgm_input_index}:a]volume={volume:.6f},"
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
    result = subprocess.run(
        [str(ffmpeg_path), "-version"], capture_output=True, text=True
    )
    if result.returncode != 0:
        return "unknown"
    return result.stdout.splitlines()[0] if result.stdout else "unknown"
