from __future__ import annotations

from collections import defaultdict
from typing import Any


COMPARABLE_MATURITY_STATUSES = {"complete", "snapshot_fallback"}


def build_dual_period_evaluation(
    recent_summary: dict[str, Any], history_summary: dict[str, Any]
) -> dict[str, Any]:
    """Build a cautious, side-effect-free comparison of two API summaries."""

    periods = {
        "recent_28_days": _evaluate_period(recent_summary),
        "all_history": _evaluate_period(history_summary),
    }
    limitations = _limitations(periods)
    return {
        "schema_version": "youtube-analytics-evaluation-1.0.0",
        "periods": periods,
        "limitations": limitations,
        "interpretation_policy": (
            "比較は同じ成熟度で視聴数が比較可能な動画に限定する。"
            "標本数が3未満の実験グループは方向性の参考にも使わず、因果関係を主張しない。"
        ),
    }


def format_evaluation_markdown(evaluation: dict[str, Any]) -> str:
    """Format the evaluation as a compact, human-readable Japanese report."""

    lines = ["# YouTube Analytics 二期間評価", ""]
    for label, title in (
        ("recent_28_days", "直近28日"),
        ("all_history", "全履歴"),
    ):
        period = evaluation.get("periods", {}).get(label, {})
        query = period.get("query", {})
        totals = period.get("totals", {})
        weighted = period.get("weighted_averages", {})
        lines.extend(
            [
                f"## {title}",
                "",
                f"対象期間: {query.get('start_date', 'n/a')} から {query.get('end_date', 'n/a')}",
                f"対象動画: {period.get('video_count', 0)}本 / 比較可能動画: {period.get('comparable_video_count', 0)}本",
                f"再生数: {_format_int(totals.get('views'))}",
                f"加重平均視聴率: {_format_percent(weighted.get('average_view_percentage'))}",
                f"加重平均視聴時間: {_format_seconds(weighted.get('average_view_duration'))}",
                f"高評価率: {_format_percent(period.get('rates', {}).get('likes_per_view'), ratio=True)}",
                "",
                "### 成熟度別・実験グループ別", "",
            ]
        )
        maturity_groups = period.get("maturity_groups", {})
        if not maturity_groups:
            lines.append("比較可能な成熟度グループはありません。")
        for maturity, groups in maturity_groups.items():
            lines.append(f"#### {maturity}")
            for group, values in groups.items():
                lines.append(
                    "- "
                    f"{group}: n={values.get('n', 0)}, "
                    f"視聴率={_format_percent(values.get('weighted_averages', {}).get('average_view_percentage'))}, "
                    f"状態={values.get('comparison_status', 'unknown')}"
                )
            lines.append("")
    lines.extend(["## 制約", ""])
    limitations = evaluation.get("limitations", [])
    if limitations:
        lines.extend(f"- {item}" for item in limitations)
    else:
        lines.append("重大なデータ品質上の制約は検出されませんでした。")
    lines.append("")
    return "\n".join(lines)


def format_evaluation_console(evaluation: dict[str, Any]) -> list[str]:
    lines = ["YouTube analytics dual-period evaluation written."]
    for label in ("recent_28_days", "all_history"):
        period = evaluation["periods"][label]
        lines.append(
            f"{label}: videos={period['video_count']}, "
            f"comparable={period['comparable_video_count']}, "
            f"views={_format_int(period['totals'].get('views'))}, "
            f"retention={_format_percent(period['weighted_averages'].get('average_view_percentage'))}"
        )
    lines.append(f"Limitations: {len(evaluation['limitations'])}")
    return lines


