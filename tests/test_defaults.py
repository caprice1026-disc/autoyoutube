from __future__ import annotations


def test_defaults_expose_video_bgm_subtitle_and_quality_constants() -> None:
    import src.defaults as defaults

    assert defaults.TARGET_WIDTH == 1080
    assert defaults.TARGET_HEIGHT == 1920
    assert defaults.TARGET_ASPECT_RATIO == "9:16"
    assert defaults.TARGET_FPS == 30
    assert defaults.MAX_SHORTS_DURATION_SEC == 60.0
    assert defaults.DEFAULT_VIDEO_CODEC == "libx264"
    assert defaults.DEFAULT_AUDIO_CODEC == "aac"
    assert defaults.DEFAULT_PIX_FMT == "yuv420p"
    assert defaults.DEFAULT_CRF == 20
    assert defaults.DEFAULT_PRESET == "medium"
    assert defaults.DEFAULT_BGM_VOLUME_DB == -26
    assert defaults.DEFAULT_BGM_FADE_IN_MS == 500
    assert defaults.DEFAULT_BGM_FADE_OUT_MS == 1200
    assert defaults.DEFAULT_SUBTITLE_FONT_NAME == "Yu Gothic UI Semibold"
    assert defaults.DEFAULT_SUBTITLE_FONT_SIZE == 72
    assert defaults.DEFAULT_SUBTITLE_MARGIN_V == 220
    assert defaults.DEFAULT_NARRATION_PEAK_DBFS == -3.0
    assert defaults.MAX_SUBTITLE_CHARS == 24
    assert defaults.MIN_SUBTITLE_DURATION_SEC == 1.2
    assert defaults.MAX_SUBTITLE_CPS == 16.0
    assert defaults.MAX_SUBTITLE_LINES == 2
    assert defaults.OPENING_SILENCE_SEC == 0.5
    assert defaults.SILENCE_DBFS_THRESHOLD == -50.0
    assert defaults.AUDIO_CLIPPING_DBFS_THRESHOLD == -0.1
    assert defaults.MAX_FINAL_AUDIO_DURATION_DIFF_SEC == 0.1
    assert defaults.MIN_SOURCE_SHORT_EDGE == 720
    assert defaults.MAX_VIDEO_FILE_SIZE_MB == 200
