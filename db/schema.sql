-- ============================================================
-- trivia-shorts-maker SQLite schema
-- YouTube Shorts特化版
--
-- 対応:
--   - project.youtube.schema.json
--   - rendered.youtube.schema.json
--
-- 方針:
--   1. project_json / rendered_json は原本として保存
--   2. 検索・分析・再利用したい項目だけテーブル化
--   3. SQLiteなので boolean は INTEGER 0/1 で扱う
--   4. 配列は必要に応じてJSON文字列として保存
-- ============================================================

PRAGMA foreign_keys = ON;

-- ============================================================
-- 1. ChatGPTが出力した project.youtube.json の管理
-- ============================================================

CREATE TABLE IF NOT EXISTS youtube_projects (
    id TEXT PRIMARY KEY,

    schema_version TEXT NOT NULL DEFAULT 'youtube-1.0.0',
    platform_profile TEXT NOT NULL DEFAULT 'youtube_shorts',

    topic TEXT NOT NULL,
    internal_title TEXT NOT NULL,
    hook TEXT NOT NULL,

    -- 元JSONの保存場所とハッシュ
    project_json_path TEXT NOT NULL,
    project_json_hash TEXT,
    raw_project_json TEXT,

    -- target
    planned_duration_sec REAL NOT NULL,
    aspect_ratio TEXT NOT NULL DEFAULT '9:16',
    width INTEGER NOT NULL DEFAULT 1080,
    height INTEGER NOT NULL DEFAULT 1920,
    fps INTEGER NOT NULL DEFAULT 30,
    container TEXT NOT NULL DEFAULT 'mp4',
    video_codec TEXT NOT NULL DEFAULT 'libx264',
    audio_codec TEXT NOT NULL DEFAULT 'aac',
    pix_fmt TEXT NOT NULL DEFAULT 'yuv420p',

    -- voice
    voice_engine TEXT NOT NULL DEFAULT 'aivis_speech',
    voice_speaker TEXT NOT NULL,
    voice_speed_scale REAL NOT NULL DEFAULT 1.0,
    voice_pitch_scale REAL NOT NULL DEFAULT 0.0,
    voice_intonation_scale REAL NOT NULL DEFAULT 1.0,
    voice_sentence_gap_ms INTEGER NOT NULL DEFAULT 180,

    -- fact check / production
    manual_fact_check_required INTEGER NOT NULL DEFAULT 1,
    fact_check_notes TEXT,
    production_notes TEXT,

    status TEXT NOT NULL DEFAULT 'draft',

    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CHECK (platform_profile = 'youtube_shorts'),
    CHECK (aspect_ratio = '9:16'),
    CHECK (width = 1080),
    CHECK (height = 1920),
    CHECK (fps IN (24, 30, 60)),
    CHECK (container = 'mp4'),
    CHECK (video_codec IN ('libx264', 'h264_nvenc')),
    CHECK (audio_codec = 'aac'),
    CHECK (pix_fmt = 'yuv420p'),
    CHECK (voice_engine = 'aivis_speech'),
    CHECK (manual_fact_check_required IN (0, 1)),
    CHECK (status IN (
        'draft',
        'validated',
        'rendering',
        'rendered',
        'reviewing',
        'ready_to_upload',
        'uploaded',
        'failed',
        'archived'
    ))
);

CREATE INDEX IF NOT EXISTS idx_youtube_projects_status
ON youtube_projects(status);

CREATE INDEX IF NOT EXISTS idx_youtube_projects_topic
ON youtube_projects(topic);

CREATE INDEX IF NOT EXISTS idx_youtube_projects_created_at
ON youtube_projects(created_at);


-- ============================================================
-- 2. project.youtube.json の script[]
-- 文ごとにAivisSpeech音声・字幕・Pexels検索へ使う
-- ============================================================

CREATE TABLE IF NOT EXISTS project_script_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    project_id TEXT NOT NULL,
    item_index INTEGER NOT NULL,

    text TEXT NOT NULL,
    visual_query TEXT NOT NULL,
    estimated_duration_sec REAL NOT NULL,
    caption_style_hint TEXT NOT NULL DEFAULT 'normal',

    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (project_id)
        REFERENCES youtube_projects(id)
        ON DELETE CASCADE,

    UNIQUE (project_id, item_index),

    CHECK (item_index >= 1),
    CHECK (estimated_duration_sec > 0),
    CHECK (caption_style_hint IN (
        'normal',
        'emphasis',
        'question',
        'punchline'
    ))
);

CREATE INDEX IF NOT EXISTS idx_project_script_items_project_id
ON project_script_items(project_id);


