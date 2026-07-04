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

## Common improvements

If `SAME_ASSET_CONSECUTIVE` appears:

```text
- increase fetch-visuals --per-query
- adjust repeated visual_query values
- improve selector logic to avoid immediate reuse
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
