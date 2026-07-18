from __future__ import annotations

import json
import random
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from src.auto_repair_config import (
    load_auto_repair_config,
    resolve_max_fix_attempts,
)
from src.config import PROJECT_SCHEMA_PATH, RENDERS_DIR
from src.db.database import connect, init_db
from src.db.repositories import upsert_media_assets
from src.errors import AppError
from src.media.pexels_client import PexelsClient
from src.media.visual_fetcher import fetch_visuals_for_project
from src.pipeline.render_project import _render_dir_name, render_project
from src.quality.evaluator import evaluate_render
from src.quality.inspector import inspect_render
from src.render.ffmpeg_renderer import FfmpegVideoRenderer
from src.repair.failure_classifier import classify_exception
from src.repair.quality_repair import decide_repair
from src.utils.file_hash import sha256_file
from src.validators.json_validator import load_json, validate_json
from src.voice.aivis_client import AivisSpeechClient


@dataclass(frozen=True)
class MakeVideoOptions:
    project_path: Path
    visual_keywords: list[str] = field(default_factory=list)
    query_mode: str = "append"
    per_query: int | None = None
    max_downloads: int | None = None
    orientation: str = "portrait"
    size: str = "small"
    voice_mode: str = "aivis"
    video_mode: str = "ffmpeg"
    aivis_base_url: str | None = None
    ffmpeg_path: str | None = None
    bgm_id: str | None = None
    seed: int | None = None
    auto_fix: bool = True
    max_fix_attempts: int | None = None
    plan_only: bool = False
    dry_run: bool = False
    skip_fetch_visuals: bool = False
    skip_inspect: bool = False
    skip_evaluate: bool = False
    config_path: Path | None = None


@dataclass(frozen=True)
class MakeVideoResult:
    exit_code: int
    status: str
    run_dir: Path | None
    final_rendered_path: Path | None
    plan: dict[str, Any]


