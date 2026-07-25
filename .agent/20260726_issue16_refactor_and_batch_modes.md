# Issue #16 リファクタリングと一括実行モード拡張 ExecPlan

このExecPlanは、リポジトリルートの`PLANS.md`に従う生きた実装計画である。`Progress`、`Surprises & Discoveries`、`Decision Log`、`Outcomes & Retrospective`は作業の各停止時点で更新する。

## Purpose / Big Picture

Issue #16で確認したとおり、動画生成・品質評価・分析の入口モジュールに、外部I/O、判断規則、JSON整形、表示が集中している。利用者が得る成果は、既存の`make-video`、`make-video-with-generated-intro`、`evaluate-render`、`youtube-analytics-summary`を同じ引数と出力契約のまま使い続けながら、個々の判断規則を独立テストできる構造になることである。さらに`run-upload-command-list.bat`から、通常の素材ワークフローと冒頭だけ生成AI素材を使うワークフローを同じコマンド一覧で混在実行できるようにする。

実装後は、`commands/upload_commands.txt`に`make-video.sh`と`make-video-with-generated-intro.sh`の行を混在させ、`scripts/run-upload-command-list.bat -DryRun`でそれぞれ対応するPowerShellラッパーへ翻訳されたログを確認できる。通常のCLI実行結果、`rendered.youtube.json`、`quality_report.json`、SQLiteの保存先とJSONフィールドは変更しない。

## Progress

- [x] (2026-07-26) Issue #16の本文を確認し、対象モジュール、受け入れ条件、`projects/`・`data/`固定の制約を特定した。
- [x] (2026-07-26) 現行の一括実行bat、PowerShellランナー、コマンド一覧、両動画ラッパーの引数差を確認した。
- [x] (2026-07-26) 低リスクな責務分割とバッチのモード識別方針を決定した。
- [x] (2026-07-26) 日本語の純粋なプロジェクト正規化・計画・修復ログ層を追加し、既存入口から委譲した。
- [x] (2026-07-26) renderの説明・クレジット・字幕・BGMメタデータ生成を純粋ビルダーへ分離した。
- [x] (2026-07-26) quality評価のドメイン別ディスパッチ境界とanalytics表示層を追加した。
- [x] (2026-07-26) 一括ランナーで通常動画と生成AIイントロ動画を混在実行できるようにし、回帰テストを追加した。
- [x] (2026-07-26) Ruff、pytest、PowerShellのDryRun、構成差分を検証した。コミットとpushはこの計画更新後に行う。

## Surprises & Discoveries

- 現行の`run-upload-command-list.ps1`は、コマンド行のプロジェクトパス以降の引数を解析しているが、先頭が`make-video.sh`であることを正規表現にハードコードしている。そのため生成AIイントロ用のシェル名を追加しても、現在はパス解析自体が失敗する。
- 生成AIイントロ用PowerShellラッパーは通常ラッパーとほぼ同じ引数を持つが、Pythonの入口が`src.main make-video`ではなく`src.generated_intro_main`であり、`GeneratedIntroPath`だけ追加で受け取る。コマンド翻訳ではこの差をラッパー選択に閉じ込め、他のオプション変換は共通化する。
- 既存の`trivia_slow_closing_door_001`入力はUTF-8 JSONとして不正な制御文字を含んでいたため、コマンド一覧の通常モード実例を、同じ目的で実行可能な`trivia_tempered_glass_shatter_001`へ置き換えた。`projects/`内のJSON自体は変更していない。
- `run-upload-command-list.bat`に既定`-CommandFile`を固定付与すると、利用者が別ファイルを指定した際にPowerShellの二重バインドになることが分かった。batは既定値を`run-upload-command-list.ps1`のパラメータへ委ね、カスタム一覧を受け付けるようにした。
- `make_video.py`のスキーマフォールバックは、入力JSONを書き換えず実行時のコピーだけを変更する仕様である。分離後もこの性質を保つ必要がある。

## Decision Log

- Decision: 最初のリファクタリングでは、公開関数の名前・引数、CLI名、JSON契約、DBパスを変えず、既存関数を新モジュールへ委譲する。
  Rationale: Issue #16の主目的は振る舞いを変えない保守性向上であり、既存の動画・分析出力を再生成する移行は不要だからである。
  Date/Author: 2026-07-26 / Codex
