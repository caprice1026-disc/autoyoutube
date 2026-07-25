from __future__ import annotations

from collections.abc import Callable
from typing import Any

CheckFn = Callable[..., list[dict[str, Any]]]


def collect_quality_checks(
    rendered: dict[str, Any],
    probe_result: dict[str, Any],
    audio_checks: list[dict[str, Any]],
    *,
    file_checks: CheckFn,
    video_checks: CheckFn,
    credit_checks: CheckFn,
    subtitle_checks: CheckFn,
    bgm_checks: CheckFn,
    ffmpeg_checks: CheckFn,
    visual_checks: CheckFn,
) -> list[dict[str, Any]]:
    """Run quality checks in the stable report order, grouped by domain."""

    checks: list[dict[str, Any]] = []
    checks.extend(file_checks(rendered))
    checks.extend(video_checks(rendered, probe_result))
    checks.extend(audio_checks)
    checks.extend(credit_checks(rendered))
    checks.extend(subtitle_checks(rendered))
    checks.extend(bgm_checks(rendered))
    checks.extend(ffmpeg_checks(rendered))
    checks.extend(visual_checks(rendered))
    return checks
