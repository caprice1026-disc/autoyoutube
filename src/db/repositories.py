from __future__ import annotations

import json
import sqlite3
from typing import Any

from src.bgm.library import BgmTrack
from src.media.library import MediaAsset


def upsert_project(
    connection: sqlite3.Connection,
    project: dict[str, Any],
    project_path: str,
    project_hash: str,
) -> None:
    target = project["target"]
    voice = project["voice"]
    vf = target["video_format"]
    connection.execute(
        """
        INSERT OR REPLACE INTO youtube_projects (
            id, schema_version, platform_profile, topic, internal_title, hook,
            project_json_path, project_json_hash, raw_project_json,
            planned_duration_sec, aspect_ratio, width, height, fps, container,
            video_codec, audio_codec, pix_fmt, voice_engine, voice_speaker,
            voice_speed_scale, voice_pitch_scale, voice_intonation_scale,
            voice_sentence_gap_ms, manual_fact_check_required, fact_check_notes,
            production_notes, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'validated')
        """,
        (
            project["id"],
            project["schema_version"],
            project["platform_profile"],
            project["topic"],
            project["title"],
            project["hook"],
            project_path,
            project_hash,
            json.dumps(project, ensure_ascii=False, sort_keys=True),
            target["duration_sec"],
            target["aspect_ratio"],
            target["resolution"]["width"],
            target["resolution"]["height"],
            target["fps"],
            vf["container"],
            vf["video_codec"],
            vf["audio_codec"],
            vf["pix_fmt"],
            voice["engine"],
            voice["speaker"],
            voice["speed_scale"],
            voice["pitch_scale"],
            voice["intonation_scale"],
            voice["sentence_gap_ms"],
            int(project["manual_fact_check_required"]),
            project.get("fact_check_notes"),
            project.get("production_notes"),
        ),
    )
    connection.execute(
        "DELETE FROM project_script_items WHERE project_id = ?", (project["id"],)
    )
    for item in project["script"]:
        connection.execute(
            "INSERT INTO project_script_items (project_id, item_index, text, visual_query, estimated_duration_sec, caption_style_hint) VALUES (?, ?, ?, ?, ?, ?)",
            (
                project["id"],
                item["index"],
                item["text"],
                item["visual_query"],
                item["estimated_duration_sec"],
                item["caption_style_hint"],
            ),
        )
    bgm = project["bgm"]
    connection.execute(
        "INSERT OR REPLACE INTO project_bgm_plans (project_id, enabled, strategy, mood, intensity, volume_db, fade_in_ms, fade_out_ms, allow_sources_json, avoid_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            project["id"],
            int(bgm["enabled"]),
            bgm["strategy"],
            bgm["mood"],
            bgm["intensity"],
            bgm["volume_db"],
            bgm["fade_in_ms"],
            bgm["fade_out_ms"],
            json.dumps(bgm["allow_sources"], ensure_ascii=False),
            json.dumps(bgm["avoid"], ensure_ascii=False),
        ),
    )
    visual = project["visual_strategy"]
    connection.execute(
        "INSERT OR REPLACE INTO project_visual_strategies (project_id, source_priority_json, preferred_orientation, fallback, primary_query, fallback_queries_json, avoid_keywords_json) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            project["id"],
            json.dumps(visual["source_priority"], ensure_ascii=False),
            visual["preferred_orientation"],
            visual["fallback"],
            visual["primary_query"],
            json.dumps(visual["fallback_queries"], ensure_ascii=False),
            json.dumps(visual["avoid_keywords"], ensure_ascii=False),
        ),
    )
    yt = project["youtube"]
    sections = yt["description_sections"]
    hypo = yt["analytics_hypothesis"]
    connection.execute(
        "INSERT OR REPLACE INTO project_youtube_metadata (project_id, youtube_title, youtube_description, hashtags_json, tags_json, category_hint, privacy_status, made_for_kids, contains_synthetic_voice, description_summary, credits_policy, disclaimer, experiment_group, hypothesis, primary_metric, secondary_metrics_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            project["id"],
            yt["title"],
            yt["description"],
            json.dumps(yt["hashtags"], ensure_ascii=False),
            json.dumps(yt["tags"], ensure_ascii=False),
            yt["category_hint"],
            yt["privacy_status"],
            int(yt["made_for_kids"]),
            int(yt["contains_synthetic_voice"]),
            sections["summary"],
            sections["credits_policy"],
            sections["disclaimer"],
            hypo["experiment_group"],
            hypo["hypothesis"],
            hypo["primary_metric"],
            json.dumps(hypo["secondary_metrics"], ensure_ascii=False),
        ),
    )