def make_video(options: MakeVideoOptions) -> MakeVideoResult:
    project_path = options.project_path.resolve()
    project = load_json(project_path)
    _validate_project(project, project_path)
    config = load_auto_repair_config(options.config_path)
    max_attempts = resolve_max_fix_attempts(
        cli_value=options.max_fix_attempts,
        config=config,
    )
    seed = (
        options.seed
        if options.seed is not None
        else random.SystemRandom().randint(1, 2**31 - 1)
    )
    plan = _build_plan(options, project_path, project, max_attempts, seed)
    if options.plan_only:
        _log("plan-only: no render or external fetch will run")
        return MakeVideoResult(
            exit_code=0,
            status="planned",
            run_dir=None,
            final_rendered_path=None,
            plan=plan,
        )

    init_db()
    run_dir = _next_run_dir(project)
    inputs_dir = run_dir / "inputs"
    attempts_dir = run_dir / "attempts"
    inputs_dir.mkdir(parents=True, exist_ok=True)
    attempts_dir.mkdir(parents=True, exist_ok=True)
    _write_json(inputs_dir / "project.original.json", project)

    repair_log = _empty_repair_log(project, seed, max_attempts)
    failure_log = _empty_failure_log()
    final_rendered_path: Path | None = None
    current_project = _project_with_bgm_override(project, options.bgm_id)
    current_project = _project_with_visual_keywords(current_project, options)
    rejected_asset_ids: set[str] = set()
    rejected_source_keys: set[str] = set()
    per_query = options.per_query or _config_int(
        config, "visuals", "default_per_query", 3
    )
    max_downloads = options.max_downloads
    exit_code = 1
    status = "failed"

    for attempt in range(1, max_attempts + 1):
        _log(f"attempt {attempt} started")
        attempt_dir = attempts_dir / f"attempt_{attempt:03d}"
        attempt_project_path = inputs_dir / f"project.attempt_{attempt:03d}.json"
        _write_json(attempt_project_path, current_project)
        attempt_entry = {
            "attempt": attempt,
            "render_dir": str(attempt_dir),
            "quality_report_path": str(attempt_dir / "quality_report.json"),
            "checks": [],
            "fixes": [],
        }
        try:
            if not options.skip_fetch_visuals and not options.dry_run:
                _log(f"attempt {attempt}: fetching visuals per_query={per_query}")
                try:
                    visual_plan = _fetch_visuals(
                        attempt_project_path,
                        per_query=per_query,
                        max_downloads=max_downloads,
                        orientation=options.orientation,
                        size=options.size,
                        additional_queries=(
                            None
                            if options.query_mode == "override"
                            else options.visual_keywords
                        ),
                    )
                    duplicates = _duplicate_selected_assets(visual_plan)
                    if duplicates:
                        rejected_asset_ids.update(duplicates)
                        attempt_entry["fixes"].extend(
                            {
                                "action": "reject_visual_plan_duplicate",
                                "asset_id": asset_id,
                                "reason": "VISUAL_PLAN_DUPLICATE",
                                "before": "visual_plan.selected_asset_id",
                                "after": "exclude_before_render",
                            }
                            for asset_id in sorted(duplicates)
                        )
                        _log(
                            f"attempt {attempt}: rejected duplicate visual plan assets"
                        )
                except Exception as exc:
                    failure = classify_exception(exc)
                    failure["attempt"] = attempt
                    failure["action"] = "fallback_to_local_stock"
                    failure_log["failures"].append(failure)
                    _log(
                        "attempt "
                        f"{attempt}: visual fetch failed; continuing with local stock"
                    )
            _log(f"attempt {attempt}: rendering")
            rendered_path = _render_attempt(
                options,
                attempt_project_path,
                attempt_dir,
                rejected_asset_ids,
                rejected_source_keys,
            )
            if not options.skip_inspect and not options.dry_run:
                _log(f"attempt {attempt}: inspecting render")
                try:
                    _inspect_attempt(rendered_path, options.ffmpeg_path)
                except Exception as exc:
                    failure = classify_exception(exc)
                    failure["attempt"] = attempt
                    failure["action"] = "continue_to_evaluate"
                    failure_log["failures"].append(failure)
                    _log(f"attempt {attempt}: inspect failed; continuing to evaluate")
            _log(f"attempt {attempt}: evaluating quality")
            report = _evaluate_attempt(rendered_path, skip=options.skip_evaluate)
            attempt_entry["checks"] = _check_summaries(report.get("checks", []))
            checks = report.get("checks", [])
            duration_fix = _duration_fix(current_project, checks, config, options)
            decision = decide_repair(checks, auto_fix=options.auto_fix)
            attempt_entry["fixes"].extend(decision.fixes)
            if duration_fix:
                attempt_entry["fixes"].append(duration_fix["log"])
                current_project = duration_fix["project"]
            rejected_asset_ids.update(decision.rejected_asset_ids)
            rejected_source_keys.update(decision.rejected_source_keys)
            if decision.rejected_asset_ids or decision.rejected_source_keys:
                _log(
                    f"attempt {attempt}: rejected "
                    f"{len(decision.rejected_asset_ids)} asset id(s) and "
                    f"{len(decision.rejected_source_keys)} source key(s)"
                )
            repair_log["attempts"].append(attempt_entry)

            if duration_fix:
                if attempt == max_attempts:
                    status = "auto_fix_limit_reached"
                    exit_code = 20
                    repair_log["final_status"] = status
                    repair_log["final_attempt"] = attempt
                    _log("auto-fix limit reached after duration adjustment")
                    break
                _log(f"attempt {attempt}: retrying with adjusted voice timing")
                continue

            if not decision.blocking_checks:
                final_rendered_path = _adopt_final(run_dir, attempt_dir)
                _write_json(inputs_dir / "project.final.json", current_project)
                warning_count = int(report.get("summary", {}).get("warning_count") or 0)
                status = "success_with_warnings" if warning_count else "success"
                exit_code = 10 if warning_count else 0
                repair_log["final_status"] = status
                repair_log["final_attempt"] = attempt
                _log(f"final adopted from attempt {attempt}")
                break

            if not decision.can_retry:
                status = "human_review_required"
                exit_code = 30
                _append_quality_failure(failure_log, attempt, decision.blocking_checks)
                repair_log["final_status"] = status
                repair_log["final_attempt"] = attempt
                _log(f"attempt {attempt}: non-fixable quality issue")
                break

            if attempt == max_attempts:
                status = "auto_fix_limit_reached"
                exit_code = 20
                _append_quality_failure(failure_log, attempt, decision.blocking_checks)
                repair_log["final_status"] = status
                repair_log["final_attempt"] = attempt
                _log("auto-fix limit reached")
                break

            per_query, max_downloads = _next_fetch_budget(
                per_query,
                max_downloads,
                decision.blocking_checks,
                current_project,
                options,
            )
            _log(
                "attempt "
                f"{attempt}: retrying with per_query={per_query}"
                + (
                    f", max_downloads={max_downloads}"
                    if max_downloads is not None
                    else ""
                )
            )
        except Exception as exc:
            failure = classify_exception(exc)
            failure["attempt"] = attempt
            failure["action"] = (
                "record_and_stop" if not failure["recoverable"] else "retry_or_fallback"
            )
            failure_log["failures"].append(failure)
            repair_log["attempts"].append(attempt_entry)
            if not failure["recoverable"] or attempt == max_attempts:
                status = _status_from_failure(failure)
                exit_code = _exit_code_from_failure(failure)
                repair_log["final_status"] = status
                repair_log["final_attempt"] = attempt
                _log(f"attempt {attempt}: stopped with {failure['code']}")
                break

    _write_visual_assignment(
        run_dir,
        final_rendered_path or (attempts_dir / "attempt_001" / "rendered.youtube.json"),
        seed=seed,
        query_mode=options.query_mode,
        rejected_asset_ids=rejected_asset_ids,
        rejected_source_keys=rejected_source_keys,
    )
    _write_json(run_dir / "repair_log.json", repair_log)
    _write_json(run_dir / "failure_log.json", failure_log)
    return MakeVideoResult(
        exit_code=exit_code,
        status=status,
        run_dir=run_dir,
        final_rendered_path=final_rendered_path,
        plan=plan,
    )


