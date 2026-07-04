---
name: autoyoutube-shorts
description: Use this skill when the user wants to generate, inspect, improve, or, when explicitly requested, privately upload YouTube Shorts videos with the local autoyoutube repository. It guides project.youtube.json creation, BGM/Pexels setup, fetch-visuals, AivisSpeech/FFmpeg rendering, validate-render, inspect-render screenshots/timeline review, evaluate-render quality_report triage, Codex repair loops, and the private upload handoff.
---

# autoyoutube-shorts

Use this skill for local YouTube Shorts generation and improvement work in the `autoyoutube` repository.

## Core posture

- Treat `project.youtube.json` as the input contract.
- Treat `rendered.youtube.json`, `quality_report.json`, and `renders/<project_id>/inspect/` images as the primary evidence for repair decisions.
- Use the local CLI. Do not invent hidden services or background work.
- Keep public or automatic publishing out of scope; only do private upload when explicitly requested.
- Keep human review required before public posting.

## Assumptions

- Work from the repository root.
- Use `.\.venv\Scripts\python.exe -m src.main ...`.
- Assume `.env` already provides `PEXELS_API_KEY`.
- Assume `secrets\client_secret.json` exists for `youtube-auth`.
- Use `No One Here Gets In Alive - National Sweetheart` from `assets/bgm/bgm_manifest.json` unless the user overrides it.

## Standard workflow

1. Confirm or create `project.youtube.json`.
2. Validate project JSON.
3. Derive concrete English `visual_query` values from the script.
4. Fetch and register visual candidates with `fetch-visuals` when Pexels footage is needed.
5. Register or verify BGM if the project uses BGM.
6. Render with AivisSpeech and FFmpeg, or dry-run if the user asks for a non-real render.
7. Validate rendered JSON.
8. Run `inspect-render` to create screenshots and `timeline.png`.
9. Run `evaluate-render` to create or refresh `quality_report.json`.
10. Triage errors first, then warnings.
11. If explicitly requested, continue to private upload after review.
12. Leave final factual, rights, music, and publishing decisions to human review.

See `references/commands.md` for exact commands.

## Hard rules

Always follow `references/hard-rules.md`.

Most important rules:

- Do not commit generated videos, downloaded Pexels assets, BGM audio files, DB files, `.env`, or render outputs.
- Preserve YouTube Shorts target: 1080x1920, 9:16, MP4, H.264, AAC.
- Preserve Pexels and BGM credits.
- Preserve `manual_review.required=true` until explicit human review is recorded.
- Treat repeated visual assets and overlong renders as no-upload issues.
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
