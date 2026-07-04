# make-video CLI と自動改善ループ実装計画

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

この計画はリポジトリ直下の `PLANS.md` と `AGENTS.md` に従って管理する。作業ディレクトリは `C:\Users\Hodaka\Downloads\div\autoyoutube` であり、Python コマンドは `.\.venv\Scripts\python.exe` を使う。

## Purpose / Big Picture

この変更により、ユーザーはローカルに置いた `project.youtube.json` を起点に、Pexels素材取得、AivisSpeech音声、FFmpeg動画生成、inspect/evaluate、機械的な再試行、ログ出力までを `make-video` で一括実行できるようになる。`make-video` は投稿までは行わず、最終成果物を `renders/<日時-タイトル>/final/` にまとめる。YouTubeへの private 投稿は既存の `upload-youtube` を使い、READMEにその連携手順を明記する。

## Progress

- [x] (2026-07-04) 設計書、`README.md`、現行CLI、render pipeline、visual fetcher、quality evaluatorを確認した。
- [x] (2026-07-04) `make-video` の責務を既存CLIの合成に寄せる方針を決めた。
- [x] (2026-07-04) TDDで `make-video` のplan-only/dry-run、attempt layout、ログ生成、設定優先順位のREDを確認した。
- [x] (2026-07-04) `make-video` の実行時ログを標準出力に出し、repair/failure/visual assignmentログも保存する。
- [x] (2026-07-04) render pipelineに任意renderディレクトリ指定を追加し、既存挙動を維持する。
- [x] (2026-07-04) wrapper scriptを追加し、AivisSpeech readiness確認とDocker起動待機を実装する。
- [x] (2026-07-04) READMEとdocsを仕様に合わせて更新する。
- [x] (2026-07-04) `--video-keyword` / `--pexels-keyword` でPexels動画検索キーワードを指定し、attempt JSONへ反映できるようにした。
- [ ] Ruff、pytest、必要なCLI smokeを通し、masterへpushする。

## Surprises & Discoveries

- 現行の `render_project` は既に `YYYYMMDDHHMM-タイトル` のrenderディレクトリを作るが、attempt/final layoutを直接指定する口を持っていない。
- 現行の `evaluate-render` は `VIDEO_DURATION_TOO_LONG` を warning として出すため、設計書の「60秒超えで停止しない」方針と整合する。
- 既存の `upload-youtube` は別コマンドとして存在しており、設計書の「make-videoはuploadしない」と整合する。
- `autoyoutube-private-publisher` の実運用では、`inspect-render` がWindows上でtimeline PNGの一部生成に失敗しても、`evaluate-render` が `pass` なら投稿まで進めていた。`make-video` ではinspect失敗をfailure logに残し、evaluateの結果で採用可否を判断する方針にする。
- 過去の実運用では、初回renderが60秒を超えた場合に速度調整して再renderしたが、本設計では動画尺のみを理由に自動変更しないため、`VIDEO_DURATION_TOO_LONG` はログに残すだけにする。
- ユーザー指定の「動画キーワード」は、plan表示だけでなく実際のPexels検索対象に入る必要があるため、`override` 時は `script[].visual_query` もCLI指定キーワードへ割り当て直す。

## Decision Log

- Decision: `make-video` は既存の `fetch_visuals_for_project`、`render_project`、`inspect_render`、`evaluate_render` をオーケストレーションする薄いpipelineとして実装する。
  Rationale: レンダラーやYouTube uploadを作り直すより、既存の検証済み部品を組み合わせる方が安全で、設計書の責務分離にも合うため。
  Date/Author: 2026-07-04 / Codex

- Decision: `make-video` 本体はYouTube uploadをしない。READMEには `make-video` 後に `upload-youtube <final/rendered.youtube.json>` を実行する手順を書く。
  Rationale: 設計書の upload gate 方針で、生成と投稿は分けると明記されているため。
  Date/Author: 2026-07-04 / Codex

- Decision: attempt出力は `render_project(..., render_dir=attempt_dir)` の任意引数で実現し、既存の `render` CLIの出力ディレクトリ仕様は変えない。
  Rationale: 既存コマンド互換を保ちながら `make-video` だけが `attempts/attempt_001` と `final/` を使えるため。
  Date/Author: 2026-07-04 / Codex

