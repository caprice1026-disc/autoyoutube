from __future__ import annotations

import json
import sqlite3
from datetime import date
from pathlib import Path

import src.youtube.analytics_summary as analytics_summary
from src.db.database import connect, init_db
from src.db.repositories import (
    insert_render_summary,
    upsert_project,
    upsert_youtube_uploads,
)
from src.youtube.analytics_summary import (
    collect_uploaded_video_targets,
    YoutubeAnalyticsTarget,
    build_summary,
    fetch_daily_video_metrics,
    fetch_video_metrics,
    generate_youtube_analytics_summary,
    sync_render_quality_reports,
    sync_youtube_uploads_from_rendered_files,
)
from tests.test_db_repositories import _project, _rendered


class FakeQueryRequest:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def execute(self) -> dict[str, object]:
        return self.payload


class FakeReportsResource:
    def __init__(self, payloads: dict[tuple[str, ...], dict[str, object]]) -> None:
        self.payloads = payloads
        self.calls: list[dict[str, object]] = []

    def query(self, **kwargs: object) -> FakeQueryRequest:
        self.calls.append(dict(kwargs))
        chunk = tuple(str(kwargs["filters"]).split("==", 1)[1].split(","))
        return FakeQueryRequest(self.payloads[chunk])


class FakeAnalyticsService:
    def __init__(self, payloads: dict[tuple[str, ...], dict[str, object]]) -> None:
        self.reports_resource = FakeReportsResource(payloads)

    def reports(self) -> FakeReportsResource:
        return self.reports_resource


def test_fetch_video_metrics_parses_api_rows() -> None:
    payloads = {
        ("video-a", "video-b"): {
            "columnHeaders": [
                {"name": "video"},
                {"name": "views"},
                {"name": "averageViewPercentage"},
                {"name": "averageViewDuration"},
            ],
            "rows": [["video-a", 100, 55.5, 12.3], ["video-b", 80, 44.0, 9.1]],
        }
    }
    service = FakeAnalyticsService(payloads)

    metrics = fetch_video_metrics(
        service,
        ["video-a", "video-b"],
        start_date=date(2026, 7, 1),
        end_date=date(2026, 7, 8),
    )

    assert metrics == {
        "video-a": {
            "views": 100,
            "average_view_percentage": 55.5,
            "average_view_duration": 12.3,
        },
        "video-b": {
            "views": 80,
            "average_view_percentage": 44.0,
            "average_view_duration": 9.1,
        },
    }

    assert service.reports_resource.calls == [
        {
            "ids": "channel==MINE",
            "startDate": "2026-07-01",
            "endDate": "2026-07-08",
            "metrics": (
                "views,engagedViews,likes,comments,shares,subscribersGained,"
                "averageViewDuration,averageViewPercentage,estimatedMinutesWatched"
            ),
            "dimensions": "video",
            "filters": "video==video-a,video-b",
            "sort": "-views",
            "maxResults": 500,
        }
    ]


def test_fetch_daily_video_metrics_parses_day_and_falls_back_without_shorts_filter() -> None:
    payloads = {
        ("video-a",): {
            "columnHeaders": [
                {"name": "day"},
                {"name": "views"},
                {"name": "averageViewPercentage"},
            ],
            "rows": [["2026-07-08", 50, 40.0], ["2026-07-09", 70, 60.0]],
        }
    }
    service = FakeAnalyticsService(payloads)
    rows = fetch_daily_video_metrics(
        service,
        ["video-a"],
        start_date=date(2026, 7, 8),
        end_date=date(2026, 7, 9),
    )
    assert rows[0]["metric_date"] == "2026-07-08"
    assert rows[0]["data_through_date"] == "2026-07-09"
    assert rows[0]["dimensions_json"] == "{}"
    assert len(service.reports_resource.calls) == 2


