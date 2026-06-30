# 深海発光生物ショート動画生成と品質改善ループ

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

この計画はリポジトリ直下の `PLANS.md` と `AGENTS.md` に従って管理する。作業ディレクトリは `C:\Users\Hodaka\Downloads\div\autoyoutube` で、Pythonコマンドはユーザー作成済みの `.\.venv\Scripts\python.exe` を使う。

## Purpose / Big Picture

ユーザー提供の「深海で光る生き物の理由」という約1分台本から、YouTube Shorts用の `project.youtube.json` を作成し、AivisSpeech、Pexels素材、指定BGM、FFmpegで実動画を生成する。その後 `evaluate-render` で `quality_report.json` を作成し、検査結果をもとにコードを改善する。目的はバズ判定ではなく、生成物の破綻、クレジット漏れ、ファイル不整合、動画仕様不一致を減らすことである。

## Progress

- [x] (2026-06-29 23:15 JST) 現在のGit状態、BGM登録、Pexels素材登録を確認した。
- [x] (2026-06-29 23:16 JST) AivisSpeech Engineの `/version` がlocalhostで応答することを確認した。
- [x] (2026-06-29 23:18 JST) 1分台本用のproject JSONを作成し、schema検証が成功した。
- [x] (2026-06-29 23:19 JST) Pexels素材を8件取得し、DBへ登録した。
- [x] (2026-06-29 23:20 JST) AivisSpeech実音声とFFmpegで動画を生成した。
- [x] (2026-06-29 23:21 JST) `evaluate-render` とffprobeで品質検査し、初回は実MP4尺とrendered JSON尺のずれを確認した。
- [x] (2026-06-29 23:27 JST) TDDでffprobe実検査、FFmpeg `-t` 指定、字幕自動改行を追加した。
- [x] (2026-06-29 23:30 JST) 修正後に再レンダーし、`quality_report.json` が `status: pass` になることを確認した。
- [x] (2026-06-29 23:33 JST) ExecPlanを更新した。
- [x] (2026-06-29 23:32 JST) Ruff、pytest、schema検証を実行した。

## Surprises & Discoveries

- Observation: 既存DBには深海・潜水艦系のPexels素材が6件ある。
  Evidence: `list-assets` は `dark ocean`, `underwater light`, `dark deep ocean`, `black submarine underwater` などを表示した。

- Observation: 今回の台本には `glowing jellyfish`, `glowing plankton`, `anglerfish deep sea` など、既存cacheにないvisual queryが含まれる。
  Evidence: ユーザー台本の各映像指定と `list-assets` 出力を比較した。

- Observation: 初回レンダーでは `rendered.target.actual_duration_sec=66.021` に対して、ffprobeの実MP4尺が `68.233333` 秒だった。
  Evidence: 手動ffprobeでは約68.23秒、当時のquality reportではこの差分が検出されていなかった。

- Observation: FFmpegコマンドに `-t <duration>` を明示した後、実MP4尺とrendered JSON尺の差分は `0.001` 秒まで縮小した。
  Evidence: 最終quality reportの `duration_diff_sec` は `0.001`、`status` は `pass` である。

- Observation: 台本7文目の字幕は全文で33文字だったが、ASS改行 `\N` により1行最大32文字以内に収まった。
  Evidence: 最終 `subtitle.ass` では「たとえばチョウチンアンコウは、\N頭の先にある光で小さな魚を誘います。」として出力された。

## Decision Log

- Decision: 新しいproject IDは `trivia_deep_sea_bioluminescence_001` とする。
  Rationale: テーマが深海発光生物であり、既存の潜水艦サンプルと区別できる名前にするため。
  Date/Author: 2026-06-29 / Codex

- Decision: sample BGMは既に登録済みの `No One Here Gets In Alive` を使い、`mood=mysterious`, `intensity=low`, `allow_sources=["youtube_audio_library"]` とする。
  Rationale: ユーザーが直前に指定したBGMを継続利用し、BGM選定を安定させるため。
  Date/Author: 2026-06-29 / Codex

- Decision: 自己改善の初期対象は `evaluate-render` の検査精度向上とする。
  Rationale: 既存のquality evaluatorはJSONとファイル存在中心で、実MP4のdurationやdimensionをffprobeで検査していない。実動画生成後の改善ループでは、まず検査器自体の信頼性を上げるのが効果的である。
  Date/Author: 2026-06-29 / Codex

- Decision: FFmpeg出力には `-shortest` に加えて `-t <actual_duration>` を指定する。
  Rationale: ループ背景動画とBGMを扱う実レンダーで、コンテナ尺がナレーション実測尺より伸びるケースを防ぐため。
  Date/Author: 2026-06-29 / Codex

- Decision: 長い字幕は台本本文を変えず、subtitle itemとASS出力側で `\N` による表示改行を入れる。
  Rationale: ナレーション原文は保持しつつ、動画上の字幕可読性とquality evaluatorの1行文字数チェックを両立するため。
  Date/Author: 2026-06-29 / Codex

## Outcomes & Retrospective