-- ============================================================
-- 3. project.youtube.json の bgm
-- YouTube Audio Library / local safe bgm 用
-- ============================================================

CREATE TABLE IF NOT EXISTS project_bgm_plans (
    project_id TEXT PRIMARY KEY,

    enabled INTEGER NOT NULL DEFAULT 1,
    strategy TEXT NOT NULL DEFAULT 'youtube_safe_bgm',

    mood TEXT NOT NULL,
    intensity TEXT NOT NULL,

    volume_db REAL NOT NULL DEFAULT -26,
    fade_in_ms INTEGER NOT NULL DEFAULT 500,
    fade_out_ms INTEGER NOT NULL DEFAULT 1200,

    -- JSON配列文字列として保存
    allow_sources_json TEXT NOT NULL,
    avoid_json TEXT NOT NULL,

    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (project_id)
        REFERENCES youtube_projects(id)
        ON DELETE CASCADE,

    CHECK (enabled IN (0, 1)),
    CHECK (strategy IN (
        'youtube_safe_bgm',
        'local_safe_bgm',
        'none'
    )),
    CHECK (mood IN (
        'none',
        'calm',
        'light',
        'pop',
        'tech',
        'minimal',
        'mysterious',
        'tension_low',
        'dark',
        'ambient'
    )),
    CHECK (intensity IN (
        'none',
        'low',
        'medium'
    )),
    CHECK (volume_db BETWEEN -40 AND -12),
    CHECK (fade_in_ms BETWEEN 0 AND 3000),
    CHECK (fade_out_ms BETWEEN 0 AND 5000)
);


-- ============================================================
-- 4. project.youtube.json の visual_strategy
-- Pexels素材検索戦略
-- ============================================================

CREATE TABLE IF NOT EXISTS project_visual_strategies (
    project_id TEXT PRIMARY KEY,

    -- JSON配列文字列: ["pexels", "local"]
    source_priority_json TEXT NOT NULL,

    preferred_orientation TEXT NOT NULL DEFAULT 'portrait',
    fallback TEXT NOT NULL DEFAULT 'crop_landscape_to_9_16',

    primary_query TEXT NOT NULL,

    -- JSON配列文字列
    fallback_queries_json TEXT NOT NULL,
    avoid_keywords_json TEXT NOT NULL,

    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (project_id)
        REFERENCES youtube_projects(id)
        ON DELETE CASCADE,

    CHECK (preferred_orientation = 'portrait'),
    CHECK (fallback IN (
        'crop_landscape_to_9_16',
        'blur_background_with_center_crop'
    ))
);


-- ============================================================
-- 5. YouTube投稿メタ情報
-- project.youtube.json の youtube
-- ============================================================

CREATE TABLE IF NOT EXISTS project_youtube_metadata (
    project_id TEXT PRIMARY KEY,

    youtube_title TEXT NOT NULL,
    youtube_description TEXT NOT NULL,

    -- JSON配列文字列
    hashtags_json TEXT NOT NULL,
    tags_json TEXT NOT NULL,

    category_hint TEXT NOT NULL DEFAULT 'education',
    privacy_status TEXT NOT NULL DEFAULT 'private',

    made_for_kids INTEGER NOT NULL DEFAULT 0,
    contains_synthetic_voice INTEGER NOT NULL DEFAULT 1,

    description_summary TEXT,
    credits_policy TEXT NOT NULL DEFAULT 'include_pexels_and_bgm_credits',
    disclaimer TEXT,

    -- 分析仮説
    experiment_group TEXT NOT NULL,
    hypothesis TEXT NOT NULL,
    primary_metric TEXT NOT NULL DEFAULT 'average_view_percentage',
    secondary_metrics_json TEXT NOT NULL,

    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (project_id)
        REFERENCES youtube_projects(id)
        ON DELETE CASCADE,

    CHECK (category_hint IN (
        'education',
        'science_and_technology',
        'entertainment',
        'people_and_blogs',
        'gaming',
        'news_and_politics'
    )),
    CHECK (privacy_status IN (
        'private',
        'unlisted',
        'public'
    )),
    CHECK (made_for_kids IN (0, 1)),
    CHECK (contains_synthetic_voice = 1),
    CHECK (credits_policy IN (
        'include_pexels_and_bgm_credits',
        'include_bgm_credits_only',
        'include_pexels_credits_only',
        'none'
    )),
    CHECK (primary_metric IN (
        'views',
        'engaged_views',
        'average_view_percentage',
        'average_view_duration',
        'likes_per_view',
        'subscribers_gained'
    ))
);

