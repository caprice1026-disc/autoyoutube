from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from src.youtube.analytics_analysis import (
    build_rule_based_recommendations,
    classify_group_size,
    classify_view_confidence,
    derive_rates,
    duration_bucket,
    maturity_window_status,
    choose_baseline,
    hypothesis_status,
    nearest_snapshot,
)


def test_maturity_uses_pacific_calendar_and_dst_boundary() -> None:
    # 03/08/2026 is the US DST transition date. The calendar date must remain PT.
    uploaded = datetime(2026, 3, 8, 7, 30, tzinfo=timezone.utc)
    result = maturity_window_status(
        uploaded,
        window_days=1,
        today_pt=date(2026, 3, 9),
        data_through_date=date(2026, 3, 9),
    )
    assert result["launch_date_pt"] == "2026-03-07"
    assert result["maturity_date_pt"] == "2026-03-08"
    assert result["status"] == "complete"
    assert result["window"] == "D1"


def test_all_maturity_windows_use_the_first_complete_days_after_launch() -> None:
    uploaded = "2026-07-10T12:00:00Z"
    for window_days, label in ((1, "D1"), (3, "D3"), (7, "D7"), (28, "D28")):
        result = maturity_window_status(
            uploaded,
            window_days=window_days,
            today_pt=date(2026, 7, 10) + timedelta(days=window_days + 1),
            data_through_date=date(2026, 7, 10) + timedelta(days=window_days),
        )
        assert result["window"] == label
        assert result["status"] == "complete"


def test_maturity_reports_partial_and_api_lag_states() -> None:
    uploaded = "2026-07-10T12:00:00Z"
    partial = maturity_window_status(
        uploaded,
        window_days=1,
        today_pt=date(2026, 7, 10),
        data_through_date=date(2026, 7, 9),
    )
    assert partial["status"] == "launch_partial_day"

    pending = maturity_window_status(
        uploaded,
        window_days=7,
        today_pt=date(2026, 7, 19),
        data_through_date=date(2026, 7, 16),
    )
    assert pending["status"] == "pending_api_data"

    no_data = maturity_window_status(
        uploaded,
        window_days=1,
        today_pt=date(2026, 7, 20),
        data_through_date=None,
    )
    assert no_data["status"] == "api_no_data"


def test_nearest_snapshot_respects_twelve_hour_tolerance() -> None:
    target = datetime(2026, 7, 10, 12, tzinfo=timezone.utc)
    assert nearest_snapshot(
        [{"collected_at": (target - timedelta(hours=12)).isoformat(), "views": 3}],
        target,
    )["views"] == 3
    assert nearest_snapshot(
        [{"collected_at": (target + timedelta(hours=12)).isoformat(), "views": 1}],
        target,
    )["views"] == 1
    assert nearest_snapshot(
        [{"collected_at": (target + timedelta(hours=12, minutes=1)).isoformat(), "views": 2}],
        target,
    ) is None


def test_thresholds_and_duration_buckets_are_explicit() -> None:
    assert classify_view_confidence(None) == "insufficient"
    assert classify_view_confidence(99) == "insufficient"
    assert classify_view_confidence(100) == "provisional"
    assert classify_view_confidence(499) == "provisional"
    assert classify_view_confidence(500) == "comparable"
    assert classify_group_size(1) == "insufficient_group"
    assert classify_group_size(2) == "insufficient_group"
    assert classify_group_size(3) == "directional"
    assert classify_group_size(4) == "directional"
    assert classify_group_size(5) == "actionable"
    assert duration_bucket(45) == "short"
    assert duration_bucket(45.1) == "medium"
    assert duration_bucket(60) == "medium"
    assert duration_bucket(61) == "long"
    assert duration_bucket(None) is None