- Decision: `--bgm-id` が指定されない場合は、既存のproject JSONとDB上のBGM選定をそのまま使い、READMEとplan logには既定候補として `No One Here Gets In Alive - National Sweetheart` を明記する。
  Rationale: `autoyoutube-private-publisher` の既定運用がこのBGMであり、make-videoで別の既定ロジックを導入すると過去の動画と音作りがずれるため。
  Date/Author: 2026-07-04 / Codex

- Decision: `make-video` 実行中は `[make-video] ...` 形式で標準出力に段階ログを出す。
  Rationale: 長いrenderやfetch中にどこで止まったかを把握でき、repair/failure JSONを見る前の運用性が上がるため。
  Date/Author: 2026-07-04 / Codex

- Decision: Pexels動画検索キーワードは `--visual-keyword` に加え、利用者向け別名として `--video-keyword` と `--pexels-keyword` も受け付ける。
  Rationale: ユーザーの意図は「クエリ内容」より「このキーワードで動画素材を検索する」ことであり、CLI名もそれに合わせる方が誤用が少ないため。
  Date/Author: 2026-07-04 / Codex

## Outcomes & Retrospective

`make-video` は `src.main make-video` として追加され、`scripts/make-video.ps1` / `scripts/make-video.sh` からAivisSpeech readiness確認後に呼び出せる。attempt/final layout、`repair_log.json`、`failure_log.json`、`visual_assignment.json` を出力し、`--bgm-id` 未指定時は既存BGM選定を維持する。`--video-keyword` / `--pexels-keyword` / `--visual-keyword` はPexels動画検索キーワードとしてattempt JSONへ反映される。検証は `ruff check .`、対象CLI smoke、`pytest -q --basetemp .pytest_tmp` が通過した。`ruff format . --check` は今回触っていない既存13ファイルに整形差分が残っている。

## Context and Orientation

現行CLIの入口は `src/main.py` である。`render` サブコマンドは `src.pipeline.render_project.render_project` を呼び、`rendered.youtube.json` を生成する。Pexels取得は `src.media.visual_fetcher.fetch_visuals_for_project`、品質検査は `src.quality.evaluator.evaluate_render`、表示検査は `src.quality.inspector.inspect_render` が担当する。YouTube private uploadは `src.youtube.uploader.upload_private_video` を既存の `upload-youtube` コマンドから呼ぶ。

今回追加する `make-video` は、これらの既存機能を順番に呼び出す。ここでいう attempt は「同じ元project JSONから作った1回分のレンダー試行」であり、final は「採用されたattemptの成果物をコピーした最終出力」である。repair log はattemptごとの品質checkと自動処理を記録するJSON、failure log は環境/API/render/qualityなどの失敗分類を記録するJSONである。

## Plan of Work

最初にテストを追加する。`tests/test_make_video.py` で、plan-onlyが副作用なしに計画を返すこと、dry-runがattempt/final layoutとログを作ること、`AUTOYOUTUBE_MAX_FIX_ATTEMPTS` が設定ファイルより優先されることを確認する。`tests/test_render_project_ffmpeg.py` には、任意renderディレクトリ指定でも既存render内容が作られることを追加する。

次に、`config/auto_repair.youtube_shorts.json` を追加し、`src/config/auto_repair_config.py` でCLI引数、環境変数、設定ファイル、コードデフォルトの順に設定を解決する。`src/pipeline/make_video.py` は `MakeVideoOptions` と `make_video` を定義し、run directory、inputs、attempts、final、repair/failure/visual assignmentログを管理する。

`src/repair/quality_repair.py` は初期実装として、修正可能checkを分類し、再fetchまたは再renderに進む判断を返す。台本短縮、事実確認、タイトル改善はしない。`VIDEO_DURATION_TOO_LONG` はwarningとして記録するが停止条件にしない。`SAME_ASSET_CONSECUTIVE`、`SAME_ASSET_REUSED`、`SOURCE_RESOLUTION_TOO_LOW` は過去のprivate publisher運用で見つかった重要な機械的問題としてblocking warning扱いにし、候補数を増やして再試行する。Pexels失敗時はDBに既にあるローカル/stock素材でrender継続できるよう、fetch失敗をfailure logに記録して処理を続ける。

