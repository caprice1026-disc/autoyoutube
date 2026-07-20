"""Pure, deterministic helpers for post-publication Shorts analysis.

The functions in this module intentionally do not call the YouTube API or the
database.  Keeping the policy decisions here makes the maturity and proposal
rules easy to fixture-test and prevents an LLM from silently changing them.
"""

from __future__ import annotations

import math
from calendar import monthcalendar
from datetime import date, datetime, timedelta, timezone, tzinfo
from statistics import median
from typing import Any, Iterable, Mapping
try:
    from zoneinfo import ZoneInfo

    PACIFIC: tzinfo = ZoneInfo("America/Los_Angeles")
except Exception:  # pragma: no cover - Windows Python without the tzdata wheel
    class _PacificFallback(tzinfo):
        """Small IANA-compatible fallback for environments without tzdata."""

        @staticmethod
        def _sunday(year: int, month: int, occurrence: int) -> date:
            Sundays = [
                day
                for week in monthcalendar(year, month)
                for day in [week[6]]
                if day
            ]
            return date(year, month, Sundays[occurrence - 1])

        @classmethod
        def _utc_bounds(cls, year: int) -> tuple[datetime, datetime]:
            start = datetime.combine(
                cls._sunday(year, 3, 2), datetime.min.time(), tzinfo=timezone.utc
            ) + timedelta(hours=10)
            end = datetime.combine(
                cls._sunday(year, 11, 1), datetime.min.time(), tzinfo=timezone.utc
            ) + timedelta(hours=9)
            return start, end

        def fromutc(self, dt: datetime) -> datetime:
            utc = dt.replace(tzinfo=timezone.utc)
            start, end = self._utc_bounds(utc.year)
            offset = timedelta(hours=-7 if start <= utc < end else -8)
            return (utc + offset).replace(tzinfo=self)

        def utcoffset(self, dt: datetime | None) -> timedelta:
            if dt is None:
                return timedelta(hours=-8)
            # For local wall-clock values, the DST period is unambiguous except
            # for the transition hour; fold=1 chooses the standard-time side.
            start = self._sunday(dt.year, 3, 2)
            end = self._sunday(dt.year, 11, 1)
            in_dst = start < dt.date() < end
            if dt.date() == start:
                in_dst = dt.hour >= 2
            if dt.date() == end:
                in_dst = dt.hour < 2 and not dt.fold
            return timedelta(hours=-7 if in_dst else -8)

        def dst(self, dt: datetime | None) -> timedelta:
            return self.utcoffset(dt) - timedelta(hours=-8)

        def tzname(self, dt: datetime | None) -> str:
            return "PDT" if self.dst(dt) else "PST"

    PACIFIC = _PacificFallback()
MATURITY_WINDOWS: tuple[tuple[str, int], ...] = (
    ("D1", 1),
    ("D3", 3),
    ("D7", 7),
    ("D28", 28),
)
MIN_COMPARABLE_VIEWS = 500
MIN_PROVISIONAL_VIEWS = 100
MIN_ACTIONABLE_GROUP = 5
MIN_DIRECTIONAL_GROUP = 3
SNAPSHOT_TOLERANCE_HOURS = 12
API_LAG_TOLERANCE_HOURS = 72


