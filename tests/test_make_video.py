from __future__ import annotations

import json
import sys
from types import SimpleNamespace
from pathlib import Path
from typing import Any

import pytest

import src.main as main_module
import src.pipeline.make_video as make_video_module
import src.pipeline.project_normalization as project_normalization_module
from src.errors import AppError
from src.pipeline.make_video import MakeVideoOptions, make_video


def _project() -> dict[str, Any]:
    return {
        "schema_version": "youtube-1.0.0",
        "platform_profile": "youtube_shorts",
        "id": "make_video_test",
        "topic": "Make video test",
        "title": "Make video test #Shorts",
        "hook": "A short hook",
        "target": {
            "duration_sec": 12,
            "aspect_ratio": "9:16",
            "resolution": {"width": 1080, "height": 1920},
            "fps": 30,
            "video_format": {
                "container": "mp4",
                "video_codec": "libx264",
                "audio_codec": "aac",
                "pix_fmt": "yuv420p",
            },
        },
        "voice": {
            "engine": "aivis_speech",
            "speaker": "Anneli",
            "speed_scale": 1.0,
            "pitch_scale": 0.0,
            "intonation_scale": 1.0,
            "sentence_gap_ms": 100,
        },
        "bgm": {
            "enabled": True,
            "strategy": "youtube_safe_bgm",
            "mood": "mysterious",
            "intensity": "low",
            "volume_db": -26,
            "fade_in_ms": 500,
            "fade_out_ms": 1200,
            "allow_sources": ["youtube_audio_library"],
            "avoid": ["vocal"],
        },
        "visual_strategy": {
            "source_priority": ["pexels", "local"],
            "preferred_orientation": "portrait",
            "fallback": "crop_landscape_to_9_16",
            "primary_query": "deep ocean",
            "fallback_queries": ["dark ocean"],
            "avoid_keywords": ["toy"],
        },
        "script": [
            {
                "index": 1,
                "text": "First sentence",
                "visual_query": "deep ocean",
                "estimated_duration_sec": 1.0,
                "caption_style_hint": "normal",
            },
            {
                "index": 2,
                "text": "Second sentence",
                "visual_query": "black submarine",
                "estimated_duration_sec": 1.0,
                "caption_style_hint": "emphasis",
            },
            {
                "index": 3,
                "text": "Third sentence",
                "visual_query": "dark ocean",
                "estimated_duration_sec": 1.0,
                "caption_style_hint": "punchline",
            },
        ],
        "youtube": {
            "title": "Make video test #Shorts",
            "description": "A short description",
            "hashtags": ["#Shorts"],
            "tags": ["test"],
            "category_hint": "education",
            "privacy_status": "private",
            "made_for_kids": False,
            "contains_synthetic_voice": True,
            "description_sections": {
                "summary": "Summary",
                "credits_policy": "include_bgm_credits_only",
                "disclaimer": "Check facts before publishing.",
            },
            "analytics_hypothesis": {
                "experiment_group": "make_video_test",
                "hypothesis": "A short test keeps viewers watching.",
                "primary_metric": "average_view_percentage",
                "secondary_metrics": ["views"],
            },
        },
        "manual_fact_check_required": True,
    }


def _write_project(tmp_path: Path) -> Path:
    project_path = tmp_path / "project.youtube.json"
    project_path.write_text(
        json.dumps(_project(), ensure_ascii=False), encoding="utf-8"
    )
    return project_path


