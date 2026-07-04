# Visual inspection

Use inspection images when improving subtitle position, readability, brightness, or render timing.

## Files

`inspect-render` writes:

```text
renders/<project_id>/inspect/opening.png
renders/<project_id>/inspect/middle.png
renders/<project_id>/inspect/ending.png
renders/<project_id>/inspect/subtitle_001.png
renders/<project_id>/inspect/subtitle_002.png
renders/<project_id>/inspect/timeline.png
```

## Review opening/middle/ending

Look for:

```text
- black or meaningless opening frame
- too-dark footage
- too-bright footage that weakens white subtitles
- wrong crop or stretched source footage
- visually repetitive footage
```

## Review subtitle frames

Look for:

```text
- text hidden by UI-safe area
- text too low
- text too large
- outline too weak
- 3 or more lines on screen
- white text blending into bright background
- long subtitles that are hard to read quickly
```

## Review timeline.png

Timeline panels:

```text
Top: frame strip sampled across the video
Middle: audio waveform from final_audio.wav
Bottom: subtitle timing blocks
```

Look for:

```text
- long silent opening
- very dense subtitle blocks
- CPS warning concentration
- scene changes that do not match narration timing
- ending audio or subtitle cut-off
```

## Suggested fixes

For subtitle readability:

```text
- reduce font size slightly
- increase outline
- increase vertical margin if text is too low
- split long script items
- lower MAX_SUBTITLE_CHARS
```

For footage issues:

```text
- run fetch-visuals with higher --per-query
- change visual_query to be more specific
- prefer portrait source footage
- avoid repeated asset IDs
- replace low-resolution media
```

For timing issues:

```text
- adjust sentence_gap_ms
- split or merge script items
- check final_audio.wav duration
- check segment durations in visuals[]
```
