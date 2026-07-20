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
            voice_style_id, voice_speed_scale, voice_pitch_scale, voice_intonation_scale,
            voice_sentence_gap_ms, manual_fact_check_required, fact_check_notes,
            production_notes, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'validated')
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
            voice.get("style_id"),
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
    voice = rendered["voice"]
    connection.execute(
        """
        INSERT INTO render_voice_settings (
            render_id, engine, speaker, voice_style_id, speed_scale, pitch_scale,
            intonation_scale, sentence_gap_ms, sample_rate, audio_format
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            rendered["render_id"],
            voice["engine"],
            voice["speaker"],
            voice.get("style_id"),
            voice["speed_scale"],
            voice["pitch_scale"],
            voice["intonation_scale"],
            voice["sentence_gap_ms"],
            voice["sample_rate"],
            voice["audio_format"],
        ),
    )
    mr = rendered.get("manual_review")
    if mr is not None:
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

    subtitles = rendered.get("subtitles") or {}
    style = subtitles.get("style") if isinstance(subtitles, dict) else None
    if isinstance(style, dict) and style:
        connection.execute(
            """
            INSERT OR REPLACE INTO render_subtitle_styles (
                render_id, format, font_name, font_size, primary_color,
                outline_color, outline, shadow, alignment, margin_v
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                rendered["render_id"],
                subtitles.get("format") or "ass",
                style.get("font_name") or "Arial",
                style.get("font_size") or 72,
                style.get("primary_color") or "FFFFFF",
                style.get("outline_color") or "000000",
                style.get("outline") or 0,
                style.get("shadow") or 0,
                style.get("alignment") or "bottom_center",
                style.get("margin_v") or 0,
            ),
        )
    connection.execute(
        "DELETE FROM render_subtitle_items WHERE render_id = ?",
        (rendered["render_id"],),
    )
    for item in subtitles.get("items", []) if isinstance(subtitles, dict) else []:
        if not isinstance(item, dict):
            continue
        connection.execute(
            """
            INSERT INTO render_subtitle_items (
                render_id, item_index, text, start_sec, end_sec, caption_style_hint
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                rendered["render_id"],
                item.get("index") or 1,
                item.get("text") or "",
                item.get("start_sec") or 0,
                item.get("end_sec") or 0,
                item.get("caption_style_hint") or "normal",
            ),
        )

    validation = rendered.get("validation") or {}
    connection.execute(
        "INSERT OR REPLACE INTO render_validation_results (render_id, project_json_valid, rendered_json_valid) VALUES (?, ?, ?)",
        (
            rendered["render_id"],
            int(bool(validation.get("project_json_valid", True))),
            int(bool(validation.get("rendered_json_valid", True))),
        ),
    )
    connection.execute(
        "DELETE FROM render_validation_messages WHERE render_id = ?",
        (rendered["render_id"],),
    )
    for level, messages in (
        ("warning", validation.get("warnings") or []),
        ("error", validation.get("errors") or []),
    ):
        for index, message in enumerate(messages):
            if isinstance(message, dict):
                code = str(message.get("code") or f"VALIDATION_{level.upper()}")
                text = str(message.get("message") or message)
                details = json.dumps(message, ensure_ascii=False, sort_keys=True)
            else:
                code = f"VALIDATION_{level.upper()}_{index + 1}"
                text = str(message)
                details = None
            connection.execute(
                "INSERT INTO render_validation_messages (render_id, level, code, message, details_json) VALUES (?, ?, ?, ?, ?)",
                (rendered["render_id"], level, code, text, details),
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
                asset_id, source, pexels_id, photographer, photographer_url,
                pexels_url, original_video_url, local_file_path, original_width, original_height,
                original_duration_sec, orientation, selected_quality, query,
                tags_json, used_count, is_active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(asset_id) DO UPDATE SET
                source = excluded.source,
                pexels_id = excluded.pexels_id,
                photographer = excluded.photographer,
                photographer_url = excluded.photographer_url,
                pexels_url = excluded.pexels_url,
                original_video_url = excluded.original_video_url,
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
                asset.pexels_id,
                asset.photographer,
                asset.photographer_url,
                asset.pexels_url,
                asset.original_video_url,
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
            asset_id, source, pexels_id, photographer, photographer_url,
            pexels_url, original_video_url, local_file_path, original_width, original_height,
            original_duration_sec, orientation, selected_quality, query,
            tags_json, used_count, is_active
        FROM media_assets
        WHERE is_active = 1
        ORDER BY used_count ASC, asset_id ASC
        """
    ).fetchall()
    return [_media_asset_from_row(row) for row in rows]


