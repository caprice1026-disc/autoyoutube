from __future__ import annotations

from typing import Any, Sequence

from src.bgm.library import BgmTrack
from src.errors import AppError


def select_bgm_track(project_bgm: dict[str, Any], tracks: Sequence[BgmTrack]) -> BgmTrack | None:
    if not project_bgm.get("enabled") or project_bgm.get("strategy") == "none":
        return None

    allow_sources = set(project_bgm.get("allow_sources") or [])
    mood = project_bgm.get("mood")
    intensity = project_bgm.get("intensity")
    matches = [
        track
        for track in tracks
        if track.is_active
        and track.source in allow_sources
        and track.mood == mood
        and track.intensity == intensity
        and "youtube_shorts" in track.allowed_platforms
    ]
    if not matches:
        raise AppError(
            "No BGM track matched project requirements.",
            details=f"mood={mood}, intensity={intensity}, allow_sources={sorted(allow_sources)}",
            next_step="Import a matching BGM manifest or change project.bgm settings.",
        )
    return sorted(matches, key=lambda track: (track.used_count, track.track_id))[0]
