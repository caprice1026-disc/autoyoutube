# 3本台本の実生成と品質チェック改善ループ

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

この計画はリポジトリ直下の `PLANS.md` と `AGENTS.md` に従って管理する。作業ディレクトリは `C:\Users\Hodaka\Downloads\div\autoyoutube` で、Pythonコマンドは `.\.venv\Scripts\python.exe` を使う。このプロジェクトはYouTube Shorts向け動画生成に集中し、自動投稿やバズ予測は追加しない。

## Purpose / Big Picture

ユーザー提供の3本の1分台本、雲、火山、夜の街を同じ生成ワークフローで実動画化し、`evaluate-render` の品質チェックを通す。目的は動画の面白さ判定ではなく、複数テーマを連続で流したときに、素材取得、音声、字幕、BGM、FFmpeg、rendered JSON、quality reportのどこに機械的な破綻が出るかを見つけ、コード側で直せるものをTDDで改善することである。

## Progress

- [x] (2026-06-30 00:10 JST) ユーザー要件を確認し、3本をproject JSON化して同一CLIワークフローで検証する方針を決めた。
- [x] (2026-06-30 00:25 JST) 3本分のproject JSONを追加し、`validate-project` を通した。
- [x] (2026-06-30 00:42 JST) Pexels素材を取得し、AivisSpeech実音声とFFmpegで3本をレンダーした。
- [x] (2026-06-30 00:50 JST) 3本の `quality_report.json` を比較し、火山の `MEDIA_FILE_MISSING` と3本共通の60秒超過未検出を特定した。
- [x] (2026-06-30 01:10 JST) 品質チェック結果に基づき、素材fallbackと `VIDEO_DURATION_TOO_LONG` をTDDで改善した。
- [x] (2026-06-30 01:35 JST) 速度調整後に必要な動画を再レンダーし、3本ともquality reportがpassになることを確認した。
- [x] (2026-06-30 01:45 JST) Ruff、pytest、schema検証、evaluate-renderを最終実行した。

## Surprises & Discoveries

- AivisSpeech実音声では、project JSONの `target.duration_sec=60` だけでは最終尺を保証できない。速度1.0では雲が約69.4秒、火山が約66.8秒、夜景が約69.3秒になった。
- 初回の火山レンダーでは `seismic graph` に一致するPexels素材がなく、`rendered.youtube.json` に `renders/.../video/material_012.mp4` という存在しないplaceholder pathが残り、`MEDIA_FILE_MISSING` になった。
- 既存のquality checkはMP4実尺とrendered JSONの差分は見ていたが、Shorts向け上限60秒そのものは見ていなかったため、69秒台でもpassしていた。
- `voice.speed_scale` を火山1.18、雲と夜景1.22に調整すると、AivisSpeech実音声でも3本とも60秒以内に収まった。

## Decision Log

- Decision: 3本とも既存BGM登録に合わせて `mood=mysterious`, `intensity=low`, `allow_sources=["youtube_audio_library"]` を指定する。
  Rationale: 現在確実に登録済みのBGM `No One Here Gets In Alive` を使い、BGM未選定による比較ノイズを避けるため。
  Date/Author: 2026-06-30 / Codex

- Decision: project IDは `trivia_clouds_not_falling_001`, `trivia_volcano_sudden_eruption_001`, `trivia_city_lights_night_001` とする。
  Rationale: テーマごとにrenderディレクトリを分離し、quality reportを比較しやすくするため。
  Date/Author: 2026-06-30 / Codex

- Decision: visual queryに一致する素材がない場合は、許可ソース内の既存cache素材へfallbackし、`rendered.youtube.json` に存在しない素材パスを残さない。
  Rationale: FFmpegが単一背景で成功しても、rendered JSONの各visual pathは成果物契約として実在すべきため。
  Date/Author: 2026-06-30 / Codex

- Decision: `evaluate-render` に `VIDEO_DURATION_TOO_LONG` を追加し、MP4実尺またはrendered実尺が60秒を超えた場合にwarningを出す。
  Rationale: YouTube Shorts向けMVPの実尺上限を機械検査で検出し、AivisSpeech実測の伸びを自己改善ループに載せるため。
  Date/Author: 2026-06-30 / Codex

## Outcomes & Retrospective

最終確認で、3本とも `validate-project` と `validate-render` が成功し、`quality_report.json` はpassになった。`ruff check .`、`ruff format . --check`、`pytest -q --basetemp .pytest_tmp` も成功した。

- 雲: `renders/trivia_clouds_not_falling_001/output.mp4`, 実尺59.266秒, quality status pass
- 火山: `renders/trivia_volcano_sudden_eruption_001/output.mp4`, 実尺58.852秒, quality status pass
- 夜の街: `renders/trivia_city_lights_night_001/output.mp4`, 実尺59.664秒, quality status pass

コード修正として、素材未一致時のfallbackを `src/pipeline/render_project.py` に追加し、`src/quality/evaluator.py` に60秒超過検査を追加した。試作project JSONではAivisSpeech実測に合わせて `voice.speed_scale` を調整した。動画内容の自然さ、事実確認、投稿可否は引き続き人間レビュー対象である。

