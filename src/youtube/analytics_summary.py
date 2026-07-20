from __future__ import annotations

import json
import hashlib
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any

from src.config import RENDERS_DIR
from src.db.database import connect, init_db
from src.db.repositories import (
    upsert_render_quality_reports,
    upsert_youtube_daily_metrics,
    upsert_youtube_metrics_snapshots,
    upsert_youtube_uploads,
)
from src.errors import AppError
from src.youtube.auth import build_youtube_analytics_service
from src.youtube.analytics_analysis import (
    MATURITY_WINDOWS,
    PACIFIC,
    choose_baseline,
    classify_group_size,
    classify_view_confidence,
    derive_rates,
    duration_bucket,
    hypothesis_status,
    maturity_window_status,
    nearest_snapshot,
    to_pacific_date,
)

DEFAULT_SUMMARY_PATH = Path("data/youtube_analytics_summary.json")
ANALYTICS_METRICS = (
    "views,engagedViews,likes,comments,shares,subscribersGained,"
    "averageViewDuration,averageViewPercentage,estimatedMinutesWatched"
)

API_METRIC_TO_COLUMN = {
    "views": ("views", int),
    "engagedViews": ("engaged_views", int),
    "likes": ("likes", int),
    "comments": ("comments", int),
    "shares": ("shares", int),
    "subscribersGained": ("subscribers_gained", int),
    "averageViewDuration": ("average_view_duration", float),
    "averageViewPercentage": ("average_view_percentage", float),
    "estimatedMinutesWatched": ("estimated_minutes_watched", float),
}

PRIMARY_METRIC_ALIASES = {
    "views": "views",
    "engaged_views": "engaged_views",
    "average_view_percentage": "average_view_percentage",
    "average_view_duration": "average_view_duration",
    "subscribers_gained": "subscribers_gained",
    "likes_per_view": "likes_per_view",
}

SNAPSHOT_NUMERIC_KEYS = {
    "views",
    "engaged_views",
    "likes",
    "comments",
    "shares",
    "subscribers_gained",
    "average_view_duration",
    "average_view_percentage",
    "estimated_minutes_watched",
}


@dataclass(frozen=True)
class YoutubeAnalyticsTarget:
    render_id: str
    project_id: str
    topic: str | None
    internal_title: str
    youtube_title: str
    youtube_video_id: str
    youtube_url: str | None
    uploaded_at: str | None
    completed_at: str | None
    experiment_group: str | None
    hypothesis: str | None
    primary_metric: str | None
    secondary_metrics: list[str]
    actual_duration_sec: float | None = None
    raw_project_json: str | None = None
    raw_rendered_json: str | None = None
    actual_uploaded_at: str | None = None


