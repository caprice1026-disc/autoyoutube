# upload_commands.txt の失敗修正と全件プライベート公開

この ExecPlan は生きた計画書であり、リポジトリ直下の `PLANS.md` に従って更新する。`Progress`、`Surprises & Discoveries`、`Decision Log`、`Outcomes & Retrospective` は作業の進行に合わせて事実を記録する。

## Purpose / Big Picture

`commands/upload_commands.txt` の9件を同じワークフローで実行し、失敗しているプロジェクトもレンダー品質を確認したうえで YouTube に非公開でアップロードできる状態にする。今回の失敗はランナーのコマンド変換ではなく、6つのプロジェクトJSONで `visual_strategy.avoid_keywords` がスキーマ上限20件を超えていることが原因である。修正後は `validate-project` の成功、既存成功3件のアップロード記録、残り6件の `uploaded_private` 記録を確認する。

## Progress

- [x] (2026-07-27 20:00 JST) 既存ランナーを実行し、9件中3件が完了、6件が exit code 1 になることを再現した。
- [x] (2026-07-27 20:01 JST) 6件の失敗を `validate-project` で再実行し、`avoid_keywords` の `maxItems=20` 超過を根本原因として特定した。
- [x] (2026-07-27 20:02 JST) 既存成功3件の最終rendered JSONが `rendered_json_valid=true`、検証エラー0件、YouTube状態 `uploaded_private` であることを確認した。
- [x] (2026-07-27 20:03 JST) 失敗6件の `avoid_keywords` を20件以内に修正し、6件すべてを `validate-project` で通した。
- [x] (2026-07-27 20:26 JST) 修正後の6件を既存コマンドと同じPowerShellラッパーで実行し、6件すべてをレンダー・品質評価・非公開アップロードまで完了した。
- [x] (2026-07-27 20:31 JST) 9件すべてについて成功・品質・非公開アップロードURLを照合し、Ruffとpytestも完了した。

## Surprises & Discoveries

- Observation: ランナーは9件を最後まで継続したが、子プロセスの詳細エラーをランナーログへ保存していなかった。
  Evidence: `logs/upload-command-runner/run_20260727_194738.log` では6件が `failed with exit code: 1` までで、単体 `validate-project` を実行すると具体的なスキーマエラーが表示された。
- Observation: 失敗6件はレンダー開始前に止まっており、`renders/` に今回の失敗用出力は作られていなかった。
  Evidence: 各JSONの検証結果は `$.visual_strategy.avoid_keywords` が21〜26件で `expected=20` だった。
- Observation: 既存成功3件は警告付きのものもあるが、現時点の最終JSONでは検証エラーがなく、警告数は品質レポートで個別確認できる。
  Evidence: `202607271947`、`202607271950`、`202607271952` の `final/rendered.youtube.json` は `rendered_json_valid=True`、`validation.errors` 空、`youtube.upload.status=uploaded_private` だった。
- Observation: 修正後6件はすべて `success_with_warnings` だったが、品質レポートのエラー数は0で、警告は字幕の3行表示だけだった。
  Evidence: 6件の `final/quality_report.json` で `summary.error_count=0`。警告コードは `SUBTITLE_TOO_MANY_LINES` で、`SAME_ASSET_REUSED`、`SAME_SOURCE_REUSED`、`VIDEO_DURATION_TOO_LONG` は確認されなかった。
- Observation: スプレー缶動画のPexels取得は失敗したが、`make-video` のローカル素材フォールバックでレンダーと非公開アップロードが完了した。
  Evidence: 実行出力に `visual fetch failed; continuing with local stock`、続いてYouTube動画ID `Bu2Czb5xujM` が出力された。

## Decision Log

- Decision: ランナーやアップロードAPIを変更せず、失敗原因である6つのプロジェクトJSONの超過キーワードだけを修正する。
  Rationale: 同じランナーで3件は既に実行できており、6件すべての失敗は同一の入力スキーマ違反だったため、最小変更で再発条件を除去できる。
  Date/Author: 2026-07-27 / Codex