def _evaluate_period(summary: dict[str, Any]) -> dict[str, Any]:
    videos = [row for row in summary.get("videos", []) if isinstance(row, dict)]
    maturity_groups: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    comparable_video_ids: set[str] = set()
    for video in videos:
        group = str(video.get("experiment_group") or "unclassified")
        video_id = str(video.get("youtube_video_id") or "")
        for maturity, window in (video.get("maturity_windows") or {}).items():
            if not isinstance(window, dict):
                continue
            if window.get("status") not in COMPARABLE_MATURITY_STATUSES:
                continue
            if window.get("view_confidence") != "comparable":
                continue
            metrics = window.get("metrics")
            if not isinstance(metrics, dict) or _number(metrics.get("views")) is None:
                continue
            maturity_groups[str(maturity)][group].append(metrics)
            if video_id:
                comparable_video_ids.add(video_id)

    return {
        "query": dict(summary.get("query") or {}),
        "video_count": len(videos),
        "comparable_video_count": len(comparable_video_ids),
        "totals": dict(summary.get("totals") or {}),
        "weighted_averages": dict(summary.get("weighted_averages") or {}),
        "rates": _rates(dict(summary.get("totals") or {})),
        "data_quality": dict(summary.get("data_quality") or {}),
        "maturity_groups": {
            maturity: {
                group: _group_metrics(rows)
                for group, rows in sorted(groups.items())
            }
            for maturity, groups in sorted(maturity_groups.items())
        },
    }


def _group_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    totals = {metric: _sum(rows, metric) for metric in _rate_metrics()}
    return {
        "n": len(rows),
        "comparison_status": "comparable" if len(rows) >= 3 else "insufficient_group",
        "totals": totals,
        "weighted_averages": {
            "average_view_percentage": _weighted(rows, "average_view_percentage"),
            "average_view_duration": _weighted(rows, "average_view_duration"),
        },
        "rates": _rates(totals),
    }


def _limitations(periods: dict[str, dict[str, Any]]) -> list[str]:
    limits: list[str] = []
    for label, period in periods.items():
        quality = period.get("data_quality", {})
        missing = int(quality.get("missing_video_count") or 0)
        pending = int(quality.get("pending_api_video_count") or 0)
        if missing or pending:
            limits.append(f"{label}: 指標欠損={missing}本、API反映待ち={pending}本。")
        for maturity, groups in period.get("maturity_groups", {}).items():
            insufficient_count = sum(
                1
                for values in groups.values()
                if values.get("comparison_status") == "insufficient_group"
            )
            if insufficient_count:
                limits.append(
                    f"{label}/{maturity}: {insufficient_count}実験グループが"
                    "標本数3本未満のため比較判断を保留する。"
                )
    return limits


def _rates(totals: dict[str, Any]) -> dict[str, float | None]:
    views = _number(totals.get("views"))
    if not views:
        return {
            "likes_per_view": None,
            "comments_per_view": None,
            "shares_per_view": None,
            "subscribers_per_view": None,
        }
    return {
        "likes_per_view": _divide(totals.get("likes"), views),
        "comments_per_view": _divide(totals.get("comments"), views),
        "shares_per_view": _divide(totals.get("shares"), views),
        "subscribers_per_view": _divide(totals.get("subscribers_gained"), views),
    }


def _weighted(rows: list[dict[str, Any]], metric: str) -> float | None:
    denominator = 0.0
    numerator = 0.0
    for row in rows:
        views = _number(row.get("views"))
        value = _number(row.get(metric))
        if views is None or value is None:
            continue
        denominator += views
        numerator += views * value
    return round(numerator / denominator, 6) if denominator else None


def _sum(rows: list[dict[str, Any]], metric: str) -> float | int | None:
    values = [_number(row.get(metric)) for row in rows]
    actual = [value for value in values if value is not None]
    if not actual:
        return None
    total = sum(actual)
    return int(total) if all(float(value).is_integer() for value in actual) else total


def _rate_metrics() -> tuple[str, ...]:
    return ("views", "likes", "comments", "shares", "subscribers_gained")


def _divide(value: Any, denominator: float) -> float | None:
    number = _number(value)
    return round(number / denominator, 8) if number is not None else None


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _format_int(value: Any) -> str:
    number = _number(value)
    return f"{int(number):,}" if number is not None else "n/a"


def _format_percent(value: Any, *, ratio: bool = False) -> str:
    number = _number(value)
    if number is None:
        return "n/a"
    return f"{number * 100 if ratio else number:.2f}%"


def _format_seconds(value: Any) -> str:
    number = _number(value)
    return f"{number:.2f}秒" if number is not None else "n/a"
