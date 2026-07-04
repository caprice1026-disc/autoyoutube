from __future__ import annotations

from pathlib import Path


SKILL_ROOT = Path("skills/autoyoutube-shorts")


def test_autoyoutube_skill_has_required_entrypoints() -> None:
    assert (SKILL_ROOT / "SKILL.md").is_file()
    assert (SKILL_ROOT / "agents" / "openai.yaml").is_file()


def test_autoyoutube_skill_frontmatter_declares_name_and_description() -> None:
    content = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")

    assert content.startswith("---\n")
    assert "name: autoyoutube-shorts" in content
    assert "description:" in content
    assert "# autoyoutube-shorts" in content


def test_autoyoutube_skill_references_exist() -> None:
    references = [
        "commands.md",
        "hard-rules.md",
        "quality-report.md",
        "visual-inspection.md",
        "pexels-workflow.md",
        "codex-repair-loop.md",
    ]

    for filename in references:
        path = SKILL_ROOT / "references" / filename
        assert path.is_file(), f"missing skill reference: {filename}"
        assert path.read_text(encoding="utf-8").strip(), f"empty skill reference: {filename}"
