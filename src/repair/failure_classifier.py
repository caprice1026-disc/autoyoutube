from __future__ import annotations

from typing import Any


def classify_exception(exc: Exception) -> dict[str, Any]:
    message = str(exc)
    lowered = message.lower()
    if "pexels" in lowered or "rate limit" in lowered:
        return _failure("external_api_error", "PEXELS_FETCH_FAILED", message, True)
    if "aivis" in lowered or "docker" in lowered:
        return _failure("environment_error", "AIVIS_SPEECH_UNREACHABLE", message, True)
    if "ffmpeg" in lowered:
        return _failure("render_error", "FFMPEG_FAILED", message, True)
    if "encoding" in lowered or "unicode" in lowered:
        return _failure("encoding_error", "ENCODING_ERROR", message, False)
    return _failure("render_error", "UNEXPECTED_PIPELINE_ERROR", message, False)


def _failure(
    category: str, code: str, message: str, recoverable: bool
) -> dict[str, Any]:
    return {
        "category": category,
        "code": code,
        "message": message,
        "recoverable": recoverable,
    }
