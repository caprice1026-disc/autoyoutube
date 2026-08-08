# 認証済みYouTube Analyticsによる二期間評価

このExecPlanは生きた文書である。進捗、発見、判断、結果は作業に合わせて更新する。リポジトリ直下の`PLANS.md`に従い、作業ディレクトリは`C:\Users\Hodaka\Downloads\div\autoyoutube`とする。

## Purpose / Big Picture

認証済みのYouTube Analytics APIを使い、直近28日とチャンネルの全履歴を同じ指標で再取得する。利用者は、単なる再生数順位ではなく、成熟度がそろった動画の保持率、視聴あたりの反応、実験グループ別の標本数、データ欠損を一つのJSONとMarkdownレポートで確認できる。

## Progress

- [x] (2026-08-04 JST) 既存の`youtube-analytics-summary`、SQLiteスナップショット、成熟度比較、テストを確認した。
- [x] (2026-08-04 JST) ユーザーが直近28日と全履歴の両方を実行する方針を指定した。
- [x] (2026-08-04 JST) 評価器の失敗テストを追加し、未実装モジュールで`ModuleNotFoundError`になることを確認した。
- [x] (2026-08-04 JST) 二期間の認証済み取得を行うCLIと、集計評価器を実装した。
- [x] (2026-08-04 JST) 認証情報で二期間の取得・評価を実行し、JSONとMarkdownを出力した。
- [x] (2026-08-04 JST) Ruff、対象テスト、全テストで検証した。

## Surprises & Discoveries

- Observation: 既存サマリーはD1/D3/D7/D28の成熟度と実験グループ別標本数を持つが、二期間を横断して要約する専用成果物はない。
  Evidence: `src/youtube/analytics_summary.py`の`build_summary`は1期間の`summary`を返し、`src/main.py`は`youtube-analytics-summary`だけを公開している。
- Observation: 既存の動画比較は標本不足を明示し、因果関係を主張しない。
  Evidence: `hypothesis_status`とrecommendationの`limitations`が相関に基づく観察であることを記録する。

## Decision Log

- Decision: API取得は既存の`generate_youtube_analytics_summary`を再利用し、新しい評価器は生成済みサマリーを純粋に集計する。
  Rationale: OAuth、APIエラー処理、SQLiteへの日次スナップショット保存を二重実装せず、評価ロジックをAPIなしでテストできるため。
  Date/Author: 2026-08-04 / Codex
- Decision: 全履歴取得の既定期間は3,650日とする。
  Rationale: チャンネル開始日を別途推測せず、YouTube APIが返す利用可能期間をすべて含めるため。直近28日とは別ファイルに保存する。
  Date/Author: 2026-08-04 / Codex
- Decision: 主要比較は、D1/D3/D7/D28の`complete`又は`snapshot_fallback`かつ視聴数が比較可能な動画だけに限定する。
  Rationale: 投稿直後と成熟済み動画を混ぜること、少数再生の極端な維持率を結論に使うことを避けるため。
  Date/Author: 2026-08-04 / Codex

## Outcomes & Retrospective

`youtube-analytics-evaluate --recent-days 28 --history-days 3650`を認証済みトークンで実行した。直近28日は2026-07-08から2026-08-04、全履歴は2016-08-07から2026-08-04を取得対象にした。両期間とも96動画、52,989再生、加重平均視聴率44.79%、加重平均視聴時間18.59秒だった。チャンネルの計上済み視聴は直近28日に集中しており、全履歴に追加の過去視聴は確認されなかった。

2026-08-09 JSTに同じコマンドで再評価した。直近28日は2026-07-12から2026-08-08、96動画、56,121再生、加重平均視聴率45.07%、平均視聴時間18.01秒となった。全履歴は2016-08-11から2026-08-08、96動画、60,534再生、加重平均視聴率43.64%、平均視聴時間18.00秒となった。指標欠損は17本、API反映待ちは7本に減少した。D1で比較可能な群は生成AIイントロがn=3/45.49%、通常イントロがn=3/53.84%、D3では通常イントロの2群がn=3/44.35%とn=3/37.99%だった。いずれも題材・投稿時期が統制されていないため因果結論には使わない。

比較可能な動画は35本だった。D1では`generated_intro_20260729_everyday_mechanics`がn=3、視聴率45.51%、`stock_only_20260730_everyday_mechanics`がn=3、視聴率53.82%だった。D3では`generated_intro_20260730_nonstock_internal_mechanics`がn=4、視聴率38.30%だった。題材や投稿時期の統制が十分ではないため、いずれも因果関係の結論には使用しない。28本の指標欠損、20本のAPI反映待ち、D1/D3/D7の多数の少標本グループをレポートに明示した。

