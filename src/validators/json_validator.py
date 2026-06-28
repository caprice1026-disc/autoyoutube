from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import ValidationError

from src.errors import AppError


@dataclass(frozen=True)
class ValidationMessage:
    path: str
    message: str
    validator: str
    expected: Any
    actual: Any

    def to_text(self) -> str:
        return f"{self.path}: {self.message} (validator={self.validator}, expected={self.expected!r}, actual={self.actual!r})"


def load_json(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except FileNotFoundError as exc:
        raise AppError(
            "JSON file was not found.",
            location=str(path),
            next_step="Check the path and run the command again.",
        ) from exc
    except json.JSONDecodeError as exc:
        raise AppError(
            "JSON file could not be parsed.",
            location=str(path),
            details=f"line {exc.lineno}, column {exc.colno}: {exc.msg}",
            next_step="Fix the JSON syntax and run validation again.",
        ) from exc
    if not isinstance(data, dict):
        raise AppError(
            "JSON root must be an object.",
            location=str(path),
            details=f"actual type: {type(data).__name__}",
            next_step="Wrap the JSON content in an object with named fields.",
        )
    return data


def validate_json(data: dict[str, Any], schema: dict[str, Any]) -> list[ValidationMessage]:
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    return [_format_error(error) for error in sorted(validator.iter_errors(data), key=lambda item: list(item.path))]


def validate_json_file(json_path: Path, schema_path: Path) -> tuple[dict[str, Any], list[ValidationMessage]]:
    data = load_json(json_path)
    schema = load_json(schema_path)
    return data, validate_json(data, schema)


def _format_error(error: ValidationError) -> ValidationMessage:
    path = "$" + "".join(f"[{part}]" if isinstance(part, int) else f".{part}" for part in error.absolute_path)
    actual = error.instance
    expected = error.validator_value
    return ValidationMessage(path=path, message=error.message, validator=error.validator, expected=expected, actual=actual)