## Context and Orientation

CLI入口は `src/main.py` である。`render` は `src/pipeline/render_project.py` に入り、AivisSpeech音声、Pexelsまたはlocal素材、BGM、字幕、FFmpeg出力、rendered JSON保存を行う。品質検査は `src/quality/evaluator.py` の `evaluate_render()` が担当し、renderディレクトリに `quality_report.json` を書く。

今回作成するproject JSONは、`projects/trivia_clouds_not_falling_001/project.youtube.json`, `projects/trivia_volcano_sudden_eruption_001/project.youtube.json`, `projects/trivia_city_lights_night_001/project.youtube.json` である。生成物は各 `renders/<project_id>/` に出る。生成物、DB、Pexels素材、BGM実ファイルはGit管理しない。

## Plan of Work

まず3本の台本を既存schemaに合うproject JSONへ変換する。いずれもYouTube Shorts前提、1080x1920、30fps、AivisSpeech、manual fact check requiredを維持する。台本の見積もり合計は60秒付近またはやや超過するため、project targetの `duration_sec` はschema上限の60に置く。実際のrendered JSONはAivisSpeech実測durationを正とする。

次にPexels素材を取得する。各projectに対して `fetch-pexels` を実行し、既存DBにないvisual queryの素材を追加する。ネットワークまたはAPIで一部取得できない場合は既存cacheでrenderし、quality reportに残る問題を観察する。

その後3本をAivisSpeech実音声とFFmpegでレンダーし、それぞれ `validate-render` と `evaluate-render` を実行する。quality reportに共通するwarningまたはerrorがあれば、TDDで再現テストを追加してから生成コードまたは評価コードを修正する。修正後は必要な動画を再レンダーし、quality reportの改善を確認する。

## Concrete Steps

作業はすべてリポジトリ直下で行う。

    .\.venv\Scripts\python.exe -m src.main validate-project projects\trivia_clouds_not_falling_001\project.youtube.json
    .\.venv\Scripts\python.exe -m src.main validate-project projects\trivia_volcano_sudden_eruption_001\project.youtube.json
    .\.venv\Scripts\python.exe -m src.main validate-project projects\trivia_city_lights_night_001\project.youtube.json
    .\.venv\Scripts\python.exe -m src.main fetch-pexels projects\trivia_clouds_not_falling_001\project.youtube.json --per-query 1 --max-downloads 10
    .\.venv\Scripts\python.exe -m src.main fetch-pexels projects\trivia_volcano_sudden_eruption_001\project.youtube.json --per-query 1 --max-downloads 10
    .\.venv\Scripts\python.exe -m src.main fetch-pexels projects\trivia_city_lights_night_001\project.youtube.json --per-query 1 --max-downloads 10
    .\.venv\Scripts\python.exe -m src.main render projects\<project_id>\project.youtube.json --voice-mode aivis --video-mode ffmpeg --aivis-base-url http://127.0.0.1:10101
    .\.venv\Scripts\python.exe -m src.main validate-render renders\<project_id>\rendered.youtube.json
    .\.venv\Scripts\python.exe -m src.main evaluate-render renders\<project_id>\rendered.youtube.json
    .\.venv\Scripts\python.exe -m ruff check .
    .\.venv\Scripts\python.exe -m ruff format . --check
    .\.venv\Scripts\python.exe -m pytest -q --basetemp .pytest_tmp

## Validation and Acceptance

3本それぞれで `output.mp4`, `rendered.youtube.json`, `quality_report.json`, `credits.txt`, `subtitle.ass` が生成されることを確認する。`validate-project` と `validate-render` が成功することを確認する。`quality_report.json` がerrorを出す場合はコード修正対象として扱う。warningについては、コードで安全に直せるものはTDDで改善し、人間レビュー対象に残すものはOutcomesに明記する。最終的にRuffとpytestが成功することを確認する。

## Idempotence and Recovery

renderは同じrenderディレクトリを上書きするだけなので再実行できる。Pexels取得はasset_idをupsertするため同じ素材が重複登録されにくい。AivisSpeechやPexelsが失敗した場合は、同じコマンドを再実行する。pytestで作成される `.pytest_tmp` は検証後に削除する。

## Artifacts and Notes

最終報告では、3本のoutput.mp4パス、quality reportのstatus、主要な検査メトリクス、コード修正内容、残課題を示す。

## Interfaces and Dependencies

外部依存は既存のAivisSpeech Engine、Pexels API、FFmpeg、SQLite、Python仮想環境である。新しいライブラリは追加しない。コード改善が必要な場合は、既存の `src/pipeline/render_project.py`, `src/render/ffmpeg_renderer.py`, `src/quality/evaluator.py` と対応テストだけを対象にする。

## Plan Revision Notes

2026-06-30 / Codex: ユーザーが3本の台本で実動画生成と品質チェック、品質結果に基づくワークフロー改善を依頼したため、本ExecPlanを追加した。
