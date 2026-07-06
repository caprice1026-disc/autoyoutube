from __future__ import annotations

from typing import Any, Sequence

from src.media.library import MediaAsset, media_asset_source_key


def select_media_asset(
    script_item: dict[str, Any],
    visual_strategy: dict[str, Any],
    assets: Sequence[MediaAsset],
    *,
    used_source_keys: set[str] | None = None,
) -> MediaAsset | None:
    source_priority = list(visual_strategy.get("source_priority") or [])
    avoid_keywords = {
        str(keyword).lower() for keyword in visual_strategy.get("avoid_keywords") or []
    }
    visual_query = str(script_item.get("visual_query") or "").lower()
    rejected_source_keys = used_source_keys or set()

    matches = [
        asset
        for asset in assets
        if asset.is_active
        and asset.source in source_priority
        and media_asset_source_key(asset) not in rejected_source_keys
        and _matches_query(visual_query, asset)
        and not _has_avoid_keyword(asset, avoid_keywords)
    ]
    if not matches:
        return None

    return sorted(
        matches,
        key=lambda asset: (
            source_priority.index(asset.source),
            0 if asset.orientation == "portrait" else 1,
            asset.used_count,
            asset.asset_id,
        ),
    )[0]


def _matches_query(visual_query: str, asset: MediaAsset) -> bool:
    haystack = " ".join([asset.query, *asset.tags]).lower()
    tokens = [token for token in visual_query.split() if token]
    return bool(tokens) and any(token in haystack for token in tokens)


def _has_avoid_keyword(asset: MediaAsset, avoid_keywords: set[str]) -> bool:
    haystack = " ".join([asset.query, *asset.tags]).lower()
    return any(keyword in haystack for keyword in avoid_keywords)