def generate_youtube_analytics_summary(
    *,
    days: int = 28,
    output_path: Path = DEFAULT_SUMMARY_PATH,
    client_secrets_path: Path = Path("secrets/client_secret.json"),
    token_path: Path = Path("data/youtube_token.json"),
    connection: sqlite3.Connection | None = None,
    analytics_service: Any | None = None,
    today: date | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    init_db()
    owned_connection = False
    if connection is None:
        connection = connect()
        owned_connection = True

    try:
        sync_issues: list[dict[str, Any]] = []
        try:
            sync_youtube_uploads_from_rendered_files(connection, issues=sync_issues)
        except TypeError as exc:
            # Preserve compatibility with callers/tests that monkeypatch the
            # historical one-argument sync function.
            if "issues" not in str(exc):
                raise
            sync_youtube_uploads_from_rendered_files(connection)
        targets = collect_uploaded_video_targets(connection)
        if not targets:
            raise AppError(
                "No uploaded YouTube videos were found in the database.",
                location="data/trivia_shorts.db",
                next_step="Run upload-youtube for at least one rendered video, then rerun this command.",
            )

        end_date = today or date.today()
        if days < 1:
            raise AppError(
                "Days must be at least 1.",
                details=f"days={days}",
                next_step="Pass a positive integer to --days.",
            )
        start_date = end_date - timedelta(days=days - 1)

        if analytics_service is None:
            try:
                service = build_youtube_analytics_service(
                    client_secrets_path=client_secrets_path,
                    token_path=token_path,
                )
            except Exception as exc:
                raise AppError(
                    "YouTube Analytics authentication failed.",
                    details=f"category=auth_failure: {exc}",
                    next_step="Run youtube-auth and verify the Analytics scope/token.",
                ) from exc
        else:
            service = analytics_service
        try:
            metrics_by_video_id = fetch_video_metrics(
                service,
                [target.youtube_video_id for target in targets],
                start_date=start_date,
                end_date=end_date,
            )
        except Exception as exc:
            raise AppError(
                "YouTube Analytics query failed.",
                details=f"category=query_failure: {exc}",
                next_step="Retry later and inspect the Analytics API response.",
            ) from exc
        daily_rows: list[dict[str, Any]] = []
        daily_api_errors: list[dict[str, Any]] = []
        for target in targets:
            fetch_start = _daily_fetch_start(
                connection,
                target.youtube_video_id,
                start_date=start_date,
                end_date=end_date,
            )
            if fetch_start is None:
                continue
            try:
                daily_rows.extend(
                    fetch_daily_video_metrics(
                        service,
                        [target.youtube_video_id],
                        start_date=fetch_start,
                        end_date=end_date,
                    )
                )
            except Exception as exc:  # API errors are data-quality states, not data loss.
                daily_api_errors.append(
                    {
                        "category": "query_failure",
                        "youtube_video_id": target.youtube_video_id,
                        "message": str(exc),
                    }
                )
        daily_rows = _attach_daily_target_keys(daily_rows, targets)
        upsert_youtube_daily_metrics(connection, daily_rows)
        daily_rows = _load_daily_metrics(
            connection,
            [target.youtube_video_id for target in targets],
            start_date=start_date,
            end_date=end_date,
        )
        legacy_snapshots = _load_metric_snapshots(
            connection,
            [target.youtube_video_id for target in targets],
        )
        sync_render_quality_reports(connection)
        backfill_rendered_detail_tables(connection)
        summary, snapshot_rows = build_summary(
            targets,
            metrics_by_video_id,
            start_date=start_date,
            end_date=end_date,
            daily_rows=daily_rows,
            quality_by_render_id=_load_quality_features(connection),
            today_pt=end_date,
            api_errors=daily_api_errors + sync_issues,
            now=now,
            legacy_snapshots_by_video=legacy_snapshots,
        )
        upsert_youtube_metrics_snapshots(connection, snapshot_rows)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        if owned_connection:
            connection.commit()
        return summary
    finally:
        if owned_connection:
            connection.close()


def collect_uploaded_video_targets(
    connection: sqlite3.Connection,
) -> list[YoutubeAnalyticsTarget]:
    rows = connection.execute(
        """
        SELECT
            u.render_id,
            r.project_id,
            r.completed_at,
            u.youtube_video_id,
            u.youtube_url,
            u.uploaded_at,
            p.topic,
            p.internal_title,
            p.raw_project_json,
            r.raw_rendered_json,
            r.actual_duration_sec,
            ym.youtube_title,
            ym.experiment_group,
            ym.hypothesis,
            ym.primary_metric,
            ym.secondary_metrics_json
        FROM youtube_uploads u
        JOIN youtube_renders r
            ON r.render_id = u.render_id
        JOIN youtube_projects p
            ON p.id = r.project_id
        LEFT JOIN project_youtube_metadata ym
            ON ym.project_id = r.project_id
        WHERE u.status LIKE 'uploaded_%'
          AND COALESCE(u.youtube_video_id, '') <> ''
        ORDER BY COALESCE(u.uploaded_at, r.completed_at) DESC, u.render_id DESC
        """
    ).fetchall()

    targets_by_video_id: dict[str, YoutubeAnalyticsTarget] = {}
    for row in rows:
        target = YoutubeAnalyticsTarget(
            render_id=str(row["render_id"]),
            project_id=str(row["project_id"]),
            topic=row["topic"],
            internal_title=str(row["internal_title"] or row["project_id"]),
            youtube_title=str(
                row["youtube_title"] or row["internal_title"] or row["project_id"]
            ),
            youtube_video_id=str(row["youtube_video_id"] or "").strip(),
            youtube_url=_clean_optional(row["youtube_url"]),
            uploaded_at=_clean_optional(row["uploaded_at"]) or _clean_optional(
                row["completed_at"]
            ),
            completed_at=_clean_optional(row["completed_at"]),
            experiment_group=_clean_optional(row["experiment_group"]),
            hypothesis=_clean_optional(row["hypothesis"]),
            primary_metric=_clean_optional(row["primary_metric"]),
            secondary_metrics=_parse_json_list(row["secondary_metrics_json"]),
            actual_duration_sec=_float_or_none(row["actual_duration_sec"]),
            raw_project_json=_clean_optional(row["raw_project_json"]),
            raw_rendered_json=_clean_optional(row["raw_rendered_json"]),
            actual_uploaded_at=_clean_optional(row["uploaded_at"]),
        )
        current = targets_by_video_id.get(target.youtube_video_id)
        if current is None or _target_sort_key(target) > _target_sort_key(current):
            targets_by_video_id[target.youtube_video_id] = target

    return sorted(targets_by_video_id.values(), key=_target_sort_key, reverse=True)


def sync_youtube_uploads_from_rendered_files(
    connection: sqlite3.Connection,
    *,
    renders_dir: Path = RENDERS_DIR,
    issues: list[dict[str, Any]] | None = None,
) -> int:
    if not renders_dir.exists():
        return 0

    synced = 0
    for rendered_path in sorted(renders_dir.rglob("final/rendered.youtube.json")):
        rendered = _safe_json_loads(rendered_path.read_text(encoding="utf-8"))
        youtube = rendered.get("youtube")
        if not isinstance(youtube, dict):
            continue
        upload = youtube.get("upload")
        if not isinstance(upload, dict):
            continue

        render_id = str(rendered.get("render_id") or "").strip()
        status = str(upload.get("status") or "").strip()
        youtube_video_id = str(upload.get("youtube_video_id") or "").strip()
        if not render_id or not status.startswith("uploaded_") or not youtube_video_id:
            continue
        if connection.execute(
            "SELECT 1 FROM youtube_renders WHERE render_id = ?", (render_id,)
        ).fetchone() is None:
            if issues is not None:
                issues.append(
                    {
                        "category": "db_render_missing",
                        "render_id": render_id,
                        "source_path": str(rendered_path),
                    }
                )
            continue

        upsert_youtube_uploads(
            connection,
            [
                {
                    "render_id": render_id,
                    "planned": bool(upload.get("planned")),
                    "status": status,
                    "youtube_video_id": youtube_video_id,
                    "youtube_url": _clean_optional(upload.get("youtube_url")),
                    "uploaded_at": _clean_optional(upload.get("uploaded_at")),
                    "error_message": _clean_optional(upload.get("error_message")),
                }
            ],
        )
        synced += 1
    return synced


def sync_render_quality_reports(
    connection: sqlite3.Connection,
    *,
    renders_dir: Path = RENDERS_DIR,
) -> int:
    """Import only canonical ``final/quality_report.json`` files for DB renders."""

    if not renders_dir.exists():
        return 0
    valid_render_ids = {
        str(row[0])
        for row in connection.execute("SELECT render_id FROM youtube_renders")
    }
    reports: list[dict[str, Any]] = []
    for path in sorted(renders_dir.rglob("final/quality_report.json")):
        try:
            raw_bytes = path.read_bytes()
            report = json.loads(raw_bytes.decode("utf-8"))
        except (OSError, UnicodeDecodeError, TypeError, ValueError, json.JSONDecodeError):
            continue
        if not isinstance(report, dict):
            continue
        render_id = str(report.get("render_id") or "").strip()
        if not render_id or render_id not in valid_render_ids:
            continue
        summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
        metrics = report.get("metrics") if isinstance(report.get("metrics"), dict) else {}
        report_hash = "sha256:" + hashlib.sha256(raw_bytes).hexdigest()
        reports.append(
            {
                "render_id": render_id,
                "report_hash": report_hash,
                "quality_report_hash": report_hash,
                "source_path": str(path),
                "status": report.get("status"),
                "warning_count": summary.get("warning_count"),
                "error_count": summary.get("error_count"),
                "info_count": summary.get("info_count"),
                "subtitle_count": metrics.get("subtitle_count"),
                "max_subtitle_chars": metrics.get("max_subtitle_chars"),
                "max_subtitle_cps": metrics.get("max_subtitle_cps"),
                "audio_rms_db": metrics.get("final_audio_rms_dbfs"),
                "audio_peak_db": metrics.get("final_audio_peak_dbfs"),
                "summary_json": json.dumps(summary, ensure_ascii=False, sort_keys=True),
                "metrics_json": json.dumps(metrics, ensure_ascii=False, sort_keys=True),
                "checks_json": json.dumps(
                    report.get("checks") or [], ensure_ascii=False, sort_keys=True
                ),
                "raw_report_json": json.dumps(
                    report, ensure_ascii=False, sort_keys=True
                ),
            }
        )
    return upsert_render_quality_reports(connection, reports)


def _load_quality_features(
    connection: sqlite3.Connection,
) -> dict[str, dict[str, Any]]:
    rows = connection.execute(
        """
        SELECT render_id, report_hash, source_path, status, warning_count,
               error_count, info_count, subtitle_count, max_subtitle_chars,
               max_subtitle_cps, audio_rms_db, audio_peak_db, summary_json,
               metrics_json, checks_json
        FROM render_quality_reports
        """
    ).fetchall()
    output: dict[str, dict[str, Any]] = {}
    for row in rows:
        output[str(row["render_id"])] = {
            "report_hash": row["report_hash"],
            "quality_report_hash": row["report_hash"],
            "source_path": row["source_path"],
            "status": row["status"],
            "warning_count": row["warning_count"],
            "error_count": row["error_count"],
            "info_count": row["info_count"],
            "subtitle_count": row["subtitle_count"],
            "max_subtitle_chars": row["max_subtitle_chars"],
            "max_subtitle_cps": row["max_subtitle_cps"],
            "audio_rms_db": row["audio_rms_db"],
            "audio_peak_db": row["audio_peak_db"],
            "summary_json": row["summary_json"],
            "metrics_json": row["metrics_json"],
            "checks_json": row["checks_json"],
        }
    return output


def backfill_rendered_detail_tables(connection: sqlite3.Connection) -> int:
    """Backfill subtitle and validation tables from stored rendered JSON."""

    rows = connection.execute(
        "SELECT render_id, raw_rendered_json FROM youtube_renders"
    ).fetchall()
    imported = 0
    for row in rows:
        rendered = _safe_json_loads(row["raw_rendered_json"])
        if not rendered:
            continue
        render_id = str(row["render_id"])
        subtitles = rendered.get("subtitles") or {}
        items = subtitles.get("items") if isinstance(subtitles, dict) else []
        if isinstance(subtitles, dict) and isinstance(subtitles.get("style"), dict) and subtitles.get("style"):
            style = subtitles["style"]
            connection.execute(
                """
                INSERT OR REPLACE INTO render_subtitle_styles (
                    render_id, format, font_name, font_size, primary_color,
                    outline_color, outline, shadow, alignment, margin_v
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    render_id,
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
        if isinstance(items, list):
            for item in items:
                if not isinstance(item, dict):
                    continue
                connection.execute(
                    """
                    INSERT OR IGNORE INTO render_subtitle_items (
                        render_id, item_index, text, start_sec, end_sec, caption_style_hint
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        render_id,
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
                render_id,
                int(bool(validation.get("project_json_valid", True))),
                int(bool(validation.get("rendered_json_valid", True))),
            ),
        )
        existing_messages = connection.execute(
            "SELECT COUNT(*) FROM render_validation_messages WHERE render_id = ?",
            (render_id,),
        ).fetchone()[0]
        if not existing_messages:
            for level, messages in (("warning", validation.get("warnings") or []), ("error", validation.get("errors") or [])):
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
                        (render_id, level, code, text, details),
                    )
        imported += 1
    return imported


