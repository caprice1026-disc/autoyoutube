from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.bgm.library import BgmTrack, load_bgm_manifest
from src.bgm.selector import select_bgm_track
from src.db.database import init_db
from src.db.repositories import list_active_bgm_tracks, upsert_bgm_tracks
from src.errors import AppError


def test_load_bgm_manifest_resolves_relative_paths_and_defaults(tmp_path: Path) -> None:
    audio_path = tmp_path / "mystery.wav"
    audio_path.write_bytes(b"placeholder")
    manifest_path = tmp_path / "bgm.json"
    manifest_path.write_text(
        json.dumps(
            {
                "tracks": [
                    {
                        "track_id": "mystery_low",
                        "file_path": "mystery.wav",
                        "title": "Mystery Low",
                        "artist": "Local",
                        "source": "local_original",
                        "license_type": "local_safe",
                        "mood": "mysterious",
                        "intensity": "low",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    tracks = load_bgm_manifest(manifest_path)

    assert tracks == [
        BgmTrack(
            track_id="mystery_low",
            file_path=audio_path,
            title="Mystery Low",
            artist="Local",
            source="local_original",
            license_type="local_safe",
            attribution_required=False,
            attribution_text="",
            mood="mysterious",
            intensity="low",
            duration_sec=None,
            bpm=None,
            loopable=True,
            allowed_platforms=["youtube_shorts"],
            used_count=0,
            is_active=True,
        )
    ]


def test_select_bgm_track_matches_project_plan_and_lowest_used_count(
    tmp_path: Path,
) -> None:
    selected = select_bgm_track(
        {
            "enabled": True,
            "strategy": "local_safe_bgm",
            "mood": "mysterious",
            "intensity": "low",
            "allow_sources": ["local_original"],
            "avoid": ["vocal"],
        },
        [
            BgmTrack(
                track_id="used",
                file_path=tmp_path / "used.wav",
                title="Used",
                artist="Local",
                source="local_original",
                license_type="local_safe",
                attribution_required=False,
                attribution_text="",
                mood="mysterious",
                intensity="low",
                duration_sec=20,
                bpm=None,
                loopable=True,
                allowed_platforms=["youtube_shorts"],
                used_count=4,
                is_active=True,
            ),
            BgmTrack(
                track_id="fresh",
                file_path=tmp_path / "fresh.wav",
                title="Fresh",
                artist="Local",
                source="local_original",
                license_type="local_safe",
                attribution_required=False,
                attribution_text="",
                mood="mysterious",
                intensity="low",
                duration_sec=20,
                bpm=None,
                loopable=True,
                allowed_platforms=["youtube_shorts"],
                used_count=0,
                is_active=True,
            ),
        ],
    )

    assert selected.track_id == "fresh"


def test_select_bgm_track_honors_explicit_track_id(tmp_path: Path) -> None:
    selected = select_bgm_track(
        {
            "enabled": True,
            "strategy": "youtube_safe_bgm",
            "track_id": "No One Here Gets In Alive",
            "mood": "mysterious",
            "intensity": "low",
            "allow_sources": ["youtube_audio_library"],
            "avoid": ["vocal"],
        },
        [
            BgmTrack(
                track_id="fresh",
                file_path=tmp_path / "fresh.wav",
                title="Fresh",
                artist="Local",
                source="youtube_audio_library",
                license_type="youtube_audio_library_standard",
                attribution_required=False,
                attribution_text="",
                mood="mysterious",
                intensity="low",
                duration_sec=20,
                bpm=None,
                loopable=True,
                allowed_platforms=["youtube_shorts"],
                used_count=0,
                is_active=True,
            ),
            BgmTrack(
                track_id="No One Here Gets In Alive",
                file_path=tmp_path / "no-one.mp3",
                title="No One Here Gets In Alive",
                artist="National Sweetheart",
                source="youtube_audio_library",
                license_type="youtube_audio_library_standard",
                attribution_required=False,
                attribution_text="",
                mood="mysterious",
                intensity="low",
                duration_sec=20,
                bpm=None,
                loopable=True,
                allowed_platforms=["youtube_shorts"],
                used_count=8,
                is_active=True,
            ),
        ],
    )

    assert selected.track_id == "No One Here Gets In Alive"


def test_select_bgm_track_raises_actionable_error_when_no_track_matches(
    tmp_path: Path,
) -> None:
    with pytest.raises(AppError) as exc_info:
        select_bgm_track(
            {
                "enabled": True,
                "strategy": "local_safe_bgm",
                "mood": "dark",
                "intensity": "low",
                "allow_sources": ["local_original"],
                "avoid": [],
            },
            [
                BgmTrack(
                    track_id="bright",
                    file_path=tmp_path / "bright.wav",
                    title="Bright",
                    artist="Local",
                    source="local_original",
                    license_type="local_safe",
                    attribution_required=False,
                    attribution_text="",
                    mood="light",
                    intensity="low",
                    duration_sec=20,
                    bpm=None,
                    loopable=True,
                    allowed_platforms=["youtube_shorts"],
                    used_count=0,
                    is_active=True,
                )
            ],
        )

    assert exc_info.value.message == "No BGM track matched project requirements."
    assert (
        exc_info.value.next_step
        == "Import a matching BGM manifest or change project.bgm settings."
    )


def test_bgm_tracks_round_trip_through_database(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    init_db(db_path)
    track = BgmTrack(
        track_id="mystery_low",
        file_path=tmp_path / "mystery.wav",
        title="Mystery Low",
        artist="Local",
        source="local_original",
        license_type="local_safe",
        attribution_required=False,
        attribution_text="",
        mood="mysterious",
        intensity="low",
        duration_sec=12,
        bpm=90,
        loopable=True,
        allowed_platforms=["youtube_shorts"],
        used_count=0,
        is_active=True,
    )

    import sqlite3

    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        upsert_bgm_tracks(connection, [track])
        loaded = list_active_bgm_tracks(connection)

    assert loaded == [track]
