from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.errors import AppError
from src.media.library import MediaAsset
from src.media.pexels_client import PexelsClient
from src.validators.json_validator import load_json


@dataclass(frozen=True)
class VisualQuerySpec:
    query: str
    source: str
    script_indices: list[int]
    target_duration_sec: float | None = None


@dataclass(frozen=True)
class VisualFetchResult:
    assets: list[MediaAsset]
    plan: dict[str, Any]
    plan_path: Path


def fetch_visuals_for_project(
    project_path: Path,
    *,
    client: PexelsClient,
    output_dir: Path,
    per_query: int = 3,
    max_downloads: int | None = None,
    orientation: str | None = "portrait",
    size: str | None = "small",
    plan_path: Path | None = None,
) -> VisualFetchResult:
    project = load_json(project_path)
    specs = visual_query_specs(project)
    if not specs:
        raise AppError(
            "No visual queries were found.",
            location=str(project_path),
            next_step="Add visual_strategy.primary_query, fallback_queries, or script visual_query values.",
        )

    queries = [spec.query for spec in specs]
    assets = client.fetch_assets_for_queries(
        queries,
        output_dir=output_dir,
        per_query=per_query,
        max_downloads=max_downloads,
        orientation=orientation,
        size=size,
    )
    if plan_path is None:
        project_id = str(project.get("id") or project_path.stem)
        plan_path = output_dir / f"{project_id}.visual_plan.json"
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan = build_visual_plan(
        project,
        specs,
        assets,
        output_dir=output_dir,
        per_query=per_query,
        max_downloads=max_downloads,
        orientation=orientation,
        size=size,
    )
    plan_path.write_text(
        json.dumps(plan, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return VisualFetchResult(assets=assets, plan=plan, plan_path=plan_path)


def visual_query_specs(project: dict[str, Any]) -> list[VisualQuerySpec]:
    specs: list[VisualQuerySpec] = []
    visual_strategy = project.get("visual_strategy", {})
    if isinstance(visual_strategy, dict):
        primary_query = _clean(visual_strategy.get("primary_query"))
        if primary_query:
            specs.append(
                VisualQuerySpec(
                    query=primary_query,
                    source="visual_strategy.primary_query",
                    script_indices=[],
                )
            )
    script = project.get("script", [])
    if isinstance(script, list):
        grouped: dict[str, dict[str, Any]] = {}
        for item in script:
            if not isinstance(item, dict):
                continue
            query = _clean(item.get("visual_query"))
            if not query:
                continue
            entry = grouped.setdefault(
                query,
                {"script_indices": [], "target_duration_sec": 0.0},
            )
            index = _int_or_none(item.get("index"))
            if index is not None:
                entry["script_indices"].append(index)
            duration = _float_or_none(item.get("estimated_duration_sec"))
            if duration is not None:
                entry["target_duration_sec"] += duration
        for query, entry in grouped.items():
            specs.append(
                VisualQuerySpec(
                    query=query,
                    source="script.visual_query",
                    script_indices=entry["script_indices"],
                    target_duration_sec=entry["target_duration_sec"] or None,
                )
            )
    if isinstance(visual_strategy, dict):
        fallback_queries = visual_strategy.get("fallback_queries", [])
        if isinstance(fallback_queries, list):
            for query_raw in fallback_queries:
                query = _clean(query_raw)
                if query:
                    specs.append(
                        VisualQuerySpec(
                            query=query,
                            source="visual_strategy.fallback_queries",
                            script_indices=[],
                        )
                    )
    return _dedupe_specs(specs)


def build_visual_plan(
    project: dict[str, Any],
    specs: list[VisualQuerySpec],
    assets: list[MediaAsset],
    *,
    output_dir: Path,
    per_query: int,
    max_downloads: int | None,
    orientation: str | None,
    size: str | None,
) -> dict[str, Any]:
    by_query: dict[str, list[MediaAsset]] = {}
    for asset in assets:
        by_query.setdefault(asset.query, []).append(asset)

    query_plans: list[dict[str, Any]] = []
    for spec in specs:
        candidates = [
            _candidate_plan(asset, spec, preferred_orientation=orientation)
            for asset in by_query.get(spec.query, [])
        ]
        candidates.sort(key=lambda item: (-item["score"], item["asset_id"]))
        query_plans.append(
            {
                "query": spec.query,
                "source": spec.source,
                "script_indices": spec.script_indices,
                "target_duration_sec": spec.target_duration_sec,
                "candidate_count": len(candidates),
                "selected_asset_id": candidates[0]["asset_id"] if candidates else None,
                "candidates": candidates,
            }
        )

    return {
        "schema_version": "visual-plan-1.0.0",
        "project_id": project.get("id"),
        "project_path": str(project.get("input_path") or ""),
        "fetch": {
            "provider": "pexels",
            "output_dir": str(output_dir),
            "per_query": per_query,
            "max_downloads": max_downloads,
            "orientation": orientation,
            "size": size,
        },
        "summary": {
            "query_count": len(query_plans),
            "downloaded_asset_count": len(assets),
            "queries_with_candidates": sum(
                1 for item in query_plans if item["candidate_count"] > 0
            ),
        },
        "queries": query_plans,
    }


def _candidate_plan(
    asset: MediaAsset,
    spec: VisualQuerySpec,
    *,
    preferred_orientation: str | None,
) -> dict[str, Any]:
    score, reasons = score_asset(
        asset,
        preferred_orientation=preferred_orientation,
        target_duration_sec=spec.target_duration_sec,
    )
    return {
        "asset_id": asset.asset_id,
        "score": score,
        "reasons": reasons,
        "source": asset.source,
        "local_file_path": str(asset.local_file_path),
        "pexels_id": asset.pexels_id,
        "photographer": asset.photographer,
        "photographer_url": asset.photographer_url,
        "pexels_url": asset.pexels_url,
        "original_video_url": asset.original_video_url,
        "original_width": asset.original_width,
        "original_height": asset.original_height,
        "original_duration_sec": asset.original_duration_sec,
        "orientation": asset.orientation,
        "selected_quality": asset.selected_quality,
        "tags": asset.tags,
    }


def score_asset(
    asset: MediaAsset,
    *,
    preferred_orientation: str | None = "portrait",
    target_duration_sec: float | None = None,
) -> tuple[int, list[str]]:
    score = 0
    reasons: list[str] = []

    if preferred_orientation and asset.orientation == preferred_orientation:
        score += 35
        reasons.append(f"orientation matches {preferred_orientation}")
    elif asset.orientation == "portrait":
        score += 20
        reasons.append("portrait orientation")
    elif asset.orientation == "landscape":
        score -= 10
        reasons.append("landscape crop may be aggressive")

    width = asset.original_width or 0
    height = asset.original_height or 0
    if width >= 1080 and height >= 1920:
        score += 25
        reasons.append("meets 1080x1920 target")
    elif min(width, height) >= 720:
        score += 12
        reasons.append("usable source resolution")
    elif width and height:
        score -= 15
        reasons.append("source resolution is low")

    duration = asset.original_duration_sec
    if duration is not None and target_duration_sec is not None:
        if duration >= target_duration_sec:
            score += 15
            reasons.append("duration covers target script window")
        elif duration >= max(1.0, target_duration_sec * 0.5):
            score += 5
            reasons.append("duration covers part of target script window")
        else:
            score -= 10
            reasons.append("duration is short for target script window")
    elif duration is not None and duration >= 5:
        score += 5
        reasons.append("duration is long enough for short clips")

    quality_rank = _quality_rank(asset.selected_quality)
    score += quality_rank * 5
    if quality_rank > 0:
        reasons.append(f"quality={asset.selected_quality}")

    if asset.pexels_url and asset.photographer:
        score += 5
        reasons.append("credit metadata is complete")

    if asset.used_count > 0:
        penalty = min(20, asset.used_count * 5)
        score -= penalty
        reasons.append(f"used_count penalty={penalty}")

    return score, reasons


def _dedupe_specs(specs: list[VisualQuerySpec]) -> list[VisualQuerySpec]:
    merged: dict[str, VisualQuerySpec] = {}
    order: list[str] = []
    for spec in specs:
        key = spec.query.lower()
        if key not in merged:
            merged[key] = spec
            order.append(key)
            continue
        current = merged[key]
        merged[key] = VisualQuerySpec(
            query=current.query,
            source=f"{current.source}+{spec.source}",
            script_indices=sorted(set(current.script_indices + spec.script_indices)),
            target_duration_sec=(current.target_duration_sec or 0)
            + (spec.target_duration_sec or 0)
            or None,
        )
    return [merged[key] for key in order]


def _quality_rank(value: str) -> int:
    return {"sd": 1, "hd": 2, "uhd": 3, "original": 4}.get(value, 0)


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _int_or_none(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