`scripts/make-video.ps1` と `scripts/make-video.sh` はAivisSpeechの `/version` を確認し、未起動なら `docker compose --profile aivis up -d aivis-engine` を実行して待機する。JSONはpipeせず、必ずファイルパスを `python -m src.main make-video` に渡す。

READMEには、`make-video` の目的、基本コマンド、wrapper scriptの使い方、attempt/final出力、ログ、upload-youtubeへのつなぎ方、exit code、注意点を追加する。

## Concrete Steps

1. `tests/test_make_video.py` と必要な既存テストにREDテストを追加する。
2. 追加テストを個別に実行し、期待通り失敗することを確認する。
3. `src/config/auto_repair_config.py`、`src/pipeline/make_video.py`、`src/repair/*` を追加し、`src/main.py` に `make-video` サブコマンドを追加する。
4. `src/pipeline/render_project.py` に任意 `render_dir` 引数を追加する。
5. `scripts/make-video.ps1` と `scripts/make-video.sh` を追加する。
6. `docs/make_video.md`、`docs/auto_repair.md`、`README.md` を更新する。
7. 追加テスト、全体pytest、Ruff check/format checkを実行する。
8. masterへpushする前に `git status` と `git diff --stat` で生成物が含まれていないことを確認する。

## Validation and Acceptance

以下を満たしたら受け入れとする。

- `.\.venv\Scripts\python.exe -m src.main make-video <project> --plan-only` が計画JSONを表示し、renderやPexels downloadを行わない。
- `.\.venv\Scripts\python.exe -m src.main make-video <project> --dry-run --skip-fetch-visuals` が `renders/<run_id>/inputs/`、`attempts/attempt_001/`、`final/`、`repair_log.json`、`failure_log.json`、`visual_assignment.json` を作る。
- `make-video` 実行中に `[make-video] attempt 1 started` などの進捗ログが標準出力へ出る。
- `--bgm-id` 未指定時のplanに `No One Here Gets In Alive - National Sweetheart` が既定候補として出る。
- `AUTOYOUTUBE_MAX_FIX_ATTEMPTS` が設定ファイルより優先される。
- `VIDEO_DURATION_TOO_LONG` warningだけでは失敗扱いにならない。
- `scripts/make-video.ps1 -ProjectPath <project>` がAivisSpeech readiness確認後にCLIを呼び出す。
- READMEに `make-video` と `upload-youtube` の使い方が載っている。
- `.\.venv\Scripts\python.exe -m ruff check .`、`.\.venv\Scripts\python.exe -m ruff format . --check`、`.\.venv\Scripts\python.exe -m pytest -q --basetemp .pytest_tmp` が通る。

## Idempotence and Recovery

`make-video` は元の `project.youtube.json` を直接書き換えない。run directoryは既存名と衝突した場合に `-2`、`-3` を付けて作るため、同じコマンドを繰り返しても既存結果を上書きしない。Pexels取得やinspectが失敗した場合はfailure logへ記録し、可能な範囲でrender/evaluateを続ける。generated media、Pexels assets、DB、tokens、secrets、rendersはcommitしない。

## Artifacts and Notes

実装後に、代表的なCLI出力、テスト結果、push先ブランチをここに追記する。

## Interfaces and Dependencies

`src.pipeline.make_video` に以下を定義する。

    @dataclass
    class MakeVideoOptions:
        project_path: Path
        visual_keywords: list[str]
        query_mode: str
        per_query: int | None
        max_downloads: int | None
        orientation: str
        size: str
        voice_mode: str
        video_mode: str
        aivis_base_url: str | None
        ffmpeg_path: str | None
        bgm_id: str | None
        seed: int | None
        auto_fix: bool
        max_fix_attempts: int | None
        plan_only: bool
        dry_run: bool
        skip_fetch_visuals: bool
        skip_inspect: bool
        skip_evaluate: bool

    def make_video(options: MakeVideoOptions) -> MakeVideoResult:
        ...

`src.main` は `make-video` サブコマンドを追加し、成功ならexit code 0、warningあり成功なら10、auto-fix上限なら20、非修正可能品質エラーなら30、環境エラーなら40、外部APIなら50、render失敗なら60、encodingなら70を返す。

## Plan Revision Notes

2026-07-04 / Codex: ユーザー設計書をもとに、既存CLIを合成する `make-video` とREADME更新の実装計画を追加した。
