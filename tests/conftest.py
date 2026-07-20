from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def isolate_optional_llm_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep CLI tests from leaking repository .env into unrelated fixtures."""

    for key in (
        "ENABLE_LLM_KEYWORD_EXTRACTION",
        "GEMINI_API_KEY",
        "GEMINI_MODEL",
    ):
        monkeypatch.delenv(key, raising=False)
