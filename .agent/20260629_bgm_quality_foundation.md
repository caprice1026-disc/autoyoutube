# BGM実運用と自動品質検査基盤の追加

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

この計画はリポジトリ直下の `PLANS.md` と `AGENTS.md` に従って管理する。作業ディレクトリは `C:\Users\Hodaka\Downloads\div\autoyoutube` で、Pythonコマンドはユーザー作成済みの `.\.venv\Scripts\python.exe` を使う。

## Purpose / Big Picture

この変更により、利用者は `assets\bgm\No One Here Gets In Alive - National Sweetheart.mp3` をBGMとして登録し、実際のrenderで選ばれることを確認できる。さらに、Pexels素材やBGMのクレジット漏れ、字幕の長さ、必須ファイル欠落などを `evaluate-render` コマンドで検査し、Codexに渡せる `quality_report.json` を生成できるようにする。これはバズ予測ではなく、生成動画の破綻を減らすための品質検査と改善ループの土台である。

## Progress

- [x] (2026-06-29 22:39 JST) 指定BGMファイルと `assets/bgm/bgm_manifest.json` を確認した。
- [x] (2026-06-29 22:40 JST) 現行manifestは指定曲を登録しているが、`mood=chill` がproject schemaの許可値外であり、projectの `mood=mysterious` と一致しないことを確認した。
- [x] (2026-06-29 22:46 JST) 指定BGMが選ばれるmanifest/project条件へ修正した。
- [x] (2026-06-29 22:52 JST) Pexels video creditとBGM creditの欠落を防ぐテストを追加し、失敗を確認した。
- [x] (2026-06-29 22:52 JST) `voice.style_id` をSQLiteへ保存するテストを追加し、失敗を確認した。
- [x] (2026-06-29 22:52 JST) 主要定数を `src/defaults.py` へ分離するテストを追加し、失敗を確認した。
- [x] (2026-06-29 22:52 JST) `evaluate-render` と `quality_report.json` のテストを追加し、失敗を確認した。
- [x] (2026-06-29 22:57 JST) 最小実装でテストを通した。
- [x] (2026-06-29 22:59 JST) README、dev_memo、AGENTSを更新した。
- [x] (2026-06-29 22:56 JST) 指定BGMでimport/list/render/evaluate-renderを実行した。
- [x] (2026-06-29 23:00 JST) Ruffとpytestを実行した。

## Surprises & Discoveries

- Observation: `assets/bgm/bgm_manifest.json` はJSONとして読め、`import-bgm` は2曲を読み込めた。
  Evidence: `.\.venv\Scripts\python.exe -m src.main import-bgm assets\bgm\bgm_manifest.json` は `Imported BGM tracks: 2` を返した。

- Observation: 指定曲はDBへ登録済みだが、現在のmanifestでは `mood=chill` である。
  Evidence: `list-bgm` は `No One Here Gets In Alive	local_original	chill/low	...No One Here Gets In Alive - National Sweetheart.mp3` を表示した。

## Decision Log

- Decision: 指定曲は `source=youtube_audio_library`, `mood=mysterious`, `intensity=low` として扱い、sample projectの `allow_sources` を `youtube_audio_library` に絞る。
  Rationale: ユーザーの指示書はYouTube Studio Audio Library由来BGMを使う運用を前提にしている。sample projectで確実に指定曲を選ぶには、既存の `generated_mystery_low` と同じ条件にしない方がよい。
  Date/Author: 2026-06-29 / Codex

- Decision: `evaluate-render` の初期版は、動画の面白さや投稿可否を判断せず、ファイル、schema、credits、subtitle長などの機械的検査だけを行う。
  Rationale: 指示書はCodexにバズ判定を任せず、品質検査結果に基づいた実装改善を任せる方針である。
  Date/Author: 2026-06-29 / Codex

## Outcomes & Retrospective

指定BGM `No One Here Gets In Alive` は `youtube_audio_library / mysterious / low` としてDBに登録され、sample projectの `allow_sources=["youtube_audio_library"]` によりrenderで選ばれた。`rendered.youtube.json.bgm.track_id` は `No One Here Gets In Alive` になり、`credits.txt` と `credits.items[]` にはBGM creditとPexels video creditが出力された。

`evaluate-render` CLIを追加し、`quality_report.json` を生成できるようになった。直近のsample renderでは `status=pass`, `checks=[]` で、metricsには `has_bgm=true`, `has_pexels_visual=true`, `max_subtitle_chars=29` が記録された。`voice.style_id` は `youtube_projects.voice_style_id` と `render_voice_settings.voice_style_id` に保存される。

残課題は、ffprobeによる実尺・解像度検査、スクリーンショット生成、review CLI、thumbnail生成、複数素材タイムライン合成である。

## Context and Orientation

CLI入口は `src/main.py` で、`render` や `import-bgm` などのサブコマンドを定義している。動画生成の中心は `src/pipeline/render_project.py` で、project JSON検証、音声生成、BGM選定、素材選定、字幕、credits、rendered JSON生成、DB保存を行う。BGM manifestは `src/bgm/library.py` が読み、`src/db/repositories.py` がSQLiteへ保存する。FFmpeg実行は `src/render/ffmpeg_renderer.py` が担当する。

`rendered.youtube.json` は生成結果ログである。`credits.items[]` は `credit_type` を使う。Pexels素材は `rendered.visuals[]` に `source=pexels`, `photographer`, `pexels_url` などとして残る。今回追加する `evaluate-render` は、rendered JSONと実ファイルを読み、機械的な品質チェック結果を `quality_report.json` に保存する。

## Plan of Work

まず、BGM manifestを修正し、指定曲がsample projectの条件で必ず選ばれるようにする。ファイル本体はGit管理しない前提なので、manifestとproject JSONだけを変更する。