def fetch_video_metrics(
    service: Any,
    youtube_video_ids: list[str],
    *,
    start_date: date,
    end_date: date,
) -> dict[str, dict[str, Any]]:
    metrics_by_video_id: dict[str, dict[str, Any]] = {}
    for chunk in _chunked(_unique_non_empty(youtube_video_ids), 500):
        response = (
            service.reports()
            .query(
                ids="channel==MINE",
                startDate=start_date.isoformat(),
                endDate=end_date.isoformat(),
                metrics=ANALYTICS_METRICS,
                dimensions="video",
                filters=f"video=={','.join(chunk)}",
                sort="-views",
                maxResults=500,
            )
            .execute()
        )
        headers = [str(header.get("name") or "") for header in response.get("columnHeaders", [])]
        for raw_row in response.get("rows", []) or []:
            row = _normalize_report_row(headers, raw_row)
            video_id = str(row.pop("youtube_video_id", "")).strip()
            if not video_id:
                continue
            metrics_by_video_id[video_id] = row
    return metrics_by_video_id


def fetch_daily_video_metrics(
    service: Any,
    youtube_video_ids: list[str],
    *,
    start_date: date,
    end_date: date,
) -> list[dict[str, Any]]:
    """Fetch per-video/day rows, preferring Shorts-filtered Analytics data.

    Some Analytics accounts/report combinations reject ``creatorContentType``;
    in that case the query is retried with the video filter only and the
    caller records the relaxed dimensions in ``dimensions_json``.
    """

    rows: list[dict[str, Any]] = []
    for video_id in _unique_non_empty(youtube_video_ids):
        query_kwargs = {
            "ids": "channel==MINE",
            "startDate": start_date.isoformat(),
            "endDate": end_date.isoformat(),
            "metrics": ANALYTICS_METRICS,
            "dimensions": "day",
            "filters": f"video=={video_id};creatorContentType==SHORTS",
            "sort": "day",
            "maxResults": 500,
        }
        used_shorts_filter = True
        try:
            response = service.reports().query(**query_kwargs).execute()
        except Exception:
            used_shorts_filter = False
            response = (
                service.reports()
                .query(
                    **{
                        **query_kwargs,
                        "filters": f"video=={video_id}",
                    }
                )
                .execute()
            )
        headers = [
            str(header.get("name") or "")
            for header in response.get("columnHeaders", [])
        ]
        parsed_rows: list[dict[str, Any]] = []
        for raw_row in response.get("rows", []) or []:
            parsed = _normalize_report_row(headers, raw_row)
            metric_date = parsed.pop("metric_date", None)
            if not metric_date:
                continue
            parsed["youtube_video_id"] = video_id
            parsed["metric_date"] = str(metric_date)
            parsed_rows.append(parsed)
        data_through_date = max(
            (row["metric_date"] for row in parsed_rows), default=None
        )
        dimensions = {"creatorContentType": "SHORTS"} if used_shorts_filter else {}
        for parsed in parsed_rows:
            parsed["report_kind"] = "daily_video"
            parsed["dimensions_json"] = json.dumps(
                dimensions, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            )
            parsed["data_through_date"] = data_through_date
            parsed["raw_metrics_json"] = json.dumps(
                parsed, ensure_ascii=False, sort_keys=True
            )
            rows.append(parsed)
    return rows


def _daily_fetch_start(
    connection: sqlite3.Connection,
    youtube_video_id: str,
    *,
    start_date: date,
    end_date: date,
) -> date | None:
    """Use the daily cache while re-fetching the recent API lag window."""

    row = connection.execute(
        "SELECT MAX(metric_date) AS latest FROM youtube_daily_metrics WHERE youtube_video_id = ?",
        (youtube_video_id,),
    ).fetchone()
    latest_text = row["latest"] if row is not None else None
    if not latest_text:
        return start_date
    try:
        latest = date.fromisoformat(str(latest_text))
    except ValueError:
        return start_date
    if latest >= end_date:
        return max(start_date, end_date - timedelta(days=3))
    return max(start_date, latest - timedelta(days=3))


def _load_daily_metrics(
    connection: sqlite3.Connection,
    youtube_video_ids: list[str],
    *,
    start_date: date,
    end_date: date,
) -> list[dict[str, Any]]:
    ids = _unique_non_empty(youtube_video_ids)
    if not ids:
        return []
    placeholders = ",".join("?" for _ in ids)
    rows = connection.execute(
        f"""
        SELECT render_id, project_id, youtube_video_id, metric_date, report_kind,
               dimensions_json, data_through_date, views, engaged_views, likes,
               comments, shares, subscribers_gained, average_view_duration,
               average_view_percentage, estimated_minutes_watched, raw_metrics_json
        FROM youtube_daily_metrics
        WHERE youtube_video_id IN ({placeholders})
          AND metric_date BETWEEN ? AND ?
        ORDER BY youtube_video_id, metric_date
        """,
        (*ids, start_date.isoformat(), end_date.isoformat()),
    ).fetchall()
    return [dict(row) for row in rows]