CREATE INDEX IF NOT EXISTS idx_project_youtube_metadata_experiment_group
ON project_youtube_metadata(experiment_group);


-- ============================================================
-- 6. レンダリング結果 rendered.youtube.json の親テーブル
-- 1つのprojectから複数回renderできる想定
-- ============================================================

CREATE TABLE IF NOT EXISTS youtube_renders (
    render_id TEXT PRIMARY KEY,

    project_id TEXT NOT NULL,

    schema_version TEXT NOT NULL DEFAULT 'rendered-youtube-1.0.0',
    platform_profile TEXT NOT NULL DEFAULT 'youtube_shorts',

    status TEXT NOT NULL,

    created_at TEXT NOT NULL,
    completed_at TEXT,

    -- input
    project_json_path TEXT NOT NULL,
    project_json_hash TEXT NOT NULL,
    project_schema_path TEXT NOT NULL,

    -- output
    video_path TEXT NOT NULL,
    thumbnail_path TEXT,
    subtitle_ass_path TEXT NOT NULL,
    description_path TEXT NOT NULL,
    credits_path TEXT NOT NULL,
    rendered_json_path TEXT NOT NULL,
    logs_dir TEXT,

    raw_rendered_json TEXT,

    -- target
    planned_duration_sec REAL NOT NULL,
    actual_duration_sec REAL,
    aspect_ratio TEXT NOT NULL DEFAULT '9:16',
    width INTEGER NOT NULL DEFAULT 1080,
    height INTEGER NOT NULL DEFAULT 1920,
    fps INTEGER NOT NULL DEFAULT 30,

    container TEXT NOT NULL DEFAULT 'mp4',
    video_codec TEXT NOT NULL DEFAULT 'libx264',
    audio_codec TEXT NOT NULL DEFAULT 'aac',
    pix_fmt TEXT NOT NULL DEFAULT 'yuv420p',

    FOREIGN KEY (project_id)
        REFERENCES youtube_projects(id)
        ON DELETE CASCADE,

    CHECK (platform_profile = 'youtube_shorts'),
    CHECK (status IN (
        'success',
        'partial_success',
        'failed'
    )),
    CHECK (aspect_ratio = '9:16'),
    CHECK (width = 1080),
    CHECK (height = 1920),
    CHECK (fps IN (24, 30, 60)),
    CHECK (container = 'mp4'),
    CHECK (video_codec IN ('libx264', 'h264_nvenc')),
    CHECK (audio_codec = 'aac'),
    CHECK (pix_fmt = 'yuv420p')
);

CREATE INDEX IF NOT EXISTS idx_youtube_renders_project_id
ON youtube_renders(project_id);

CREATE INDEX IF NOT EXISTS idx_youtube_renders_status
ON youtube_renders(status);

CREATE INDEX IF NOT EXISTS idx_youtube_renders_created_at
ON youtube_renders(created_at);


-- ============================================================
-- 7. rendered.voice
-- 実際に使ったAivisSpeech設定
-- ============================================================

CREATE TABLE IF NOT EXISTS render_voice_settings (
    render_id TEXT PRIMARY KEY,

    engine TEXT NOT NULL DEFAULT 'aivis_speech',
    speaker TEXT NOT NULL,

    speed_scale REAL NOT NULL,
    pitch_scale REAL NOT NULL,
    intonation_scale REAL NOT NULL,
    sentence_gap_ms INTEGER NOT NULL,

    sample_rate INTEGER NOT NULL,
    audio_format TEXT NOT NULL DEFAULT 'wav',

    FOREIGN KEY (render_id)
        REFERENCES youtube_renders(render_id)
        ON DELETE CASCADE,

    CHECK (engine = 'aivis_speech'),
    CHECK (speed_scale BETWEEN 0.5 AND 2.0),
    CHECK (pitch_scale BETWEEN -0.15 AND 0.15),
    CHECK (intonation_scale BETWEEN 0.0 AND 2.0),
    CHECK (sentence_gap_ms BETWEEN 0 AND 1000),
    CHECK (sample_rate BETWEEN 8000 AND 96000),
    CHECK (audio_format = 'wav')
);


-- ============================================================
-- 8. rendered.audio
-- 文ごとの音声ファイル
-- ============================================================

