from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from src.voice.aivis_client import AivisSpeechClient


class RecordingTransport:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict[str, str], bytes | None, str | None]] = []

    def get(self, path: str, query: dict[str, str]) -> tuple[str, bytes]:
        self.calls.append(("GET", path, query, None, None))
        speakers = [
            {
                "name": "Anneli",
                "styles": [
                    {"name": "Normal", "id": 888753760, "type": "talk"},
                ],
            }
        ]
        return "application/json", json.dumps(speakers).encode("utf-8")

    def post(self, path: str, query: dict[str, str], body: bytes | None, content_type: str | None) -> tuple[str, bytes]:
        self.calls.append(("POST", path, query, body, content_type))
        if path == "/audio_query":
            return "application/json", json.dumps({"speedScale": 1.0, "pitchScale": 0.0, "intonationScale": 1.0}).encode("utf-8")
        if path == "/synthesis":
            return "audio/wav", b"RIFFfake-wav"
        raise AssertionError(f"unexpected path: {path}")


def test_aivis_client_creates_query_then_synthesizes_wav(tmp_path: Path) -> None:
    transport = RecordingTransport()
    client = AivisSpeechClient(transport=transport)
    output_path = tmp_path / "001.wav"

    client.synthesize_to_file(
        "hello",
        speaker="888753760",
        output_path=output_path,
        speed_scale=1.2,
        pitch_scale=-0.02,
        intonation_scale=0.8,
    )

    assert output_path.read_bytes() == b"RIFFfake-wav"
    assert transport.calls[0][:3] == ("POST", "/audio_query", {"text": "hello", "speaker": "888753760"})
    method, path, query, body, content_type = transport.calls[1]
    assert (method, path, query, content_type) == ("POST", "/synthesis", {"speaker": "888753760"}, "application/json")
    assert body is not None
    sent_query: dict[str, Any] = json.loads(body.decode("utf-8"))
    assert sent_query["speedScale"] == pytest.approx(1.2)
    assert sent_query["pitchScale"] == pytest.approx(-0.02)
    assert sent_query["intonationScale"] == pytest.approx(0.8)


def test_aivis_client_resolves_speaker_name_from_speakers_endpoint(tmp_path: Path) -> None:
    transport = RecordingTransport()
    client = AivisSpeechClient(transport=transport)

    client.synthesize_to_file(
        "hello",
        speaker="Anneli",
        output_path=tmp_path / "001.wav",
        speed_scale=1.0,
        pitch_scale=0.0,
        intonation_scale=1.0,
    )

    assert transport.calls[0][:3] == ("GET", "/speakers", {})
    assert transport.calls[1][:3] == ("POST", "/audio_query", {"text": "hello", "speaker": "888753760"})
