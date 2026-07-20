# YouTube投稿後分析の成熟度・比較可能性強化 ExecPlan

## Purpose

`youtube-analytics-summary --days 28` を、Shorts の投稿後に同じ成熟度で比較できる分析へ拡張する。日次APIデータ、レンダー時の生成情報、`quality_report.json` を同じ動画単位で結び、断定できない場合は明示的に保留する。既存のCLI出力・`youtube_metrics_snapshots` の互換性を維持し、アップロードやバズ予測は追加しない。

## Progress checklist

- [x] 現行CLI、DB件数、投稿日、再生数、尺、品質レポートの実データを確認
- [ ] 日本時間ではなく YouTube Analytics の PT 日境界を扱う純粋な分析関数を追加
- [ ] D1/D3/D7/D28、遅延、±12時間フォールバック、視聴数・グループ閾値をテスト先行で実装
- [ ] `youtube_daily_metrics` と `render_quality_reports` を追加し、冪等upsert/hash dedupeを実装
- [ ] production features、中央値/IQRベースライン、仮説、決定論的提案を実装
- [ ] v2 JSON と既存キーを併記し、コンソール表示・エラー分類・CLI互換性を更新
- [x] 対象テスト、Ruff、認証が利用可能なら実CLIスモークを実行
- [ ] 全pytest（既存の別作業による3件の失敗を切り分け中）
- [ ] `rendered.youtube.json`、`quality_report.json`、DB行から提案までの証拠参照を確認

## Surprises & Discoveries

- 2026-07-20時点の実DBはアップロード47件に対し集計スナップショット9件で、全件が同日取得だった。
- 投稿は2026-07-09に17件、07-18に10件、07-19に20件。投稿後経過日数は約0.95〜11.01日で、D28を満たす動画は現時点では存在しない。
- 再生数は2〜888で、`>=500` は7件、`<100` は1件。実験グループは一回限りが多く、現状のままでは因果的な比較はできない。
- `render_subtitle_items` と `render_validation_messages` は現行DBで0件だが、レンダーJSON/品質レポートには情報があるため正規化取り込みが必要。
- `quality_report.json` は古い試行を含む可能性があるため、DBの有効な`render_id`とfinalパスを照合する。
- 実CLIでは47本中9本に集計値、日次24行、品質レポート48行、字幕514行を取り込みできた。D28完了は0本で、比較可能グループは0だった。
- 全pytestは141 passed / 3 failed。失敗は既存の`make_video`視覚リトライ・Geminiキーワード・Pexelsキーワードキャッシュの未コミット変更にあるテストで、今回の分析変更とは無関係。

## Decision Log

1. 成熟度は D1/D3/D7/D28 の4窓。YouTube Analytics準拠の `America/Los_Angeles` の暦日で判定し、投稿日の部分日を `launch_partial_day` として別集計する。
2. 成熟度許容誤差はスナップショットの最近傍を±12時間。APIの最終日から72時間以内は `pending_api_data`、72時間超で該当行なしは `api_no_data`。
3. 視聴数信頼度は `<100=insufficient`、`100-499=provisional`、`>=500=comparable`。0/nullを分母にした率は0ではなくnull。
4. 比較可能な最小グループ数は5。3〜4は`directional`、1〜2は`insufficient_group`とし、改善提案は5以上に限定する。
5. ベースラインは同テーマ+成熟度+尺バケット（5件以上）→チャンネル同成熟度+尺バケット→チャンネル同成熟度の順にフォールバックし、中央値とIQRを保存する。
6. 日次APIを基本とし、既取得範囲はDBキャッシュを利用する。直近72時間だけ再取得し、`data_through_date`を保持する。
7. `youtube_metrics_snapshots` は変更せず、`youtube_daily_metrics` と `render_quality_reports` を追加する。品質レポートはsha256で同一内容を重複登録しない。
8. 提案は完全ルールベース。LLMを使う場合も説明文・次の実験案だけに限定し、常に`review_required=true`とする。

## Outcomes & Retrospective

既存v1キーを壊さずv2スキーマを追加し、比較不能理由を出力できた。日次取得・品質取り込みは再実行しても行数が増えず、`render_quality_reports`のhash dedupeもfixtureで確認した。全pytestの3件は既存の別変更を直すと解消する見込みだが、スコープ外のため修正しない。

## Context and Orientation