CREATE TABLE IF NOT EXISTS render_narration_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    render_id TEXT NOT NULL,
    item_index INTEGER NOT NULL,

    text TEXT NOT NULL,
    path TEXT NOT NULL,

    estimated_duration_sec REAL NOT NULL,
    actual_duration_sec REAL NOT NULL,

    start_sec REAL NOT NULL,
    end_sec REAL NOT NULL,

    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (render_id)
        REFERENCES youtube_renders(render_id)
        ON DELETE CASCADE,

    UNIQUE (render_id, item_index),

    CHECK (item_index >= 1),
    CHECK (estimated_duration_sec > 0),
    CHECK (actual_duration_sec > 0),
    CHECK (start_sec >= 0),
    CHECK (end_sec >= 0)
);

CREATE INDEX IF NOT EXISTS idx_render_narration_files_render_id
ON render_narration_files(render_id);


CREATE TABLE IF NOT EXISTS render_audio_outputs (
    render_id TEXT PRIMARY KEY,

    merged_narration_path TEXT NOT NULL,
    merged_narration_duration_sec REAL NOT NULL,

    final_audio_path TEXT NOT NULL,
    final_audio_duration_sec REAL NOT NULL,

    loudness_normalization_enabled INTEGER NOT NULL DEFAULT 0,
    target_i_lufs REAL,
    target_tp_db REAL,
    target_lra REAL,

    FOREIGN KEY (render_id)
        REFERENCES youtube_renders(render_id)
        ON DELETE CASCADE,

    CHECK (merged_narration_duration_sec > 0),
    CHECK (final_audio_duration_sec > 0),
    CHECK (loudness_normalization_enabled IN (0, 1))
);


-- ============================================================
-- 9. BGMライブラリ
-- YouTube Audio Library / local_original / pixabay
-- 実体の曲メタデータを管理する
-- ============================================================

CREATE TABLE IF NOT EXISTS bgm_tracks (
    track_id TEXT PRIMARY KEY,

    file_path TEXT NOT NULL,
    title TEXT,
    artist TEXT,

    source TEXT NOT NULL,
    license_type TEXT,
    attribution_required INTEGER NOT NULL DEFAULT 0,
    attribution_text TEXT,

    mood TEXT,
    intensity TEXT,

    duration_sec REAL,
    bpm REAL,
    loopable INTEGER NOT NULL DEFAULT 0,

    allowed_platforms_json TEXT NOT NULL DEFAULT '["youtube_shorts"]',

    used_count INTEGER NOT NULL DEFAULT 0,
    last_used_at TEXT,

    is_active INTEGER NOT NULL DEFAULT 1,

    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CHECK (source IN (
        'youtube_audio_library',
        'local_original',
        'pixabay'
    )),
    CHECK (attribution_required IN (0, 1)),
    CHECK (loopable IN (0, 1)),
    CHECK (is_active IN (0, 1))
);

CREATE INDEX IF NOT EXISTS idx_bgm_tracks_source
ON bgm_tracks(source);

CREATE INDEX IF NOT EXISTS idx_bgm_tracks_mood_intensity
ON bgm_tracks(mood, intensity);

CREATE INDEX IF NOT EXISTS idx_bgm_tracks_used_count
ON bgm_tracks(used_count);


-- ============================================================
-- 10. rendered.bgm
-- 実際にそのrenderで使ったBGM
-- ============================================================

CREATE TABLE IF NOT EXISTS render_bgm_usage (
    render_id TEXT PRIMARY KEY,

    enabled INTEGER NOT NULL,

    strategy TEXT,
    track_id TEXT,
    file_path TEXT,

    title TEXT,
    artist TEXT,
    source TEXT,
    license_type TEXT,

    attribution_required INTEGER,
    attribution_text TEXT,

    mood TEXT,
    intensity TEXT,

    volume_db REAL,
    fade_in_ms INTEGER,
    fade_out_ms INTEGER,

    looped INTEGER,
    used_start_sec REAL,
    used_duration_sec REAL,

    FOREIGN KEY (render_id)
        REFERENCES youtube_renders(render_id)
        ON DELETE CASCADE,

    FOREIGN KEY (track_id)
        REFERENCES bgm_tracks(track_id)
        ON DELETE SET NULL,

    CHECK (enabled IN (0, 1)),
    CHECK (strategy IS NULL OR strategy IN (
        'youtube_safe_bgm',
        'local_safe_bgm',
        'none'
    )),
    CHECK (source IS NULL OR source IN (
        'youtube_audio_library',
        'local_original',
        'pixabay',
        'none'
    )),
    CHECK (attribution_required IS NULL OR attribution_required IN (0, 1)),
    CHECK (looped IS NULL OR looped IN (0, 1))
);


-- ============================================================
-- 11. Pexels / local 素材キャッシュ
-- projectとは独立して素材台帳として持つ
-- ============================================================

