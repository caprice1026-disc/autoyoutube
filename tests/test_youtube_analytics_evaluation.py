from __future__ import annotations

from src.youtube.analytics_evaluation import build_dual_period_evaluation


def _summary(*, period: str, retention: float, views: int) -> dict[str, object]:
    return {
        "schema_version": "youtube-analytics-summary-2.0.0",
        "query": {"start_date": period, "end_date": period, "days": 28},
        "totals": {
            "views": views,
            "likes": 20,
            "comments": 4,
            "shares": 2,
            "subscribers_gained": 1,
            "estimated_minutes_watched": 50.0,
        },
        "weighted_averages": {
            "average_view_percentage": retention,
            "average_view_duration": 18.0,
        },
        "data_quality": {
            "comparable_view_video_count": 2,
            "missing_video_count": 1,
            "pending_api_video_count": 0,
        },
        "videos": [
            {
                "youtube_video_id": "video-a",
                "experiment_group": "stock_only",
                "views": views,
                "likes": 20,
                "comments": 4,
                "shares": 2,
                "subscribers_gained": 1,
                "average_view_percentage": retention,
                "average_view_duration": 18.0,
                "maturity_windows": {
                    "D7": {
                        "status": "complete",
                        "view_confidence": "comparable",
                        "metrics": {
                            "views": views,
                            "likes": 20,
                            "comments": 4,
                            "shares": 2,
                            "subscribers_gained": 1,
                            "average_view_percentage": retention,
                            "average_view_duration": 18.0,
                        },
                    }
                },
            },
            {
                "youtube_video_id": "video-b",
                "experiment_group": "stock_only",
                "views": 500,
                "likes": 10,
                "comments": 2,
                "shares": 1,
                "subscribers_gained": 0,
                "average_view_percentage": 40.0,
                "average_view_duration": 15.0,
                "maturity_windows": {
                    "D7": {
                        "status": "complete",
                        "view_confidence": "comparable",
                        "metrics": {
                            "views": 500,
                            "likes": 10,
                            "comments": 2,
                            "shares": 1,
                            "subscribers_gained": 0,
                            "average_view_percentage": 40.0,
                            "average_view_duration": 15.0,
                        },
                    }
                },
            },
        ],
    }


def test_build_dual_period_evaluation_reports_period_metrics_and_limits() -> None:
    evaluation = build_dual_period_evaluation(
        _summary(period="2026-07-01", retention=50.0, views=1_000),
        _summary(period="2025-01-01", retention=45.0, views=2_000),
    )

    recent = evaluation["periods"]["recent_28_days"]
    assert recent["weighted_averages"]["average_view_percentage"] == 50.0
    assert recent["rates"]["likes_per_view"] == 0.02
    group = recent["maturity_groups"]["D7"]["stock_only"]
    assert group["n"] == 2
    assert group["comparison_status"] == "insufficient_group"
    assert group["weighted_averages"]["average_view_percentage"] == 46.666667
    assert evaluation["periods"]["all_history"]["totals"]["views"] == 2_000
    assert evaluation["limitations"]
    assert "recent_28_days/D7: 1実験グループが標本数3本未満のため比較判断を保留する。" in evaluation["limitations"]
