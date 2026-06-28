from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import ValidationError


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
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, dict):
        raise ValueError(f"JSONのルートはobjectである必要があります: {path}")
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