def _validate_project(project: dict[str, Any], project_path: Path) -> None:
    schema = load_json(PROJECT_SCHEMA_PATH)
    errors = validate_json(project, schema)
    if errors:
        raise AppError(
            "project JSON validation failed.",
            location=str(project_path),
            details="\n".join(error.to_text() for error in errors),
            next_step="Fix project JSON schema errors and run make-video again.",
        )


def _build_plan(
    options: MakeVideoOptions,
    project_path: Path,
    project: dict[str, Any],
    max_attempts: int,
    seed: int,
) -> dict[str, Any]:
    return {
        "project_path": str(project_path),
        "project_id": project.get("id"),
        "queries": _queries_for_plan(project, options),
        "query_mode": options.query_mode,
        "fetch_visuals": not options.skip_fetch_visuals and not options.dry_run,
        "bgm": {
            "bgm_id": options.bgm_id,
            "default_behavior": "use_existing_default"
            if options.bgm_id is None
            else "use_bgm_id",
            "default_track_hint": "No One Here Gets In Alive - National Sweetheart",
        },
        "voice_mode": "dry-run" if options.dry_run else options.voice_mode,
        "video_mode": "dry-run" if options.dry_run else options.video_mode,
        "auto_fix": options.auto_fix,
        "max_fix_attempts": max_attempts,
        "seed": seed,
        "output_layout": "renders/<run_id>/{inputs,attempts,final,repair_log.json,failure_log.json,visual_assignment.json}",
    }


def _project_with_bgm_override(
    project: dict[str, Any], bgm_id: str | None
) -> dict[str, Any]:
    if not bgm_id:
        return project
    updated = json.loads(json.dumps(project, ensure_ascii=False))
    bgm = updated.setdefault("bgm", {})
    if isinstance(bgm, dict):
        bgm["track_id"] = bgm_id
    return updated


