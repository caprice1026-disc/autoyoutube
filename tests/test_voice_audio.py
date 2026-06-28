from __future__ import annotations

import wave
from pathlib import Path

import pytest

from src.voice.audio_merge import merge_wav_files
from src.voice.duration import get_wav_duration


def _write_silent_wav(path: Path, duration_sec: float, *, framerate: int = 8000, channels: int = 1, sample_width: int = 2) -> None:
    frames = int(duration_sec * framerate)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(channels)
        wav.setsampwidth(sample_width)
        wav.setframerate(framerate)
        wav.writeframes(b"\x00" * frames * channels * sample_width)


def test_get_wav_duration_uses_frame_count(tmp_path: Path) -> None:
    wav_path = tmp_path / "one_and_half.wav"
    _write_silent_wav(wav_path, 1.5)

    assert get_wav_duration(wav_path) == pytest.approx(1.5)


def test_merge_wav_files_inserts_silence_between_sentences(tmp_path: Path) -> None:
    first = tmp_path / "first.wav"
    second = tmp_path / "second.wav"
    merged = tmp_path / "merged.wav"
    _write_silent_wav(first, 1.0)
    _write_silent_wav(second, 2.0)

    duration = merge_wav_files([first, second], merged, gap_ms=250)

    assert duration == pytest.approx(3.25)
    assert get_wav_duration(merged) == pytest.approx(3.25)


def test_merge_wav_files_rejects_mismatched_formats(tmp_path: Path) -> None:
    first = tmp_path / "first.wav"
    second = tmp_path / "second.wav"
    _write_silent_wav(first, 1.0, framerate=8000)
    _write_silent_wav(second, 1.0, framerate=16000)

    with pytest.raises(ValueError, match="same WAV format"):
        merge_wav_files([first, second], tmp_path / "merged.wav", gap_ms=0)