完了。`projects/trivia_deep_sea_bioluminescence_001/project.youtube.json` からAivisSpeech実音声、Pexels素材、指定BGM `No One Here Gets In Alive`、FFmpegで `renders/trivia_deep_sea_bioluminescence_001/output.mp4` を生成した。

最終的な `quality_report.json` は `status: pass`、`checks: []` である。主なメトリクスは、`video_width=1080`、`video_height=1920`、`video_fps=30.0`、`video_duration_sec=65.695011`、`duration_diff_sec=0.001`、`max_subtitle_chars=32`、`bgm_volume_db=-26`、`has_bgm=true`、`has_pexels_visual=true` である。

自己改善として、`src/quality/evaluator.py` にffprobe実検査と動画尺・解像度チェックを追加し、`src/render/ffmpeg_renderer.py` に出力尺を固定する `-t` を追加し、`src/pipeline/render_project.py` に字幕自動改行を追加した。関連テストも追加し、最終的にRuffとpytestが通った。

## Context and Orientation

CLI入口は `src/main.py` である。`render` は `src/pipeline/render_project.py` を呼び、project JSON検証、音声生成、BGM選定、映像素材選定、FFmpeg実行、rendered JSON作成を行う。BGMとPexels素材はSQLiteの `bgm_tracks` と `media_assets` から選ばれる。品質検査は `src/quality/evaluator.py` の `evaluate_render()` が担当し、`quality_report.json` を出力する。

今回作成するproject JSONは `projects/trivia_deep_sea_bioluminescence_001/project.youtube.json` に置く。生成物は `renders/trivia_deep_sea_bioluminescence_001/` に作られる。生成物、DB、Pexels/BGM実ファイルはGit管理しない。

## Plan of Work

まずユーザー台本をschemaに合うproject JSONへ変換する。15文、合計想定約59.5秒、`voice.style_id=888753760`、BGMは `youtube_audio_library` の `mysterious/low` を指定する。

次にPexels素材を取得する。ネットワークやAPI制限で取得できない場合は、既存cacheから選ばれる素材でrenderし、quality reportに残る内容を確認する。

動画生成後、`evaluate-render` とffprobeを実行する。現在のquality evaluatorが実MP4のdurationやdimensionを検査していない場合、TDDで `VIDEO_DIMENSION_INVALID` と `VIDEO_DURATION_MISMATCH` の検査を追加する。ffprobeがない環境ではwarningを出す形にし、既存の生成処理を止めない。

## Concrete Steps

作業はすべてリポジトリ直下で行う。

    .\.venv\Scripts\python.exe -m src.main validate-project projects\trivia_deep_sea_bioluminescence_001\project.youtube.json
    .\.venv\Scripts\python.exe -m src.main fetch-pexels projects\trivia_deep_sea_bioluminescence_001\project.youtube.json --per-query 1 --max-downloads 8
    .\.venv\Scripts\python.exe -m src.main render projects\trivia_deep_sea_bioluminescence_001\project.youtube.json --voice-mode aivis --video-mode ffmpeg --aivis-base-url http://127.0.0.1:10101
    .\.venv\Scripts\python.exe -m src.main validate-render renders\trivia_deep_sea_bioluminescence_001\rendered.youtube.json
    .\.venv\Scripts\python.exe -m src.main evaluate-render renders\trivia_deep_sea_bioluminescence_001\rendered.youtube.json
    .\.venv\Scripts\python.exe -m ruff check .
    .\.venv\Scripts\python.exe -m ruff format . --check
    .\.venv\Scripts\python.exe -m pytest -q

## Validation and Acceptance

動画生成の受け入れ条件は、`renders/trivia_deep_sea_bioluminescence_001/output.mp4` が存在し0 byteではなく、`rendered.youtube.json` がschema validであること、BGMとPexels creditsが出力されること、`quality_report.json` が生成されることである。コード改善の受け入れ条件は、改善対象に対する失敗テストを先に確認し、実装後にそのテストと全体pytest、Ruffが通ることである。

## Idempotence and Recovery

project JSONは再生成しても同じIDのrenderディレクトリを上書きするだけである。Pexels取得は同じasset IDをupsertする。AivisSpeechやPexelsが一時的に失敗した場合は、接続状態を確認して同じコマンドを再実行する。生成物とDBはGit管理しないため、必要なら削除して再生成できる。

## Artifacts and Notes

台本の合計想定尺は約59.5秒である。AivisSpeechの実測では読み上げ速度により尺が変わるため、字幕とrendered JSONは実測durationを正とする。

## Interfaces and Dependencies

既存の `src.quality.evaluator.evaluate_render(rendered_path: Path) -> dict[str, Any]` を拡張する場合は、戻り値の `status`, `checks`, `metrics` 構造を維持する。ffprobeはFFmpegに同梱されている実行ファイルを使う。見つからない場合は `FFPROBE_NOT_AVAILABLE` warningを出す。

## Plan Revision Notes

2026-06-29 / Codex: ユーザーが1分台本から実動画を生成し、AivisSpeech/FFmpeg等でチェックして自己改善ループを回すよう依頼したため、本ExecPlanを追加した。
