# 直近28日Analyticsに基づく第2回10本Shortsイントロ実験

このExecPlanは `PLANS.md` に従い、実行中も更新する。作業場所は `C:\Users\Hodaka\Downloads\div\autoyoutube`。

## Purpose / Big Picture

直近28日のYouTube Analyticsを再取得し、日用品・身近な機構という高保持率の傾向を引き継いだ10本を制作する。5本は通常のストック映像だけで品質ゲートを通した後にprivate投稿する。残り5本は生成AIイントロを先頭に合成するための入力定義と投稿コマンドだけを用意し、実行は各プロジェクトに `generated_intro.mp4` が置かれた後に限定する。

## Progress

- [x] (2026-07-30) `youtube-analytics-summary --days 28` を実行し、46/76本、33,752再生、加重平均視聴率42.83%、比較可能なactionable group=0を確認した。
- [x] (2026-07-30) PexelsとAivisSpeechの利用可能性を確認した。Docker Desktop停止によりAivisSpeechが未待受だったため、デーモンとコンテナ起動後に `/speakers` の応答を確認した。
- [x] 新規のストック映像5本・生成AIイントロ5本のJSONをスキーマ検証した（10/10）。
- [x] ストック映像5本をレンダリング、品質ゲート、private投稿した。
- [x] 生成AIイントロ5本だけを `commands/upload_commands.txt` に登録し、DryRunで5/5を確認した。
- [x] 生成物と投稿結果を再検証した。Ruffは成功、pytestは166 passed。

## Decision Log

- Decision: 主評価指標は `average_view_percentage` とし、同じ日用品・小型機構の領域でストック映像群と生成AIイントロ群を分ける。
  Rationale: 直近の保持率上位には橋の伸縮装置、マンホール、レール継ぎ目、ホチキス、電子レンジが含まれる一方、条件間の比較可能な群はまだないため、因果結論ではなく追加標本として設計する。
  Date/Author: 2026-07-30 / Codex
- Decision: 生成AIイントロ群のMP4未配置時はコマンドを実行しない。
  Rationale: パイプラインは入力がないとストック映像へフォールバックするため、対照条件を守れなくなる。
  Date/Author: 2026-07-30 / Codex
- Decision: 生成AIイントロ群の題材は、ストックサイトで代替しにくい内部断面・不可視の流れ・極端な接写だけを冒頭で見せるものにする。
  Rationale: 生成AIを使う理由が明確になり、通常のストック映像群との条件差を保てる。
  Date/Author: 2026-07-30 / Codex

## Concrete Steps

1. `projects/<id>/project.youtube.json` を10本分作り、全件に独自ID、38-42秒想定の9カット、private設定、共通のexperiment groupを入れる。
2. `validate-project` で10件を検証し、Pexels検索可能性を確認する。
3. ストック群だけを `scripts/make-video.ps1` で1件ずつ作り、`quality_report.json` のerrors/warnings、`rendered.youtube.json` の検証・投稿状態を確認してから `upload-youtube` を実行する。
4. 生成AIイントロ群は `scripts/make-video-with-generated-intro.ps1 ... -UploadYoutube` を5行だけ `commands/upload_commands.txt` に書く。コメントを混在させず、バッチrunnerのDryRunで5行すべてを確認する。
5. Ruff、pytest、成果物の状態を確認する。

## Validation and Acceptance

10本すべてのproject JSONが有効であること。ストック群5本はMP4あり、品質エラー0・警告0・render検証有効・ブロッカーなし・`uploaded_private` であること。生成AIイントロ群はコマンド5件がDryRunで通り、各プロジェクト直下の `generated_intro.mp4` が唯一の入力配置先として明記されること。

## Outcomes

- ストック映像群の投稿URL: 鉛筆削り `https://www.youtube.com/watch?v=ALB2cL4T-3Y`、カラビナ `https://www.youtube.com/watch?v=a4egLxN4VAk`、ポンプボトル `https://www.youtube.com/watch?v=rntj81Nj__Q`、テープ台 `https://www.youtube.com/watch?v=n7iuhYmgEY8`、ドア蝶番 `https://www.youtube.com/watch?v=d-rxz8jvQwk`。
- 各投稿は最終 `rendered.youtube.json` のPythonスキーマ検証に成功し、品質レポートのエラー0・警告0、MP4存在、`uploaded_private` を確認した。
- ポンプボトル制作中にPexelsの大型動画を全量メモリ読み込みして待つ事象を再現した。ダウンロードを64KiB単位でストリーミング化し、1080x1920を満たす最小の縦型ファイルを優先するよう修正した。テストを先に失敗させ、修正後にPexelsテスト5件と全166件を通した。

## Idempotence and Recovery

投稿済みのストック群は再投稿しない。レンダリング失敗時はログと品質レポートから層を特定して最小修正を行う。生成AIイントロ群は入力MP4を置く前に実行しない。

## Plan Revision Notes

2026-07-30 / Codex: 初版作成。実行結果をProgressへ追記する。
2026-07-30 / Codex: 利用者の指定により、生成AIイントロ題材をストック映像で代替しにくい表現へ限定した。
2026-07-30 / Codex: ストック群5本のprivate投稿、生成AIイントロ群コマンド5件のDryRun、Pexelsダウンロード修正と回帰検証を完了した。
