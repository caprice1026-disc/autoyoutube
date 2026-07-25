from __future__ import annotations

from typing import Any


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
            f"cached_metrics={quality.get('cached_metric_video_count', 0)}, "
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


def _format_int(value: Any) -> str:
    if value is None:
        return "n/a"
    try:
        return f"{int(value):,}"
    except (TypeError, ValueError):
        return "n/a"


def _format_float(value: Any) -> str:
    if value is None:
        return "n/a"
    try:
        return f"{float(value):.2f}"
    except (TypeError, ValueError):
        return "n/a"


def _format_percentage(value: Any) -> str:
    if value is None:
        return "n/a"
    try:
        return f"{float(value):.2f}%"
    except (TypeError, ValueError):
        return "n/a"