- Decision: 既に `uploaded_private` の3件は再アップロードせず、残り6件だけを再実行する。
  Rationale: 全9件を無条件に再実行すると、成功済み動画の重複アップロードを作るため。9件の完了条件は既存3件と修正後6件を合算して確認する。
  Date/Author: 2026-07-27 / Codex
- Decision: YouTubeの公開状態は既存コマンドの `-UploadYoutube` に従い、常に `private` とする。
  Rationale: リポジトリの公開ガードレールとプライベート公開ワークフローに従い、公開・限定公開へ変更しない。
  Date/Author: 2026-07-27 / Codex

## Outcomes & Retrospective

作業完了時に、修正したファイル、9件の品質レポート、YouTubeの非公開動画IDまたはURL、テスト結果、警告と人手確認事項をここへ追記する。未完了の場合は、外部API・認証・品質ゲートなど具体的な停止理由を記録する。

2026-07-27の実績: 失敗6件の入力JSONを修正し、9件すべてが `uploaded_private` になった。動画IDは、メジャー `KoL4VMKu0xU`、ボールペン `zlTlosvy0HU`、ワイパー `kLvMQyvIJnM`、スプレー缶 `Bu2Czb5xujM`、エレベーター `S6As3DHWgxg`、蛇口 `xVrvNj_lRls`、レール `LL-yR0c04Nw`、橋 `k73kCbZSJEg`、自動ドア `XZY3T7r0Qoc` である。9件とも `rendered_json_valid=true`、検証エラー0件、品質エラー0件だった。警告は字幕の3行表示のみで、人手による最終映像確認は引き続き必要である。全プロジェクト検証、ランナーDryRun 9/9、Ruff、pytest `164 passed` を確認した。

## Context and Orientation

作業ディレクトリは `C:\Users\Hodaka\Downloads\div\autoyoutube` である。`commands/upload_commands.txt` は9件のPowerShellコマンドを持ち、`scripts/run-upload-command-list.bat` が `scripts/run-upload-command-list.ps1` を呼ぶ。後者は各行を読み、`scripts/make-video.ps1` または `scripts/make-video-with-generated-intro.ps1` に変換する。各ラッパーは `.venv\Scripts\python.exe` で `src.main make-video` または `src.generated_intro_main` を起動する。

`make-video` は最初に `schemas/project.youtube.schema.json` で入力JSONを検証し、成功後にPexels素材、AivisSpeech音声、FFmpeg動画、`quality_report.json`、`rendered.youtube.json` を生成する。今回のエラーはこの最初の入力検証で発生するため、入力JSONの `visual_strategy.avoid_keywords` を20件以内にすることが修正点になる。アップロード前には品質レポートのエラー0件、`rendered.validation.errors` 空、`rendered.validation.rendered_json_valid=true`、重複素材や長すぎる動画のブロッカーなしを確認する。

## Plan of Work

まず失敗6件の `projects/<id>/project.youtube.json` を編集し、各 `avoid_keywords` の末尾にある一般的・重複的な項目を削除して、既存の重要な除外条件を先頭から20件残す。編集後に6件すべてへ `validate-project` を実行する。

次に既存の成功3件を再アップロードせず、失敗していた6件だけを `scripts/run-upload-command-list.ps1` の個別コマンド形式で実行する。各コマンドは現在の `commands/upload_commands.txt` と同じ引数、`-UploadYoutube`、既定のBGM、AivisSpeech、FFmpegを使う。失敗した場合はそのプロジェクトの標準出力・`failure_log.json`・`quality_report.json`を確認し、品質ブロッカー、環境エラー、外部APIエラーを分離して最小限の追加対応を行う。

最後に `renders/**/final/rendered.youtube.json` と対応する `quality_report.json` をプロジェクトIDごとに読み、9件の結果を集計する。非公開アップロード済みでない、検証エラーがある、品質エラーがある動画は完了扱いにしない。