CREATE TABLE IF NOT EXISTS media_assets (
    asset_id TEXT PRIMARY KEY,

    source TEXT NOT NULL,

    -- Pexelsの場合
    pexels_id TEXT,
    photographer TEXT,
    photographer_url TEXT,
    pexels_url TEXT,
    original_video_url TEXT,

    -- local共通
    local_file_path TEXT NOT NULL,

    original_width INTEGER,
    original_height INTEGER,
    original_duration_sec REAL,
    orientation TEXT,
    selected_quality TEXT,

    -- 取得・検索情報
    query TEXT,
    tags_json TEXT,

    used_count INTEGER NOT NULL DEFAULT 0,
    last_used_at TEXT,

    is_active INTEGER NOT NULL DEFAULT 1,
    is_low_quality INTEGER NOT NULL DEFAULT 0,
    notes TEXT,

    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CHECK (source IN ('pexels', 'local')),
    CHECK (orientation IS NULL OR orientation IN (
        'portrait',
        'landscape',
        'square',
        'unknown'
    )),
    CHECK (selected_quality IS NULL OR selected_quality IN (
        'sd',
        'hd',
        'uhd',
        'original',
        'unknown'
    )),
    CHECK (is_active IN (0, 1)),
    CHECK (is_low_quality IN (0, 1))
);

CREATE INDEX IF NOT EXISTS idx_media_assets_source
ON media_assets(source);

CREATE INDEX IF NOT EXISTS idx_media_assets_pexels_id
ON media_assets(pexels_id);

CREATE INDEX IF NOT EXISTS idx_media_assets_query
ON media_assets(query);

CREATE INDEX IF NOT EXISTS idx_media_assets_used_count
ON media_assets(used_count);


-- ============================================================
-- 12. rendered.visuals[]
-- 実際に動画内で使った素材とクロップ情報
-- ============================================================

CREATE TABLE IF NOT EXISTS render_visual_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    render_id TEXT NOT NULL,

    item_index INTEGER NOT NULL,
    script_index INTEGER NOT NULL,

    visual_query TEXT NOT NULL,

    source TEXT NOT NULL,
    asset_id TEXT,

    pexels_id TEXT,
    photographer TEXT,
    photographer_url TEXT,
    pexels_url TEXT,
    original_video_url TEXT,

    local_file_path TEXT NOT NULL,

    original_width INTEGER NOT NULL,
    original_height INTEGER NOT NULL,
    original_duration_sec REAL NOT NULL,

    orientation TEXT NOT NULL,
    selected_quality TEXT NOT NULL,

    transform_type TEXT NOT NULL,

    crop_x INTEGER,
    crop_y INTEGER,
    crop_width INTEGER,
    crop_height INTEGER,

    scale_width INTEGER NOT NULL DEFAULT 1080,
    scale_height INTEGER NOT NULL DEFAULT 1920,

    used_start_sec REAL NOT NULL,
    used_duration_sec REAL NOT NULL,

    video_start_sec REAL NOT NULL,
    video_end_sec REAL NOT NULL,

    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (render_id)
        REFERENCES youtube_renders(render_id)
        ON DELETE CASCADE,

    FOREIGN KEY (asset_id)
        REFERENCES media_assets(asset_id)
        ON DELETE SET NULL,

    UNIQUE (render_id, item_index),

    CHECK (item_index >= 1),
    CHECK (script_index >= 1),
    CHECK (source IN ('pexels', 'local')),
    CHECK (orientation IN (
        'portrait',
        'landscape',
        'square',
        'unknown'
    )),
    CHECK (selected_quality IN (
        'sd',
        'hd',
        'uhd',
        'original',
        'unknown'
    )),
    CHECK (transform_type IN (
        'none',
        'crop_landscape_to_9_16',
        'blur_background_with_center_crop'
    )),
    CHECK (scale_width = 1080),
    CHECK (scale_height = 1920),
    CHECK (used_start_sec >= 0),
    CHECK (used_duration_sec > 0),
    CHECK (video_start_sec >= 0),
    CHECK (video_end_sec >= 0)
);

CREATE INDEX IF NOT EXISTS idx_render_visual_items_render_id
ON render_visual_items(render_id);

CREATE INDEX IF NOT EXISTS idx_render_visual_items_asset_id
ON render_visual_items(asset_id);

CREATE INDEX IF NOT EXISTS idx_render_visual_items_script_index
ON render_visual_items(script_index);


-- ============================================================
-- 13. rendered.subtitles
-- ASS字幕のスタイルと文ごとの字幕
-- ============================================================

