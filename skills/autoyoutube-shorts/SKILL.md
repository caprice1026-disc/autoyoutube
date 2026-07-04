---
name: autoyoutube-shorts
description: Use this skill when the user wants to generate, inspect, or improve YouTube Shorts videos with the local autoyoutube repository. It guides project.youtube.json creation, BGM/Pexels setup, fetch-visuals, AivisSpeech/FFmpeg rendering, validate-render, inspect-render screenshots/timeline review, evaluate-render quality_report triage, and Codex repair loops. It assumes local execution, no automatic upload, and human review before publishing.
---

# autoyoutube-shorts

Use this skill for local YouTube Shorts generation and improvement work in the `autoyoutube` repository.

## Core posture

- Treat `project.youtube.json` as the input contract.
- Treat `rendered.youtube.json`, `quality_report.json`, and `renders/<project_id>/inspect/` images as the primary evidence for repair decisions.
- Use the local CLI. Do not invent hidden services or background work.
- Keep automatic publishing out of scope unless the user explicitly asks for it.
- Keep human review required before public posting.

## Standard workflow

1. Confirm or create `project.youtube.json`.
2. Validate project JSON.
3. Fetch visual candidates with `fetch-visuals` when Pexels footage is needed.
4. Register or verify BGM if the project uses BGM.
5. Render with AivisSpeech and FFmpeg, or dry-run if the user asks for a non-real render.
6. Validate rendered JSON.
7. Run `inspect-render` to create screenshots and `timeline.png`.
8. Run `evaluate-render` to create or refresh `quality_report.json`.
9. Triage errors first, then warnings.
10. Produce a Codex repair brief when code changes are needed.
11. Leave final factual, rights, music, and publishing decisions to human review.

See `references/commands.md` for exact commands.

## Hard rules

Always follow `references/hard-rules.md`.

Most important rules:

- Do not commit generated videos, downloaded Pexels assets, BGM audio files, DB files, `.env`, or render outputs.
- Preserve YouTube Shorts target: 1080x1920, 9:16, MP4, H.264, AAC.
- Preserve Pexels and BGM credits.
- Preserve `manual_review.required=true` until explicit human review is recorded.
- Prefer targeted fixes over broad refactors.

## When to load references

- Commands and local workflow: `references/commands.md`
- Guardrails and forbidden changes: `references/hard-rules.md`
- `quality_report.json` triage: `references/quality-report.md`
- Screenshots and timeline review: `references/visual-inspection.md`
- Pexels and `visual_plan.json`: `references/pexels-workflow.md`
- Codex repair prompts: `references/codex-repair-loop.md`

## Repair loop

When asked to improve a render, use this order:

1. Read `quality_report.json`.
2. Review `artifacts.screenshot_paths`, `artifacts.subtitle_frame_paths`, and `artifacts.timeline_png_path` if present.
3. Fix `error` checks before `warning` checks.
4. Prefer checks with `auto_fixable=true` and useful `codex_hint`.
5. Re-run relevant tests, render, inspect, and evaluate.
6. Summarize what changed and what still needs human judgment.