def _load_metric_snapshots(
    connection: sqlite3.Connection, youtube_video_ids: list[str]
) -> dict[str, list[dict[str, Any]]]:
    ids = _unique_non_empty(youtube_video_ids)
    if not ids:
        return {}
    placeholders = ",".join("?" for _ in ids)
    rows = connection.execute(
        f"""
        SELECT youtube_video_id, collected_at, snapshot_date, views,
               engaged_views, likes, comments, shares, subscribers_gained,
               average_view_duration, average_view_percentage,
               estimated_minutes_watched
        FROM youtube_metrics_snapshots
        WHERE youtube_video_id IN ({placeholders})
        """,
        ids,
    ).fetchall()
    result: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        result.setdefault(str(row["youtube_video_id"]), []).append(dict(row))
    return result


def _attach_daily_target_keys(
    rows: list[dict[str, Any]], targets: list[YoutubeAnalyticsTarget]
) -> list[dict[str, Any]]:
    target_by_video = {target.youtube_video_id: target for target in targets}
    attached: list[dict[str, Any]] = []
    for row in rows:
        target = target_by_video.get(str(row.get("youtube_video_id") or ""))
        if target is None:
            continue
        attached.append(
            {
                **row,
                "render_id": target.render_id,
                "project_id": target.project_id,
            }
        )
    return attached