def _project_with_visual_keywords(
    project: dict[str, Any], options: MakeVideoOptions
) -> dict[str, Any]:
    keywords = _unique_non_empty(options.visual_keywords)
    if not keywords:
        return project

    updated = json.loads(json.dumps(project, ensure_ascii=False))
    visual_strategy = updated.setdefault("visual_strategy", {})
    if not isinstance(visual_strategy, dict):
        visual_strategy = {}
        updated["visual_strategy"] = visual_strategy

    if options.query_mode == "override":
        visual_strategy["primary_query"] = keywords[0]
        visual_strategy["fallback_queries"] = _limit_unique_queries(
            keywords[1:] or [keywords[0]], 8
        )
        script = updated.get("script", [])
        if isinstance(script, list):
            for index, item in enumerate(script):
                if isinstance(item, dict):
                    item["visual_query"] = keywords[index % len(keywords)]
        return updated

    fallback_queries = visual_strategy.get("fallback_queries", [])
    if not isinstance(fallback_queries, list):
        fallback_queries = []
    visual_strategy["fallback_queries"] = _limit_unique_queries(
        [str(query) for query in fallback_queries] + keywords, 8
    )
    return updated


def _queries_for_plan(project: dict[str, Any], options: MakeVideoOptions) -> list[str]:
    json_queries: list[str] = []
    visual_strategy = project.get("visual_strategy", {})
    if isinstance(visual_strategy, dict) and visual_strategy.get("primary_query"):
        json_queries.append(str(visual_strategy["primary_query"]))
    for item in project.get("script", []):
        if isinstance(item, dict) and item.get("visual_query"):
            json_queries.append(str(item["visual_query"]))
    if isinstance(visual_strategy, dict):
        for query in visual_strategy.get("fallback_queries", []):
            if query:
                json_queries.append(str(query))

    if options.query_mode == "override":
        return list(options.visual_keywords)
    if options.query_mode == "fallback":
        return json_queries + list(options.visual_keywords)
    return json_queries + list(options.visual_keywords)


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


def _limit_unique_queries(values: list[str], limit: int) -> list[str]:
    return _unique_non_empty(values)[:limit]


def _fetch_visuals(
    project_path: Path,
    *,
    per_query: int,
    max_downloads: int | None,
    orientation: str,
    size: str,
    additional_queries: list[str] | None = None,
) -> dict[str, Any]:
    result = fetch_visuals_for_project(
        project_path,
        client=PexelsClient(),
        output_dir=Path("assets/pexels"),
        per_query=per_query,
        max_downloads=max_downloads,
        orientation=orientation,
        size=size,
        additional_queries=additional_queries,
    )
    with connect() as connection:
        upsert_media_assets(connection, result.assets)
    return result.plan


def _render_attempt(
    options: MakeVideoOptions,
    project_path: Path,
    attempt_dir: Path,
    rejected_asset_ids: set[str],
    rejected_source_keys: set[str],
) -> Path:
    voice_service = None
    video_renderer = None
    if not options.dry_run and options.voice_mode == "aivis":
        voice_service = AivisSpeechClient(base_url=options.aivis_base_url)
    if not options.dry_run and options.video_mode == "ffmpeg":
        video_renderer = FfmpegVideoRenderer(options.ffmpeg_path)
    return render_project(
        project_path,
        voice_service=voice_service,
        video_renderer=video_renderer,
        render_dir=attempt_dir,
        rejected_asset_ids=rejected_asset_ids,
        rejected_source_keys=rejected_source_keys,
    )


def _inspect_attempt(rendered_path: Path, ffmpeg_path: str | None) -> None:
    inspect_render(rendered_path, ffmpeg_path=ffmpeg_path)


