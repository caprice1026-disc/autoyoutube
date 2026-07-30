# 直近28日 Analytics に基づく10本のShorts比較実験

このExecPlanは生きた計画書であり、リポジトリ直下の `PLANS.md` に従って更新する。作業ディレクトリは `C:\Users\Hodaka\Downloads\div\autoyoutube` である。

## Purpose / Big Picture

直近28日間のYouTube Analyticsで、身近な物の内部構造を早く示す動画が高い視聴率を得ていることを確認した。一方、生成AIイントロの有無は既存データの実験群が小さく、効果を結論づけられない。そこで、同じ長さ・声・BGM・説明密度のShortsを10本作り、生成AIイントロを使う5本と使わない5本を共通の実験群として記録する。

## Progress

- [x] (2026-07-29 00:00 JST) `youtube-analytics-summary --days 28` を実行し、2026-07-01〜28の42/66本を取得した。
- [x] (2026-07-29 00:01 JST) 高視聴・高維持の題材を、電子レンジの皿、ホチキスの裏、線路の石など「答えがすぐ見える日用品の構造」と特定した。
- [x] (2026-07-29 00:02 JST) 既存の生成AIイントロ群は各1本で比較不能なため、5本ずつ共通のexperiment groupを使う設計に決定した。
- [x] (2026-07-29 00:26 JST) 生成AIイントロ待ち5本とストック冒頭5本の新規 `project.youtube.json` を作成し、全10件を検証した。
- [x] (2026-07-29 00:46 JST) ストック冒頭5本を実レンダー・品質ゲート・非公開アップロードまで実施した。
- [x] (2026-07-29 00:48 JST) 生成AIイントロ待ち5本だけを `commands/upload_commands.txt` に記載し、DryRunで5/5の解釈を確認した。
- [x] (2026-07-29 00:49 JST) 最終JSON、品質レポート、アップロード状態、Ruff、pytestを確認した。Ruffは正常、pytestは164件成功した。

## Surprises & Discoveries

- Observation: 直近28日の加重平均視聴率は37.99%だが、「ホチキスの裏」は68.50%、「電子レンジの皿」は66.85%だった。
  Evidence: `data/youtube_analytics_summary.json` の `top_by_retention`。
- Observation: 既存の比較実験はactionable=0、directional=3で、生成AIイントロの因果的な優劣を示すには不十分である。
  Evidence: CLI出力の `Comparable groups: actionable=0, directional=3, insufficient=134`。
- Observation: AivisSpeechのコンテナは停止しており、最初のレンダー時にDocker DesktopのAPIソケットが存在しなかった。
  Evidence: `make-video.ps1` は `AivisSpeech did not become ready` を出力し、Docker APIのnamed pipe不在を報告した。Docker Desktop起動後、`docker compose --profile aivis up -d aivis-engine` で復旧した。
- Observation: コメントの直後に置いた最初のコマンドは、既定エンコーディングのPowerShell `Get-Content` でコメント行と連結され、ランナーから除外された。
  Evidence: DryRunが4件しか数えなかった。コメントを削除して5つのコマンドだけにすると、`commands: 5` と表示された。

## Decision Log

- Decision: 両群の主指標を `average_view_percentage` とし、実験グループ名を各群で共通化する。
  Rationale: 現在は動画ごとに実験群が分かれていてサンプル数が1になり、Analytics summaryが判定を保留しているため。
  Date/Author: 2026-07-29 / Codex
- Decision: 生成AIイントロの5本はレンダー・公開を保留し、コマンドと受け入れ先だけを作る。
  Rationale: 生成AIのMP4はユーザーが用意する前提であり、ファイル不在時のストック映像フォールバックを実験条件として混入させないため。
  Date/Author: 2026-07-29 / Codex
- Decision: `commands/upload_commands.txt` は既にアップロード済みの9件を残さず、今回の生成AIイントロ待ち5件だけに置き換える。
  Rationale: 古いコマンドを残すと次回バッチで同じ動画を重複アップロードする危険があるため。
  Date/Author: 2026-07-29 / Codex

## Outcomes & Retrospective

完了時に、10本のproject ID、ストック冒頭5本の非公開URL、生成AIイントロ5本のMP4保存先、品質警告と検証結果を記録する。