def parse_datetime(value: str | datetime | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        text = str(value).strip()
        if not text:
            return None
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def to_pacific_date(value: str | datetime | None) -> date | None:
    parsed = parse_datetime(value)
    return parsed.astimezone(PACIFIC).date() if parsed else None


def duration_bucket(duration_sec: float | int | None) -> str | None:
    if duration_sec is None:
        return None
    duration = float(duration_sec)
    if duration <= 45:
        return "short"
    if duration <= 60:
        return "medium"
    return "long"


def classify_view_confidence(views: int | float | None) -> str:
    if views is None or float(views) < MIN_PROVISIONAL_VIEWS:
        return "insufficient"
    if float(views) < MIN_COMPARABLE_VIEWS:
        return "provisional"
    return "comparable"


def classify_group_size(size: int | None) -> str:
    if size is None or size < MIN_DIRECTIONAL_GROUP:
        return "insufficient_group"
    if size < MIN_ACTIONABLE_GROUP:
        return "directional"
    return "actionable"


def maturity_window_status(
    uploaded_at: str | datetime | None,
    window_days: int,
    today_pt: date,
    data_through_date: date | None,
    *,
    api_lag_tolerance_hours: int = API_LAG_TOLERANCE_HOURS,
) -> dict[str, Any]:
    """Return the state of one maturity window using PT calendar dates.

    A window is due on ``launch_date + window_days``.  The upload date itself
    is retained as a separate partial day and is never silently counted as a
    complete maturity day.
    """

    launch_date = to_pacific_date(uploaded_at)
    label = f"D{window_days}"
    if launch_date is None:
        return {
            "window": label,
            "launch_date_pt": None,
            "maturity_date_pt": None,
            "status": "invalid_upload_date",
            "data_through_date": data_through_date.isoformat()
            if data_through_date
            else None,
        }
    maturity_date = launch_date + timedelta(days=window_days)
    result: dict[str, Any] = {
        "window": label,
        "launch_date_pt": launch_date.isoformat(),
        "maturity_date_pt": maturity_date.isoformat(),
        "data_through_date": data_through_date.isoformat()
        if data_through_date
        else None,
        "launch_partial_day": today_pt >= launch_date,
    }
    if today_pt == launch_date:
        result["status"] = "launch_partial_day"
        return result
    if today_pt < maturity_date:
        result["status"] = "pending_maturity"
        return result
    if data_through_date is not None and data_through_date >= maturity_date:
        result["status"] = "complete"
        return result

    lag_days = (today_pt - (data_through_date or launch_date)).days
    # API reports are date-granular, so a three-day difference is the largest
    # uncertainty window that can still be a normal recent-data delay.
    result["status"] = (
        "pending_api_data"
        if lag_days * 24 <= api_lag_tolerance_hours
        else "api_no_data"
    )
    return result


def nearest_snapshot(
    snapshots: Iterable[Mapping[str, Any]],
    target: datetime,
    *,
    tolerance_hours: int = SNAPSHOT_TOLERANCE_HOURS,
) -> Mapping[str, Any] | None:
    """Return the nearest snapshot within the documented ±12-hour window."""

    candidates: list[tuple[float, Mapping[str, Any]]] = []
    for snapshot in snapshots:
        raw = snapshot.get("collected_at") or snapshot.get("snapshot_at")
        parsed = parse_datetime(str(raw) if raw is not None else None)
        if parsed is None:
            continue
        distance = abs((parsed - target).total_seconds()) / 3600
        if distance <= tolerance_hours:
            candidates.append((distance, snapshot))
    return min(candidates, key=lambda item: item[0])[1] if candidates else None


def _number(metrics: Mapping[str, Any], key: str) -> float | None:
    value = metrics.get(key)
    if value is None:
        return None
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def derive_rates(metrics: Mapping[str, Any]) -> dict[str, Any]:
    views = _number(metrics, "views")
    unavailable: dict[str, str] = {}

    def rate(key: str) -> float | None:
        numerator = _number(metrics, key)
        if views is None:
            unavailable[key] = "views_missing"
            return None
        if views <= 0:
            unavailable[key] = "views_zero"
            return None
        if numerator is None:
            unavailable[key] = "numerator_missing"
            return None
        return numerator / views

    minutes = _number(metrics, "estimated_minutes_watched")
    watch_minutes_per_view = (
        minutes / views if minutes is not None and views and views > 0 else None
    )
    if views is None:
        unavailable["watch_minutes_per_view"] = "views_missing"
    elif views <= 0:
        unavailable["watch_minutes_per_view"] = "views_zero"
    elif minutes is None:
        unavailable["watch_minutes_per_view"] = "numerator_missing"
    return {
        "engaged_view_rate": rate("engaged_views"),
        "like_rate": rate("likes"),
        "comment_rate": rate("comments"),
        "share_rate": rate("shares"),
        "subscriber_gain_rate": rate("subscribers_gained"),
        "watch_minutes_per_view": watch_minutes_per_view,
        "rate_unavailable_reasons": unavailable,
    }


def _percentile(values: list[float], fraction: float) -> float:
    if len(values) == 1:
        return values[0]
    position = (len(values) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return values[lower]
    weight = position - lower
    return values[lower] * (1 - weight) + values[upper] * weight


def median_iqr(values: Iterable[float | int | None]) -> dict[str, float | int | None]:
    clean = sorted(float(value) for value in values if value is not None)
    if not clean:
        return {"n": 0, "median": None, "q1": None, "q3": None, "iqr": None}
    q1 = _percentile(clean, 0.25)
    q3 = _percentile(clean, 0.75)
    return {
        "n": len(clean),
        "median": median(clean),
        "q1": q1,
        "q3": q3,
        "iqr": q3 - q1,
    }


def choose_baseline(
    topic_rows: Iterable[Mapping[str, Any]],
    *,
    topic: str | None,
    maturity: str,
    duration_bucket_name: str | None,
    value_key: str,
    channel_rows: Iterable[Mapping[str, Any]],
    minimum_group_size: int = MIN_ACTIONABLE_GROUP,
) -> dict[str, Any]:
    topic_candidates = [
        row
        for row in topic_rows
        if row.get("topic") == topic
        and row.get("maturity") == maturity
        and row.get("duration_bucket") == duration_bucket_name
        and row.get(value_key) is not None
    ]
    channel_candidates = [
        row
        for row in channel_rows
        if row.get("maturity") == maturity
        and row.get("duration_bucket") == duration_bucket_name
        and row.get(value_key) is not None
    ]
    maturity_candidates = [
        row
        for row in channel_rows
        if row.get("maturity") == maturity and row.get(value_key) is not None
    ]
    for scope, candidates in (
        ("same_topic_duration", topic_candidates),
        ("channel_maturity_duration", channel_candidates),
        ("channel_maturity", maturity_candidates),
    ):
        if len(candidates) >= minimum_group_size:
            result = median_iqr(row[value_key] for row in candidates)
            return {
                "scope": scope,
                "video_ids": [
                    row.get("video_id") or row.get("youtube_video_id")
                    for row in candidates
                    if row.get("video_id") or row.get("youtube_video_id")
                ],
                **result,
            }
    return {
        "scope": "insufficient_baseline",
        "video_ids": [],
        "n": max(len(topic_candidates), len(channel_candidates), len(maturity_candidates)),
        "median": None,
        "q1": None,
        "q3": None,
        "iqr": None,
    }


def hypothesis_status(
    *,
    value: float | None,
    baseline_median: float | None,
    group_size: int,
    baseline_iqr: float | None,
    minimum_group_size: int = MIN_ACTIONABLE_GROUP,
) -> str:
    if group_size < MIN_DIRECTIONAL_GROUP:
        return "insufficient_group"
    if value is None:
        return "insufficient_data"
    if baseline_median is None:
        return "insufficient_baseline"
    difference = value - baseline_median
    threshold = max(float(baseline_iqr or 0), abs(float(baseline_median)) * 0.10)
    if difference >= threshold and threshold > 0:
        return "actionable_positive" if group_size >= minimum_group_size else "directional_positive"
    if difference <= -threshold and threshold > 0:
        return "actionable_negative" if group_size >= minimum_group_size else "directional_negative"
    return "inconclusive"


def build_rule_based_recommendations(
    observations: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    recommendations: list[dict[str, Any]] = []
    for observation in observations:
        status = str(observation.get("hypothesis_status") or "")
        value = observation.get("value")
        baseline = observation.get("baseline_median")
        if status == "actionable_positive":
            action = "keep"
            rationale = "基準中央値をIQR以上上回ったため、次回も同じ要素を維持する。"
        elif status == "actionable_negative":
            action = "change"
            rationale = "基準中央値をIQR以上下回ったため、要素を変更して再検証する。"
        elif status in {"directional_positive", "directional_negative"}:
            action = "hold"
            rationale = "方向性は参考表示に留め、5本未満のため改善提案は生成しない。"
        elif observation.get("group_status") == "actionable" and status == "inconclusive":
            action = "test_next"
            rationale = "比較可能なグループだが結論が不一致のため、次の実験で再検証する。"
        else:
            action = "hold"
            rationale = "比較可能性が不足しているため、追加データまで判断を保留する。"
        recommendations.append(
            {
                "recommendation_id": f"{action}:{observation.get('video_id')}:{observation.get('maturity')}:{observation.get('metric')}",
                "video_id": observation.get("video_id"),
                "action": action,
                "statement": rationale,
                "rationale": rationale,
                "evidence_video_ids": observation.get("evidence_video_ids") or [observation.get("video_id")],
                "evidence_metrics": {
                    "metric": observation.get("metric"),
                    "value": value,
                    "baseline_median": baseline,
                    "baseline_iqr": observation.get("baseline_iqr"),
                    "median_difference": observation.get("median_difference"),
                },
                "comparison": observation.get("comparison") or {
                    "scope": observation.get("baseline", {}).get("scope"),
                    "median": baseline,
                    "iqr": observation.get("baseline_iqr"),
                    "n": observation.get("baseline", {}).get("n"),
                },
                "evidence": {
                    "metric": observation.get("metric"),
                    "value": value,
                    "baseline_median": baseline,
                    "baseline_iqr": observation.get("baseline_iqr"),
                    "hypothesis_status": status,
                },
                "confidence": "high" if status.startswith("actionable_") else "low",
                "limitations": "相関に基づく観察であり、因果関係を主張しない。",
                "maturity_window": observation.get("maturity"),
                "duration_bucket": observation.get("duration_bucket"),
                # Every proposal is advisory; a human must review it before
                # changing a project or scheduling the next experiment.
                "review_required": True,
            }
        )
    return recommendations
