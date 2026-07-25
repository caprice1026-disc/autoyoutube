from __future__ import annotations

from typing import Any

from src.bgm.library import BgmTrack
from src.defaults import (
    DEFAULT_SUBTITLE_FONT_NAME,
    DEFAULT_SUBTITLE_FONT_SIZE,
    DEFAULT_SUBTITLE_MARGIN_V,
    DEFAULT_SUBTITLE_OUTLINE,
    DEFAULT_SUBTITLE_SHADOW,
    MAX_BGM_VOLUME_DB,
    MAX_SUBTITLE_CHARS,
    TARGET_HEIGHT,
    TARGET_WIDTH,
)


def build_description(project: dict[str, Any]) -> str:
    yt = project["youtube"]
    sections = yt["description_sections"]
    return (
        "\n".join(
            [
                yt["description"],
                "",
                sections["summary"],
                "",
                " ".join(yt["hashtags"]),
                "",
                sections["disclaimer"],
            ]
        ).strip()
        + "\n"
    )


def build_bgm_render(
    project_bgm: dict[str, Any], track: BgmTrack | None, actual_duration: float
) -> dict[str, Any] | None:
    if track is None:
        return None
    requested_volume_db = float(project_bgm["volume_db"])
    effective_volume_db = max(requested_volume_db, MAX_BGM_VOLUME_DB)
    return {
        "enabled": True,
        "strategy": project_bgm["strategy"],
        "track_id": track.track_id,
        "file_path": str(track.file_path),
        "title": track.title,
        "artist": track.artist,
        "source": track.source,
        "license_type": track.license_type,
        "attribution_required": track.attribution_required,
        "attribution_text": track.attribution_text,
        "mood": track.mood,
        "intensity": track.intensity,
        "volume_db": effective_volume_db,
        "fade_in_ms": project_bgm["fade_in_ms"],
        "fade_out_ms": project_bgm["fade_out_ms"],
        "looped": bool(
            track.loopable
            and track.duration_sec is not None
            and track.duration_sec < actual_duration
        ),
        "used_start_sec": 0,
        "used_duration_sec": actual_duration,
    }


def build_credits(
    track: BgmTrack | None, visuals: list[dict[str, Any]]
) -> tuple[bool, list[dict[str, Any]], str]:
    items: list[dict[str, Any]] = []
    lines: list[str] = []
    required = False
    if track is not None:
        text = track.attribution_text or f"BGM: {track.title} by {track.artist}".strip()
        items.append(
            {"credit_type": "bgm", "source": track.source, "text": text, "url": None}
        )
        lines.append(text)
        required = track.attribution_required

    seen_pexels_urls: set[str] = set()
    for visual in visuals:
        if visual.get("source") != "pexels":
            continue
        pexels_url = str(visual.get("pexels_url") or "").strip()
        if not pexels_url or pexels_url in seen_pexels_urls:
            continue
        seen_pexels_urls.add(pexels_url)
        photographer = str(visual.get("photographer") or "Pexels creator").strip()
        text = f"Video by {photographer} on Pexels"
        items.append(
            {
                "credit_type": "video",
                "source": "pexels",
                "text": text,
                "url": pexels_url,
            }
        )
        lines.extend([f"Video: {text}", pexels_url])

    if not items:
        return False, [], "Dry-run render: external visual media and BGM were not used.\n"
    return required or bool(seen_pexels_urls), items, "\n".join(lines) + "\n"


def build_subtitle(subtitle_items: list[dict[str, Any]]) -> str:
    lines = [
        "[Script Info]",
        "ScriptType: v4.00+",
        f"PlayResX: {TARGET_WIDTH}",
        f"PlayResY: {TARGET_HEIGHT}",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: Default,{DEFAULT_SUBTITLE_FONT_NAME},{DEFAULT_SUBTITLE_FONT_SIZE},"
        "&H00FFFFFF,&H00000000,1,"
        f"{DEFAULT_SUBTITLE_OUTLINE},{DEFAULT_SUBTITLE_SHADOW},2,80,80,"
        f"{DEFAULT_SUBTITLE_MARGIN_V},1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    for item in subtitle_items:
        lines.append(
            f"Dialogue: 0,{ass_time(item['start_sec'])},{ass_time(item['end_sec'])},Default,,0,0,0,,{item['text']}"
        )
    return "\n".join(lines) + "\n"


def wrap_subtitle_text(text: str, max_chars: int = MAX_SUBTITLE_CHARS) -> str:
    if len(text) <= max_chars:
        return text
    remaining = text
    lines: list[str] = []
    while len(remaining) > max_chars:
        break_at = subtitle_break_position(remaining, max_chars)
        lines.append(remaining[:break_at].strip())
        remaining = remaining[break_at:].strip()
    if remaining:
        lines.append(remaining)
    return r"\N".join(lines)


def subtitle_break_position(text: str, max_chars: int) -> int:
    search_limit = min(max_chars, len(text) - 1)
    midpoint = min(len(text), max_chars * 2) / 2
    punctuation = "、。！？!? "
    candidates = [
        index + 1
        for index, char in enumerate(text[:search_limit])
        if char in punctuation and 0 < index + 1 < len(text)
    ]
    if candidates:
        return min(candidates, key=lambda position: abs(position - midpoint))
    return search_limit


def ass_time(seconds: float) -> str:
    centis = int(round(seconds * 100))
    s, cs = divmod(centis, 100)
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"