- Decision: プロジェクト正規化、修復ログ、renderメタデータ、analytics表示を優先して抽出し、巨大な品質チェック関数の全面移動はドメインディスパッチ境界の追加に留める。
  Rationale: 依存が少ない純粋処理から先に分離することで、外部APIやFFmpegを呼ばずに回帰を検証でき、データ構成を触らずにIssueの責務分割を実証できるからである。
  Date/Author: 2026-07-26 / Codex
- Decision: コマンド一覧の後方互換性のため、通常行は`make-video.sh`、生成AIイントロ行は`make-video-with-generated-intro.sh`として扱い、PowerShell側では対応するラッパーを選択する。省略時は通常ラッパーを使う。
  Rationale: 既存の一覧を壊さず、Linux由来のコマンド表記をWindowsの実行環境で安全に再利用できるからである。
  Date/Author: 2026-07-26 / Codex

## Outcomes & Retrospective

作業完了時に、抽出したモジュール、batの実行例、検証結果、残る技術的負債をここへ追記する。`projects/`または`data/`の構成差分が発生した場合は未達として扱い、生成物を削除・コミットせず原因を記録する。

2026-07-26時点では、純粋処理層と品質チェックの順序付きディスパッチを追加し、通常・生成AIイントロの両ラッパーを含む一時一覧で`-PlanOnly -DryRun -RequireUploadYoutube`を実行して、両方の翻訳と生成AI素材の解決を確認した。Ruffはエラー0件、pytestは164件成功、`git diff --check`も問題なしだった。ローカルの無視対象`commands/upload_commands.txt`には両モードの実例を置いたが、意図された一時入力ファイルのためコミット対象から除外する。

## Context and Orientation

`src/pipeline/make_video.py`は動画生成の高レベル入口で、プロジェクトJSONの検証、視覚素材取得、リトライ、修復ログ、最終成果物採用を一つのモジュールに持つ。`src/pipeline/render_project.py`は音声・字幕・説明・クレジット・BGM・FFmpeg実行・`rendered.youtube.json`保存を担当する。`src/quality/evaluator.py`は`quality_report.json`を作成し、ファイル、動画、音声、字幕、BGM、FFmpeg、視覚のチェックをまとめている。`src/youtube/analytics_summary.py`はYouTube API取得、DB同期、成熟度分析、推奨、コンソール表示を担当する。`scripts/run-upload-command-list.bat`はPowerShellの`run-upload-command-list.ps1`を呼び、`commands/upload_commands.txt`を順番に処理する。

ここでいう純粋ビルダーとは、入力辞書や値から文字列・辞書を作り、ファイルやネットワークへ書き込まない関数を指す。ドメイン別ディスパッチとは、品質チェックをファイル・動画・音声などの単位で列挙し、入口がその順序を管理する境界を指す。`projects/`は入力プロジェクトJSON、`data/`はDB・分析出力を含むため、本計画では移動、改名、再編成、マイグレーションを行わない。

## Plan of Work

まず`src/pipeline/project_normalization.py`にスキーマを読み、未知の`bgm.mood`を許可された`mysterious`へコピー上でフォールバックする処理、BGM上書き、視覚キーワード適用、クエリ重複排除を移す。`make_video.py`は互換名を保った委譲関数またはインポート別名だけを残し、高レベルのリトライループに集中させる。次に`src/repair/logs.py`へ修復・失敗ログの初期化、チェック要約、品質失敗整形、失敗カテゴリからの終了コード変換、JSON書き込みを移す。

続いて`src/pipeline/render_metadata.py`へ説明、クレジット、字幕ASS、BGMレンダー辞書の純粋生成を移し、`render_project.py`のI/O境界から呼び出す。`src/youtube/analytics_presentation.py`へコンソール行整形と数値表示を移し、`analytics_summary.py`から互換的に再エクスポートする。品質評価はチェック関数の実装を直ちに移動せず、`src/quality/check_groups.py`に順序付きドメイン実行関数を作り、`evaluate_render()`から呼ぶことで、各ドメインを個別に差し替え・テストできる境界を作る。

