from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from src.db.database import init_db
from src.db.repositories import list_active_media_assets, upsert_media_assets
from src.media.library import MediaAsset, load_media_manifest, media_asset_source_key
from src.media.selector import select_media_asset


def test_load_media_manifest_resolves_relative_paths_and_defaults(
    tmp_path: Path,
) -> None:
    video_path = tmp_path / "ocean.mp4"
    video_path.write_bytes(b"placeholder")
    manifest_path = tmp_path / "media_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "assets": [
                    {
                        "asset_id": "ocean_portrait",
                        "local_file_path": "ocean.mp4",
                        "query": "dark ocean",
                        "tags": ["ocean", "deep sea"],
                        "original_width": 1080,
                        "original_height": 1920,
                        "original_duration_sec": 8.0,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    assets = load_media_manifest(manifest_path)

    assert assets == [
        MediaAsset(
            asset_id="ocean_portrait",
            source="local",
            local_file_path=video_path.resolve(),
            original_width=1080,
            original_height=1920,
            original_duration_sec=8.0,
            orientation="portrait",
            selected_quality="unknown",
            query="dark ocean",
            tags=["ocean", "deep sea"],
            used_count=0,
            is_active=True,
        )
    ]


def test_select_media_asset_matches_visual_query_and_lowest_used_count(
    tmp_path: Path,
) -> None:
    used = MediaAsset(
        asset_id="used_ocean",
        source="local",
        local_file_path=tmp_path / "used.mp4",
        original_width=1080,
        original_height=1920,
        original_duration_sec=10,
        orientation="portrait",
        selected_quality="hd",
        query="dark ocean",
        tags=["ocean"],
        used_count=5,
        is_active=True,
    )
    fresh = MediaAsset(
        asset_id="fresh_ocean",
        source="local",
        local_file_path=tmp_path / "fresh.mp4",
        original_width=1080,
        original_height=1920,
        original_duration_sec=10,
        orientation="portrait",
        selected_quality="hd",
        query="deep ocean",
        tags=["ocean"],
        used_count=0,
        is_active=True,
    )

    selected = select_media_asset(
        {"visual_query": "ocean"},
        {"source_priority": ["local"], "avoid_keywords": ["toy"]},
        [used, fresh],
    )

    assert selected == fresh


def test_select_media_asset_returns_none_when_no_asset_matches(tmp_path: Path) -> None:
    selected = select_media_asset(
        {"visual_query": "submarine"},
        {"source_priority": ["local"], "avoid_keywords": []},
        [
            MediaAsset(
                asset_id="ocean",
                source="local",
                local_file_path=tmp_path / "ocean.mp4",
                original_width=1080,
                original_height=1920,
                original_duration_sec=10,
                orientation="portrait",
                selected_quality="hd",
                query="dark ocean",
                tags=["ocean"],
                used_count=0,
                is_active=True,
            )
        ],
    )

    assert selected is None


def test_select_media_asset_skips_used_source_key_even_if_asset_ids_differ(
    tmp_path: Path,
) -> None:
    shared_path = tmp_path / "shared.mp4"
    shared_path.write_bytes(b"fake mp4")
    first = MediaAsset(
        asset_id="shared_a",
        source="local",
        local_file_path=shared_path,
        original_width=1080,
        original_height=1920,
        original_duration_sec=10,
        orientation="portrait",
        selected_quality="hd",
        query="ocean",
        tags=["ocean"],
        used_count=0,
        is_active=True,
    )
    second = MediaAsset(
        asset_id="shared_b",
        source="local",
        local_file_path=shared_path,
        original_width=1080,
        original_height=1920,
        original_duration_sec=10,
        orientation="portrait",
        selected_quality="hd",
        query="ocean",
        tags=["ocean"],
        used_count=0,
        is_active=True,
    )

    selected = select_media_asset(
        {"visual_query": "ocean"},
        {"source_priority": ["local"], "avoid_keywords": []},
        [first, second],
        used_source_keys={media_asset_source_key(first)},
    )

    assert selected is None


def test_media_assets_round_trip_through_database(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    init_db(db_path)
    asset = MediaAsset(
        asset_id="ocean_portrait",
        source="local",
        local_file_path=tmp_path / "ocean.mp4",
        original_width=1080,
        original_height=1920,
        original_duration_sec=8.0,
        orientation="portrait",
        selected_quality="hd",
        query="dark ocean",
        tags=["ocean", "deep sea"],
        used_count=0,
        is_active=True,
    )

    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        upsert_media_assets(connection, [asset])
        loaded = list_active_media_assets(connection)

    assert loaded == [asset]


def test_pexels_media_asset_round_trip_keeps_source_metadata(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "test.db"
    init_db(db_path)
    asset = MediaAsset(
        asset_id="pexels_20349819_deep_ocean",
        source="pexels",
        local_file_path=tmp_path / "pexels_20349819_deep_ocean.mp4",
        original_width=1080,
        original_height=1920,
        original_duration_sec=12.0,
        orientation="portrait",
        selected_quality="hd",
        query="deep ocean",
        tags=["deep", "ocean"],
        pexels_id="20349819",
        photographer="Pexels Creator",
        photographer_url="https://www.pexels.com/@creator",
        pexels_url="https://www.pexels.com/video/deep-ocean-20349819/",
        original_video_url="https://videos.pexels.com/video-files/hd.mp4",
    )

    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        upsert_media_assets(connection, [asset])
        loaded = list_active_media_assets(connection)

    assert loaded == [asset]