def _evaluate_attempt(rendered_path: Path, *, skip: bool) -> dict[str, Any]:
    if skip:
        return {
            "summary": {"status": "skipped", "error_count": 0, "warning_count": 0},
            "checks": [],
        }
    report = evaluate_render(rendered_path)
    report_path = rendered_path.parent / "quality_report.json"
    if not report_path.is_file():
        _write_json(report_path, report)
    return report


def _duplicate_selected_assets(visual_plan: dict[str, Any] | None) -> set[str]:
    if not visual_plan:
        return set()
    seen: set[str] = set()
    duplicates: set[str] = set()
    for query in visual_plan.get("queries", []):
        if not isinstance(query, dict):
            continue
        asset_id = str(query.get("selected_asset_id") or "").strip()
        if not asset_id:
            continue
        if asset_id in seen:
            duplicates.add(asset_id)
        seen.add(asset_id)
    return duplicates


def _duration_fix(
    project: dict[str, Any],
    checks: list[dict[str, Any]],
    config: dict[str, Any],
    options: MakeVideoOptions,
) -> dict[str, Any] | None:
    if not options.auto_fix:
        return None
    duration_config = config.get("duration", {})
    if not isinstance(duration_config, dict):
        return None
    if not duration_config.get("auto_increase_speed_for_duration"):
        return None
    duration_check = next(
        (check for check in checks if check.get("code") == "VIDEO_DURATION_TOO_LONG"),
        None,
    )
    if duration_check is None:
        return None

    updated = json.loads(json.dumps(project, ensure_ascii=False))
    voice = updated.get("voice", {})
    if not isinstance(voice, dict):
        return None
    before = {
        "speed_scale": voice.get("speed_scale"),
        "sentence_gap_ms": voice.get("sentence_gap_ms"),
    }
    speed_scale = min(2.0, round(float(voice.get("speed_scale", 1.0)) + 0.08, 2))
    gap = max(0, int(voice.get("sentence_gap_ms", 0)) - 40)
    voice["speed_scale"] = speed_scale
    voice["sentence_gap_ms"] = gap
    return {
        "project": updated,
        "log": {
            "action": "increase_voice_speed_for_duration",
            "asset_id": None,
            "reason": "VIDEO_DURATION_TOO_LONG",
            "before": before,
            "after": {
                "speed_scale": speed_scale,
                "sentence_gap_ms": gap,
            },
        },
    }


def _adopt_final(run_dir: Path, attempt_dir: Path) -> Path:
    final_dir = run_dir / "final"
    if final_dir.exists():
        shutil.rmtree(final_dir)
    shutil.copytree(attempt_dir, final_dir)
    return final_dir / "rendered.youtube.json"


def _next_run_dir(project: dict[str, Any]) -> Path:
    base_name = _render_dir_name(project, datetime.now())
    candidate = RENDERS_DIR / base_name
    if not candidate.exists():
        return candidate
    suffix = 2
    while True:
        candidate = RENDERS_DIR / f"{base_name}-{suffix}"
        if not candidate.exists():
            return candidate
        suffix += 1


def _empty_repair_log(
    project: dict[str, Any], seed: int, max_attempts: int
) -> dict[str, Any]:
    return {
        "schema_version": "repair-log-1.0.0",
        "project_id": project.get("id"),
        "seed": seed,
        "max_attempts": max_attempts,
        "final_status": "running",
        "final_attempt": None,
        "attempts": [],
    }


def _empty_failure_log() -> dict[str, Any]:
    return {"schema_version": "failure-log-1.0.0", "failures": []}


def _check_summaries(checks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "code": check.get("code"),
            "level": check.get("level"),
            "auto_fixable": bool(check.get("auto_fixable")),
            "target": check.get("target"),
        }
        for check in checks
    ]


def _append_quality_failure(
    failure_log: dict[str, Any],
    attempt: int,
    checks: list[dict[str, Any]],
) -> None:
    for check in checks:
        failure_log["failures"].append(
            {
                "category": "quality_error",
                "code": check.get("code"),
                "message": check.get("message"),
                "attempt": attempt,
                "recoverable": bool(check.get("auto_fixable")),
                "action": "human_review_required",
            }
        )