最後に`run-upload-command-list.ps1`のコマンド解析を、先頭スクリプト名から`make-video.ps1`または`make-video-with-generated-intro.ps1`を選ぶ構造に変更する。生成AIイントロ固有の`--generated-intro-path`もコマンドから安全に転送し、未指定時は既存同様にラッパー側の既定動作へ委ねる。`commands/upload_commands.txt`には実例として両モードを一行ずつ追加するが、実行時に外部APIやYouTubeへ送信するのはユーザーが明示的に実行した場合だけとする。

## Concrete Steps

作業ディレクトリは`C:\Users\Hodaka\Downloads\div\autoyoutube`とする。各実装単位で、先に回帰テストを追加し、対象テストを失敗させてから最小実装を入れる。

    .\.venv\Scripts\python.exe -m pytest tests\test_make_video.py -q
    .\.venv\Scripts\python.exe -m pytest tests\test_quality_evaluator.py tests\test_render_project_ffmpeg.py -q
    .\.venv\Scripts\python.exe -m pytest tests\test_youtube_analytics_summary.py tests\test_cli_youtube.py -q

バッチの検証は外部APIを呼ばないDryRunで行う。

    .\scripts\run-upload-command-list.bat -DryRun

ログに各行の翻訳先として`make-video.ps1`と`make-video-with-generated-intro.ps1`が表示され、`commands/upload_commands.txt`の各行が実行スキップされれば成功である。PowerShellのパースに失敗した場合は、コマンドファイルやログを修正し、DryRunを再実行する。

最終検証では、次をリポジトリルートで実行し、Ruffがエラー0件、pytestが失敗0件であることを確認する。

    .\.venv\Scripts\python.exe -m ruff check src tests
    .\.venv\Scripts\python.exe -m pytest -q
    git diff --check
    git status --short

最後の差分では`projects/`、`data/`、SQLite、生成メディア、`.env`、ダウンロード済み素材、render出力が変更・追跡対象になっていないことを確認する。

## Validation and Acceptance

通常動画と生成AIイントロ動画の既存単体テストが通り、未知のBGM moodフォールバック、説明・字幕・クレジットの文字列、品質レポートのstatus/checks、分析コンソールの行が以前と同じ値になることを検証する。CLIの公開名と引数が変わっていないことは`src/main.py`とPowerShellラッパーの差分で確認する。

一括実行については、DryRunログで通常行が`make-video.ps1`、生成AIイントロ行が`make-video-with-generated-intro.ps1`へ翻訳されること、`--upload-youtube`が両方へ渡ること、`-RequireUploadYoutube`が両方の行を受け入れることを確認する。実際のYouTubeアップロードはこの計画の自動受け入れ条件には含めず、既存の品質ゲートと人間確認を経た明示実行に限る。

## Idempotence and Recovery

新モジュールは既存の入力を読み取り、`projects/`・`data/`を変更しない。テストとDryRunは何度実行しても同じ結果になる。途中でテストが失敗した場合は、直前の小さな変更だけを修正し、生成されたログや一時成果物をコミットせず、再度対象テストから実行する。DBスキーマや保存先に触れないため、移行やバックアップは不要である。

## Artifacts and Notes

主な成果物は新しい`src/pipeline/project_normalization.py`、`src/repair/logs.py`、`src/pipeline/render_metadata.py`、`src/youtube/analytics_presentation.py`、`src/quality/check_groups.py`、回帰テスト、`scripts/run-upload-command-list.ps1`とコマンド一覧の差分である。生成された`quality_report.json`やrenderディレクトリは検証用に参照するだけで、Gitへ追加しない。

## Interfaces and Dependencies

新モジュールはPython標準ライブラリ、既存の`src.config.PROJECT_SCHEMA_PATH`、既存のJSONバリデータ、既存の品質チェック関数を利用する。公開互換性を保つため、`make_video()`、`render_project()`、`evaluate_render()`、`generate_youtube_analytics_summary()`、`format_console_summary()`の名前とシグネチャは変更しない。PowerShell側では`Invoke-ConvertedCommand`が選択したラッパーへ、共通引数と`--generated-intro-path`を同じ値で渡す。

## 変更履歴

- 2026-07-26: Issue #16本文、現行コード、バッチ実装を確認し、純粋処理の段階的抽出と2種類のラッパー選択方式を計画へ反映した。
- 2026-07-26: 正規化・修復ログ・renderメタデータ・品質チェック境界・analytics表示層と、batの2モード翻訳を実装し、単体・統合検証結果を記録した。