次にTDDでPexels creditsを追加する。`render_project()` の既存の流れでは、`_build_credits()` がBGMだけを見ているため、選定済み `visuals` を渡してPexels creditを重複排除しながら追加する。

次にDB保存を拡張する。`db/schema.sql` の `youtube_projects` と `render_voice_settings` に `voice_style_id INTEGER` を追加し、`upsert_project()` と `insert_render_summary()` で保存する。既存projectに `style_id` がない場合はNULLで保存する。

次に `src/defaults.py` を作成し、YouTube Shortsのサイズ、FFmpeg codec、BGM音量、字幕スタイル、品質検査しきい値を集約する。既存挙動を変えず、既存コードはこの定数を参照する。

最後に `src/quality/evaluator.py` と `evaluate-render` CLIを追加する。初期チェックは `FILE_MISSING`, `OUTPUT_VIDEO_EMPTY`, `BGM_CREDIT_MISSING`, `PEXELS_CREDIT_MISSING`, `SUBTITLE_TOO_LONG` を実装する。`quality_report.json` はrendered JSONと同じディレクトリへ出力する。

## Concrete Steps

作業はすべてリポジトリ直下で行う。

    .\.venv\Scripts\python.exe -m src.main import-bgm assets\bgm\bgm_manifest.json
    .\.venv\Scripts\python.exe -m src.main list-bgm
    .\.venv\Scripts\python.exe -m pytest -q tests\test_render_project_ffmpeg.py tests\test_bgm_library.py tests\test_quality_evaluator.py
    .\.venv\Scripts\python.exe -m src.main render projects\trivia_submarine_black_001\project.youtube.json --voice-mode aivis --video-mode ffmpeg
    .\.venv\Scripts\python.exe -m src.main evaluate-render renders\trivia_submarine_black_001\rendered.youtube.json
    .\.venv\Scripts\python.exe -m ruff check .
    All checks passed!

    .\.venv\Scripts\python.exe -m ruff format . --check
    50 files already formatted

    .\.venv\Scripts\python.exe -m pytest -q
    57 passed in 1.96s

    .\.venv\Scripts\python.exe -m src.main import-bgm assets\bgm\bgm_manifest.json
    Imported BGM tracks: 2

    .\.venv\Scripts\python.exe -m src.main list-bgm
    No One Here Gets In Alive    youtube_audio_library    mysterious/low    C:\Users\Hodaka\Downloads\div\autoyoutube\assets\bgm\No One Here Gets In Alive - National Sweetheart.mp3

    .\.venv\Scripts\python.exe -m src.main render projects\trivia_submarine_black_001\project.youtube.json --video-mode ffmpeg
    Render complete: C:\Users\Hodaka\Downloads\div\autoyoutube\renders\trivia_submarine_black_001\rendered.youtube.json

    .\.venv\Scripts\python.exe -m src.main evaluate-render renders\trivia_submarine_black_001\rendered.youtube.json
    Quality report written: renders\trivia_submarine_black_001\quality_report.json

## Validation and Acceptance

`list-bgm` に `no_one_here_gets_in_alive_national_sweetheart` が `youtube_audio_library/mysterious/low` として表示されること。sample projectをrenderすると `rendered.youtube.json.bgm.track_id` がこのtrack IDになり、`credits.txt` と `rendered.youtube.json.credits.items[]` にBGM creditが残ること。Pexels素材が使われた場合は、`credits.items[]` に `credit_type=video`, `source=pexels` の項目が重複なしで入ること。

`evaluate-render` を実行すると `renders/{project_id}/quality_report.json` が生成され、少なくとも `status`, `checks`, `metrics` を含むこと。BGM creditやPexels creditが欠けるfixtureでは該当errorを出し、正常なrenderでは致命的errorが出ないこと。

## Idempotence and Recovery

`import-bgm` は同じtrack IDをupsertするため再実行できる。`render` と `evaluate-render` は `renders/{project_id}/` の生成物を上書きする。DB schemaは新規初期化用の `CREATE TABLE IF NOT EXISTS` なので、既存DBに列を追加する本格migrationは今回扱わない。既存DBで列が足りない場合は、開発環境では `data/trivia_shorts.db` を削除して `init-db` し直せるが、生成DBはGit管理しない。

## Artifacts and Notes

指定BGMファイルは `assets\bgm\No One Here Gets In Alive - National Sweetheart.mp3` である。BGMファイル本体はGit管理しない。manifestのsourceはYouTube Audio Library由来として `youtube_audio_library` にするが、file_pathはユーザー指定の実配置に合わせて `No One Here Gets In Alive - National Sweetheart.mp3` のままにする。

## Interfaces and Dependencies

`src.defaults` は次の定数を提供する。

    TARGET_WIDTH = 1080
    TARGET_HEIGHT = 1920
    TARGET_ASPECT_RATIO = "9:16"
    TARGET_FPS = 30
    DEFAULT_VIDEO_CODEC = "libx264"
    DEFAULT_AUDIO_CODEC = "aac"
    DEFAULT_PIX_FMT = "yuv420p"
    DEFAULT_CRF = 20
    DEFAULT_PRESET = "medium"
    DEFAULT_BGM_VOLUME_DB = -26
    DEFAULT_BGM_FADE_IN_MS = 500
    DEFAULT_BGM_FADE_OUT_MS = 1200
    MAX_SUBTITLE_CHARS = 32

`src.quality.evaluator.evaluate_render(rendered_path: Path) -> dict[str, Any]` はquality reportのdictを返し、同じディレクトリに `quality_report.json` を書く。

## Plan Revision Notes

2026-06-29 / Codex: ユーザーが指定BGMの使用と、自動品質改善フローの初回実装を依頼したため、本ExecPlanを追加した。