- CLI入口: `src/main.py`
- 現行集計: `src/youtube/analytics_summary.py`
- DBスキーマ: `db/schema.sql`
- DBリポジトリ: `src/db/repositories.py`
- 品質出力: `src/quality/evaluator.py` が `final/quality_report.json` を生成
- 主なテスト: `tests/test_youtube_analytics_summary.py`, `tests/test_db_repositories.py`, `tests/test_cli_youtube.py`

## Plan of Work

1. 純粋関数（PT/DST、窓、遅延、閾値、尺バケット、中央値/IQR、仮説、提案）を先に追加し、fixtureでRED→GREENにする。
2. DBへ日次指標と品質レポートを追加し、既存のrender summaryから字幕・検証メッセージも冪等保存する。
3. API取得を日次・動画単位に拡張し、キャッシュ、直近72時間再取得、API列欠損・認証・クエリ失敗を分類する。
4. v2サマリーに成熟度、production features、ベースライン、仮説、観察、提案、データ品質、証拠参照を追加する。
5. コンソール表示とREADMEを更新し、既存のCLI引数・旧キー・既存テストを維持する。

## Concrete Steps

- `.agent/`の本計画を実装中に更新する。
- `src/youtube/analytics_analysis.py` を追加する。
- `db/schema.sql` と `src/db/repositories.py` を変更する。
- `src/youtube/analytics_summary.py` は追加機能を小さな関数へ分離し、既存のaggregate API経路をフォールバックとして残す。
- テストでは時刻を注入し、ネットワーク・認証に依存しないfixtureを使う。

## Validation and Acceptance

- PT/DST境界、D1/D3/D7/D28、±12時間、72時間遅延、視聴数3段階、グループ3段階、ベースラインフォールバック、尺バケット、日次upsert、品質hash dedupe、旧attempt除外をfixtureで検証。
- JSONが`youtube-analytics-summary-2.x`で、facts/interpretations/proposalsが混ざらず、既存v1キーも存在することを検証。
- `\.venv\Scripts\python.exe -m pytest tests/test_youtube_analytics_summary.py tests/test_youtube_analytics_analysis.py tests/test_db_repositories.py tests/test_cli_youtube.py`
- `\.venv\Scripts\python.exe -m ruff check src tests`
- `\.venv\Scripts\python.exe -m pytest`
- 認証情報がある場合のみ実CLIを実行し、秘密情報・DB・生成メディアをコミットしない。

## Idempotence and Recovery

日次行は動画・日付・レポート種別・dimensionsの一意キーでupsertし、品質レポートはrender_idとハッシュで再取り込み可能にする。API失敗は既存データを削除せず、`data_quality`のエラー分類として残す。v1出力を別ファイルへ退避する必要はなく、同じ出力パスを更新する。

## Artifacts and Notes

主な成果物は `youtube_daily_metrics`、`render_quality_reports`、`data/youtube_analytics_summary.json`、純粋分析モジュールとfixtureテスト。`rendered.youtube.json` と `quality_report.json` のパスまたはハッシュを証拠参照として出力する。

## Interfaces and Dependencies

YouTube Analytics APIの`day`ディメンションとPT日境界、既存SQLite接続、`zoneinfo`、標準JSON/hashlibを使う。LLM・外部検索・自動公開は必須依存にしない。
\n## Final Verification Notes

- `\\.venv\\Scripts\\python.exe -m ruff check src tests`: 通過。
- 分析関連および既存機能の除外テスト: 132件通過。
- 全pytest: 143件通過、3件失敗。失敗は既存の`make_video`リトライ/キーワード期待値2件とPexelsキーワードキャッシュ1件で、今回の分析変更外の未コミット差分に起因するため修正しない。
- 実CLI `youtube-analytics-summary --days 28`: 成功。47本中9本を集計、日次24行、品質48行、字幕514行を正規化し、同じCLIを再実行して行数増加なし。

## Completion Audit

- 品質レポートは`status/error_count/warning_count/info_count/metrics_json/checks_json/raw_report_json/quality_report_hash/source_path/imported_at`を保持する列へ移行し、既存48件をバックフィル済み。
- 成熟度、ビュー信頼度、グループ閾値、中央値/IQR、日次キャッシュ、±12時間フォールバック、スナップショット差分、制作特徴、根拠付き提案をJSONで検証済み。
- 全pytestは146件通過、Ruffも通過。実CLIは成功し、push前の最終差分確認へ進む。
