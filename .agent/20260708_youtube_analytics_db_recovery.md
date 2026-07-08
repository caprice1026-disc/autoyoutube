# DB正本でproject JSONを復元し、YouTube Analyticsサマリーを追加する

この ExecPlan は生きた文書です。`Progress`、`Surprises & Discoveries`、`Decision Log`、`Outcomes & Retrospective` を作業に合わせて更新します。

`PLANS.md` と `AGENTS.md` に従い、この作業では `C:\Users\Hodaka\Downloads\div\autoyoutube` を作業ディレクトリとして扱います。`data/trivia_shorts.db` を正本として `projects/` の壊れた JSON を復元し、その上で YouTube Analytics API を使った動画サマリー CLI を追加します。最後に、ローカルのバッチ実行用コマンド列を現在の DB 内容に合わせて再生成し、実行確認まで行います。

## Purpose / Big Picture

この変更が入ると、`projects/` 配下の文字化けした `project.youtube.json` を DB の正しい内容で復元でき、`make-video` 系のバッチが壊れた JSON に引きずられずに動くようになります。さらに、すでに私的投稿された AutoYoutube の動画について、YouTube Analytics API から視聴回数や維持率などをまとめて取得し、ローカルにサマリー JSON と DB のスナップショットを残せるようになります。

利用者は、復元後の `project.youtube.json` をそのまま `validate-project` や `make-video` に渡せます。また、新しい `youtube-analytics-summary` コマンドを実行すると、対象動画の上位指標と、DB に保存された企画上の仮説を見比べられます。

## Progress

- [x] (2026-07-08 進行中) `projects/` と `data/trivia_shorts.db` の差分を調べ、壊れている JSON と欠損ファイルの範囲を把握した。
- [ ] DB の `raw_project_json` を使って、差分のある `projects/*/project.youtube.json` と欠損ファイルを復元する。
- [ ] `src/main.py`、`src/youtube/auth.py`、`src/youtube/*`、`src/db/repositories.py` に YouTube Analytics サマリー用の CLI と保存処理を追加する。
- [ ] ローカルのバッチ実行用 command list を DB 正本に合わせて再生成し、`scripts/run-upload-command-list.bat` を実行して確認する。
- [ ] `.gitignore`、`README.md` を更新し、`ruff` と `pytest` を通してから master に push する。

## Surprises & Discoveries

- Observation: `projects/` の 54 件を DB の `raw_project_json` と比較したところ、34 件が不一致、10 件が JSON として parse 不可、2 件が欠損だった。
  Evidence: `trivia_elevator_mirror_001` や `trivia_surgical_gown_001` は `Expecting ',' delimiter` で parse 失敗し、`trivia_qr_error_correction_001` や `trivia_pet_bottle_base_001` は DB とファイルの title が異なっていた。
- Observation: `youtube_uploads` と `youtube_metrics_snapshots` は空だった。
  Evidence: `select count(*)` でどちらも 0 件だった。
- Observation: `renders/**/final/rendered.youtube.json` には `uploaded_private` の video id が多数残っていた。
  Evidence: `trivia_qr_error_correction_001` などは render JSON 側に `youtube_video_id` があり、DB 側にはまだ移送されていない。
- Observation: `commands/upload_commands.txt` は git で追跡されていない local ファイルで、しかも root の 7 行は DB に存在しない古い project id を指していた。
  Evidence: `trivia_ballpoint_pen_ball_001` など 7 件が `youtube_projects` に存在しない。

## Decision Log

- Decision: `projects/` の内容は手で直さず、`data/trivia_shorts.db` の `raw_project_json` を正として復元する。
  Rationale: ユーザーが DB を正本にしたいと明言しており、DB の JSON は現行の構造と整合しているため。
  Date/Author: 2026-07-08 / Codex

- Decision: YouTube Analytics の取得結果は、まず CLI のサマリーとして出し、同時に `youtube_metrics_snapshots` へ UPSERT する。
  Rationale: 画面で確認できる出力と、後から再集計できる永続化の両方が必要だから。
  Date/Author: 2026-07-08 / Codex

