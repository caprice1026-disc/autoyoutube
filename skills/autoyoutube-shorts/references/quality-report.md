# quality_report.json triage

Use `quality_report.json` as the machine-readable diagnosis for a render.

## Reading order

1. `summary.status`
2. `summary.error_count`
3. `summary.warning_count`
4. `checks[]`
5. `metrics`
6. `artifacts`

## Priority order

Fix in this order:

```text
1. error checks
2. credit and rights checks
3. audio checks
4. subtitle readability checks
5. video dimension/duration checks
6. visual asset checks
7. file-size/performance warnings
```

## Important fields

Each check may include:

```text
code
level
target
message
suggestion
metrics
auto_fixable
codex_hint
```

If `auto_fixable=true`, prefer using the `codex_hint` as part of a repair brief. If a check is not auto-fixable, summarize it for human review.

## Common checks

```text
FILE_MISSING
OUTPUT_VIDEO_EMPTY
VIDEO_DIMENSION_INVALID
VIDEO_DURATION_MISMATCH
OPENING_NO_AUDIO
AUDIO_CLIPPING
FINAL_AUDIO_DURATION_MISMATCH
BGM_CREDIT_MISSING
PEXELS_CREDIT_MISSING
SUBTITLE_TOO_LONG
SUBTITLE_TOO_MANY_LINES
SUBTITLE_CPS_TOO_HIGH
SUBTITLE_TOO_SHORT
BGM_TOO_LOUD
FFMPEG_WARNING_DETECTED
FONT_FALLBACK_DETECTED
SOURCE_RESOLUTION_TOO_LOW
SAME_ASSET_CONSECUTIVE
MANUAL_REVIEW_DISABLED
```

## Artifacts

If present, inspect these before proposing visual or subtitle fixes:

```text
artifacts.screenshot_paths
artifacts.subtitle_frame_paths
artifacts.timeline_png_path
```

## Repair brief format

When producing a Codex repair brief, include:

```text
Context:
  rendered path
  quality report path
  inspect artifact paths

Top issues:
  code, level, target, message

Required fixes:
  concrete code areas and expected behavior

Validation:
  pytest
  ruff
  validate-render
  inspect-render
  evaluate-render

Constraints:
  no generated files committed
  no auto upload
  preserve credits
  preserve manual review
```
