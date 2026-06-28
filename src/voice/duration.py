from __future__ import annotations

import wave
from pathlib import Path


def get_wav_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as wav:
        frame_count = wav.getnframes()
        frame_rate = wav.getframerate()
    if frame_rate <= 0:
        raise ValueError(f"WAV file has invalid frame rate: {path}")
    return frame_count / frame_rate
