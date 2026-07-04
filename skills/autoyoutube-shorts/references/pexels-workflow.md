# Pexels and visual workflow

Use this reference when a task involves footage selection, `fetch-visuals`, `visual_plan.json`, or multi-visual rendering.

## Query sources

`fetch-visuals` reads:

```text
visual_strategy.primary_query
script[].visual_query
visual_strategy.fallback_queries[]
```

Prefer English search queries for Pexels.

Derive those queries from the script before running `fetch-visuals`:

```text
- Use one concrete English visual_query per script item.
- Include visible nouns, locations, actions, and states.
- Avoid abstract-only queries such as "problem", "gas", or "mystery".
- Vary repeated script concepts so each cut can get a different asset.
- Put the strongest overall scene in visual_strategy.primary_query.
- Put 3-8 broader but still concrete searches in visual_strategy.fallback_queries[].
```

Examples:

```text
rainy city street night
wet asphalt neon reflection
volcano eruption ash cloud
molten lava close up
```

## Fetch command

```powershell
.\.venv\Scripts\python.exe -m src.main fetch-visuals projects\<project_id>\project.youtube.json --per-query 3 --max-downloads 20
```

Use higher `--per-query` when footage is repetitive or low quality.

## visual_plan.json

Expected output:

```text
assets/pexels/<project_id>.visual_plan.json
```

Key fields:

```text
schema_version
project_id
fetch
summary
queries[].query
queries[].script_indices
queries[].target_duration_sec
queries[].selected_asset_id
queries[].candidates[].score
queries[].candidates[].reasons
queries[].candidates[].local_file_path
queries[].candidates[].pexels_url
```

If multiple `queries[].selected_asset_id` values point to the same asset for a single project, improve the repeated `script[].visual_query` values and fetch more candidates before rendering.

Treat duplicate asset selection as a blocker for review. Do not upload if the same `asset_id` appears more than once in one render.

## Candidate score interpretation

Good signs:

```text
orientation matches portrait
meets 1080x1920 target
duration covers target script window
quality=hd / quality=uhd
credit metadata is complete
```

Risk signs:

```text
landscape crop may be aggressive
source resolution is low
duration is short for target script window
used_count penalty
```

## Render relation

The renderer uses media assets registered in SQLite. After `fetch-visuals`, run render with FFmpeg:

```powershell
.\.venv\Scripts\python.exe -m src.main render projects\<project_id>\project.youtube.json --voice-mode aivis --video-mode ffmpeg
```

When multiple visual assets are assigned to `visuals[]`, FFmpeg should generate:

```text
renders/<project_id>/video_segments/segment_001.mp4
renders/<project_id>/video_segments/segment_002.mp4
renders/<project_id>/video/background_timeline.mp4
```

Within one render, the same `asset_id` should not appear more than once in `rendered.youtube.json` `visuals[]`. If there are not enough unused registered assets, the renderer leaves that visual without an `asset_id` and lets the existing FFmpeg fallback path handle the background instead of repeating the same Pexels footage.

Duplicate check:

```powershell
$rendered = Get-Content renders\<render_dir>\rendered.youtube.json -Raw | ConvertFrom-Json
$rendered.visuals | Where-Object asset_id | Group-Object asset_id | Where-Object Count -gt 1
```

No output means no registered asset was reused in that render.

## Common improvements

If `SAME_ASSET_CONSECUTIVE` or `SAME_ASSET_REUSED` appears:

```text
- increase fetch-visuals --per-query
- adjust repeated visual_query values
- add concrete fallback_queries
- improve selector logic to avoid reuse within the whole render
```

If `SOURCE_RESOLUTION_TOO_LOW` appears:

```text
- fetch with better candidates
- avoid SD-only sources
- prefer portrait HD or UHD
```

If visual context is wrong:

```text
- rewrite visual_query values
- add fallback_queries
- make generic queries more specific
```
