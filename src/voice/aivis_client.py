from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol
from urllib import error, parse, request


class AivisSpeechError(RuntimeError):
    pass


class AivisTransport(Protocol):
    def get(self, path: str, query: dict[str, str]) -> tuple[str, bytes]:
        ...

    def post(self, path: str, query: dict[str, str], body: bytes | None, content_type: str | None) -> tuple[str, bytes]:
        ...


class UrlLibAivisTransport:
    def __init__(self, base_url: str = "http://127.0.0.1:10101", timeout: float = 60.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def get(self, path: str, query: dict[str, str]) -> tuple[str, bytes]:
        return self._request("GET", path, query, None, None)

    def post(self, path: str, query: dict[str, str], body: bytes | None, content_type: str | None) -> tuple[str, bytes]:
        return self._request("POST", path, query, body if body is not None else b"", content_type)

    def _request(self, method: str, path: str, query: dict[str, str], body: bytes | None, content_type: str | None) -> tuple[str, bytes]:
        url = f"{self.base_url}{path}"
        if query:
            url = f"{url}?{parse.urlencode(query)}"
        headers = {}
        if content_type:
            headers["Content-Type"] = content_type
        req = request.Request(url, data=body, headers=headers, method=method)
        try:
            with request.urlopen(req, timeout=self.timeout) as response:
                return response.headers.get("Content-Type", ""), response.read()
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise AivisSpeechError(f"AivisSpeech returned HTTP {exc.code} for {method} {path}: {detail}") from exc
        except error.URLError as exc:
            raise AivisSpeechError(f"Could not connect to AivisSpeech at {self.base_url}: {exc.reason}") from exc


class AivisSpeechClient:
    def __init__(self, base_url: str = "http://127.0.0.1:10101", transport: AivisTransport | None = None) -> None:
        self.transport = transport or UrlLibAivisTransport(base_url=base_url)
        self._speakers_cache: list[dict] | None = None

    def synthesize_to_file(
        self,
        text: str,
        speaker: str | int,
        output_path: Path,
        speed_scale: float,
        pitch_scale: float,
        intonation_scale: float,
    ) -> Path:
        speaker_id = self._resolve_speaker_id(speaker)
        _, query_bytes = self.transport.post("/audio_query", {"text": text, "speaker": str(speaker_id)}, None, None)
        audio_query = json.loads(query_bytes.decode("utf-8"))
        audio_query["speedScale"] = speed_scale
        audio_query["pitchScale"] = pitch_scale
        audio_query["intonationScale"] = intonation_scale

        body = json.dumps(audio_query, ensure_ascii=False).encode("utf-8")
        _, wav_bytes = self.transport.post("/synthesis", {"speaker": str(speaker_id)}, body, "application/json")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(wav_bytes)
        return output_path

    def _resolve_speaker_id(self, speaker: str | int) -> int:
        if isinstance(speaker, int):
            return speaker
        speaker_text = str(speaker).strip()
        if speaker_text.isdecimal():
            return int(speaker_text)

        for entry in self._speakers():
            styles = entry.get("styles", [])
            for style in styles:
                style_id = style.get("id")
                if style_id is not None and style.get("name") == speaker_text:
                    return int(style_id)
            if entry.get("name") == speaker_text:
                talk_styles = [style for style in styles if style.get("type", "talk") == "talk"]
                selected = (talk_styles or styles)[0] if styles else None
                if selected and selected.get("id") is not None:
                    return int(selected["id"])
        raise ValueError(f"AivisSpeech speaker must be a numeric style ID or a name from /speakers: {speaker_text}")

    def _speakers(self) -> list[dict]:
        if self._speakers_cache is None:
            _, body = self.transport.get("/speakers", {})
            loaded = json.loads(body.decode("utf-8"))
            if not isinstance(loaded, list):
                raise AivisSpeechError("/speakers did not return a list")
            self._speakers_cache = loaded
        return self._speakers_cache