def test_build_summary_computes_totals_and_snapshot_rows() -> None:
    targets = [
        YoutubeAnalyticsTarget(
            render_id="render-1",
            project_id="project-1",
            topic="topic",
            internal_title="Internal Title",
            youtube_title="Public Title",
            youtube_video_id="video-a",
            youtube_url="https://www.youtube.com/watch?v=video-a",
            uploaded_at="2026-07-08T00:00:00Z",
            completed_at="2026-07-08T00:00:00Z",
            experiment_group="group-a",
            hypothesis="Hook improves retention.",
            primary_metric="average_view_percentage",
            secondary_metrics=["views", "likes", "likes_per_view"],
        )
    ]
    metrics_by_video_id = {
        "video-a": {
            "views": 100,
            "engaged_views": 90,
            "likes": 12,
            "comments": 3,
            "shares": 1,
            "subscribers_gained": 2,
            "average_view_duration": 11.5,
            "average_view_percentage": 55.5,
            "estimated_minutes_watched": 18.2,
        }
    }

    summary, snapshot_rows = build_summary(
        targets,
        metrics_by_video_id,
        start_date=date(2026, 7, 1),
        end_date=date(2026, 7, 8),
    )

    assert summary["video_count"] == 1
    assert summary["analyzed_video_count"] == 1
    assert summary["totals"] == {
        "views": 100,
        "engaged_views": 90,
        "likes": 12,
        "comments": 3,
        "shares": 1,
        "subscribers_gained": 2,
        "estimated_minutes_watched": 18.2,
    }
    assert summary["weighted_averages"] == {
        "average_view_duration": 11.5,
        "average_view_percentage": 55.5,
    }
    assert summary["top_by_views"][0]["youtube_video_id"] == "video-a"
    assert summary["top_by_retention"][0]["youtube_video_id"] == "video-a"
    assert summary["videos"][0]["primary_metric_value"] == 55.5
    assert summary["videos"][0]["secondary_metrics"] == {
        "views": 100,
        "likes": 12,
        "likes_per_view": 0.12,
    }
    assert snapshot_rows == [
        {
            "render_id": "render-1",
            "project_id": "project-1",
            "youtube_video_id": "video-a",
            "snapshot_date": "2026-07-08",
            "views": 100,
            "engaged_views": 90,
            "likes": 12,
            "comments": 3,
            "shares": 1,
            "subscribers_gained": 2,
            "average_view_duration": 11.5,
            "average_view_percentage": 55.5,
            "estimated_minutes_watched": 18.2,
            "raw_metrics_json": snapshot_rows[0]["raw_metrics_json"],
        }
    ]


def test_build_summary_adds_maturity_windows_and_v2_quality_fields() -> None:
    target = YoutubeAnalyticsTarget(
        render_id="render-1",
        project_id="project-1",
        topic="ocean",
        internal_title="Internal",
        youtube_title="Ocean",
        youtube_video_id="video-a",
        youtube_url=None,
        uploaded_at="2026-07-08T00:00:00Z",
        completed_at="2026-07-08T00:00:00Z",
        experiment_group="group-a",
        hypothesis="Hook improves retention.",
        primary_metric="average_view_percentage",
        secondary_metrics=[],
        actual_duration_sec=42,
    )
    summary, _ = build_summary(
        [target],
        {"video-a": {"views": 100, "average_view_percentage": 50.0}},
        start_date=date(2026, 7, 8),
        end_date=date(2026, 7, 10),
        daily_rows=[
            {
                "youtube_video_id": "video-a",
                "metric_date": "2026-07-09",
                "data_through_date": "2026-07-09",
                "views": 100,
                "average_view_percentage": 50.0,
            }
        ],
        today_pt=date(2026, 7, 10),
    )
    assert summary["schema_version"] == "youtube-analytics-summary-2.0.0"
    assert {
        "query",
        "data_coverage",
        "maturity_windows",
        "baselines",
        "videos",
        "experiments",
        "observations",
        "recommendations",
        "data_quality",
        "source_versions",
        "facts",
        "interpretations",
        "proposals",
    }.issubset(summary)
    assert set(summary["maturity_windows"]) == {"D1", "D3", "D7", "D28"}
    assert summary["videos"][0]["maturity_windows"]["D1"]["status"] == "complete"
    assert summary["videos"][0]["production_features"]["duration_bucket"] == "short"
    assert "data_quality" in summary
    assert "recommendations" in summary


def test_build_summary_uses_legacy_snapshot_within_twelve_hours() -> None:
    target = YoutubeAnalyticsTarget(
        render_id="render-1",
        project_id="project-1",
        topic="ocean",
        internal_title="Internal",
        youtube_title="Ocean",
        youtube_video_id="video-a",
        youtube_url=None,
        uploaded_at="2026-07-08T00:00:00Z",
        completed_at="2026-07-08T00:00:00Z",
        experiment_group=None,
        hypothesis=None,
        primary_metric="average_view_percentage",
        secondary_metrics=[],
        actual_duration_sec=42,
    )
    summary, _ = build_summary(
        [target],
        {},
        start_date=date(2026, 7, 8),
        end_date=date(2026, 7, 10),
        legacy_snapshots_by_video={
            "video-a": [
                {
                    "collected_at": "2026-07-08T07:00:00Z",
                    "views": 500,
                    "average_view_percentage": 55.0,
                }
            ]
        },
    )
    assert summary["videos"][0]["maturity_windows"]["D1"]["status"] == "snapshot_fallback"
    assert summary["videos"][0]["maturity_windows"]["D1"]["metrics"]["views"] == 500