def test_derived_rates_keep_zero_denominators_null() -> None:
    rates = derive_rates(
        {
            "views": 0,
            "engaged_views": 0,
            "likes": 3,
            "comments": 1,
            "shares": 2,
            "subscribers_gained": 1,
            "estimated_minutes_watched": 2,
            "average_view_duration": 4,
        }
    )
    assert rates["engaged_view_rate"] is None
    assert rates["like_rate"] is None
    assert rates["comment_rate"] is None
    assert rates["share_rate"] is None
    assert rates["subscriber_gain_rate"] is None
    assert rates["watch_minutes_per_view"] is None
    assert rates["rate_unavailable_reasons"]["likes"] == "views_zero"

    missing_views = derive_rates({"views": None, "likes": 3})
    assert missing_views["like_rate"] is None
    assert missing_views["rate_unavailable_reasons"]["likes"] == "views_missing"

    rates = derive_rates({"views": 100, "likes": 12, "estimated_minutes_watched": 25})
    assert rates["like_rate"] == 0.12
    assert rates["watch_minutes_per_view"] == 0.25


def test_baseline_fallback_returns_median_and_iqr() -> None:
    rows = [
        {"video_id": "a", "topic": "ocean", "maturity": "D1", "duration_bucket": "short", "value": 10},
        {"video_id": "b", "topic": "ocean", "maturity": "D1", "duration_bucket": "short", "value": 20},
        {"video_id": "c", "topic": "ocean", "maturity": "D1", "duration_bucket": "short", "value": 30},
        {"video_id": "d", "topic": "space", "maturity": "D1", "duration_bucket": "short", "value": 40},
        {"video_id": "e", "topic": "space", "maturity": "D1", "duration_bucket": "short", "value": 50},
    ]
    baseline = choose_baseline(
        rows,
        topic="ocean",
        maturity="D1",
        duration_bucket_name="short",
        value_key="value",
        channel_rows=rows,
        minimum_group_size=3,
    )
    assert baseline["scope"] == "same_topic_duration"
    assert baseline["n"] == 3
    assert baseline["median"] == 20
    assert baseline["iqr"] == 10

    fallback = choose_baseline(
        rows[:2],
        topic="ocean",
        maturity="D1",
        duration_bucket_name="short",
        value_key="value",
        channel_rows=rows,
        minimum_group_size=3,
    )
    assert fallback["scope"] == "channel_maturity_duration"


def test_hypothesis_and_recommendations_never_claim_causality() -> None:
    assert hypothesis_status(value=60, baseline_median=40, group_size=2, baseline_iqr=10) == "insufficient_group"
    assert hypothesis_status(value=None, baseline_median=40, group_size=10, baseline_iqr=10) == "insufficient_data"
    assert hypothesis_status(value=60, baseline_median=40, group_size=3, baseline_iqr=10) == "directional_positive"
    assert hypothesis_status(value=40, baseline_median=40, group_size=3, baseline_iqr=10) == "inconclusive"
    assert hypothesis_status(value=60, baseline_median=40, group_size=10, baseline_iqr=10) == "actionable_positive"
    assert hypothesis_status(value=41, baseline_median=40, group_size=10, baseline_iqr=10) == "inconclusive"

    recommendations = build_rule_based_recommendations(
        [
            {
                "video_id": "v1",
                "topic": "ocean",
                "maturity": "D1",
                "metric": "average_view_percentage",
                "value": 60,
                "baseline_median": 40,
                "baseline_iqr": 10,
                "group_status": "actionable",
                "hypothesis_status": "actionable_positive",
            }
        ]
    )
    assert recommendations[0]["action"] in {"keep", "change", "test_next", "hold"}
    assert recommendations[0]["review_required"] is True
    assert "因果" in recommendations[0]["limitations"]
    assert recommendations[0]["recommendation_id"]
    assert recommendations[0]["statement"]
    assert recommendations[0]["evidence_video_ids"]
    assert "evidence_metrics" in recommendations[0]
    assert "comparison" in recommendations[0]

    directional = build_rule_based_recommendations(
        [{**recommendations[0], "hypothesis_status": "directional_positive", "group_status": "directional"}]
    )
    assert directional[0]["action"] == "hold"