def test_make_video_plan_only_reports_queries_without_side_effects(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    project_path = _write_project(tmp_path)
    monkeypatch.setattr(make_video_module, "RENDERS_DIR", tmp_path / "renders")

    result = make_video(
        MakeVideoOptions(
            project_path=project_path,
            visual_keywords=["glowing jellyfish"],
            query_mode="append",
            plan_only=True,
        )
    )

    assert result.exit_code == 0
    assert result.plan["project_path"] == str(project_path)
    assert result.plan["queries"] == [
        "deep ocean",
        "deep ocean",
        "black submarine",
        "dark ocean",
        "dark ocean",
        "glowing jellyfish",
    ]
    assert result.plan["bgm"]["default_track_hint"] == (
        "No One Here Gets In Alive - National Sweetheart"
    )
    assert result.run_dir is None
    assert not (tmp_path / "renders").exists()
    captured = capsys.readouterr()
    assert (
        "[make-video] plan-only: no render or external fetch will run" in captured.out
    )


def test_make_video_appends_end_cta_to_render_input_without_mutating_source(
    tmp_path: Path, monkeypatch
) -> None:
    project_path = _write_project(tmp_path)
    monkeypatch.setattr(make_video_module, "RENDERS_DIR", tmp_path / "renders")
    monkeypatch.setattr(make_video_module, "init_db", lambda: None)
    monkeypatch.setattr(
        make_video_module, "_fetch_visuals", lambda *args, **kwargs: None
    )
    monkeypatch.setattr(
        make_video_module, "_inspect_attempt", lambda *args, **kwargs: None
    )

    result = make_video(
        MakeVideoOptions(
            project_path=project_path,
            append_end_cta=True,
            dry_run=True,
            skip_fetch_visuals=True,
            skip_inspect=True,
            skip_evaluate=True,
            seed=123,
        )
    )

    assert result.exit_code == 0
    assert result.run_dir is not None
    saved_project = json.loads(
        (result.run_dir / "inputs" / "project.final.json").read_text(
            encoding="utf-8"
        )
    )
    assert saved_project["script"][-1] == {
        "index": 4,
        "text": "高評価とチャンネル登録、ぜひお願いします！",
        "visual_query": "youtube like subscribe button animation vertical",
        "estimated_duration_sec": 3.0,
        "caption_style_hint": "punchline",
    }
    assert result.plan["end_cta"] == {
        "enabled": True,
        "text": "高評価とチャンネル登録、ぜひお願いします！",
        "visual_query": "youtube like subscribe button animation vertical",
    }
    source_project = json.loads(project_path.read_text(encoding="utf-8"))
    assert len(source_project["script"]) == 3


def test_end_cta_rejects_project_at_script_item_limit() -> None:
    project = _project()
    project["script"] = project["script"] * 6

    with pytest.raises(AppError, match="end CTA"):
        project_normalization_module.project_with_end_cta(project)


def test_make_video_dry_run_writes_attempt_final_and_logs(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    project_path = _write_project(tmp_path)
    monkeypatch.setattr(make_video_module, "RENDERS_DIR", tmp_path / "renders")
    monkeypatch.setattr(make_video_module, "init_db", lambda: None)
    monkeypatch.setattr(
        make_video_module, "_fetch_visuals", lambda *args, **kwargs: None
    )
    monkeypatch.setattr(
        make_video_module, "_inspect_attempt", lambda *args, **kwargs: None
    )
    monkeypatch.setattr(
        make_video_module,
        "evaluate_render",
        lambda rendered_path: {
            "summary": {"status": "warning", "error_count": 0, "warning_count": 1},
            "checks": [
                {
                    "code": "VIDEO_DURATION_TOO_LONG",
                    "level": "warning",
                    "auto_fixable": True,
                    "target": "target.actual_duration_sec",
                    "message": "too long",
                }
            ],
        },
    )

    result = make_video(
        MakeVideoOptions(
            project_path=project_path,
            dry_run=True,
            skip_fetch_visuals=True,
            skip_inspect=True,
            skip_evaluate=False,
            seed=123,
        )
    )

    assert result.exit_code == 10
    assert result.final_rendered_path is not None
    assert result.final_rendered_path.match("*/final/rendered.youtube.json")
    run_dir = result.run_dir
    assert run_dir is not None
    assert (run_dir / "inputs" / "project.original.json").is_file()
    assert (run_dir / "inputs" / "project.attempt_001.json").is_file()
    assert (run_dir / "inputs" / "project.final.json").is_file()
    assert (run_dir / "attempts" / "attempt_001" / "rendered.youtube.json").is_file()
    assert (run_dir / "final" / "rendered.youtube.json").is_file()
    repair_log = json.loads((run_dir / "repair_log.json").read_text(encoding="utf-8"))
    assert repair_log["seed"] == 123
    assert repair_log["final_status"] == "success_with_warnings"
    assert repair_log["final_attempt"] == 1
    assert repair_log["attempts"][0]["checks"][0]["code"] == "VIDEO_DURATION_TOO_LONG"
    failure_log = json.loads((run_dir / "failure_log.json").read_text(encoding="utf-8"))
    assert failure_log["failures"] == []
    visual_assignment = json.loads(
        (run_dir / "visual_assignment.json").read_text(encoding="utf-8")
    )
    assert visual_assignment["seed"] == 123
    assert visual_assignment["keyword_extraction"]["status"] == "disabled"
    assert visual_assignment["assignments"]
    captured = capsys.readouterr()
    assert "[make-video] attempt 1 started" in captured.out
    assert "[make-video] final adopted from attempt 1" in captured.out


def test_make_video_records_generated_keyword_plan_with_selected_visual(
    tmp_path: Path, monkeypatch
) -> None:
    project_path = _write_project(tmp_path)
    enhanced = _project()
    enhanced["script"][0]["visual_query"] = "silicon wafer clean room"
    metadata = {
        "enabled": True,
        "status": "generated",
        "model": "gemini-test",
        "scene_plans": {
            "1": {
                "primary_keywords": ["silicon wafer"],
                "secondary_keywords": ["clean room"],
                "visual_intent": "silicon wafer close-up",
                "avoid_keywords": ["brand logo"],
                "search_query": "silicon wafer clean room",
            }
        },
    }
    monkeypatch.setattr(make_video_module, "RENDERS_DIR", tmp_path / "renders")
    monkeypatch.setattr(make_video_module, "init_db", lambda: None)
    monkeypatch.setattr(
        make_video_module,
        "extract_keywords_for_project",
        lambda project: SimpleNamespace(project=enhanced, metadata=metadata),
    )
    monkeypatch.setattr(make_video_module, "_fetch_visuals", lambda *args, **kwargs: {})
    monkeypatch.setattr(make_video_module, "_inspect_attempt", lambda *args: None)
    monkeypatch.setattr(
        make_video_module,
        "evaluate_render",
        lambda rendered_path: {
            "summary": {"status": "pass", "error_count": 0, "warning_count": 0},
            "checks": [],
        },
    )

    def fake_render_attempt(
        options: MakeVideoOptions,
        project_path: Path,
        attempt_dir: Path,
        rejected_asset_ids: set[str],
        rejected_source_keys: set[str],
    ) -> Path:
        attempt_dir.mkdir(parents=True, exist_ok=True)
        path = attempt_dir / "rendered.youtube.json"
        path.write_text(
            json.dumps(
                {
                    "visuals": [
                        {
                            "script_index": 1,
                            "visual_query": "silicon wafer clean room",
                            "asset_id": "pexels_1",
                            "source": "pexels",
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        return path

    monkeypatch.setattr(make_video_module, "_render_attempt", fake_render_attempt)

    result = make_video(
        MakeVideoOptions(
            project_path=project_path,
            voice_mode="dry-run",
            video_mode="dry-run",
            max_fix_attempts=1,
            skip_inspect=True,
        )
    )

    assignment = json.loads(
        (result.run_dir / "visual_assignment.json").read_text(encoding="utf-8")
    )
    assert assignment["keyword_extraction"]["status"] == "generated"
    assert assignment["assignments"][0]["keyword_plan"]["visual_intent"] == (
        "silicon wafer close-up"
    )


def test_make_video_max_attempts_env_overrides_config(
    tmp_path: Path, monkeypatch
) -> None:
    project_path = _write_project(tmp_path)
    config_path = tmp_path / "auto_repair.youtube_shorts.json"
    config_path.write_text(
        json.dumps({"repair": {"max_attempts": 2}}),
        encoding="utf-8",
    )
    monkeypatch.setenv("AUTOYOUTUBE_MAX_FIX_ATTEMPTS", "4")

    result = make_video(
        MakeVideoOptions(
            project_path=project_path,
            plan_only=True,
            config_path=config_path,
        )
    )

    assert result.plan["max_fix_attempts"] == 4


def test_make_video_retries_visual_quality_issue_with_rejected_asset(
    tmp_path: Path, monkeypatch
) -> None:
    project_path = _write_project(tmp_path)
    fetch_calls: list[tuple[int, int | None]] = []
    render_rejections: list[tuple[set[str], set[str]]] = []
    report_calls = 0
    monkeypatch.setattr(make_video_module, "RENDERS_DIR", tmp_path / "renders")
    monkeypatch.setattr(make_video_module, "init_db", lambda: None)

    def fake_fetch_visuals(
        _project_path: Path,
        *,
        per_query: int,
        max_downloads: int | None,
        orientation: str,
        size: str,
        additional_queries: list[str] | None = None,
        keyword_extraction_metadata: dict[str, Any] | None = None,
    ) -> None:
        fetch_calls.append((per_query, max_downloads))

    def fake_render_attempt(
        options: MakeVideoOptions,
        project_path: Path,
        attempt_dir: Path,
        rejected_asset_ids: set[str],
        rejected_source_keys: set[str],
    ) -> Path:
        render_rejections.append((set(rejected_asset_ids), set(rejected_source_keys)))
        attempt_dir.mkdir(parents=True, exist_ok=True)
        rendered_path = attempt_dir / "rendered.youtube.json"
        rendered_path.write_text(json.dumps({"visuals": []}), encoding="utf-8")
        return rendered_path

    def fake_evaluate(_rendered_path: Path) -> dict[str, Any]:
        nonlocal report_calls
        report_calls += 1
        if report_calls == 1:
            return {
                "summary": {"status": "warning", "error_count": 0, "warning_count": 1},
                "checks": [
                    {
                        "code": "SAME_SOURCE_REUSED",
                        "level": "warning",
                        "auto_fixable": True,
                        "target": "visuals[2]",
                        "message": "same source",
                        "metrics": {
                            "source_key": "pexels:12345",
                            "first_index": 0,
                            "current_index": 2,
                            "first_asset_id": "pexels_bad_a",
                            "current_asset_id": "pexels_bad_b",
                        },
                    }
                ],
            }
        return {
            "summary": {"status": "pass", "error_count": 0, "warning_count": 0},
            "checks": [],
        }

    monkeypatch.setattr(make_video_module, "_fetch_visuals", fake_fetch_visuals)
    monkeypatch.setattr(make_video_module, "_render_attempt", fake_render_attempt)
    monkeypatch.setattr(make_video_module, "_inspect_attempt", lambda *args: None)
    monkeypatch.setattr(make_video_module, "evaluate_render", fake_evaluate)

    result = make_video(
        MakeVideoOptions(
            project_path=project_path,
            voice_mode="dry-run",
            video_mode="dry-run",
            per_query=3,
            max_downloads=18,
            max_fix_attempts=2,
            skip_inspect=True,
        )
    )

    assert result.exit_code == 0
    assert fetch_calls == [(3, 18), (5, 25)]
    assert render_rejections == [
        (set(), set()),
        (set(), {"pexels:12345"}),
    ]
    repair_log = json.loads((result.run_dir / "repair_log.json").read_text("utf-8"))
    assert repair_log["final_attempt"] == 2
    assert repair_log["attempts"][0]["fixes"] == [
        {
            "action": "reject_asset_and_reselect",
            "asset_id": None,
            "source_key": "pexels:12345",
            "reason": "SAME_SOURCE_REUSED",
            "before": "visuals[2]",
            "after": "retry_attempt",
        }
    ]


def test_make_video_can_retry_duration_warning_when_config_allows_voice_adjustment(
    tmp_path: Path, monkeypatch
) -> None:
    project_path = _write_project(tmp_path)
    config_path = tmp_path / "auto_repair.youtube_shorts.json"
    config_path.write_text(
        json.dumps(
            {
                "repair": {"max_attempts": 2},
                "duration": {"auto_increase_speed_for_duration": True},
            }
        ),
        encoding="utf-8",
    )
    rendered_voice_settings: list[dict[str, Any]] = []
    report_calls = 0
    monkeypatch.setattr(make_video_module, "RENDERS_DIR", tmp_path / "renders")
    monkeypatch.setattr(make_video_module, "init_db", lambda: None)
    monkeypatch.setattr(make_video_module, "_fetch_visuals", lambda *args, **kwargs: {})
    monkeypatch.setattr(make_video_module, "_inspect_attempt", lambda *args: None)

    def fake_render_attempt(
        options: MakeVideoOptions,
        project_path: Path,
        attempt_dir: Path,
        rejected_asset_ids: set[str],
        rejected_source_keys: set[str],
    ) -> Path:
        project = json.loads(project_path.read_text(encoding="utf-8"))
        rendered_voice_settings.append(project["voice"])
        attempt_dir.mkdir(parents=True, exist_ok=True)
        rendered_path = attempt_dir / "rendered.youtube.json"
        rendered_path.write_text(json.dumps({"visuals": []}), encoding="utf-8")
        return rendered_path

    def fake_evaluate(_rendered_path: Path) -> dict[str, Any]:
        nonlocal report_calls
        report_calls += 1
        if report_calls == 1:
            return {
                "summary": {"status": "warning", "error_count": 0, "warning_count": 1},
                "checks": [
                    {
                        "code": "VIDEO_DURATION_TOO_LONG",
                        "level": "warning",
                        "auto_fixable": True,
                        "target": "target.actual_duration_sec",
                        "message": "too long",
                    }
                ],
            }
        return {
            "summary": {"status": "pass", "error_count": 0, "warning_count": 0},
            "checks": [],
        }

    monkeypatch.setattr(make_video_module, "_render_attempt", fake_render_attempt)
    monkeypatch.setattr(make_video_module, "evaluate_render", fake_evaluate)

    result = make_video(
        MakeVideoOptions(
            project_path=project_path,
            voice_mode="dry-run",
            video_mode="dry-run",
            config_path=config_path,
            skip_inspect=True,
        )
    )

    assert result.exit_code == 0
    assert rendered_voice_settings[0]["speed_scale"] == 1.0
    assert rendered_voice_settings[1]["speed_scale"] == 1.08
    assert rendered_voice_settings[1]["sentence_gap_ms"] == 60
    repair_log = json.loads((result.run_dir / "repair_log.json").read_text("utf-8"))
    assert repair_log["final_attempt"] == 2
    assert repair_log["attempts"][0]["fixes"] == [
        {
            "action": "increase_voice_speed_for_duration",
            "asset_id": None,
            "reason": "VIDEO_DURATION_TOO_LONG",
            "before": {"speed_scale": 1.0, "sentence_gap_ms": 100},
            "after": {"speed_scale": 1.08, "sentence_gap_ms": 60},
        }
    ]


def test_make_video_uses_cli_visual_keywords_for_actual_pexels_query_project(
    tmp_path: Path, monkeypatch
) -> None:
    project_path = _write_project(tmp_path)
    fetch_projects: list[dict[str, Any]] = []
    render_projects: list[dict[str, Any]] = []
    monkeypatch.setattr(make_video_module, "RENDERS_DIR", tmp_path / "renders")
    monkeypatch.setattr(make_video_module, "init_db", lambda: None)

    def fake_fetch_visuals(
        project_path: Path,
        *,
        per_query: int,
        max_downloads: int | None,
        orientation: str,
        size: str,
        additional_queries: list[str] | None = None,
        keyword_extraction_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        fetch_projects.append(json.loads(project_path.read_text(encoding="utf-8")))
        return {}

    def fake_render_attempt(
        options: MakeVideoOptions,
        project_path: Path,
        attempt_dir: Path,
        rejected_asset_ids: set[str],
        rejected_source_keys: set[str],
    ) -> Path:
        render_projects.append(json.loads(project_path.read_text(encoding="utf-8")))
        attempt_dir.mkdir(parents=True, exist_ok=True)
        rendered_path = attempt_dir / "rendered.youtube.json"
        rendered_path.write_text(json.dumps({"visuals": []}), encoding="utf-8")
        return rendered_path

    monkeypatch.setattr(make_video_module, "_fetch_visuals", fake_fetch_visuals)
    monkeypatch.setattr(make_video_module, "_render_attempt", fake_render_attempt)
    monkeypatch.setattr(make_video_module, "_inspect_attempt", lambda *args: None)
    monkeypatch.setattr(
        make_video_module,
        "evaluate_render",
        lambda rendered_path: {
            "summary": {"status": "pass", "error_count": 0, "warning_count": 0},
            "checks": [],
        },
    )

    result = make_video(
        MakeVideoOptions(
            project_path=project_path,
            visual_keywords=["macro metal mesh", "warm kitchen close up"],
            query_mode="override",
            voice_mode="dry-run",
            video_mode="dry-run",
            max_fix_attempts=1,
            skip_inspect=True,
        )
    )

    assert result.exit_code == 0
    assert fetch_projects
    assert render_projects
    fetch_project = fetch_projects[0]
    render_project = render_projects[0]
    assert fetch_project["visual_strategy"]["primary_query"] == "macro metal mesh"
    assert fetch_project["visual_strategy"]["fallback_queries"] == [
        "warm kitchen close up"
    ]
    assert [item["visual_query"] for item in fetch_project["script"]] == [
        "macro metal mesh",
        "warm kitchen close up",
        "macro metal mesh",
    ]
    assert render_project == fetch_project


def test_make_video_falls_back_unknown_bgm_mood_before_schema_validation(
    tmp_path: Path, monkeypatch
) -> None:
    project = _project()
    project["bgm"]["mood"] = "curious"
    project_path = tmp_path / "project.youtube.json"
    project_path.write_text(json.dumps(project, ensure_ascii=False), encoding="utf-8")
    render_projects: list[dict[str, Any]] = []
    monkeypatch.setattr(make_video_module, "RENDERS_DIR", tmp_path / "renders")
    monkeypatch.setattr(make_video_module, "init_db", lambda: None)
    monkeypatch.setattr(make_video_module, "_fetch_visuals", lambda *args, **kwargs: {})
    monkeypatch.setattr(make_video_module, "_inspect_attempt", lambda *args: None)
    monkeypatch.setattr(
        make_video_module,
        "evaluate_render",
        lambda rendered_path: {
            "summary": {"status": "pass", "error_count": 0, "warning_count": 0},
            "checks": [],
        },
    )

    def fake_render_attempt(
        options: MakeVideoOptions,
        project_path: Path,
        attempt_dir: Path,
        rejected_asset_ids: set[str],
        rejected_source_keys: set[str],
    ) -> Path:
        render_projects.append(json.loads(project_path.read_text(encoding="utf-8")))
        attempt_dir.mkdir(parents=True, exist_ok=True)
        rendered_path = attempt_dir / "rendered.youtube.json"
        rendered_path.write_text(json.dumps({"visuals": []}), encoding="utf-8")
        return rendered_path

    monkeypatch.setattr(make_video_module, "_render_attempt", fake_render_attempt)

    result = make_video(
        MakeVideoOptions(
            project_path=project_path,
            voice_mode="dry-run",
            video_mode="dry-run",
            max_fix_attempts=1,
            skip_inspect=True,
        )
    )

    assert result.exit_code == 0
    assert render_projects[0]["bgm"]["mood"] == "mysterious"


def test_make_video_caps_saved_fallback_queries_while_forwarding_all_cli_keywords(
    tmp_path: Path, monkeypatch
) -> None:
    project_path = _write_project(tmp_path)
    fetch_projects: list[dict[str, Any]] = []
    fetch_additional_queries: list[list[str] | None] = []
    monkeypatch.setattr(make_video_module, "RENDERS_DIR", tmp_path / "renders")
    monkeypatch.setattr(make_video_module, "init_db", lambda: None)

    def fake_fetch_visuals(
        project_path: Path,
        *,
        per_query: int,
        max_downloads: int | None,
        orientation: str,
        size: str,
        additional_queries: list[str] | None = None,
        keyword_extraction_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        fetch_projects.append(json.loads(project_path.read_text(encoding="utf-8")))
        fetch_additional_queries.append(additional_queries)
        return {}

    def fake_render_attempt(
        options: MakeVideoOptions,
        project_path: Path,
        attempt_dir: Path,
        rejected_asset_ids: set[str],
        rejected_source_keys: set[str],
    ) -> Path:
        attempt_dir.mkdir(parents=True, exist_ok=True)
        rendered_path = attempt_dir / "rendered.youtube.json"
        rendered_path.write_text(json.dumps({"visuals": []}), encoding="utf-8")
        return rendered_path

    monkeypatch.setattr(make_video_module, "_fetch_visuals", fake_fetch_visuals)
    monkeypatch.setattr(make_video_module, "_render_attempt", fake_render_attempt)
    monkeypatch.setattr(make_video_module, "_inspect_attempt", lambda *args: None)
    monkeypatch.setattr(
        make_video_module,
        "evaluate_render",
        lambda rendered_path: {
            "summary": {"status": "pass", "error_count": 0, "warning_count": 0},
            "checks": [],
        },
    )

    cli_keywords = [
        "macro metal mesh",
        "warm kitchen close up",
        "glass steam close up",
        "pudding spoon close up",
        "golden caramel close up",
        "custard texture close up",
        "kitchen dessert close up",
        "eggs and milk close up",
        "silky dessert close up",
    ]

    result = make_video(
        MakeVideoOptions(
            project_path=project_path,
            visual_keywords=cli_keywords,
            query_mode="append",
            voice_mode="dry-run",
            video_mode="dry-run",
            max_fix_attempts=1,
            skip_inspect=True,
        )
    )

    assert result.exit_code == 0
    assert fetch_projects
    assert fetch_additional_queries == [cli_keywords]
    saved_project = fetch_projects[0]
    assert len(saved_project["visual_strategy"]["fallback_queries"]) <= 8
    assert "macro metal mesh" in saved_project["visual_strategy"]["fallback_queries"]


def test_make_video_cli_passes_options(monkeypatch, capsys) -> None:
    calls: list[MakeVideoOptions] = []
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "tsm",
            "make-video",
            "projects/sample/project.youtube.json",
            "--video-keyword",
            "deep ocean",
            "--visual-keywords",
            "glowing jellyfish,anglerfish dark ocean",
            "--query-mode",
            "fallback",
            "--per-query",
            "4",
            "--max-downloads",
            "20",
            "--append-end-cta",
            "--plan-only",
        ],
    )

    def fake_make_video(options: MakeVideoOptions) -> make_video_module.MakeVideoResult:
        calls.append(options)
        return make_video_module.MakeVideoResult(
            exit_code=0,
            status="planned",
            run_dir=None,
            final_rendered_path=None,
            plan={"ok": True},
        )

    monkeypatch.setattr(main_module, "make_video", fake_make_video)

    exit_code = main_module.main()

    captured = capsys.readouterr()
    assert exit_code == 0
    assert calls[0].project_path == Path("projects/sample/project.youtube.json")
    assert calls[0].visual_keywords == [
        "deep ocean",
        "glowing jellyfish",
        "anglerfish dark ocean",
    ]
    assert calls[0].query_mode == "fallback"
    assert calls[0].per_query == 4
    assert calls[0].max_downloads == 20
    assert calls[0].append_end_cta is True
    assert calls[0].plan_only is True
    assert '"ok": true' in captured.out


def test_make_video_cli_uploads_when_flag_is_enabled_and_warnings_are_present(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    project_path = _write_project(tmp_path)
    rendered_path = tmp_path / "renders" / "run" / "final" / "rendered.youtube.json"
    rendered_path.parent.mkdir(parents=True, exist_ok=True)
    rendered_path.write_text("{}", encoding="utf-8")
    upload_calls: list[tuple[Path, str]] = []
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "tsm",
            "make-video",
            str(project_path),
            "--upload-youtube",
        ],
    )

    def fake_make_video(options: MakeVideoOptions) -> make_video_module.MakeVideoResult:
        return make_video_module.MakeVideoResult(
            exit_code=10,
            status="success_with_warnings",
            run_dir=tmp_path / "renders" / "run",
            final_rendered_path=rendered_path,
            plan={"ok": True},
        )

    def fake_upload_private_video(path: Path, *, privacy_status: str):
        upload_calls.append((path, privacy_status))
        return SimpleNamespace(
            video_id="video123",
            watch_url="https://www.youtube.com/watch?v=video123",
            uploaded_at="2026-07-04T00:00:00Z",
        )

    monkeypatch.setattr(main_module, "make_video", fake_make_video)
    monkeypatch.setattr(main_module, "upload_private_video", fake_upload_private_video)

    exit_code = main_module.main()

    captured = capsys.readouterr()
    assert exit_code == 10
    assert upload_calls == [(rendered_path, "private")]
    assert "[make-video] uploading final render to YouTube as private" in captured.out
    assert "YouTube upload complete: video123" in captured.out
    assert "https://www.youtube.com/watch?v=video123" in captured.out
