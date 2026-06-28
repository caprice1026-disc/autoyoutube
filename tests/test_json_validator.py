from __future__ import annotations

from src.validators.json_validator import validate_json


def test_validate_json_returns_readable_error_path() -> None:
    """ネストした配列内の検証エラーが、人間に読みやすいパスで返ることを確認する。"""
    schema = {
        "type": "object",
        "required": ["items"],
        "properties": {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["name"],
                    "properties": {"name": {"type": "string"}},
                },
            }
        },
    }
    data = {"items": [{"name": "OK"}, {"name": 123}]}

    errors = validate_json(data, schema)

    assert len(errors) == 1
    assert errors[0].path == "$.items[1].name"
    assert errors[0].validator == "type"
    assert errors[0].actual == 123