def upsert_youtube_uploads(
    connection: sqlite3.Connection, uploads: list[dict[str, Any]]
) -> None:
    for upload in uploads:
        render_id = str(upload.get("render_id") or "").strip()
        if not render_id:
            continue
        render_exists = connection.execute(
            "SELECT 1 FROM youtube_renders WHERE render_id = ?",
            (render_id,),
        ).fetchone()
        if render_exists is None:
            continue
        connection.execute(
            """
            INSERT INTO youtube_uploads (
                render_id, planned, status, youtube_video_id, youtube_url,
                uploaded_at, error_message
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(render_id) DO UPDATE SET
                planned = excluded.planned,
                status = excluded.status,
                youtube_video_id = excluded.youtube_video_id,
                youtube_url = excluded.youtube_url,
                uploaded_at = excluded.uploaded_at,
                error_message = excluded.error_message
            """,
            (
                render_id,
                int(bool(upload.get("planned"))),
                upload.get("status") or "not_uploaded",
                upload.get("youtube_video_id"),
                upload.get("youtube_url"),
                upload.get("uploaded_at"),
                upload.get("error_message"),
            ),
        )


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
        pexels_id=row["pexels_id"],
        photographer=row["photographer"],
        photographer_url=row["photographer_url"],
        pexels_url=row["pexels_url"],
        original_video_url=row["original_video_url"],
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


def upsert_youtube_metrics_snapshots(
    connection: sqlite3.Connection, snapshots: list[dict[str, Any]]
) -> None:
    for snapshot in snapshots:
        connection.execute(
            """
            INSERT INTO youtube_metrics_snapshots (
                render_id, project_id, youtube_video_id, snapshot_date,
                views, engaged_views, likes, comments, shares,
                subscribers_gained, average_view_duration,
                average_view_percentage, estimated_minutes_watched,
                raw_metrics_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(youtube_video_id, snapshot_date) DO UPDATE SET
                render_id = excluded.render_id,
                project_id = excluded.project_id,
                collected_at = CURRENT_TIMESTAMP,
                views = excluded.views,
                engaged_views = excluded.engaged_views,
                likes = excluded.likes,
                comments = excluded.comments,
                shares = excluded.shares,
                subscribers_gained = excluded.subscribers_gained,
                average_view_duration = excluded.average_view_duration,
                average_view_percentage = excluded.average_view_percentage,
                estimated_minutes_watched = excluded.estimated_minutes_watched,
                raw_metrics_json = excluded.raw_metrics_json
            """,
            (
                snapshot["render_id"],
                snapshot["project_id"],
                snapshot["youtube_video_id"],
                snapshot["snapshot_date"],
                snapshot.get("views"),
                snapshot.get("engaged_views"),
                snapshot.get("likes"),
                snapshot.get("comments"),
                snapshot.get("shares"),
                snapshot.get("subscribers_gained"),
                snapshot.get("average_view_duration"),
                snapshot.get("average_view_percentage"),
                snapshot.get("estimated_minutes_watched"),
                snapshot.get("raw_metrics_json"),
            ),
        )