追加テストは初めに`ModuleNotFoundError`、次に未集約の標本不足文言で期待どおり失敗した。実装後は対象テスト6件が成功し、`ruff check .`成功、`pytest -q`は173 passedだった。

## Context and Orientation

`src/main.py`はCLIの入口である。`youtube-analytics-summary`は`src/youtube/analytics_summary.py`の`generate_youtube_analytics_summary`を呼び、`secrets/client_secret.json`と`data/youtube_token.json`を使ってAnalytics APIへ接続する。取得した動画別の値はSQLiteの`youtube_metrics_snapshots`と`youtube_daily_metrics`へ保存され、JSONサマリーにまとめられる。

新しい`src/youtube/analytics_evaluation.py`はネットワークへ接続しない純粋な評価器とする。入力は28日版と全履歴版のサマリー辞書であり、出力は期間別の合計、加重平均、成熟度別の比較可能件数、実験グループ別の指標、データ品質の制約を含む辞書である。`src/main.py`の新コマンドが既存取得器を二度呼んでから評価器へ渡す。Markdownは評価JSONから生成し、人間が数値と制約を読める形にする。

## Plan of Work

最初に`tests/test_youtube_analytics_evaluation.py`へ、二期間の小さなサマリーを与えたときに、期間ラベル、成熟度がそろった実験グループの標本数、加重保持率、視聴あたりの高評価率、比較不能理由が返るテストを書く。未実装モジュールのためテストはImportErrorで失敗する。

次に`src/youtube/analytics_evaluation.py`を作る。`build_dual_period_evaluation(recent_summary, history_summary)`は各サマリーを`recent_28_days`と`all_history`として評価する。各動画の`maturity_windows`から比較可能なD1/D3/D7/D28を取り出し、`experiment_group`で集計する。視聴数を重みとした平均視聴率と平均視聴時間、視聴あたりの高評価・コメント・共有・登録率を返す。標本数が3未満、又は比較可能な視聴がない群は結論ではなく制約として出力する。`format_evaluation_markdown`は結論、両期間の集計、グループ表、制約を日本語で出力する。

その後、`src/main.py`に`youtube-analytics-evaluate`を追加する。`--recent-days`は28、`--history-days`は3650、OAuthのclient secretとtokenのパス、期間別サマリー出力先、評価JSON出力先、Markdown出力先を受け取る。既存の`_youtube_analytics_summary`相当の生成関数を二度呼び、評価JSONとMarkdownをUTF-8で保存し、主要結果を標準出力に表示する。

最後に本物の認証情報を使ってコマンドを実行する。出力は`data/youtube_analytics_summary_28d.json`、`data/youtube_analytics_summary_all.json`、`data/youtube_analytics_evaluation.json`、`data/youtube_analytics_evaluation.md`に置く。これらはローカル分析成果物でありコミットしない。

## Concrete Steps

リポジトリ直下で次を実行する。

    .\.venv\Scripts\python.exe -m pytest tests/test_youtube_analytics_evaluation.py -q
    .\.venv\Scripts\python.exe -m src.main youtube-analytics-evaluate --recent-days 28 --history-days 3650
    .\.venv\Scripts\python.exe -m ruff check .
    .\.venv\Scripts\python.exe -m pytest -q

成功時のCLIは、各期間のファイル名、対象動画数、比較可能な成熟度別件数、実験グループ数、結論が保留である場合の理由を表示する。

## Validation and Acceptance

受け入れ条件は、純粋な評価器のテストで二期間の集計と標本不足表示が検証されること、認証済みCLIが二つの期間別サマリーと二つの評価成果物をUTF-8で作ること、期間別データ品質をMarkdownで確認できること、Ruffと全pytestが通ることである。実験グループに十分な標本がない場合も、値を作らず`insufficient_group`又は欠損理由を報告する。

## Idempotence and Recovery

同じCLIはJSONとMarkdownを同じパスに安全に上書きし、Analyticsのスナップショットは既存のupsertで更新する。認証失敗又はAPI遅延時は既存サマリーが構造化されたエラーを記録するため、評価器は取得済みのキャッシュを使ってJSONを出力する。トークン、client secret、SQLite、render成果物はコミットしない。

## Interfaces and Dependencies

`src/youtube/analytics_evaluation.py`は以下を提供する。

    def build_dual_period_evaluation(recent_summary: dict[str, Any], history_summary: dict[str, Any]) -> dict[str, Any]
    def format_evaluation_markdown(evaluation: dict[str, Any]) -> str

`src/main.py`は`youtube-analytics-evaluate`サブコマンドを提供し、`generate_youtube_analytics_summary(days=..., client_secrets_path=..., token_path=..., output_path=...)`を二度呼ぶ。追加依存ライブラリは使わない。

## Plan Revision Notes

2026-08-04 / Codex: ユーザー指定により、直近28日と全履歴の両方を同一実装で評価する範囲へ確定した。