- Decision: `youtube_uploads` が空でも分析できるよう、分析対象の動画は `renders/**/final/rendered.youtube.json` から回収し、将来的には uploader 側で DB を埋める余地を残す。
  Rationale: 既存の公開済み動画をすぐ分析したい一方で、既存データの移送が未完了でも止まらないようにするため。
  Date/Author: 2026-07-08 / Codex

- Decision: ローカルの `commands/upload_commands.txt` は再生成するが、`commands/` 配下が gitignore されている前提は崩さない。
  Rationale: バッチ実行には必要だが、リポジトリの恒久的な変更としては扱わないほうが安全だから。
  Date/Author: 2026-07-08 / Codex

## Outcomes & Retrospective

未完了。作業後に、どのファイルを DB から復元したか、Analytics CLI が何を出力するようになったか、バッチ実行がどこまで進んだかをここにまとめる。

## Context and Orientation

このリポジトリでは、動画企画の正本は SQLite DB `data/trivia_shorts.db` にあり、`youtube_projects.raw_project_json` に元の `project.youtube.json` が JSON 文字列で保存されています。`projects/` 配下には同名の JSON ファイルがありますが、一部は文字化けや構文崩れで DB と一致しません。今回の復元対象は、DB に存在する project id の JSON です。

YouTube 関連のコードは `src/youtube/auth.py`、`src/youtube/uploader.py`、`src/main.py` にあります。`src/main.py` は CLI の入口で、ここに新しい YouTube Analytics コマンドを追加します。`src/db/repositories.py` は SQLite への保存処理をまとめているので、Analytics スナップショットの UPSERT もここに寄せます。`db/schema.sql` には `youtube_uploads` と `youtube_metrics_snapshots` が既に定義されています。

`renders/**/final/rendered.youtube.json` には、私的投稿済み動画の `youtube_video_id` と `youtube_url` が残っています。`youtube_uploads` が空でも、この JSON を読めば分析対象を回収できます。

`commands/upload_commands.txt` は root の local バッチ入力で、git には入れません。`scripts/run-upload-command-list.ps1` がこのファイルを読み、`scripts/make-video.ps1` へ変換して実行します。

## Plan of Work

まず、DB と不一致な `projects/*/project.youtube.json` を DB の `raw_project_json` で上書きします。JSON として壊れているファイルは、壊れた内容を手で直すのではなく、DB からそのまま再生成します。欠損している DB-backed の `project.youtube.json` もこの段階で再作成します。

次に、YouTube Analytics API でチャンネル `MINE` の動画別データを取得する CLI を追加します。`src/youtube/auth.py` には Analytics 用の service builder を加え、`src/main.py` には `youtube-analytics-summary` のサブコマンドを追加します。分析対象は DB か render JSON から回収した `uploaded_private` の video id に限定し、`views`、`likes`、`comments`、`shares`、`estimatedMinutesWatched`、`averageViewDuration`、`averageViewPercentage`、`subscribersGained`、`engagedViews` をまとめて取得します。

取得結果は、1) 端末に人間が読みやすいサマリーを表示し、2) `data/youtube_analytics_summary.json` のようなローカル JSON に保存し、3) `youtube_metrics_snapshots` に UPSERT します。ここでは、各 video id ごとに `snapshot_date` を 1 日単位で固定し、同じ日付で再実行した場合は更新されるようにします。

その後、DB 正本に合わせたローカルの command list を作り直します。古い project id を指している行は削除し、現在の DB に存在する project id を使う行へ置き換えます。必要なら `--per-query` と `--max-downloads` は 3/18 を基本にして、既存の project JSON の意図に合わせて調整します。

最後に、`.gitignore` と `README.md` を整え、`ruff` と `pytest` を通してから、master へ push します。

## Concrete Steps

1. 作業ディレクトリは `C:\Users\Hodaka\Downloads\div\autoyoutube` に固定する。

   期待する確認:

       PS> Get-Location
       Path
       ----
       C:\Users\Hodaka\Downloads\div\autoyoutube

2. `data/trivia_shorts.db` の `raw_project_json` から、DB と不一致な `projects/*/project.youtube.json` を上書きする。

   期待する確認:

       restored: 34
       recreated: 1
       skipped: 8