def build_summary(
    targets: list[YoutubeAnalyticsTarget],
    metrics_by_video_id: dict[str, dict[str, Any]],
    *,
    start_date: date,
    end_date: date,
    daily_rows: list[dict[str, Any]] | None = None,
    quality_by_render_id: dict[str, dict[str, Any]] | None = None,
    today_pt: date | None = None,
    api_errors: list[dict[str, Any]] | None = None,
    now: datetime | None = None,
    legacy_snapshots_by_video: dict[str, list[dict[str, Any]]] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Build the backwards-compatible summary plus maturity analysis."""

    daily_rows = daily_rows or []
    quality_by_render_id = quality_by_render_id or {}
    legacy_snapshots_by_video = legacy_snapshots_by_video or {}
    today_pt = today_pt or end_date
    video_rows: list[dict[str, Any]] = []
    snapshot_rows: list[dict[str, Any]] = []
    analyzed_rows: list[dict[str, Any]] = []
    daily_by_video: dict[str, list[dict[str, Any]]] = {}
    for daily_row in daily_rows:
        daily_by_video.setdefault(
            str(daily_row.get("youtube_video_id") or ""), []
        ).append(daily_row)

    for target in targets:
        metrics = metrics_by_video_id.get(target.youtube_video_id)
        metric_values = {
            key: metrics.get(key) if metrics else None
            for key in SNAPSHOT_NUMERIC_KEYS
        }
        row = {
            "render_id": target.render_id,
            "project_id": target.project_id,
            "topic": target.topic,
            "internal_title": target.internal_title,
            "youtube_title": target.youtube_title,
            "youtube_video_id": target.youtube_video_id,
            "youtube_url": target.youtube_url,
            "uploaded_at": target.uploaded_at,
            "experiment_group": target.experiment_group,
            "hypothesis": target.hypothesis,
            "primary_metric": target.primary_metric,
            "primary_metric_value": _primary_metric_value(metrics, target.primary_metric),
            "secondary_metrics": {
                metric: _metric_value(metrics, metric)
                for metric in target.secondary_metrics
            },
            **metric_values,
            "metrics": metrics,
            "snapshot_delta": _snapshot_delta(
                metrics,
                _latest_snapshot(legacy_snapshots_by_video.get(target.youtube_video_id, [])),
            ),
        }
        production = _production_features(
            target, quality_by_render_id.get(target.render_id)
        )
        rows_for_video = daily_by_video.get(target.youtube_video_id, [])
        through_dates = [
            row.get("data_through_date")
            for row in rows_for_video
            if row.get("data_through_date")
        ]
        data_through_date = max(through_dates) if through_dates else None
        maturity: dict[str, dict[str, Any]] = {}
        for label, window_days in MATURITY_WINDOWS:
            state = maturity_window_status(
                target.uploaded_at,
                window_days,
                today_pt=today_pt,
                data_through_date=(
                    date.fromisoformat(data_through_date)
                    if data_through_date
                    else None
                ),
            )
            window_metrics = _aggregate_daily_window(
                rows_for_video, target.uploaded_at, window_days
            )
            fallback = _legacy_snapshot_fallback(
                legacy_snapshots_by_video.get(target.youtube_video_id, []),
                state.get("maturity_date_pt"),
            )
            if fallback is not None and all(value is None for value in window_metrics.values()):
                window_metrics = {
                    key: fallback.get(key) for key in SNAPSHOT_NUMERIC_KEYS
                }
                state["status"] = "snapshot_fallback"
                state["fallback_tolerance_hours"] = 12
            maturity[label] = {
                **state,
                "metrics": window_metrics,
                "rates": derive_rates(window_metrics),
                "view_confidence": classify_view_confidence(
                    window_metrics.get("views")
                ),
            }
        row.update(
            {
                "duration_sec": target.actual_duration_sec,
                "duration_bucket": production.get("duration_bucket"),
                "view_confidence": classify_view_confidence(
                    metrics.get("views") if metrics else None
                ),
                "derived_rates": derive_rates(metrics or {}),
                "maturity_windows": maturity,
                "production_features": production,
            }
        )
        row["data_quality_reasons"] = _video_data_quality_reasons(
            target, metrics, maturity, production
        )
        video_rows.append(row)
        if metrics is None:
            continue
        analyzed_rows.append(row)
        snapshot_rows.append(
            {
                "render_id": target.render_id,
                "project_id": target.project_id,
                "youtube_video_id": target.youtube_video_id,
                "snapshot_date": end_date.isoformat(),
                "views": metrics.get("views"),
                "engaged_views": metrics.get("engaged_views"),
                "likes": metrics.get("likes"),
                "comments": metrics.get("comments"),
                "shares": metrics.get("shares"),
                "subscribers_gained": metrics.get("subscribers_gained"),
                "average_view_duration": metrics.get("average_view_duration"),
                "average_view_percentage": metrics.get("average_view_percentage"),
                "estimated_minutes_watched": metrics.get("estimated_minutes_watched"),
                "raw_metrics_json": json.dumps(
                    {
                        "youtube_video_id": target.youtube_video_id,
                        "metrics": metrics,
                        "start_date": start_date.isoformat(),
                        "end_date": end_date.isoformat(),
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                ),
            }
        )

    observations, baselines, experiments = _build_analysis_observations(video_rows)
    recommendations = _build_recommendations(observations)
    summary = {
        "schema_version": "youtube-analytics-summary-2.0.0",
        "legacy_schema_version": "youtube-analytics-summary-1.0.0",
        "created_at": (now or datetime.now(timezone.utc)).isoformat().replace("+00:00", "Z"),
        "query": {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "days": (end_date - start_date).days + 1,
            "timezone": "America/Los_Angeles",
            "maturity_tolerance_hours": 12,
            "api_lag_tolerance_hours": 72,
        },
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "video_count": len(video_rows),
        "analyzed_video_count": len(analyzed_rows),
        "missing_metric_video_ids": [
            row["youtube_video_id"] for row in video_rows if row["metrics"] is None
        ],
        "totals": _totals(analyzed_rows),
        "weighted_averages": _weighted_averages(analyzed_rows),
        "top_by_views": _top_rows(analyzed_rows, "views"),
        "top_by_retention": _top_rows(analyzed_rows, "average_view_percentage"),
        "reliable_top_by_views": _top_rows(
            [row for row in analyzed_rows if row.get("view_confidence") == "comparable"],
            "views",
        ),
        "reliable_top_by_retention": _top_rows(
            [row for row in analyzed_rows if row.get("view_confidence") == "comparable"],
            "average_view_percentage",
        ),
        "videos": video_rows,
        "data_coverage": {
            "uploaded_video_count": len(video_rows),
            "aggregate_metric_video_count": len(analyzed_rows),
            "daily_metric_row_count": len(daily_rows),
            "daily_data_through_dates": {
                video_id: max(
                    (str(item.get("data_through_date")) for item in rows if item.get("data_through_date")),
                    default=None,
                )
                for video_id, rows in daily_by_video.items()
            },
        },
        "maturity_windows": {
            label: {
                "days": days,
                "timezone": "America/Los_Angeles",
                "comparison_min_views": 500,
            }
            for label, days in MATURITY_WINDOWS
        },
        "baselines": baselines,
        "experiments": experiments,
        "facts": {
            "videos": video_rows,
            "data_coverage": {
                "uploaded_video_count": len(video_rows),
                "aggregate_metric_video_count": len(analyzed_rows),
                "daily_metric_row_count": len(daily_rows),
            },
        },
        "observations": observations,
        "interpretations": observations,
        "recommendations": recommendations,
        "proposals": recommendations,
        "data_quality": _data_quality(video_rows, observations, api_errors or []),
        "source_versions": {
            "summary_schema": "youtube-analytics-summary-2.0.0",
            "analysis_policy": "maturity-d1-d3-d7-d28-v1",
            "quality_report": "render_quality_reports",
        },
    }
    return summary, snapshot_rows


def _legacy_snapshot_fallback(
    snapshots: list[dict[str, Any]], maturity_date_pt: str | None
) -> dict[str, Any] | None:
    if not snapshots or not maturity_date_pt:
        return None
    try:
        target_date = date.fromisoformat(maturity_date_pt)
    except ValueError:
        return None
    target = datetime.combine(target_date, time.min, tzinfo=PACIFIC)
    return dict(nearest_snapshot(snapshots, target) or {}) or None


def _video_data_quality_reasons(
    target: YoutubeAnalyticsTarget,
    metrics: dict[str, Any] | None,
    maturity: dict[str, dict[str, Any]],
    production: dict[str, Any],
) -> list[str]:
    reasons = list(production.get("missing_reasons") or [])
    if target.actual_uploaded_at is None:
        reasons.append("uploaded_at_missing")
    if metrics is None:
        reasons.append("api_row_missing")
    for window in maturity.values():
        status = window.get("status")
        if status == "pending_api_data":
            reasons.append("pending_api_data")
        elif status == "api_no_data":
            reasons.append("api_no_data")
        elif status == "invalid_upload_date":
            reasons.append("invalid_date")
    return list(dict.fromkeys(reasons))


def _latest_snapshot(snapshots: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not snapshots:
        return None
    return max(
        snapshots,
        key=lambda row: str(row.get("collected_at") or row.get("snapshot_date") or ""),
    )


def _snapshot_delta(
    current: dict[str, Any] | None, previous: dict[str, Any] | None
) -> dict[str, Any]:
    if not current or not previous:
        return {
            "status": "no_previous_snapshot",
            "reason": "previous_snapshot_missing",
            "metrics": {key: None for key in SNAPSHOT_NUMERIC_KEYS},
        }
    deltas: dict[str, Any] = {}
    for key in SNAPSHOT_NUMERIC_KEYS:
        current_value = _metric_number(current.get(key))
        previous_value = _metric_number(previous.get(key))
        deltas[key] = (
            current_value - previous_value
            if current_value is not None and previous_value is not None
            else None
        )
    return {
        "status": "computed",
        "reason": None,
        "from_snapshot_date": previous.get("snapshot_date"),
        "metrics": deltas,
    }


def _aggregate_daily_window(
    rows: list[dict[str, Any]], uploaded_at: str | None, window_days: int
) -> dict[str, Any]:
    launch_date = to_pacific_date(uploaded_at)
    if launch_date is None:
        return {key: None for key in SNAPSHOT_NUMERIC_KEYS}
    maturity_date = launch_date + timedelta(days=window_days)
    selected = [
        row
        for row in rows
        if row.get("metric_date")
        and launch_date < date.fromisoformat(str(row["metric_date"])) <= maturity_date
    ]
    if not selected:
        return {key: None for key in SNAPSHOT_NUMERIC_KEYS}
    views = _sum_metric(selected, "views")
    result = {
        key: _sum_metric(selected, key)
        for key in SNAPSHOT_NUMERIC_KEYS
        if key not in {"average_view_duration", "average_view_percentage"}
    }
    result["average_view_duration"] = _weighted_average(selected, "average_view_duration", views or 0)
    result["average_view_percentage"] = _weighted_average(selected, "average_view_percentage", views or 0)
    return result


def _production_features(
    target: YoutubeAnalyticsTarget, quality: dict[str, Any] | None
) -> dict[str, Any]:
    project = _safe_json_loads(target.raw_project_json or "")
    rendered = _safe_json_loads(target.raw_rendered_json or "")
    visuals = rendered.get("visuals") if isinstance(rendered.get("visuals"), list) else []
    subtitles = rendered.get("subtitles") if isinstance(rendered.get("subtitles"), dict) else {}
    subtitle_items = subtitles.get("items") if isinstance(subtitles.get("items"), list) else []
    queries = [str(item.get("visual_query") or "") for item in visuals if isinstance(item, dict)]
    assets = [str(item.get("asset_id") or item.get("pexels_id") or "") for item in visuals if isinstance(item, dict)]
    quality_metrics = _safe_json_loads((quality or {}).get("metrics_json") or "")
    quality_checks = _safe_json_list((quality or {}).get("checks_json") or "")
    bgm = rendered.get("bgm") if isinstance(rendered.get("bgm"), dict) else None
    voice = rendered.get("voice") if isinstance(rendered.get("voice"), dict) else None
    if voice is None and isinstance(project.get("voice"), dict):
        voice = project["voice"]
    validation = rendered.get("validation") if isinstance(rendered.get("validation"), dict) else {}
    validation_warnings = validation.get("warnings") or []
    validation_errors = validation.get("errors") or []
    ffmpeg_warnings = [
        check
        for check in quality_checks
        if isinstance(check, dict)
        and ("FFMPEG" in str(check.get("code") or "").upper() or "ffmpeg" in str(check.get("target") or "").lower())
    ]
    missing: list[str] = []
    if not project:
        missing.append("project_json")
    if not rendered:
        missing.append("rendered_json")
    if quality is None:
        missing.append("quality_report")
    actual_duration = target.actual_duration_sec
    if actual_duration is None:
        actual_duration = _float_or_none((rendered.get("target") or {}).get("actual_duration_sec"))
    return {
        "topic": project.get("topic") or target.topic,
        "hook": project.get("hook"),
        "internal_title": target.internal_title,
        "youtube_title": target.youtube_title,
        "experiment_group": target.experiment_group,
        "hypothesis": target.hypothesis,
        "primary_metric": target.primary_metric,
        "actual_duration_sec": actual_duration,
        "duration_bucket": duration_bucket(actual_duration),
        "script_item_count": len(project.get("script") or []) if project else None,
        "subtitle_count": len(subtitle_items) if rendered else None,
        "subtitle_max_chars": max((len(str(item.get("text") or "")) for item in subtitle_items if isinstance(item, dict)), default=None),
        "max_subtitle_chars": quality.get("max_subtitle_chars") if quality else None,
        "max_subtitle_cps": quality.get("max_subtitle_cps") if quality else quality_metrics.get("max_subtitle_cps"),
        "visual_count": len(visuals) if rendered else None,
        "unique_visual_query_count": len(set(query for query in queries if query)),
        "unique_visual_count": len(set(asset for asset in assets if asset)),
        "visual_asset_reuse_count": len(assets) - len(set(asset for asset in assets if asset)),
        "repeated_visual_count": len(assets) - len(set(asset for asset in assets if asset)),
        "pexels_visual_ratio": (
            sum(1 for item in visuals if isinstance(item, dict) and item.get("source") == "pexels") / len(visuals)
            if visuals
            else None
        ),
        "pexels_ratio": (
            sum(1 for item in visuals if isinstance(item, dict) and item.get("source") == "pexels") / len(visuals)
            if visuals
            else None
        ),
        "bgm": bgm,
        "bgm_enabled": bgm.get("enabled") if bgm else None,
        "bgm_volume_db": bgm.get("volume_db") if bgm else None,
        "voice": voice,
        "voice_speaker": voice.get("speaker") if voice else None,
        "voice_style_id": voice.get("style_id") if voice else None,
        "voice_speed_scale": voice.get("speed_scale") if voice else None,
        "quality": quality,
        "quality_status": quality.get("status") if quality else None,
        "quality_warning_count": quality.get("warning_count") if quality else None,
        "quality_error_count": quality.get("error_count") if quality else None,
        "quality_info_count": quality.get("info_count") if quality else None,
        "audio_rms_db": quality.get("audio_rms_db") if quality else quality_metrics.get("final_audio_rms_dbfs"),
        "audio_peak_db": quality.get("audio_peak_db") if quality else quality_metrics.get("final_audio_peak_dbfs"),
        "ffmpeg_warnings": ffmpeg_warnings or None,
        "validation_warnings": validation_warnings or None,
        "validation_errors": validation_errors or None,
        "missing_reasons": missing,
    }


def _build_analysis_observations(
    video_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    raw_observations: list[dict[str, Any]] = []
    for row in video_rows:
        for maturity, window in row.get("maturity_windows", {}).items():
            metrics = window.get("metrics") or {}
            metric = PRIMARY_METRIC_ALIASES.get(row.get("primary_metric") or "average_view_percentage", "average_view_percentage")
            value = _metric_value(metrics, metric)
            if value is None:
                continue
            raw_observations.append(
                {
                    "video_id": row["youtube_video_id"],
                    "render_id": row["render_id"],
                    "topic": row.get("topic"),
                    "experiment_group": row.get("experiment_group"),
                    "maturity": maturity,
                    "duration_bucket": row.get("duration_bucket"),
                    "metric": metric,
                    "value": value,
                    "status": window.get("status"),
                }
            )
    observations: list[dict[str, Any]] = []
    baselines: dict[str, Any] = {}
    group_counts: dict[tuple[str | None, str], int] = {}
    for item in raw_observations:
        if item.get("experiment_group"):
            key = (item["experiment_group"], item["maturity"])
            group_counts[key] = group_counts.get(key, 0) + 1
    for item in raw_observations:
        peers = [candidate for candidate in raw_observations if candidate["video_id"] != item["video_id"]]
        baseline = choose_baseline(
            [candidate for candidate in peers if candidate.get("topic") == item.get("topic")],
            topic=item.get("topic"),
            maturity=item["maturity"],
            duration_bucket_name=item.get("duration_bucket"),
            value_key="value",
            channel_rows=peers,
        )
        group_size = group_counts.get((item.get("experiment_group"), item["maturity"]), 1)
        group_status = classify_group_size(group_size)
        status = hypothesis_status(
            value=_metric_number(item.get("value")),
            baseline_median=baseline.get("median"),
            group_size=group_size,
            baseline_iqr=baseline.get("iqr"),
        )
        if group_status == "directional" and status == "inconclusive":
            delta = (_metric_number(item.get("value")) or 0) - (baseline.get("median") or 0)
            status = "directional_positive" if delta > 0 else "directional_negative"
        enriched = {
            **item,
            "group_size": group_size,
            "group_status": group_status,
            "baseline": baseline,
            "baseline_median": baseline.get("median"),
            "baseline_iqr": baseline.get("iqr"),
            "comparison": {
                "scope": baseline.get("scope"),
                "median": baseline.get("median"),
                "iqr": baseline.get("iqr"),
                "n": baseline.get("n"),
            },
            "sample_sizes": {
                "experiment_group": group_size,
                "baseline": baseline.get("n", 0),
            },
            "median_difference": (
                _metric_number(item.get("value")) - baseline.get("median")
                if _metric_number(item.get("value")) is not None and baseline.get("median") is not None
                else None
            ),
            "evidence_video_ids": baseline.get("video_ids", []),
            "hypothesis_status": status,
            "confidence": classify_view_confidence(item.get("value")),
            "limitations": "相関に基づく観察であり、因果関係を主張しない。",
        }
        observations.append(enriched)
        baselines[f"{item['video_id']}:{item['maturity']}:{item['metric']}"] = baseline
    experiments = {
        f"{group}:{maturity}": {
            "experiment_group": group,
            "maturity": maturity,
            "n": count,
            "comparison_status": classify_group_size(count),
        }
        for (group, maturity), count in group_counts.items()
    }
    return observations, baselines, experiments


def _build_recommendations(observations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    from src.youtube.analytics_analysis import build_rule_based_recommendations

    return build_rule_based_recommendations(observations)


def _data_quality(
    rows: list[dict[str, Any]],
    observations: list[dict[str, Any]],
    api_errors: list[dict[str, Any]],
) -> dict[str, Any]:
    reason_counts: dict[str, int] = {}
    for row in rows:
        for reason in row.get("data_quality_reasons", []):
            reason_counts[reason] = reason_counts.get(reason, 0) + 1
    maturity_comparability: dict[str, dict[str, int]] = {}
    for maturity in ("D1", "D3", "D7", "D28"):
        windows = [row.get("maturity_windows", {}).get(maturity, {}) for row in rows]
        maturity_comparability[maturity] = {
            "complete": sum(1 for window in windows if window.get("status") in {"complete", "snapshot_fallback"}),
            "comparable_views": sum(
                1 for window in windows if window.get("view_confidence") == "comparable"
            ),
        }
    all_errors = list(api_errors)
    api_error_categories = {"auth_failure", "query_failure"}
    api_errors = [
        error for error in all_errors if error.get("category") in api_error_categories
    ]
    operational_errors = [
        error for error in all_errors if error.get("category") not in api_error_categories
    ]
    missing_reasons = {
        "api_row_missing",
        "uploaded_at_missing",
        "project_json",
        "rendered_json",
        "quality_report",
    }
    missing_data_video_count = sum(
        1
        for row in rows
        if set(row.get("data_quality_reasons", [])) & missing_reasons
    )
    unavailable_maturity_video_count = sum(
        1
        for row in rows
        if "api_no_data" in row.get("data_quality_reasons", [])
    )
    return {
        "uploaded_video_count": len(rows),
        "api_metric_video_count": sum(1 for row in rows if row.get("metrics") is not None),
        "pending_api_video_count": reason_counts.get("pending_api_data", 0),
        "missing_video_count": missing_data_video_count,
        "unavailable_maturity_video_count": unavailable_maturity_video_count,
        "missing_reason_counts": reason_counts,
        "maturity_comparability": maturity_comparability,
        "low_view_video_count": sum(
            1 for row in rows if classify_view_confidence(row.get("views")) == "insufficient"
        ),
        "provisional_view_video_count": sum(
            1 for row in rows if classify_view_confidence(row.get("views")) == "provisional"
        ),
        "comparable_view_video_count": sum(
            1 for row in rows if classify_view_confidence(row.get("views")) == "comparable"
        ),
        "insufficient_baseline_count": sum(
            1 for item in observations if item.get("hypothesis_status") == "insufficient_baseline"
        ),
        "insufficient_data_count": sum(
            1 for item in observations if item.get("hypothesis_status") == "insufficient_data"
        ),
        "insufficient_group_count": sum(
            1 for item in observations if item.get("group_status") == "insufficient_group"
        ),
        "missing_production_feature_video_count": sum(
            1 for row in rows if row.get("production_features", {}).get("missing_reasons")
        ),
        "api_errors": api_errors,
        "operational_errors": operational_errors,
        "error_count": len(api_errors) + len(operational_errors),
        "db_render_missing_count": sum(
            1 for error in operational_errors if error.get("category") == "db_render_missing"
        ),
    }


def format_console_summary(summary: dict[str, Any]) -> list[str]:
    lines = [
        f"Analyzed videos: {summary['analyzed_video_count']} / {summary['video_count']}",
        f"Date range: {summary['start_date']} .. {summary['end_date']}",
    ]
    totals = summary.get("totals", {})
    lines.append(
        "Totals: "
        f"views={_format_int(totals.get('views'))}, "
        f"likes={_format_int(totals.get('likes'))}, "
        f"comments={_format_int(totals.get('comments'))}, "
        f"shares={_format_int(totals.get('shares'))}, "
        f"minutes_watched={_format_float(totals.get('estimated_minutes_watched'))}"
    )
    weighted = summary.get("weighted_averages", {})
    lines.append(
        "Weighted averages: "
        f"view_duration={_format_float(weighted.get('average_view_duration'))}s, "
        f"view_percentage={_format_percentage(weighted.get('average_view_percentage'))}"
    )
    top_by_views = summary.get("top_by_views", [])
    if top_by_views:
        top = top_by_views[0]
        lines.append(
            "Top by views: "
            f"{top['youtube_title']} | views={_format_int(top.get('views'))} | "
            f"avg_view={_format_percentage(top.get('average_view_percentage'))}"
        )
    top_by_retention = summary.get("reliable_top_by_retention") or summary.get(
        "top_by_retention", []
    )
    if top_by_retention:
        top = top_by_retention[0]
        lines.append(
            "Top by retention: "
            f"{top['youtube_title']} | avg_view={_format_percentage(top.get('average_view_percentage'))} | "
            f"views={_format_int(top.get('views'))}"
        )
    quality = summary.get("data_quality", {})
    if quality:
        lines.insert(
            0,
            "Uploads: "
            f"total={quality.get('uploaded_video_count', summary.get('video_count', 0))}, "
            f"api_metrics={quality.get('api_metric_video_count', summary.get('analyzed_video_count', 0))}, "
            f"pending={quality.get('pending_api_video_count', 0)}, "
            f"missing={quality.get('missing_video_count', 0)}",
        )
        lines.append(
            "Data quality: "
            f"low_views={quality.get('low_view_video_count', 0)}, "
            f"provisional={quality.get('provisional_view_video_count', 0)}, "
            f"comparable={quality.get('comparable_view_video_count', 0)}, "
            f"api_errors={len(quality.get('api_errors', []))}, "
            f"operational_errors={len(quality.get('operational_errors', []))}"
        )
        maturity_counts = quality.get("maturity_comparability", {})
        if maturity_counts:
            lines.append(
                "Maturity comparable: "
                + ", ".join(
                    f"{key}={value.get('comparable_views', 0)}"
                    for key, value in maturity_counts.items()
                )
            )
        launch_partial = sum(
            1
            for row in summary.get("videos", [])
            if any(
                window.get("status") == "launch_partial_day"
                for window in row.get("maturity_windows", {}).values()
            )
        )
        lines.append(f"Launch partial day: {launch_partial}")
    experiments = summary.get("experiments", {})
    if experiments:
        counts = {"actionable": 0, "directional": 0, "insufficient_group": 0}
        for experiment in experiments.values():
            status = experiment.get("comparison_status")
            if status in counts:
                counts[status] += 1
        lines.append(
            "Comparable groups: "
            f"actionable={counts['actionable']}, directional={counts['directional']}, "
            f"insufficient={counts['insufficient_group']}"
        )
    observations = summary.get("observations", [])
    if observations:
        hypothesis_counts: dict[str, int] = {}
        for observation in observations:
            status = str(observation.get("hypothesis_status") or "unknown")
            hypothesis_counts[status] = hypothesis_counts.get(status, 0) + 1
        lines.append(
            "Hypotheses: "
            + ", ".join(f"{key}={value}" for key, value in sorted(hypothesis_counts.items()))
        )
    recommendations = summary.get("recommendations", [])
    if recommendations:
        proposal_counts: dict[str, int] = {}
        for recommendation in recommendations:
            action = str(recommendation.get("action") or "hold")
            proposal_counts[action] = proposal_counts.get(action, 0) + 1
        lines.append(
            "Proposals: "
            + ", ".join(f"{key}={value}" for key, value in sorted(proposal_counts.items()))
            + " (review required)"
        )
    undecidable = quality.get("insufficient_baseline_count", 0) + quality.get(
        "insufficient_group_count", 0
    )
    if undecidable:
        lines.append(f"Undecidable reasons: insufficient_baseline_or_group={undecidable}")
    return lines


def _totals(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "views": _sum_metric(rows, "views"),
        "engaged_views": _sum_metric(rows, "engaged_views"),
        "likes": _sum_metric(rows, "likes"),
        "comments": _sum_metric(rows, "comments"),
        "shares": _sum_metric(rows, "shares"),
        "subscribers_gained": _sum_metric(rows, "subscribers_gained"),
        "estimated_minutes_watched": _sum_metric(rows, "estimated_minutes_watched"),
    }


def _weighted_averages(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total_views = _sum_metric(rows, "views")
    if not total_views:
        return {"average_view_duration": None, "average_view_percentage": None}
    return {
        "average_view_duration": _weighted_average(rows, "average_view_duration", total_views),
        "average_view_percentage": _weighted_average(rows, "average_view_percentage", total_views),
    }


def _top_rows(rows: list[dict[str, Any]], metric: str, limit: int = 5) -> list[dict[str, Any]]:
    ranked = sorted(
        rows,
        key=lambda row: _top_row_sort_key(row, metric),
        reverse=True,
    )
    return [
        {
            "render_id": row["render_id"],
            "project_id": row["project_id"],
            "youtube_video_id": row["youtube_video_id"],
            "youtube_title": row["youtube_title"],
            "internal_title": row["internal_title"],
            "value": row.get(metric),
            "views": row.get("views"),
            "average_view_percentage": row.get("average_view_percentage"),
        }
        for row in ranked[:limit]
    ]


def _top_row_sort_key(row: dict[str, Any], metric: str) -> tuple[float, str]:
    metric_value = _metric_number(row.get(metric))
    return (
        float(metric_value) if metric_value is not None else float("-inf"),
        row.get("youtube_video_id") or "",
    )


def _primary_metric_value(
    metrics: dict[str, Any] | None, primary_metric: str | None
) -> Any:
    if not metrics or not primary_metric:
        return None
    normalized = PRIMARY_METRIC_ALIASES.get(primary_metric)
    if normalized == "likes_per_view":
        views = _metric_number(metrics.get("views"))
        likes = _metric_number(metrics.get("likes"))
        if not views:
            return None
        return likes / views if likes is not None else None
    if normalized:
        return metrics.get(normalized)
    return metrics.get(primary_metric)


def _metric_value(metrics: dict[str, Any] | None, metric_name: str) -> Any:
    if not metrics:
        return None
    return _primary_metric_value(metrics, metric_name)


def _sum_metric(rows: list[dict[str, Any]], key: str) -> float | int | None:
    values = [_metric_number(row.get(key)) for row in rows]
    values = [value for value in values if value is not None]
    if not values:
        return None
    total = sum(values)
    if all(isinstance(value, int) for value in values):
        return int(total)
    return float(total)


def _weighted_average(
    rows: list[dict[str, Any]], key: str, total_views: float | int
) -> float | None:
    if total_views in {None, 0}:
        return None
    numerator = 0.0
    for row in rows:
        value = _metric_number(row.get(key))
        views = _metric_number(row.get("views"))
        if value is None or views is None:
            continue
        numerator += float(value) * float(views)
    return numerator / float(total_views)


def _metric_number(value: Any) -> float | int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return value
    try:
        if isinstance(value, str) and "." in value:
            return float(value)
        return int(value)
    except (TypeError, ValueError):
        return None


def _float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if result == result else None


def _normalize_report_row(headers: list[str], raw_row: list[Any]) -> dict[str, Any]:
    row: dict[str, Any] = {}
    for index, header in enumerate(headers):
        if not header:
            continue
        value = raw_row[index] if index < len(raw_row) else None
        if header == "video":
            row["youtube_video_id"] = str(value or "").strip()
            continue
        if header == "day":
            row["metric_date"] = str(value or "").strip() or None
            continue
        column_name, caster = API_METRIC_TO_COLUMN.get(header, (header, None))
        row[column_name] = _cast_metric_value(value, caster)
    return row


def _cast_metric_value(value: Any, caster: Any) -> Any:
    if value is None or caster is None:
        return value
    try:
        return caster(value)
    except (TypeError, ValueError):
        return None


def _load_project_metadata_map(
    connection: sqlite3.Connection,
) -> dict[str, dict[str, Any]]:
    rows = connection.execute(
        """
        SELECT
            p.id,
            p.topic,
            p.internal_title,
            ym.youtube_title,
            ym.experiment_group,
            ym.hypothesis,
            ym.primary_metric,
            ym.secondary_metrics_json
        FROM youtube_projects p
        LEFT JOIN project_youtube_metadata ym
            ON ym.project_id = p.id
        """
    ).fetchall()
    metadata_map: dict[str, dict[str, Any]] = {}
    for row in rows:
        metadata_map[str(row["id"])] = {
            "topic": row["topic"],
            "internal_title": row["internal_title"],
            "youtube_title": row["youtube_title"],
            "experiment_group": row["experiment_group"],
            "hypothesis": row["hypothesis"],
            "primary_metric": row["primary_metric"],
            "secondary_metrics": _parse_json_list(row["secondary_metrics_json"]),
        }
    return metadata_map


def _parse_json_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    try:
        loaded = json.loads(value)
    except (TypeError, ValueError, json.JSONDecodeError):
        return []
    if not isinstance(loaded, list):
        return []
    return [str(item).strip() for item in loaded if str(item).strip()]


def _chunked(values: list[str], size: int) -> list[list[str]]:
    chunks: list[list[str]] = []
    for index in range(0, len(values), size):
        chunk = values[index : index + size]
        if chunk:
            chunks.append(chunk)
    return chunks


def _unique_non_empty(values: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        normalized = str(value or "").strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        output.append(normalized)
    return output


def _target_sort_key(target: YoutubeAnalyticsTarget) -> tuple[str, str]:
    return (
        target.uploaded_at or target.completed_at or "",
        target.render_id,
    )


def _safe_json_loads(text: str) -> dict[str, Any]:
    try:
        loaded = json.loads(text)
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _safe_json_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    try:
        loaded = json.loads(value or "[]")
    except (TypeError, ValueError, json.JSONDecodeError):
        return []
    return loaded if isinstance(loaded, list) else []


def _clean_optional(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _format_int(value: Any) -> str:
    number = _metric_number(value)
    if number is None:
        return "n/a"
    return f"{int(number):,}"


def _format_float(value: Any) -> str:
    number = _metric_number(value)
    if number is None:
        return "n/a"
    return f"{float(number):.2f}"


def _format_percentage(value: Any) -> str:
    number = _metric_number(value)
    if number is None:
        return "n/a"
    return f"{float(number):.2f}%"