## Concrete Steps

作業ディレクトリ `C:\Users\Hodaka\Downloads\div\autoyoutube` で次を実行する。

    .\.venv\Scripts\python.exe -m src.main validate-project projects\<project_id>\project.youtube.json

6件すべてで `Project JSON is valid` 相当の成功終了を確認する。その後、失敗6件のコマンドを同じPowerShellラッパーで順に実行する。成功時はランナーの `done` または `done with warnings` と、対象プロジェクトの `final/rendered.youtube.json` を確認する。

    .\scripts\make-video-with-generated-intro.ps1 -ProjectPath "projects\trivia_windshield_wiper_linkage_001\project.youtube.json" -PerQuery 6 -MaxDownloads 48 -UploadYoutube
    .\scripts\make-video-with-generated-intro.ps1 -ProjectPath "projects\trivia_aerosol_spray_atomization_001\project.youtube.json" -PerQuery 6 -MaxDownloads 48 -UploadYoutube
    .\scripts\make-video.ps1 -ProjectPath "projects\trivia_elevator_door_safety_sensor_001\project.youtube.json" -PerQuery 6 -MaxDownloads 48 -UploadYoutube
    .\scripts\make-video.ps1 -ProjectPath "projects\trivia_rail_expansion_joint_gap_001\project.youtube.json" -PerQuery 6 -MaxDownloads 48 -UploadYoutube
    .\scripts\make-video.ps1 -ProjectPath "projects\trivia_bridge_expansion_joint_001\project.youtube.json" -PerQuery 6 -MaxDownloads 48 -UploadYoutube
    .\scripts\make-video.ps1 -ProjectPath "projects\trivia_automatic_door_sensor_001\project.youtube.json" -PerQuery 6 -MaxDownloads 48 -UploadYoutube

全件後に、`.venv\Scripts\python.exe -m pytest -q` と `\.venv\Scripts\ruff.exe check .` を実行する。入力JSONの修正だけでコードが変わらない場合でも、リポジトリの完了条件としてテストとRuffの結果を記録する。

## Validation and Acceptance

受け入れ条件は、6つの修正JSONがスキーマ検証を通り、6件のレンダーが完了し、品質レポートの `summary.error_count` が0で、検証エラーが空であること、そして9件すべての `youtube.upload.status` が `uploaded_private` になることである。警告が残る場合は、警告コードを記録し、動画の長さ超過・素材重複・検証不備が含まれる場合は成功扱いにしない。

## Idempotence and Recovery

入力JSONのキーワード削減と `validate-project` は何度実行しても結果が変わらない。成功済み3件は再実行しない。6件の途中失敗は、最後に作られた `renders/<run_id>/failure_log.json` と `quality_report.json` を調べて対象プロジェクトだけを再実行する。YouTubeアップロードが完了した後に同じコマンドを再実行すると重複動画になるため、再試行前に `rendered.youtube.json` の `youtube.upload.status` と動画IDを確認する。

## Artifacts and Notes

主な証拠は `logs/upload-command-runner/run_*.log`、各最終レンダーの `final/quality_report.json`、`final/rendered.youtube.json`、および6つの修正済み `project.youtube.json` である。生成動画、Pexels素材、DB、OAuthトークン、`.env` はコミットしない。

## Interfaces and Dependencies

Pythonは必ずリポジトリの `.venv\Scripts\python.exe` を使う。動画の音声はローカルAivisSpeech Engine (`http://127.0.0.1:10101`)、動画合成はFFmpeg、視覚素材は既存のPexels設定、YouTubeアップロードは `secrets\client_secret.json` と `data\youtube_token.json` を利用する。アップロード処理は `src.youtube.uploader.upload_private_video` を通じて非公開状態で行われる。

## Plan Revision Notes

2026-07-27 / Codex: 直近の9件バッチ実行と6件の単体 `validate-project` の証拠を反映し、ランナー変更ではなく入力JSONの最小修正と、既存成功3件を再アップロードしない回復手順を決定した。