CREATE TABLE IF NOT EXISTS render_subtitle_styles (
    render_id TEXT PRIMARY KEY,

    format TEXT NOT NULL DEFAULT 'ass',

    font_name TEXT NOT NULL,
    font_size INTEGER NOT NULL,

    primary_color TEXT NOT NULL,
    outline_color TEXT NOT NULL,

    outline INTEGER NOT NULL,
    shadow INTEGER NOT NULL,

    alignment TEXT NOT NULL,
    margin_v INTEGER NOT NULL,

    FOREIGN KEY (render_id)
        REFERENCES youtube_renders(render_id)
        ON DELETE CASCADE,

    CHECK (format = 'ass'),
    CHECK (font_size BETWEEN 10 AND 200),
    CHECK (alignment IN (
        'top_center',
        'middle_center',
        'bottom_center'
    ))
);


CREATE TABLE IF NOT EXISTS render_subtitle_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    render_id TEXT NOT NULL,
    item_index INTEGER NOT NULL,

    text TEXT NOT NULL,
    start_sec REAL NOT NULL,
    end_sec REAL NOT NULL,

    caption_style_hint TEXT NOT NULL DEFAULT 'normal',

    FOREIGN KEY (render_id)
        REFERENCES youtube_renders(render_id)
        ON DELETE CASCADE,

    UNIQUE (render_id, item_index),

    CHECK (item_index >= 1),
    CHECK (start_sec >= 0),
    CHECK (end_sec >= 0),
    CHECK (caption_style_hint IN (
        'normal',
        'emphasis',
        'question',
        'punchline'
    ))
);

CREATE INDEX IF NOT EXISTS idx_render_subtitle_items_render_id
ON render_subtitle_items(render_id);


-- ============================================================
-- 14. rendered.youtube
-- 投稿用メタ情報とアップロード状態
-- ============================================================

CREATE TABLE IF NOT EXISTS render_youtube_metadata (
    render_id TEXT PRIMARY KEY,

    youtube_title TEXT NOT NULL,
    youtube_description TEXT NOT NULL,

    hashtags_json TEXT NOT NULL,
    tags_json TEXT NOT NULL,

    category_hint TEXT NOT NULL,
    privacy_status TEXT NOT NULL,

    made_for_kids INTEGER NOT NULL DEFAULT 0,
    contains_synthetic_voice INTEGER NOT NULL DEFAULT 1,

    description_path TEXT NOT NULL,

    experiment_group TEXT,
    hypothesis TEXT,
    primary_metric TEXT,
    secondary_metrics_json TEXT,

    FOREIGN KEY (render_id)
        REFERENCES youtube_renders(render_id)
        ON DELETE CASCADE,

    CHECK (category_hint IN (
        'education',
        'science_and_technology',
        'entertainment',
        'people_and_blogs',
        'gaming',
        'news_and_politics'
    )),
    CHECK (privacy_status IN (
        'private',
        'unlisted',
        'public'
    )),
    CHECK (made_for_kids IN (0, 1)),
    CHECK (contains_synthetic_voice = 1)
);


CREATE TABLE IF NOT EXISTS youtube_uploads (
    render_id TEXT PRIMARY KEY,

    planned INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'not_uploaded',

    youtube_video_id TEXT,
    youtube_url TEXT,
    uploaded_at TEXT,

    error_message TEXT,

    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (render_id)
        REFERENCES youtube_renders(render_id)
        ON DELETE CASCADE,

    CHECK (planned IN (0, 1)),
    CHECK (status IN (
        'not_uploaded',
        'uploaded_private',
        'uploaded_unlisted',
        'uploaded_public',
        'failed'
    ))
);

CREATE INDEX IF NOT EXISTS idx_youtube_uploads_status
ON youtube_uploads(status);

CREATE INDEX IF NOT EXISTS idx_youtube_uploads_youtube_video_id
ON youtube_uploads(youtube_video_id);


-- ============================================================
-- 15. thumbnail
-- ============================================================

CREATE TABLE IF NOT EXISTS render_thumbnails (
    render_id TEXT PRIMARY KEY,

    generated INTEGER NOT NULL DEFAULT 0,
    template TEXT,
    background_source TEXT,
    text TEXT,
    path TEXT,

    FOREIGN KEY (render_id)
        REFERENCES youtube_renders(render_id)
        ON DELETE CASCADE,

    CHECK (generated IN (0, 1))
);


-- ============================================================
-- 16. credits
-- Pexels / BGM / font など
-- ============================================================