def _write_visual_assignment(
    run_dir: Path,
    rendered_path: Path,
    *,
    seed: int,
    query_mode: str,
    rejected_asset_ids: set[str],
    rejected_source_keys: set[str],
) -> None:
    assignments: list[dict[str, Any]] = []
    if rendered_path.is_file():
        rendered = load_json(rendered_path)
        for visual in rendered.get("visuals", []):
            visual_source_key = _visual_source_key(visual)
            assignments.append(
                {
                    "script_index": visual.get("script_index") or visual.get("index"),
                    "visual_query": visual.get("visual_query"),
                    "asset_id": visual.get("asset_id"),
                    "source_key": visual_source_key,
                    "source": visual.get("source"),
                    "selection_source": "fresh_pexels"
                    if visual.get("source") == "pexels"
                    else "local_stock",
                    "score": None,
                    "reason": "selected by render media selector",
                    "fallback_used": not bool(visual.get("asset_id")),
                    "rejected": visual.get("asset_id") in rejected_asset_ids
                    or visual_source_key in rejected_source_keys,
                }
            )
    _write_json(
        run_dir / "visual_assignment.json",
        {
            "schema_version": "visual-assignment-1.0.0",
            "seed": seed,
            "query_mode": query_mode,
            "assignments": assignments,
        },
    )


def _status_from_failure(failure: dict[str, Any]) -> str:
    return str(failure.get("category") or "failed")


def _exit_code_from_failure(failure: dict[str, Any]) -> int:
    return {
        "environment_error": 40,
        "external_api_error": 50,
        "render_error": 60,
        "encoding_error": 70,
    }.get(str(failure.get("category")), 60)


def _config_int(config: dict[str, Any], section: str, key: str, default: int) -> int:
    value = (
        config.get(section, {}).get(key)
        if isinstance(config.get(section), dict)
        else None
    )
    try:
        return int(value) if value is not None else default
    except (TypeError, ValueError):
        return default


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _next_fetch_budget(
    per_query: int,
    max_downloads: int | None,
    checks: list[dict[str, Any]],
    project: dict[str, Any],
    options: MakeVideoOptions,
) -> tuple[int, int | None]:
    source_related_codes = {
        "SAME_ASSET_REUSED",
        "SAME_SOURCE_REUSED",
        "SOURCE_RESOLUTION_TOO_LOW",
        "QUERY_CANDIDATE_TOO_FEW",
        "PEXELS_FETCH_FAILED",
        "PEXELS_RATE_LIMIT",
        "VISUAL_FILE_MISSING",
        "MEDIA_FILE_MISSING",
    }
    codes = {str(check.get("code") or "") for check in checks}
    if codes & source_related_codes:
        per_query = min(per_query + 2, 8)
        if max_downloads is not None:
            query_count = max(1, len(_queries_for_plan(project, options)))
            max_downloads = max(max_downloads + query_count, per_query * query_count)
        return per_query, max_downloads

    if any(bool(check.get("auto_fixable")) for check in checks):
        # Fallback for other visual retries that do not map to a source problem.
        per_query = min(per_query + 1, 8)
    return per_query, max_downloads


def _visual_source_key(visual: dict[str, Any]) -> str | None:
    source = str(visual.get("source") or "").strip().lower()
    pexels_id = str(visual.get("pexels_id") or "").strip()
    if source == "pexels" and pexels_id:
        return f"pexels:{pexels_id}"

    original_video_url = str(visual.get("original_video_url") or "").strip()
    if source == "pexels" and original_video_url:
        return f"pexels-url:{original_video_url}"

    local_path_text = str(visual.get("local_file_path") or "").strip()
    if local_path_text:
        path = Path(local_path_text)
        if path.is_file():
            try:
                return sha256_file(path)
            except OSError:
                pass
        return f"path:{local_path_text}"
    return None


def _log(message: str) -> None:
    print(f"[make-video] {message}", flush=True)