def insert_render_summary(
    connection: sqlite3.Connection, rendered: dict[str, Any]
) -> None:
    target = rendered["target"]
    vf = target["video_format"]
    connection.execute(
        "INSERT INTO youtube_renders (render_id, project_id, schema_version, platform_profile, status, created_at, completed_at, project_json_path, project_json_hash, project_schema_path, video_path, thumbnail_path, subtitle_ass_path, description_path, credits_path, rendered_json_path, logs_dir, raw_rendered_json, planned_duration_sec, actual_duration_sec, aspect_ratio, width, height, fps, container, video_codec, audio_codec, pix_fmt) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            rendered["render_id"],
            rendered["project_id"],
            rendered["schema_version"],
            rendered["platform_profile"],
            rendered["status"],
            rendered["created_at"],
            rendered["completed_at"],
            rendered["input"]["project_json_path"],
            rendered["input"]["project_json_hash"],
            rendered["input"]["project_schema_path"],
            rendered["output"]["video_path"],
            rendered["output"].get("thumbnail_path"),
            rendered["output"]["subtitle_ass_path"],
            rendered["output"]["description_path"],
            rendered["output"]["credits_path"],
            rendered["output"]["rendered_json_path"],
            rendered["output"].get("logs_dir"),
            json.dumps(rendered, ensure_ascii=False, sort_keys=True),
            target["planned_duration_sec"],
            target["actual_duration_sec"],
            target["aspect_ratio"],
            target["resolution"]["width"],
            target["resolution"]["height"],
            target["fps"],
            vf["container"],
            vf["video_codec"],
            vf["audio_codec"],
            vf["pix_fmt"],
        ),
    )
    mr = rendered["manual_review"]
    connection.execute(
        "INSERT INTO render_manual_reviews (render_id, required, fact_check_required, checked, publish_ready, notes) VALUES (?, ?, ?, ?, ?, ?)",
        (
            rendered["render_id"],
            int(mr["required"]),
            int(mr["fact_check_required"]),
            int(mr["checked"]),
            int(mr["publish_ready"]),
            mr["notes"],
        ),
    )
    bgm = rendered["bgm"]
    connection.execute(
        """
        INSERT INTO render_bgm_usage (
            render_id, enabled, strategy, track_id, file_path, title, artist,
            source, license_type, attribution_required, attribution_text,
            mood, intensity, volume_db, fade_in_ms, fade_out_ms,
            looped, used_start_sec, used_duration_sec
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            rendered["render_id"],
            int(bool(bgm.get("enabled"))),
            bgm.get("strategy"),
            bgm.get("track_id"),
            bgm.get("file_path"),
            bgm.get("title"),
            bgm.get("artist"),
            bgm.get("source"),
            bgm.get("license_type"),
            _optional_bool_int(bgm.get("attribution_required")),
            bgm.get("attribution_text"),
            bgm.get("mood"),
            bgm.get("intensity"),
            bgm.get("volume_db"),
            bgm.get("fade_in_ms"),
            bgm.get("fade_out_ms"),
            _optional_bool_int(bgm.get("looped")),
            bgm.get("used_start_sec"),
            bgm.get("used_duration_sec"),
        ),
    )
    if bgm.get("track_id"):
        connection.execute(
            "UPDATE bgm_tracks SET used_count = used_count + 1, last_used_at = ? WHERE track_id = ?",
            (rendered["completed_at"], bgm["track_id"]),
        )
    for visual in rendered["visuals"]:
        connection.execute(
            """
            INSERT INTO render_visual_items (
                render_id, item_index, script_index, visual_query, source, asset_id,
                pexels_id, photographer, photographer_url, pexels_url, original_video_url,
                local_file_path, original_width, original_height, original_duration_sec,
                orientation, selected_quality, transform_type, crop_x, crop_y,
                crop_width, crop_height, scale_width, scale_height,
                used_start_sec, used_duration_sec, video_start_sec, video_end_sec
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                rendered["render_id"],
                visual["index"],
                visual["script_index"],
                visual["visual_query"],
                visual["source"],
                visual.get("asset_id"),
                visual.get("pexels_id"),
                visual.get("photographer"),
                visual.get("photographer_url"),
                visual.get("pexels_url"),
                visual.get("original_video_url"),
                visual["local_file_path"],
                visual["original_width"],
                visual["original_height"],
                visual["original_duration_sec"],
                visual["orientation"],
                visual["selected_quality"],
                visual["transform"]["type"],
                visual["transform"].get("crop_x"),
                visual["transform"].get("crop_y"),
                visual["transform"].get("crop_width"),
                visual["transform"].get("crop_height"),
                visual["transform"]["scale_width"],
                visual["transform"]["scale_height"],
                visual["used_start_sec"],
                visual["used_duration_sec"],
                visual["video_start_sec"],
                visual["video_end_sec"],
            ),
        )
        if visual.get("asset_id"):
            connection.execute(
                "UPDATE media_assets SET used_count = used_count + 1, last_used_at = ? WHERE asset_id = ?",
                (rendered["completed_at"], visual["asset_id"]),
            )