CREATE TABLE IF NOT EXISTS render_credits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    render_id TEXT NOT NULL,

    credit_type TEXT NOT NULL,
    source TEXT NOT NULL,
    text TEXT NOT NULL,
    url TEXT,

    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (render_id)
        REFERENCES youtube_renders(render_id)
        ON DELETE CASCADE,

    CHECK (credit_type IN (
        'video',
        'image',
        'bgm',
        'sound_effect',
        'font',
        'other'
    ))
);

CREATE INDEX IF NOT EXISTS idx_render_credits_render_id
ON render_credits(render_id);


CREATE TABLE IF NOT EXISTS render_credit_summaries (
    render_id TEXT PRIMARY KEY,

    required INTEGER NOT NULL DEFAULT 1,
    description_text TEXT NOT NULL,

    FOREIGN KEY (render_id)
        REFERENCES youtube_renders(render_id)
        ON DELETE CASCADE,

    CHECK (required IN (0, 1))
);


-- ============================================================
-- 17. FFmpeg実行ログ
-- ============================================================

CREATE TABLE IF NOT EXISTS render_ffmpeg_logs (
    render_id TEXT PRIMARY KEY,

    version TEXT NOT NULL,

    command_log_path TEXT NOT NULL,
    stderr_log_path TEXT NOT NULL,

    video_codec TEXT NOT NULL,
    audio_codec TEXT NOT NULL DEFAULT 'aac',
    pix_fmt TEXT NOT NULL DEFAULT 'yuv420p',

    preset TEXT NOT NULL DEFAULT 'medium',
    crf INTEGER NOT NULL DEFAULT 20,

    FOREIGN KEY (render_id)
        REFERENCES youtube_renders(render_id)
        ON DELETE CASCADE,

    CHECK (video_codec IN ('libx264', 'h264_nvenc')),
    CHECK (audio_codec = 'aac'),
    CHECK (pix_fmt = 'yuv420p'),
    CHECK (preset IN (
        'ultrafast',
        'superfast',
        'veryfast',
        'faster',
        'fast',
        'medium',
        'slow',
        'slower',
        'veryslow'
    )),
    CHECK (crf BETWEEN 0 AND 51)
);


-- ============================================================
-- 18. validation
-- project/renderedの検証結果
-- ============================================================

CREATE TABLE IF NOT EXISTS render_validation_results (
    render_id TEXT PRIMARY KEY,

    project_json_valid INTEGER NOT NULL,
    rendered_json_valid INTEGER NOT NULL,

    FOREIGN KEY (render_id)
        REFERENCES youtube_renders(render_id)
        ON DELETE CASCADE,

    CHECK (project_json_valid IN (0, 1)),
    CHECK (rendered_json_valid IN (0, 1))
);


CREATE TABLE IF NOT EXISTS render_validation_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    render_id TEXT NOT NULL,

    level TEXT NOT NULL,
    code TEXT NOT NULL,
    message TEXT NOT NULL,
    details_json TEXT,

    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (render_id)
        REFERENCES youtube_renders(render_id)
        ON DELETE CASCADE,

    CHECK (level IN (
        'warning',
        'error'
    ))
);

CREATE INDEX IF NOT EXISTS idx_render_validation_messages_render_id
ON render_validation_messages(render_id);

CREATE INDEX IF NOT EXISTS idx_render_validation_messages_level
ON render_validation_messages(level);


-- ============================================================
-- 19. manual_review
-- 半自動運用の肝
-- ============================================================

CREATE TABLE IF NOT EXISTS render_manual_reviews (
    render_id TEXT PRIMARY KEY,

    required INTEGER NOT NULL DEFAULT 1,
    fact_check_required INTEGER NOT NULL DEFAULT 1,

    checked INTEGER NOT NULL DEFAULT 0,
    publish_ready INTEGER NOT NULL DEFAULT 0,

    checked_at TEXT,
    reviewer TEXT,
    notes TEXT,

    FOREIGN KEY (render_id)
        REFERENCES youtube_renders(render_id)
        ON DELETE CASCADE,

    CHECK (required IN (0, 1)),
    CHECK (fact_check_required IN (0, 1)),
    CHECK (checked IN (0, 1)),
    CHECK (publish_ready IN (0, 1))
);

CREATE INDEX IF NOT EXISTS idx_render_manual_reviews_publish_ready
ON render_manual_reviews(publish_ready);


-- ============================================================
-- 20. YouTube Analytics用
-- 将来的な改善ループに使う
-- rendered schema そのものには必須ではないが、
-- YouTube特化版なら最初から用意しておくとよい
-- ============================================================

