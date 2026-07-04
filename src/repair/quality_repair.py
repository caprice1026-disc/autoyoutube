from __future__ import annotations

from dataclasses import dataclass
from typing import Any


BLOCKING_WARNING_CODES = {
    "SAME_ASSET_CONSECUTIVE",
    "SAME_ASSET_REUSED",
    "SOURCE_RESOLUTION_TOO_LOW",
}

VISUAL_REPAIR_CODES = {
    "SAME_ASSET_CONSECUTIVE",
    "SAME_ASSET_REUSED",
    "ASSET_RECENTLY_USED",
    "SOURCE_RESOLUTION_TOO_LOW",
    "VISUAL_FILE_MISSING",
    "MEDIA_FILE_MISSING",
    "QUERY_CANDIDATE_TOO_FEW",
    "PEXELS_FETCH_FAILED",
    "PEXELS_RATE_LIMIT",
}

NON_BLOCKING_WARNING_CODES = {
    "VIDEO_DURATION_TOO_LONG",
}


@dataclass(frozen=True)
class RepairDecision:
    blocking_checks: list[dict[str, Any]]
    can_retry: bool
    fixes: list[dict[str, Any]]
    rejected_asset_ids: set[str]


def decide_repair(
    checks: list[dict[str, Any]],
    *,
    auto_fix: bool,
) -> RepairDecision:
    blocking = [check for check in checks if _is_blocking(check)]
    fixes: list[dict[str, Any]] = []
    rejected_asset_ids: set[str] = set()
    for check in blocking:
        code = str(check.get("code") or "")
        asset_id = _asset_id(check)
        if asset_id:
            rejected_asset_ids.add(asset_id)
        action = _fix_action(code)
        fixes.append(
            {
                "action": action,
                "asset_id": asset_id,
                "reason": code,
                "before": check.get("target"),
                "after": "retry_attempt" if action != "manual_review" else None,
            }
        )

    can_retry = bool(
        auto_fix and blocking and all(check.get("auto_fixable") for check in blocking)
    )
    return RepairDecision(
        blocking_checks=blocking,
        can_retry=can_retry,
        fixes=fixes,
        rejected_asset_ids=rejected_asset_ids,
    )


def _is_blocking(check: dict[str, Any]) -> bool:
    code = str(check.get("code") or "")
    level = str(check.get("level") or "")
    if code in NON_BLOCKING_WARNING_CODES:
        return False
    if level == "error":
        return True
    return code in BLOCKING_WARNING_CODES


def _fix_action(code: str) -> str:
    if code in VISUAL_REPAIR_CODES:
        return "reject_asset_and_reselect"
    if code == "FFMPEG_TRANSIENT_ERROR":
        return "retry_ffmpeg_render"
    return "manual_review"


def _asset_id(check: dict[str, Any]) -> str | None:
    if check.get("asset_id"):
        return str(check["asset_id"])
    metrics = check.get("metrics")
    if isinstance(metrics, dict) and metrics.get("asset_id"):
        return str(metrics["asset_id"])
    return None