def test_sync_render_quality_reports_uses_final_only_and_db_render_ids(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "test.db"
    init_db(db_path)
    project = _project(style_id=888753760)
    rendered = _rendered(project)
    rendered["render_id"] = "render_quality"
    quality = {
        "render_id": "render_quality",
        "project_id": project["id"],
        "status": "pass",
        "summary": {"warning_count": 0, "error_count": 0},
        "checks": [],
        "metrics": {
            "subtitle_count": 1,
            "max_subtitle_chars": 10,
            "max_subtitle_cps": 4.0,
            "final_audio_rms_dbfs": -20.0,
            "final_audio_peak_dbfs": -2.0,
        },
    }
    final_dir = tmp_path / "renders" / "item" / "final"
    attempt_dir = tmp_path / "renders" / "item" / "attempts" / "attempt_001"
    final_dir.mkdir(parents=True)
    attempt_dir.mkdir(parents=True)
    (final_dir / "quality_report.json").write_text(json.dumps(quality), encoding="utf-8")
    (attempt_dir / "quality_report.json").write_text(json.dumps({**quality, "status": "warning"}), encoding="utf-8")
    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        upsert_project(connection, project, "projects/sample/project.youtube.json", "hash")
        insert_render_summary(connection, rendered)
        imported = sync_render_quality_reports(connection, renders_dir=tmp_path / "renders")
        row = connection.execute(
            "SELECT status, source_path FROM render_quality_reports"
        ).fetchone()
    assert imported == 1
    assert row["status"] == "pass"
    assert row["source_path"].endswith("final\\quality_report.json")


def test_sync_youtube_uploads_from_rendered_files_backfills_db(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "test.db"
    init_db(db_path)
    project = _project(style_id=888753760)
    rendered = _rendered(project)
    rendered["youtube"]["upload"] = {
        "planned": True,
        "status": "uploaded_private",
        "youtube_video_id": "abc123",
        "youtube_url": "https://www.youtube.com/watch?v=abc123",
        "uploaded_at": "2026-07-09T00:00:00Z",
        "error_message": None,
    }

    render_dir = tmp_path / "renders" / "202607090018-test" / "final"
    render_dir.mkdir(parents=True)
    (render_dir / "rendered.youtube.json").write_text(
        json.dumps(rendered), encoding="utf-8"
    )

    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        upsert_project(
            connection, project, "projects/sample/project.youtube.json", "hash"
        )
        insert_render_summary(connection, rendered)

        synced = sync_youtube_uploads_from_rendered_files(
            connection, renders_dir=tmp_path / "renders"
        )
        targets = collect_uploaded_video_targets(connection)

    assert synced == 1
    assert len(targets) == 1
    assert targets[0].youtube_video_id == "abc123"
    assert targets[0].youtube_url == "https://www.youtube.com/watch?v=abc123"
    assert targets[0].uploaded_at == "2026-07-09T00:00:00Z"


def test_generate_youtube_analytics_summary_persists_snapshots_for_owned_connection(
    tmp_path: Path, monkeypatch: object
) -> None:
    db_path = tmp_path / "test.db"
    init_db(db_path)
    project = _project(style_id=888753760)
    rendered = _rendered(project)

    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        upsert_project(
            connection, project, "projects/sample/project.youtube.json", "hash"
        )
        insert_render_summary(connection, rendered)
        upsert_youtube_uploads(
            connection,
            [
                {
                    "render_id": rendered["render_id"],
                    "planned": True,
                    "status": "uploaded_private",
                    "youtube_video_id": "abc123",
                    "youtube_url": "https://www.youtube.com/watch?v=abc123",
                    "uploaded_at": "2026-07-09T00:00:00Z",
                    "error_message": None,
                }
            ],
        )

    service = FakeAnalyticsService(
        {
            ("abc123",): {
                "columnHeaders": [
                    {"name": "video"},
                    {"name": "views"},
                    {"name": "engagedViews"},
                    {"name": "likes"},
                    {"name": "comments"},
                    {"name": "shares"},
                    {"name": "subscribersGained"},
                    {"name": "averageViewDuration"},
                    {"name": "averageViewPercentage"},
                    {"name": "estimatedMinutesWatched"},
                ],
                "rows": [["abc123", 100, 90, 12, 3, 1, 2, 11.5, 55.5, 18.2]],
            }
        }
    )
    monkeypatch.setattr(analytics_summary, "init_db", lambda: None)
    monkeypatch.setattr(analytics_summary, "connect", lambda: connect(db_path))
    monkeypatch.setattr(
        analytics_summary,
        "sync_youtube_uploads_from_rendered_files",
        lambda connection: 0,
    )

    summary = generate_youtube_analytics_summary(
        days=1,
        output_path=tmp_path / "summary.json",
        analytics_service=service,
    )

    assert summary["analyzed_video_count"] == 1
    with sqlite3.connect(db_path) as connection:
        count = connection.execute(
            "SELECT COUNT(*) FROM youtube_metrics_snapshots"
        ).fetchone()[0]
    assert count == 1