3. 代表的な project JSON に対して `validate-project` を実行し、復元が成功したことを確認する。

   例:

       .\.venv\Scripts\python.exe -m src.main validate-project projects\trivia_qr_error_correction_001\project.youtube.json

   期待する出力:

       project JSON validation succeeded: projects\trivia_qr_error_correction_001\project.youtube.json

4. `src/youtube/auth.py` と `src/main.py` に Analytics 用の CLI を追加し、`tests/test_cli_youtube.py` か新規テストでコマンドの呼び出しを検証する。

5. `src/db/repositories.py` に Analytics スナップショット保存用の helper を追加する。必要なら `youtube_uploads` の保存もここに寄せる。

6. `README.md` に `youtube-analytics-summary` の使い方と、`projects/` は DB から復元する前提であることを追記する。`.gitignore` に `AivisSpeech/` を追加する。

7. local の `commands/upload_commands.txt` を DB 正本に合わせて再生成する。これは gitignore 対象のため、実行確認用の作業ファイルとして扱う。

8. `scripts/run-upload-command-list.bat -DryRun` で翻訳されたコマンドを確認し、その後で実行する。

   期待する出力の例:

       [runner] command file: ...
       [runner] commands: 8
       [runner] dry-run mode. commands will not be executed.

9. `.\.venv\Scripts\python.exe -m ruff check .` と `.\.venv\Scripts\python.exe -m pytest -q --basetemp .pytest_tmp` を実行する。

10. 変更を確認し、`git add` で意図したファイルのみを stage して commit し、`git push -u origin master` を実行する。

## Validation and Acceptance

次の条件を満たしたら完了とみなします。

- `projects/` の DB-backed JSON が parse でき、少なくとも不一致だった代表ファイルが DB と同じ内容になっている。
- `youtube-analytics-summary` を実行すると、少なくとも 1 件以上の uploaded video を分析し、端末に summary を表示し、`data/youtube_analytics_summary.json` と `youtube_metrics_snapshots` の両方が更新される。
- `scripts/run-upload-command-list.bat` が local の command list を解釈でき、壊れた project id で停止しない。
- `ruff check .` と `pytest -q --basetemp .pytest_tmp` が通る。
- README に新しい Analytics コマンドと DB 正本の扱いが書かれている。

## Idempotence and Recovery

DB から `projects/` を再生成する処理は上書き型でよく、同じスクリプトを何度実行しても最終結果は同じになります。`youtube_metrics_snapshots` は `(youtube_video_id, snapshot_date)` に対する UPSERT にして、同日の再実行でも重複しないようにします。

もし Analytics API の呼び出しに失敗したら、まず `youtube-auth` を再実行して OAuth token を確認し、次に同じ `youtube-analytics-summary` を再実行します。DB は更新前の状態を維持するか、同日 UPSERT で上書きされるだけにします。

local の `commands/upload_commands.txt` は gitignore 対象なので、壊れても DB から再生成すれば戻せます。

## Artifacts and Notes

作業中に残すべき主な成果物は次のとおりです。

- `data/youtube_analytics_summary.json`
- `logs/upload-command-runner/run_*.log`
- `youtube_metrics_snapshots` の追加行
- 直した `projects/*/project.youtube.json`
- 更新した `README.md` と `.gitignore`

## Interfaces and Dependencies

`src/youtube/auth.py` には、既存の upload 用 builder に加えて Analytics 用 builder を追加します。最終的に次の関数が存在することを期待します。

    def build_youtube_analytics_service(
        *,
        client_secrets_path: Path = Path("secrets/client_secret.json"),
        token_path: Path = Path("data/youtube_token.json"),
    ) -> Any:

`src/main.py` には、少なくとも次のサブコマンドが必要です。

    youtube-analytics-summary

`src/db/repositories.py` には、Analytics スナップショットを保存する helper が必要です。

    def upsert_youtube_metrics_snapshots(
        connection: sqlite3.Connection,
        snapshots: list[dict[str, Any]],
    ) -> None:

必要なら、`youtube_uploads` の保存も同じモジュールにまとめます。

この計画の変更理由: 2026-07-08 時点で `projects/` の一部が DB と不一致かつ一部は JSON として壊れていることが分かったため、当初の「個別修正」ではなく「DB からの再生成」を中核にした。