def upsert_bgm_tracks(connection: sqlite3.Connection, tracks: list[BgmTrack]) -> None:
    for track in tracks:
        connection.execute(
            """
            INSERT INTO bgm_tracks (
                track_id, file_path, title, artist, source, license_type,
                attribution_required, attribution_text, mood, intensity,
                duration_sec, bpm, loopable, allowed_platforms_json,
                used_count, is_active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(track_id) DO UPDATE SET
                file_path = excluded.file_path,
                title = excluded.title,
                artist = excluded.artist,
                source = excluded.source,
                license_type = excluded.license_type,
                attribution_required = excluded.attribution_required,
                attribution_text = excluded.attribution_text,
                mood = excluded.mood,
                intensity = excluded.intensity,
                duration_sec = excluded.duration_sec,
                bpm = excluded.bpm,
                loopable = excluded.loopable,
                allowed_platforms_json = excluded.allowed_platforms_json,
                is_active = excluded.is_active
            """,
            (
                track.track_id,
                str(track.file_path),
                track.title,
                track.artist,
                track.source,
                track.license_type,
                int(track.attribution_required),
                track.attribution_text,
                track.mood,
                track.intensity,
                track.duration_sec,
                track.bpm,
                int(track.loopable),
                json.dumps(track.allowed_platforms, ensure_ascii=False),
                track.used_count,
                int(track.is_active),
            ),
        )


def list_active_bgm_tracks(connection: sqlite3.Connection) -> list[BgmTrack]:
    rows = connection.execute(
        """
        SELECT
            track_id, file_path, title, artist, source, license_type,
            attribution_required, attribution_text, mood, intensity,
            duration_sec, bpm, loopable, allowed_platforms_json,
            used_count, is_active
        FROM bgm_tracks
        WHERE is_active = 1
        ORDER BY used_count ASC, track_id ASC
        """
    ).fetchall()
    return [_bgm_track_from_row(row) for row in rows]


def upsert_media_assets(
    connection: sqlite3.Connection, assets: list[MediaAsset]
) -> None:
    for asset in assets:
        connection.execute(
            """
            INSERT INTO media_assets (
                asset_id, source, local_file_path, original_width, original_height,
                original_duration_sec, orientation, selected_quality, query,
                tags_json, used_count, is_active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(asset_id) DO UPDATE SET
                source = excluded.source,
                local_file_path = excluded.local_file_path,
                original_width = excluded.original_width,
                original_height = excluded.original_height,
                original_duration_sec = excluded.original_duration_sec,
                orientation = excluded.orientation,
                selected_quality = excluded.selected_quality,
                query = excluded.query,
                tags_json = excluded.tags_json,
                is_active = excluded.is_active
            """,
            (
                asset.asset_id,
                asset.source,
                str(asset.local_file_path),
                asset.original_width,
                asset.original_height,
                asset.original_duration_sec,
                asset.orientation,
                asset.selected_quality,
                asset.query,
                json.dumps(asset.tags, ensure_ascii=False),
                asset.used_count,
                int(asset.is_active),
            ),
        )


def list_active_media_assets(connection: sqlite3.Connection) -> list[MediaAsset]:
    rows = connection.execute(
        """
        SELECT
            asset_id, source, local_file_path, original_width, original_height,
            original_duration_sec, orientation, selected_quality, query,
            tags_json, used_count, is_active
        FROM media_assets
        WHERE is_active = 1
        ORDER BY used_count ASC, asset_id ASC
        """
    ).fetchall()
    return [_media_asset_from_row(row) for row in rows]


def _bgm_track_from_row(row: sqlite3.Row) -> BgmTrack:
    from pathlib import Path

    return BgmTrack(
        track_id=row["track_id"],
        file_path=Path(row["file_path"]),
        title=row["title"] or "",
        artist=row["artist"] or "",
        source=row["source"],
        license_type=row["license_type"] or "",
        attribution_required=bool(row["attribution_required"]),
        attribution_text=row["attribution_text"] or "",
        mood=row["mood"] or "none",
        intensity=row["intensity"] or "none",
        duration_sec=row["duration_sec"],
        bpm=row["bpm"],
        loopable=bool(row["loopable"]),
        allowed_platforms=json.loads(row["allowed_platforms_json"]),
        used_count=int(row["used_count"]),
        is_active=bool(row["is_active"]),
    )


def _media_asset_from_row(row: sqlite3.Row) -> MediaAsset:
    from pathlib import Path

    return MediaAsset(
        asset_id=row["asset_id"],
        source=row["source"],
        local_file_path=Path(row["local_file_path"]),
        original_width=row["original_width"],
        original_height=row["original_height"],
        original_duration_sec=row["original_duration_sec"],
        orientation=row["orientation"] or "unknown",
        selected_quality=row["selected_quality"] or "unknown",
        query=row["query"] or "",
        tags=json.loads(row["tags_json"] or "[]"),
        used_count=int(row["used_count"]),
        is_active=bool(row["is_active"]),
    )


def _optional_bool_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(bool(value))