def upsert_youtube_daily_metrics(
    connection: sqlite3.Connection, rows: list[dict[str, Any]]
) -> int:
    """Persist per-video/day Analytics rows without duplicating API retries."""

    written = 0
    for row in rows:
        dimensions_json = row.get("dimensions_json") or "{}"
        if not isinstance(dimensions_json, str):
            dimensions_json = json.dumps(
                dimensions_json, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            )
        connection.execute(
            """
            INSERT INTO youtube_daily_metrics (
                render_id, project_id, youtube_video_id, metric_date, report_kind,
                dimensions_json, data_through_date, views, engaged_views, likes,
                comments, shares, subscribers_gained, average_view_duration,
                average_view_percentage, estimated_minutes_watched, raw_metrics_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(youtube_video_id, metric_date, report_kind, dimensions_json)
            DO UPDATE SET
                render_id = excluded.render_id,
                project_id = excluded.project_id,
                data_through_date = excluded.data_through_date,
                collected_at = CURRENT_TIMESTAMP,
                views = excluded.views,
                engaged_views = excluded.engaged_views,
                likes = excluded.likes,
                comments = excluded.comments,
                shares = excluded.shares,
                subscribers_gained = excluded.subscribers_gained,
                average_view_duration = excluded.average_view_duration,
                average_view_percentage = excluded.average_view_percentage,
                estimated_minutes_watched = excluded.estimated_minutes_watched,
                raw_metrics_json = excluded.raw_metrics_json
            """,
            (
                row["render_id"],
                row["project_id"],
                row["youtube_video_id"],
                row["metric_date"],
                row.get("report_kind") or "daily_video",
                dimensions_json,
                row.get("data_through_date"),
                row.get("views"),
                row.get("engaged_views"),
                row.get("likes"),
                row.get("comments"),
                row.get("shares"),
                row.get("subscribers_gained"),
                row.get("average_view_duration"),
                row.get("average_view_percentage"),
                row.get("estimated_minutes_watched"),
                row.get("raw_metrics_json"),
            ),
        )
        written += 1
    return written


def upsert_render_quality_reports(
    connection: sqlite3.Connection, reports: list[dict[str, Any]]
) -> int:
    """Store final quality reports; identical hashes are treated as no-ops."""

    written = 0
    for report in reports:
        render_id = str(report.get("render_id") or "").strip()
        report_hash = str(report.get("report_hash") or "").strip()
        if not render_id or not report_hash:
            continue
        duplicate = connection.execute(
            "SELECT render_id, report_hash FROM render_quality_reports WHERE report_hash = ?",
            (report_hash,),
        ).fetchone()
        if duplicate is not None:
            # The same final file is already imported. Refresh newly added
            # normalized columns for legacy rows, but never duplicate content.
            if duplicate[0] == render_id:
                connection.execute(
                    """
                    UPDATE render_quality_reports
                    SET quality_report_hash = ?, info_count = ?, metrics_json = ?
                    WHERE render_id = ?
                    """,
                    (
                        report.get("quality_report_hash") or report_hash,
                        report.get("info_count"),
                        report.get("metrics_json"),
                        render_id,
                    ),
                )
            continue
        connection.execute(
            """
            INSERT INTO render_quality_reports (
                render_id, report_hash, quality_report_hash, source_path, status,
                warning_count, error_count, info_count, subtitle_count,
                max_subtitle_chars, max_subtitle_cps, audio_rms_db, audio_peak_db,
                summary_json, metrics_json, checks_json, raw_report_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(render_id) DO UPDATE SET
                report_hash = excluded.report_hash,
                quality_report_hash = excluded.quality_report_hash,
                source_path = excluded.source_path,
                status = excluded.status,
                warning_count = excluded.warning_count,
                error_count = excluded.error_count,
                info_count = excluded.info_count,
                subtitle_count = excluded.subtitle_count,
                max_subtitle_chars = excluded.max_subtitle_chars,
                max_subtitle_cps = excluded.max_subtitle_cps,
                audio_rms_db = excluded.audio_rms_db,
                audio_peak_db = excluded.audio_peak_db,
                summary_json = excluded.summary_json,
                metrics_json = excluded.metrics_json,
                checks_json = excluded.checks_json,
                raw_report_json = excluded.raw_report_json,
                imported_at = CURRENT_TIMESTAMP
            """,
            (
                render_id,
                report_hash,
                report.get("quality_report_hash") or report_hash,
                report.get("source_path") or "",
                report.get("status"),
                report.get("warning_count"),
                report.get("error_count"),
                report.get("info_count"),
                report.get("subtitle_count"),
                report.get("max_subtitle_chars"),
                report.get("max_subtitle_cps"),
                report.get("audio_rms_db"),
                report.get("audio_peak_db"),
                report.get("summary_json"),
                report.get("metrics_json"),
                report.get("checks_json"),
                report.get("raw_report_json") or "{}",
            ),
        )
        written += 1
    return written


def _optional_bool_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(bool(value))
