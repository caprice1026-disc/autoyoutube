from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT_DIR = Path(__file__).resolve().parent.parent
PROJECT_SCHEMA_PATH = ROOT_DIR / "schemas" / "project.youtube.schema.json"
RENDERED_SCHEMA_PATH = ROOT_DIR / "schemas" / "rendered.youtube.schema.json"
SAMPLE_PROJECT_PATH = ROOT_DIR / "projects" / "trivia_submarine_black_001" / "project.youtube.json"


def _load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as file:
        return json.load(file)


def test_youtube_schema_files_are_valid_draft_2020_12() -> None:
    """YouTube用JSON Schema自体がDraft 2020-12として有効であることを確認する。"""
    for schema_path in [PROJECT_SCHEMA_PATH, RENDERED_SCHEMA_PATH]:
        Draft202012Validator.check_schema(_load_json(schema_path))


def test_sample_project_matches_project_schema() -> None:
    """同梱サンプルのproject.youtube.jsonが整形済みスキーマで検証できることを確認する。"""
    schema = _load_json(PROJECT_SCHEMA_PATH)
    project = _load_json(SAMPLE_PROJECT_PATH)

    Draft202012Validator(schema).validate(project)


def test_project_schema_rejects_unexpected_property() -> None:
    """additionalProperties=falseの制約が期待どおり余分な項目を拒否することを確認する。"""
    schema = _load_json(PROJECT_SCHEMA_PATH)
    project = _load_json(SAMPLE_PROJECT_PATH)
    project["unexpected_field"] = "許可されていない項目です"

    errors = list(Draft202012Validator(schema).iter_errors(project))

    assert errors
    assert any(error.validator == "additionalProperties" for error in errors)
