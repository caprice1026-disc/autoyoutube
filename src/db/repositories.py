from __future__ import annotations

import json
import sqlite3
from typing import Any


def upsert_project(connection: sqlite3.Connection, project: dict[str, Any], project_path: str, project_hash: str) -> None:
    target = project["target"]
    voice = project["voice"]
    vf = target["video_format"]
    connection.execute(
        """
        INSERT OR REPLACE INTO youtube_projects (
            id, schema_version, platform_profile, topic, internal_title, hook,
            project_json_path, project_json_hash, raw_project_json,
            planned_duration_sec, aspect_ratio, width, height, fps, container,
            video_codec, audio_codec, pix_fmt, voice_engine, voice_speaker,
            voice_speed_scale, voice_pitch_scale, voice_intonation_scale,
            voice_sentence_gap_ms, manual_fact_check_required, fact_check_notes,
            production_notes, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'validated')
        """,
        (
            project["id"], project["schema_version"], project["platform_profile"], project["topic"], project["title"], project["hook"],
            project_path, project_hash, json.dumps(project, ensure_ascii=False, sort_keys=True),
            target["duration_sec"], target["aspect_ratio"], target["resolution"]["width"], target["resolution"]["height"], target["fps"], vf["container"],
            vf["video_codec"], vf["audio_codec"], vf["pix_fmt"], voice["engine"], voice["speaker"], voice["speed_scale"], voice["pitch_scale"],
            voice["intonation_scale"], voice["sentence_gap_ms"], int(project["manual_fact_check_required"]), project.get("fact_check_notes"), project.get("production_notes"),
        ),
    )
    connection.execute("DELETE FROM project_script_items WHERE project_id = ?", (project["id"],))
    for item in project["script"]:
        connection.execute(
            "INSERT INTO project_script_items (project_id, item_index, text, visual_query, estimated_duration_sec, caption_style_hint) VALUES (?, ?, ?, ?, ?, ?)",
            (project["id"], item["index"], item["text"], item["visual_query"], item["estimated_duration_sec"], item["caption_style_hint"]),
        )
    bgm = project["bgm"]
    connection.execute(
        "INSERT OR REPLACE INTO project_bgm_plans (project_id, enabled, strategy, mood, intensity, volume_db, fade_in_ms, fade_out_ms, allow_sources_json, avoid_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (project["id"], int(bgm["enabled"]), bgm["strategy"], bgm["mood"], bgm["intensity"], bgm["volume_db"], bgm["fade_in_ms"], bgm["fade_out_ms"], json.dumps(bgm["allow_sources"], ensure_ascii=False), json.dumps(bgm["avoid"], ensure_ascii=False)),
    )
    visual = project["visual_strategy"]
    connection.execute(
        "INSERT OR REPLACE INTO project_visual_strategies (project_id, source_priority_json, preferred_orientation, fallback, primary_query, fallback_queries_json, avoid_keywords_json) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (project["id"], json.dumps(visual["source_priority"], ensure_ascii=False), visual["preferred_orientation"], visual["fallback"], visual["primary_query"], json.dumps(visual["fallback_queries"], ensure_ascii=False), json.dumps(visual["avoid_keywords"], ensure_ascii=False)),
    )
    yt = project["youtube"]
    sections = yt["description_sections"]
    hypo = yt["analytics_hypothesis"]
    connection.execute(
        "INSERT OR REPLACE INTO project_youtube_metadata (project_id, youtube_title, youtube_description, hashtags_json, tags_json, category_hint, privacy_status, made_for_kids, contains_synthetic_voice, description_summary, credits_policy, disclaimer, experiment_group, hypothesis, primary_metric, secondary_metrics_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (project["id"], yt["title"], yt["description"], json.dumps(yt["hashtags"], ensure_ascii=False), json.dumps(yt["tags"], ensure_ascii=False), yt["category_hint"], yt["privacy_status"], int(yt["made_for_kids"]), int(yt["contains_synthetic_voice"]), sections["summary"], sections["credits_policy"], sections["disclaimer"], hypo["experiment_group"], hypo["hypothesis"], hypo["primary_metric"], json.dumps(hypo["secondary_metrics"], ensure_ascii=False)),
    )


def insert_render_summary(connection: sqlite3.Connection, rendered: dict[str, Any]) -> None:
    target = rendered["target"]
    vf = target["video_format"]
    connection.execute(
        "INSERT INTO youtube_renders (render_id, project_id, schema_version, platform_profile, status, created_at, completed_at, project_json_path, project_json_hash, project_schema_path, video_path, thumbnail_path, subtitle_ass_path, description_path, credits_path, rendered_json_path, logs_dir, raw_rendered_json, planned_duration_sec, actual_duration_sec, aspect_ratio, width, height, fps, container, video_codec, audio_codec, pix_fmt) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (rendered["render_id"], rendered["project_id"], rendered["schema_version"], rendered["platform_profile"], rendered["status"], rendered["created_at"], rendered["completed_at"], rendered["input"]["project_json_path"], rendered["input"]["project_json_hash"], rendered["input"]["project_schema_path"], rendered["output"]["video_path"], rendered["output"].get("thumbnail_path"), rendered["output"]["subtitle_ass_path"], rendered["output"]["description_path"], rendered["output"]["credits_path"], rendered["output"]["rendered_json_path"], rendered["output"].get("logs_dir"), json.dumps(rendered, ensure_ascii=False, sort_keys=True), target["planned_duration_sec"], target["actual_duration_sec"], target["aspect_ratio"], target["resolution"]["width"], target["resolution"]["height"], target["fps"], vf["container"], vf["video_codec"], vf["audio_codec"], vf["pix_fmt"]),
    )
    mr = rendered["manual_review"]
    connection.execute("INSERT INTO render_manual_reviews (render_id, required, fact_check_required, checked, publish_ready, notes) VALUES (?, ?, ?, ?, ?, ?)", (rendered["render_id"], int(mr["required"]), int(mr["fact_check_required"]), int(mr["checked"]), int(mr["publish_ready"]), mr["notes"]))