2026-07-29の実績: ストック冒頭群は全5本が品質 `pass`、エラー0、警告0、検証エラー0、ブロッカーなしで非公開アップロードされた。動画IDは、洗濯ばさみ `_bYqw6IbajM`、バインダークリップ `8ypAFCwzXdc`、はさみ `ETZSzrm-u8s`、炊飯器 `iIWvVuofkyQ`、氷 `ifOt3uYN-9E`。生成AIイントロ群は、トースター、ファスナー、傘、南京錠、魔法瓶の5本であり、各フォルダの `generated_intro.mp4` を待機している。

最終検証では、10/10のproject JSONが有効、ストック群5/5が `uploaded_private`、品質エラー0、警告0、検証エラー0、素材重複・動画長のブロッカーなしだった。`commands/upload_commands.txt` は生成AIイントロ群5件をDryRunで解析できた。`python -m ruff check .` は正常、`python -m pytest -q` は `164 passed` だった。

## Context and Orientation

プロジェクトJSONは `projects/<project_id>/project.youtube.json` に置く。`scripts/make-video.ps1` はストック冒頭の動画を、`scripts/make-video-with-generated-intro.ps1` は各project JSONと同じフォルダにある `generated_intro.mp4` を最初の映像へ差し替える。後者は生成動画の音声を削除し先頭1秒をトリムする。生成AIイントロがない場合はストックへフォールバックするため、実験群を守るためにMP4を置いてから実行する。

## Plan of Work

生成AIイントロ群は、トースター、ファスナー、傘、南京錠、魔法瓶の内部構造を冒頭で見せる。ストック冒頭群は、洗濯ばさみ、バインダークリップ、はさみ、炊飯器の蒸気口、アイスキューブを対象にする。全動画は38〜42秒、答えを最初の3秒に置き、既定BGM `No One Here Gets In Alive` とAivisSpeechを使う。

ストック冒頭群は `make-video.ps1` で1本ずつ実行する。各最終rendered JSONについて、品質エラー0件、検証エラーなし、素材重複・動画長超過なしを確認した場合だけ、個別の `upload-youtube` でprivateアップロードする。生成AIイントロ群のコマンドは `commands/upload_commands.txt` にPowerShell形式で記録する。

## Concrete Steps

    .\.venv\Scripts\python.exe -m src.main validate-project projects\<project_id>\project.youtube.json
    powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\make-video.ps1 -ProjectPath "projects\<project_id>\project.youtube.json" -PerQuery 6 -MaxDownloads 48
    .\.venv\Scripts\python.exe -m src.main upload-youtube "<final rendered.youtube.json>"

生成AIイントロ群は次のコマンドを `commands/upload_commands.txt` に書く。

    .\scripts\make-video-with-generated-intro.ps1 -ProjectPath "projects\<project_id>\project.youtube.json" -PerQuery 6 -MaxDownloads 48 -UploadYoutube

## Validation and Acceptance

10個すべてのJSONがスキーマ検証を通ること。ストック冒頭5本は、品質レポートのエラー数0、検証エラーなし、素材重複・動画長超過なし、YouTube状態 `uploaded_private` を満たすこと。生成AIイントロ群は、コマンドの5行と各 `generated_intro.mp4` 保存先が一致すること。最後にRuffとpytestを実行する。

## Idempotence and Recovery

JSON検証は繰り返して安全である。privateアップロード済みの最終JSONを再アップロードしない。生成AIイントロは各プロジェクト固有のフォルダへ `generated_intro.mp4` として置き、無関係なファイルを上書きしない。生成AI動画が未配置の場合は実行せず、ストックへの意図しないフォールバックを防ぐ。

## Artifacts and Notes

Analyticsの証拠は `data/youtube_analytics_summary.json`、動画の品質証拠は `renders/<run_id>/final/quality_report.json` と `rendered.youtube.json` である。生成物、Pexels素材、DB、OAuthトークンはコミットしない。

## Interfaces and Dependencies

既存CLI、Pexels、AivisSpeech、FFmpeg、YouTube uploaderを使う。動画はすべて9:16、1080x1920、30fps、MP4、AivisSpeech音声、既定BGM、非公開で扱う。

## Plan Revision Notes

2026-07-29 / Codex: 直近28日Analyticsの取得結果を反映し、5対5の共通experiment groupを新設する比較実験として作成した。
