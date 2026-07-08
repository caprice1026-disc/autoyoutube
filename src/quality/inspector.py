from __future__ import annotations

import json
import math
import shutil
import struct
import subprocess
import wave
import zlib
from pathlib import Path
from typing import Any

from src.errors import AppError
from src.validators.json_validator import load_json


DEFAULT_SCREENSHOT_NAMES = ("opening", "middle", "ending")
TIMELINE_WIDTH = 1080
FRAME_STRIP_HEIGHT = 240
WAVEFORM_HEIGHT = 220
SUBTITLE_BAND_HEIGHT = 260
TIMELINE_FRAME_COUNT = 8


Color = tuple[int, int, int]


COLORS: dict[str, Color] = {
    "background": (10, 15, 25),
    "panel": (24, 33, 48),
    "grid": (58, 69, 88),
    "text": (238, 242, 247),
    "muted": (145, 158, 178),
    "accent": (111, 180, 255),
    "warning": (255, 203, 107),
    "subtitle": (77, 171, 247),
}


FONT: dict[str, tuple[str, ...]] = {
    " ": ("00000", "00000", "00000", "00000", "00000", "00000", "00000"),
    "-": ("00000", "00000", "00000", "11111", "00000", "00000", "00000"),
    ".": ("00000", "00000", "00000", "00000", "00000", "01100", "01100"),
    ":": ("00000", "01100", "01100", "00000", "01100", "01100", "00000"),
    "/": ("00001", "00010", "00100", "01000", "10000", "00000", "00000"),
    "0": ("01110", "10001", "10011", "10101", "11001", "10001", "01110"),
    "1": ("00100", "01100", "00100", "00100", "00100", "00100", "01110"),
    "2": ("01110", "10001", "00001", "00010", "00100", "01000", "11111"),
    "3": ("11110", "00001", "00001", "01110", "00001", "00001", "11110"),
    "4": ("00010", "00110", "01010", "10010", "11111", "00010", "00010"),
    "5": ("11111", "10000", "10000", "11110", "00001", "00001", "11110"),
    "6": ("00110", "01000", "10000", "11110", "10001", "10001", "01110"),
    "7": ("11111", "00001", "00010", "00100", "01000", "01000", "01000"),
    "8": ("01110", "10001", "10001", "01110", "10001", "10001", "01110"),
    "9": ("01110", "10001", "10001", "01111", "00001", "00010", "11100"),
    "A": ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
    "B": ("11110", "10001", "10001", "11110", "10001", "10001", "11110"),
    "C": ("01111", "10000", "10000", "10000", "10000", "10000", "01111"),
    "D": ("11110", "10001", "10001", "10001", "10001", "10001", "11110"),
    "E": ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
    "F": ("11111", "10000", "10000", "11110", "10000", "10000", "10000"),
    "G": ("01111", "10000", "10000", "10011", "10001", "10001", "01111"),
    "H": ("10001", "10001", "10001", "11111", "10001", "10001", "10001"),
    "I": ("11111", "00100", "00100", "00100", "00100", "00100", "11111"),
    "J": ("00001", "00001", "00001", "00001", "10001", "10001", "01110"),
    "K": ("10001", "10010", "10100", "11000", "10100", "10010", "10001"),
    "L": ("10000", "10000", "10000", "10000", "10000", "10000", "11111"),
    "M": ("10001", "11011", "10101", "10101", "10001", "10001", "10001"),
    "N": ("10001", "11001", "10101", "10011", "10001", "10001", "10001"),
    "O": ("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
    "P": ("11110", "10001", "10001", "11110", "10000", "10000", "10000"),
    "Q": ("01110", "10001", "10001", "10001", "10101", "10010", "01101"),
    "R": ("11110", "10001", "10001", "11110", "10100", "10010", "10001"),
    "S": ("01111", "10000", "10000", "01110", "00001", "00001", "11110"),
    "T": ("11111", "00100", "00100", "00100", "00100", "00100", "00100"),
    "U": ("10001", "10001", "10001", "10001", "10001", "10001", "01110"),
    "V": ("10001", "10001", "10001", "10001", "10001", "01010", "00100"),
    "W": ("10001", "10001", "10001", "10101", "10101", "10101", "01010"),
    "X": ("10001", "10001", "01010", "00100", "01010", "10001", "10001"),
    "Y": ("10001", "10001", "01010", "00100", "00100", "00100", "00100"),
    "Z": ("11111", "00001", "00010", "00100", "01000", "10000", "11111"),
}


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
    timeline_png_path = _build_timeline_png(
        ffmpeg,
        video_path,
        inspect_dir,
        rendered,
        duration_sec,
    )

    report = {
        "render_id": rendered["render_id"],
        "project_id": rendered["project_id"],
        "inspect_dir": _rel(inspect_dir),
        "screenshot_paths": [_rel(path) for path in screenshot_paths],
        "subtitle_frame_paths": [_rel(path) for path in subtitle_frame_paths],
        "timeline_png_path": _rel(timeline_png_path),
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


def _build_timeline_png(
    ffmpeg_path: Path,
    video_path: Path,
    inspect_dir: Path,
    rendered: dict[str, Any],
    duration_sec: float,
) -> Path:
    parts_dir = inspect_dir / "timeline_parts"
    parts_dir.mkdir(parents=True, exist_ok=True)
    frame_strip_path = _build_frame_strip(
        ffmpeg_path,
        video_path,
        parts_dir,
        duration_sec,
    )
    waveform_path = parts_dir / "waveform.png"
    _write_waveform_png(
        waveform_path,
        rendered.get("audio", {}).get("final_audio_path"),
        duration_sec,
    )
    subtitle_band_path = parts_dir / "subtitles.png"
    _write_subtitle_band_png(
        subtitle_band_path,
        rendered.get("subtitles", {}).get("items", []),
        duration_sec,
    )
    output_path = inspect_dir / "timeline.png"
    _stack_timeline_parts(
        ffmpeg_path,
        [frame_strip_path, waveform_path, subtitle_band_path],
        output_path,
    )
    return output_path


def _build_frame_strip(
    ffmpeg_path: Path,
    video_path: Path,
    parts_dir: Path,
    duration_sec: float,
) -> Path:
    frame_paths: list[Path] = []
    for index, timestamp in enumerate(_timeline_sample_points(duration_sec), start=1):
        frame_path = parts_dir / f"timeline_frame_{index:03d}.png"
        _extract_frame(ffmpeg_path, video_path, timestamp, frame_path)
        frame_paths.append(frame_path)
    frame_width = TIMELINE_WIDTH // len(frame_paths)
    output_path = parts_dir / "frames.png"
    filters = []
    labels = []
    for index in range(len(frame_paths)):
        label = f"f{index}"
        labels.append(f"[{label}]")
        filters.append(
            f"[{index}:v]scale={frame_width}:{FRAME_STRIP_HEIGHT}:"
            f"force_original_aspect_ratio=increase,"
            f"crop={frame_width}:{FRAME_STRIP_HEIGHT}[{label}]"
        )
    filters.append("".join(labels) + f"hstack=inputs={len(frame_paths)}[out]")
    _run_ffmpeg(
        [
            str(ffmpeg_path),
            "-y",
            *sum((["-i", str(path)] for path in frame_paths), []),
            "-filter_complex",
            ";".join(filters),
            "-map",
            "[out]",
            str(output_path),
        ],
        output_path,
        "FFmpeg timeline frame strip generation failed.",
    )
    return output_path


def _stack_timeline_parts(
    ffmpeg_path: Path, input_paths: list[Path], output_path: Path
) -> None:
    labels = [f"[p{index}]" for index in range(len(input_paths))]
    filters = [
        f"[{index}:v]scale={TIMELINE_WIDTH}:-1[{label[1:-1]}]"
        for index, label in enumerate(labels)
    ]
    filters.append("".join(labels) + f"vstack=inputs={len(input_paths)}[out]")
    _run_ffmpeg(
        [
            str(ffmpeg_path),
            "-y",
            *sum((["-i", str(path)] for path in input_paths), []),
            "-filter_complex",
            ";".join(filters),
            "-map",
            "[out]",
            str(output_path),
        ],
        output_path,
        "FFmpeg timeline PNG assembly failed.",
    )


def _extract_frame(
    ffmpeg_path: Path,
    video_path: Path,
    timestamp_sec: float,
    output_path: Path,
) -> None:
    _run_ffmpeg(
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
        output_path,
        "FFmpeg frame extraction failed.",
    )


def _run_ffmpeg(command: list[str], output_path: Path, error_message: str) -> None:
    completed = subprocess.run(
        command,
        capture_output=True,
        check=False,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if completed.returncode != 0:
        raise AppError(
            error_message,
            location=str(output_path),
            details=completed.stderr[-2000:] or completed.stdout[-2000:],
            next_step="Confirm output.mp4 is readable and ffmpeg can create inspection artifacts.",
        )
    if not output_path.is_file() or output_path.stat().st_size == 0:
        raise AppError(
            "FFmpeg did not create an inspect artifact.",
            location=str(output_path),
            next_step="Inspect the ffmpeg command and output video duration.",
        )


def _write_waveform_png(
    path: Path,
    audio_path_text: Any,
    duration_sec: float,
) -> None:
    canvas = _new_canvas(TIMELINE_WIDTH, WAVEFORM_HEIGHT, COLORS["panel"])
    _draw_text(canvas, 18, 16, "AUDIO WAVEFORM", COLORS["text"], scale=3)
    _draw_text(canvas, 18, 52, f"DURATION {duration_sec:.1f}S", COLORS["muted"], scale=2)
    _draw_grid(canvas, top=76, bottom=WAVEFORM_HEIGHT - 28)

    samples = _read_audio_samples(audio_path_text)
    if samples:
        _draw_waveform(canvas, samples, top=76, bottom=WAVEFORM_HEIGHT - 28)
    else:
        _draw_text(canvas, 330, 118, "NO READABLE AUDIO", COLORS["warning"], scale=3)
    _write_png(path, TIMELINE_WIDTH, WAVEFORM_HEIGHT, canvas)


def _write_subtitle_band_png(
    path: Path,
    subtitle_items: list[dict[str, Any]],
    duration_sec: float,
) -> None:
    canvas = _new_canvas(TIMELINE_WIDTH, SUBTITLE_BAND_HEIGHT, COLORS["background"])
    _draw_text(canvas, 18, 16, "SUBTITLE TIMELINE", COLORS["text"], scale=3)
    _draw_time_ticks(canvas, duration_sec, top=58, bottom=SUBTITLE_BAND_HEIGHT - 28)
    for item in subtitle_items:
        start_sec = _float_or_none(item.get("start_sec"))
        end_sec = _float_or_none(item.get("end_sec"))
        if start_sec is None or end_sec is None:
            continue
        left = _time_to_x(start_sec, duration_sec)
        right = max(left + 4, _time_to_x(end_sec, duration_sec))
        index = int(item.get("index") or 0)
        text = str(item.get("text") or "")
        duration = max(0.001, end_sec - start_sec)
        cps = len(text.replace(r"\N", "")) / duration
        color = COLORS["warning"] if cps > 16 else COLORS["subtitle"]
        top = 88 + ((index - 1) % 4) * 38
        _draw_rect(canvas, left, top, right, top + 24, color)
        _draw_text(canvas, left + 4, top + 6, f"S{index:03d} {cps:.1f}CPS", COLORS["background"], scale=1)
    _write_png(path, TIMELINE_WIDTH, SUBTITLE_BAND_HEIGHT, canvas)


def _read_audio_samples(audio_path_text: Any) -> list[int]:
    if not audio_path_text:
        return []
    audio_path = _resolve_path(str(audio_path_text))
    if not audio_path.is_file():
        return []
    try:
        with wave.open(str(audio_path), "rb") as wav:
            sample_width = wav.getsampwidth()
            if sample_width != 2:
                return []
            raw = wav.readframes(wav.getnframes())
            channels = max(1, wav.getnchannels())
    except (OSError, wave.Error):
        return []
    values = [
        int.from_bytes(raw[index : index + sample_width], "little", signed=True)
        for index in range(0, len(raw), sample_width)
    ]
    if channels == 1:
        return values
    return [
        int(sum(values[index : index + channels]) / channels)
        for index in range(0, len(values), channels)
    ]


def _draw_waveform(canvas: bytearray, samples: list[int], *, top: int, bottom: int) -> None:
    height = bottom - top
    center_y = top + height // 2
    max_sample = max(max(abs(sample) for sample in samples), 1)
    bucket_size = max(1, math.ceil(len(samples) / TIMELINE_WIDTH))
    _draw_rect(canvas, 0, center_y, TIMELINE_WIDTH, center_y + 1, COLORS["grid"])
    for x in range(TIMELINE_WIDTH):
        bucket = samples[x * bucket_size : (x + 1) * bucket_size]
        if not bucket:
            continue
        peak = max(abs(sample) for sample in bucket)
        amplitude = int((peak / max_sample) * (height / 2 - 4))
        _draw_rect(
            canvas,
            x,
            center_y - amplitude,
            x + 1,
            center_y + amplitude + 1,
            COLORS["accent"],
        )


def _draw_grid(canvas: bytearray, *, top: int, bottom: int) -> None:
    for x in range(0, TIMELINE_WIDTH, 120):
        _draw_rect(canvas, x, top, x + 1, bottom, COLORS["grid"])


def _draw_time_ticks(canvas: bytearray, duration_sec: float, *, top: int, bottom: int) -> None:
    _draw_rect(canvas, 18, top, TIMELINE_WIDTH - 18, top + 2, COLORS["grid"])
    for tick in range(0, 6):
        seconds = duration_sec * tick / 5
        x = _time_to_x(seconds, duration_sec)
        _draw_rect(canvas, x, top - 8, x + 2, bottom, COLORS["grid"])
        _draw_text(canvas, x + 4, top - 24, f"{seconds:.0f}S", COLORS["muted"], scale=1)


def _time_to_x(seconds: float, duration_sec: float) -> int:
    if duration_sec <= 0:
        return 18
    usable_width = TIMELINE_WIDTH - 36
    return 18 + int((seconds / duration_sec) * usable_width)


def _new_canvas(width: int, height: int, color: Color) -> bytearray:
    return bytearray(color * (width * height))


def _draw_rect(
    canvas: bytearray,
    left: int,
    top: int,
    right: int,
    bottom: int,
    color: Color,
    *,
    width: int = TIMELINE_WIDTH,
) -> None:
    left = max(0, min(width, left))
    right = max(0, min(width, right))
    top = max(0, top)
    bottom = max(0, bottom)
    for y in range(top, bottom):
        row_start = y * width * 3
        for x in range(left, right):
            index = row_start + x * 3
            if index + 2 < len(canvas):
                canvas[index : index + 3] = bytes(color)


def _draw_text(
    canvas: bytearray,
    x: int,
    y: int,
    text: str,
    color: Color,
    *,
    scale: int = 2,
) -> None:
    cursor = x
    for char in text.upper():
        pattern = FONT.get(char, FONT[" "])
        for row_index, row in enumerate(pattern):
            for col_index, value in enumerate(row):
                if value == "1":
                    _draw_rect(
                        canvas,
                        cursor + col_index * scale,
                        y + row_index * scale,
                        cursor + (col_index + 1) * scale,
                        y + (row_index + 1) * scale,
                        color,
                    )
        cursor += 6 * scale


def _write_png(path: Path, width: int, height: int, rgb_data: bytearray) -> None:
    def chunk(chunk_type: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + chunk_type
            + data
            + struct.pack(">I", zlib.crc32(chunk_type + data) & 0xFFFFFFFF)
        )

    rows = []
    stride = width * 3
    for y in range(height):
        rows.append(b"\x00" + bytes(rgb_data[y * stride : (y + 1) * stride]))
    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(b"".join(rows), level=9))
    png += chunk(b"IEND", b"")
    path.write_bytes(png)


def _timeline_sample_points(duration_sec: float) -> list[float]:
    if duration_sec <= 0:
        return [0.0]
    if TIMELINE_FRAME_COUNT == 1:
        return [_clamp_time(duration_sec / 2, duration_sec)]
    return [
        _clamp_time(duration_sec * index / (TIMELINE_FRAME_COUNT - 1), duration_sec)
        for index in range(TIMELINE_FRAME_COUNT)
    ]


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
