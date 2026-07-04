# Codex repair loop

Use this reference when code changes are needed after render inspection or quality checks.

## Standard repair loop

```text
1. Read quality_report.json
2. Inspect artifacts if visual or subtitle issues exist
3. Identify top errors and warnings
4. Prepare a targeted Codex repair brief
5. Apply minimal code/config changes
6. Run tests and linters
7. Re-render or re-evaluate as needed
8. Summarize remaining human-review items
```

## Repair brief template

```text
Context:
- Repository: caprice1026-disc/autoyoutube
- Rendered JSON: renders/<project_id>/rendered.youtube.json
- Quality report: renders/<project_id>/quality_report.json
- Inspect artifacts: renders/<project_id>/inspect/

Top issues:
1. <CODE> <level> <target>
   Message: <message>
   Metrics: <metrics>
   Codex hint: <codex_hint>

Required changes:
- <specific expected behavior>
- <files or modules likely involved>

Validation:
- python -m pytest -q
- python -m ruff check .
- python -m src.main validate-render renders/<project_id>/rendered.youtube.json
- python -m src.main inspect-render renders/<project_id>/rendered.youtube.json
- python -m src.main evaluate-render renders/<project_id>/rendered.youtube.json

Constraints:
- Do not add automatic upload or publishing.
- Do not commit generated media, DB, downloaded assets, BGM files, or .env.
- Preserve credits.
- Preserve manual review.
```

## Error-first policy

Treat these as blocking until fixed:

```text
FILE_MISSING
OUTPUT_VIDEO_EMPTY
VIDEO_DIMENSION_INVALID
BGM_CREDIT_MISSING
PEXELS_CREDIT_MISSING
MANUAL_REVIEW_DISABLED
```

## Warning triage

Prioritize warnings that affect viewer experience:

```text
OPENING_NO_AUDIO
AUDIO_CLIPPING
SUBTITLE_CPS_TOO_HIGH
SUBTITLE_TOO_SHORT
FONT_FALLBACK_DETECTED
SAME_ASSET_CONSECUTIVE
SOURCE_RESOLUTION_TOO_LOW
```

## Things Codex may fix

```text
- CLI wiring
- FFmpeg command construction
- subtitle wrapping defaults
- BGM volume defaults
- media selection rules
- credit generation
- quality checks
- tests and docs
```

## Things Codex should not decide alone

```text
- whether a video is factually correct
- whether a rights/license situation is safe enough to publish
- whether the final video is publishable
- whether a topic should be posted publicly
- whether to upload automatically
```