CREATE TABLE IF NOT EXISTS youtube_metrics_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    render_id TEXT NOT NULL,
    project_id TEXT NOT NULL,

    youtube_video_id TEXT NOT NULL,

    snapshot_date TEXT NOT NULL,
    collected_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    views INTEGER,
    engaged_views INTEGER,

    likes INTEGER,
    comments INTEGER,
    shares INTEGER,

    subscribers_gained INTEGER,

    average_view_duration REAL,
    average_view_percentage REAL,
    estimated_minutes_watched REAL,

    raw_metrics_json TEXT,

    FOREIGN KEY (render_id)
        REFERENCES youtube_renders(render_id)
        ON DELETE CASCADE,

    FOREIGN KEY (project_id)
        REFERENCES youtube_projects(id)
        ON DELETE CASCADE,

    UNIQUE (youtube_video_id, snapshot_date)
);

CREATE INDEX IF NOT EXISTS idx_youtube_metrics_snapshots_render_id
ON youtube_metrics_snapshots(render_id);

CREATE INDEX IF NOT EXISTS idx_youtube_metrics_snapshots_project_id
ON youtube_metrics_snapshots(project_id);

CREATE INDEX IF NOT EXISTS idx_youtube_metrics_snapshots_video_date
ON youtube_metrics_snapshots(youtube_video_id, snapshot_date);


-- ============================================================
-- 21. 便利ビュー
-- レンダリング一覧をざっくり確認する用
-- ============================================================

CREATE VIEW IF NOT EXISTS v_youtube_render_overview AS
SELECT
    r.render_id,
    r.project_id,
    p.topic,
    p.internal_title,
    ym.youtube_title,
    r.status AS render_status,
    r.actual_duration_sec,
    u.status AS upload_status,
    u.youtube_video_id,
    u.youtube_url,
    mr.checked AS review_checked,
    mr.publish_ready,
    r.video_path,
    r.created_at,
    r.completed_at
FROM youtube_renders r
JOIN youtube_projects p
    ON p.id = r.project_id
LEFT JOIN render_youtube_metadata ym
    ON ym.render_id = r.render_id
LEFT JOIN youtube_uploads u
    ON u.render_id = r.render_id
LEFT JOIN render_manual_reviews mr
    ON mr.render_id = r.render_id;


-- ============================================================
-- 22. updated_at更新用トリガー
-- SQLiteにはON UPDATE CURRENT_TIMESTAMPがないため手動トリガー
-- ============================================================

CREATE TRIGGER IF NOT EXISTS trg_youtube_projects_updated_at
AFTER UPDATE ON youtube_projects
FOR EACH ROW
BEGIN
    UPDATE youtube_projects
    SET updated_at = CURRENT_TIMESTAMP
    WHERE id = OLD.id;
END;

CREATE TRIGGER IF NOT EXISTS trg_project_bgm_plans_updated_at
AFTER UPDATE ON project_bgm_plans
FOR EACH ROW
BEGIN
    UPDATE project_bgm_plans
    SET updated_at = CURRENT_TIMESTAMP
    WHERE project_id = OLD.project_id;
END;

CREATE TRIGGER IF NOT EXISTS trg_project_visual_strategies_updated_at
AFTER UPDATE ON project_visual_strategies
FOR EACH ROW
BEGIN
    UPDATE project_visual_strategies
    SET updated_at = CURRENT_TIMESTAMP
    WHERE project_id = OLD.project_id;
END;

CREATE TRIGGER IF NOT EXISTS trg_project_youtube_metadata_updated_at
AFTER UPDATE ON project_youtube_metadata
FOR EACH ROW
BEGIN
    UPDATE project_youtube_metadata
    SET updated_at = CURRENT_TIMESTAMP
    WHERE project_id = OLD.project_id;
END;

CREATE TRIGGER IF NOT EXISTS trg_bgm_tracks_updated_at
AFTER UPDATE ON bgm_tracks
FOR EACH ROW
BEGIN
    UPDATE bgm_tracks
    SET updated_at = CURRENT_TIMESTAMP
    WHERE track_id = OLD.track_id;
END;

CREATE TRIGGER IF NOT EXISTS trg_media_assets_updated_at
AFTER UPDATE ON media_assets
FOR EACH ROW
BEGIN
    UPDATE media_assets
    SET updated_at = CURRENT_TIMESTAMP
    WHERE asset_id = OLD.asset_id;
END;

CREATE TRIGGER IF NOT EXISTS trg_youtube_uploads_updated_at
AFTER UPDATE ON youtube_uploads
FOR EACH ROW
BEGIN
    UPDATE youtube_uploads
    SET updated_at = CURRENT_TIMESTAMP
    WHERE render_id = OLD.render_id;
END;