from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def empty_repair_log(
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


def empty_failure_log() -> dict[str, Any]:
    return {"schema_version": "failure-log-1.0.0", "failures": []}


def check_summaries(checks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "code": check.get("code"),
            "level": check.get("level"),
            "auto_fixable": bool(check.get("auto_fixable")),
            "target": check.get("target"),
        }
        for check in checks
    ]


def append_quality_failure(
    failure_log: dict[str, Any], attempt: int, checks: list[dict[str, Any]]
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


def status_from_failure(failure: dict[str, Any]) -> str:
    return str(failure.get("category") or "failed")


def exit_code_from_failure(failure: dict[str, Any]) -> int:
    return {
        "environment_error": 40,
        "external_api_error": 50,
        "render_error": 60,
        "encoding_error": 70,
    }.get(str(failure.get("category")), 60)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
