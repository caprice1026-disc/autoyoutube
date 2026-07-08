from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from src.config import RENDERS_DIR
from src.db.database import connect, init_db
from src.db.repositories import (
    upsert_youtube_metrics_snapshots,
    upsert_youtube_uploads,
)
from src.errors import AppError
from src.youtube.auth import build_youtube_analytics_service

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


def generate_youtube_analytics_summary(
    *,
    days: int = 28,
    output_path: Path = DEFAULT_SUMMARY_PATH,
    client_secrets_path: Path = Path("secrets/client_secret.json"),
    token_path: Path = Path("data/youtube_token.json"),
    connection: sqlite3.Connection | None = None,
    analytics_service: Any | None = None,
) -> dict[str, Any]:
    init_db()
    owned_connection = False
    if connection is None:
        connection = connect()
        owned_connection = True

    try:
        sync_youtube_uploads_from_rendered_files(connection)
        targets = collect_uploaded_video_targets(connection)
        if not targets:
            raise AppError(
                "No uploaded YouTube videos were found in the database.",
                location="data/trivia_shorts.db",
                next_step="Run upload-youtube for at least one rendered video, then rerun this command.",
            )

        end_date = date.today()
        if days < 1:
            raise AppError(
                "Days must be at least 1.",
                details=f"days={days}",
                next_step="Pass a positive integer to --days.",
            )
        start_date = end_date - timedelta(days=days - 1)

        service = analytics_service or build_youtube_analytics_service(
            client_secrets_path=client_secrets_path,
            token_path=token_path,
        )
        metrics_by_video_id = fetch_video_metrics(
            service,
            [target.youtube_video_id for target in targets],
            start_date=start_date,
            end_date=end_date,
        )
        summary, snapshot_rows = build_summary(
            targets,
            metrics_by_video_id,
            start_date=start_date,
            end_date=end_date,
        )
        upsert_youtube_metrics_snapshots(connection, snapshot_rows)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
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
        )
        current = targets_by_video_id.get(target.youtube_video_id)
        if current is None or _target_sort_key(target) > _target_sort_key(current):
            targets_by_video_id[target.youtube_video_id] = target

    return sorted(targets_by_video_id.values(), key=_target_sort_key, reverse=True)


def sync_youtube_uploads_from_rendered_files(
    connection: sqlite3.Connection,
    *,
    renders_dir: Path = RENDERS_DIR,
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


def build_summary(
    targets: list[YoutubeAnalyticsTarget],
    metrics_by_video_id: dict[str, dict[str, Any]],
    *,
    start_date: date,
    end_date: date,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    video_rows: list[dict[str, Any]] = []
    snapshot_rows: list[dict[str, Any]] = []
    analyzed_rows: list[dict[str, Any]] = []

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
        }
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

    summary = {
        "schema_version": "youtube-analytics-summary-1.0.0",
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
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
        "videos": video_rows,
    }
    return summary, snapshot_rows


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
    top_by_retention = summary.get("top_by_retention", [])
    if top_by_retention:
        top = top_by_retention[0]
        lines.append(
            "Top by retention: "
            f"{top['youtube_title']} | avg_view={_format_percentage(top.get('average_view_percentage'))} | "
            f"views={_format_int(top.get('views'))}"
        )
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


def _normalize_report_row(headers: list[str], raw_row: list[Any]) -> dict[str, Any]:
    row: dict[str, Any] = {}
    for index, header in enumerate(headers):
        if not header:
            continue
        value = raw_row[index] if index < len(raw_row) else None
        if header == "video":
            row["youtube_video_id"] = str(value or "").strip()
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
