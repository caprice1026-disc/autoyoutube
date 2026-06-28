from __future__ import annotations

import wave
from pathlib import Path

from src.voice.duration import get_wav_duration


def merge_wav_files(input_paths: list[Path], output_path: Path, gap_ms: int) -> float:
    if not input_paths:
        raise ValueError("input_paths must contain at least one WAV file")
    if gap_ms < 0:
        raise ValueError("gap_ms must be zero or greater")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    first_params = _read_params(input_paths[0])
    for path in input_paths[1:]:
        if _read_params(path) != first_params:
            raise ValueError("All input files must use the same WAV format")

    channels, sample_width, frame_rate = first_params
    gap_frames = round(frame_rate * gap_ms / 1000)
    gap_bytes = b"\x00" * gap_frames * channels * sample_width

    with wave.open(str(output_path), "wb") as output:
        output.setnchannels(channels)
        output.setsampwidth(sample_width)
        output.setframerate(frame_rate)
        for index, path in enumerate(input_paths):
            if index > 0 and gap_bytes:
                output.writeframes(gap_bytes)
            with wave.open(str(path), "rb") as source:
                output.writeframes(source.readframes(source.getnframes()))

    return get_wav_duration(output_path)


def _read_params(path: Path) -> tuple[int, int, int]:
    with wave.open(str(path), "rb") as wav:
        return wav.getnchannels(), wav.getsampwidth(), wav.getframerate()
