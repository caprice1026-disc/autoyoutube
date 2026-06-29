# 開発メモ

最終確認日: 2026-06-28 JST
対象ブランチ: `codex-error-handling-bgm`
直近push済みコミット: `61f7667 Add Pexels media fetching`

このメモは、要件定義書に対する現在地と次に実装する内容を整理するためのものです。Docker周りは、現在のリポジトリにある `Dockerfile`, `docker-compose.yml`, `docker-compose.aivis-build.yml` を正とします。

## 現在の状況

- 作業ツリーは、スキーマ契約厳密化の未コミット差分を含みます。
- Python実行はユーザー作成済みの `.venv` を使う前提です。
- `requirements.txt` には `jsonschema`, `pytest`, `ruff` が入っています。
- 直近の確認では `ruff check .`, `ruff format . --check`, `pytest -q` が成功し、pytestは `49 passed` でした。
- `pytest.ini` でテスト収集対象を `tests/` に限定しています。これは、ローカルにcloneした外部リポジトリ `AivisSpeech-Engine/` のテストを誤って収集しないためです。
- Aivis実音声、Pexels素材、ローカルBGM、FFmpegを通したサンプルrenderを確認済みです。生成MP4は H.264 / 1080x1920 / yuv420p / 30fps / AAC、実尺 16.8秒でした。

## Docker / AivisSpeech Engine の現状

Docker周りは現状実装を正とします。

- `Dockerfile` はPythonアプリ実行環境を作り、コンテナ内にFFmpegをインストールします。
- `docker-compose.yml` は `app` と `aivis-engine` の2サービス構成です。
- `aivis-engine` は profile `aivis` 配下で、既定では `ghcr.io/aivis-project/aivisspeech-engine:cpu-latest` を使います。
- `app` からのAivis接続先は `AIVIS_SPEECH_BASE_URL=http://aivis-engine:10101` です。
- ホストからは `10101:10101` でAivisSpeech Engineへアクセスできます。
- AivisSpeech Engineの永続データは `data/aivis-engine/` に保存します。
- `docker-compose.aivis-build.yml` は、`AivisSpeech-Engine/` からローカルbuildしたい場合のoverrideです。
- `AivisSpeech-Engine/` はGitHubからclone済みですが、外部リポジトリなので `.gitignore` 対象です。
- 実機確認では、Docker Desktop 4.78.0 / Docker CLI 29.5.3 / Docker Compose v5.1.4 を使用しました。
- 公式CPUイメージで `/version`, `/speakers`, `AivisSpeechClient.synthesize_to_file()` の短文WAV生成まで疎通確認済みです。
- Windows通常権限で Docker pipe permission が出る場合は、`docker-users` グループ反映のためサインアウト/サインインが必要です。

注意点:

- サンプル `project.youtube.json` は、公式CPUイメージ初回状態で確認できた `まお` のstyle ID `888753760` を指定しています。別モデルを使う場合は、起動中Engineの `/speakers` でstyle IDを確認して差し替えてください。

## 実装済み

### JSON / CLI / エラーハンドリング

- `schemas/project.youtube.schema.json` と `schemas/rendered.youtube.schema.json` を使った検証があります。
- `project.youtube.schema.json` は任意の `voice.style_id` を受け付けます。
- `rendered.youtube.schema.json` は、音声、映像、字幕、credits、validation、manual_reviewなどの主要構造を詳細に検証します。
- credits itemは `credit_type` に統一しています。
- `validate-project`, `validate-render`, `init-db`, `render`, `import-bgm`, `list-bgm`, `import-media`, `list-assets` CLIがあります。
- CLIの業務エラーは `Error`, `Location`, `Details`, `Next step` 形式で表示します。
- `--debug` 指定時はtracebackを表示します。

### DB

- `db/schema.sql` には、要件定義書にある主要テーブル群が定義されています。
- `init-db` でSQLite DBを初期化できます。
- project原本パス、ハッシュ、raw JSONは `youtube_projects` に保存します。
- render結果は `youtube_renders.raw_rendered_json` に保存します。
- 現時点で正規化保存しているrender関連テーブルは主に `render_manual_reviews`, `render_bgm_usage`, `render_visual_items` です。
- BGM使用時は `bgm_tracks.used_count` を更新します。
- 映像素材使用時は `media_assets.used_count` を更新します。

未完了のDB正規化:

- `render_voice_settings`
- `render_narration_files`
- `render_audio_outputs`
- `render_subtitle_styles`
- `render_subtitle_items`
- `render_youtube_metadata`
- `youtube_uploads`
- `render_thumbnails`
- `render_credits`
- `render_credit_summaries`
- `render_ffmpeg_logs`
- `render_validation_results`
- `render_validation_messages`

これらはテーブル定義はありますが、現時点では全項目を個別テーブルへ保存していません。raw rendered JSONにはまとまって残ります。

### 音声 / 字幕

- dry-runでは文単位の無音WAVを生成します。
- AivisSpeech APIクライアントがあります。
- `AIVIS_SPEECH_BASE_URL` と `--aivis-base-url` で接続先を切り替えられます。
- `voice.style_id` がproject JSONにある場合、音声生成では `speaker` よりstyle IDを優先します。
- 文単位WAVを `sentence_gap_ms` を挟んで `narration.wav` に結合します。
- WAV実測時間から字幕タイミングを作ります。
- ASS字幕 `subtitle.ass` を生成します。

### BGM

- BGM manifestを `import-bgm` でDBへ登録できます。
- `mood`, `intensity`, `allow_sources`, `avoid` に基づいてBGMを選定します。
- FFmpeg実行時にBGMをナレーションへミックスします。
- fade in / fade out / volume_db を反映します。
- `credits.txt` にBGMクレジットを出します。

### 映像素材

- `.env` の `PEXELS_API_KEY` を使い、`check-pexels` でPexels APIの疎通確認ができます。
- `fetch-pexels` はproject JSONから検索語を集め、Pexels動画を `assets/pexels/` へdownloadし、`media_assets` へ登録します。
- ローカル映像素材manifestも `import-media` でDB登録できます。
- `visual_query`, `source_priority`, `avoid_keywords`, `used_count` を見てローカル素材を選定します。
- 選定素材は `rendered.youtube.json.visuals` と `render_visual_items` に残します。
- FFmpeg背景動画として最初に選ばれた素材をループ利用できます。
- 現時点では、文ごとに別素材へ切り替えるタイムライン合成は未実装です。

### FFmpeg

- FFmpegで 1080x1920 / H.264 / AAC / yuv420p のMP4を生成できます。
- 背景がない場合は単色canvasを使います。
- 背景動画がある場合は `scale` と `crop` で9:16へ合わせます。
- `logs/ffmpeg_command.txt` と `logs/ffmpeg_stderr.log` を出力します。

### README / ExecPlan / テスト

- READMEは現在のCLI、Docker、AivisSpeech Engine、BGM、映像素材manifest、検証手順を反映済みです。
- `.agent/20260628_schema_contract_hardening.md` にスキーマ契約厳密化の計画と結果を残しています。
- テストはJSON検証、CLIエラー、AivisSpeechクライアント、BGM、ローカル映像素材、Pexels APIクライアント、Docker Compose設定、FFmpegコマンド、レンダーパイプライン、`voice.style_id` 優先利用を対象にしています。

## 要件定義書に対する進捗

### Phase 1: 基盤構築

状態: 完了

- ディレクトリ構成、schema、DB schema、SQLite初期化、JSONバリデーションCLIは実装済みです。
- エラー表示も運用向けに改善済みです。
- 方針書の推奨に合わせて、`voice.style_id` と厳密な `rendered.youtube.schema.json` も追加済みです。

### Phase 2: 仮レンダリング

状態: 実動画E2Eまで確認済み、thumbnailは未実装

- 外部APIなしでdry-run音声とFFmpeg出力ができます。
- AivisSpeech実音声、Pexels素材、ローカルBGM、FFmpegで1本のMP4生成を確認済みです。
- rendered JSON、description、credits、subtitle、ログを生成できます。
- thumbnailはまだ生成していません。

### Phase 3: AivisSpeech連携

状態: 接続経路とサンプル実音声renderは確認済み、話者管理CLIが残り

- AivisSpeech Engine Dockerサーバーとの疎通は確認済みです。
- AivisSpeechClientから短文WAV生成も確認済みです。
- サンプルprojectはDocker初期モデルで使える `style_id: 888753760` を指定済みです。
- 起動中Engineの話者一覧をCLIで表示・検証する機能はまだありません。

### Phase 4: Pexels連携

状態: 最小実装済み、render中自動取得と複数素材合成は未完

- `check-pexels` でAPI疎通を確認できます。
- `fetch-pexels` でPexels API検索、portrait優先検索、download、Pexelsメタデータ保存ができます。
- 登録済みPexels素材は `media_assets` から選定され、`rendered.youtube.json.visuals` に `pexels_id` などの情報が残ります。
- render中の自動Pexels検索、文ごとの複数素材切り替え、より詳細なPexelsレート制限対策は未実装です。

### Phase 5: BGM連携

状態: ローカルBGMは実装済み

- BGM manifest登録、条件選定、音量調整、fade、FFmpeg mix、クレジット出力は実装済みです。
- YouTube Audio Library由来ファイルの運用ルールや実データ投入は今後です。

### Phase 6: レビュー支援

状態: 一部実装

- `description.txt`, `credits.txt`, `manual_review` 初期状態の出力はあります。
- `mark-ready` のようなレビュー状態更新CLIは未実装です。
- `thumbnail.jpg` 生成は未実装です。

### Phase 7: YouTube分析連携

状態: 未実装

- DBテーブルはあります。
- YouTube動画ID登録、指標取得、`analytics_summary.json` 生成は未実装です。

## 現在の主なギャップ

1. 話者管理が弱い
   - `voice.style_id` の入力と優先利用は入りましたが、AivisSpeechの話者名/style IDを一覧表示・検証するCLIはまだありません。
   - サンプルprojectは既定Engine向けstyle IDへ更新済みですが、別モデル利用時の検証支援は未実装です。

2. render結果のDB正規化が未完
   - raw JSON保存はありますが、要件上の全render系テーブルへはまだ保存していません。

3. Pexelsはキャッシュ型で、render中自動検索はまだない
   - `fetch-pexels` で先に素材を取る運用です。
   - API制限やネットワーク失敗をrenderから切り離せる一方、完全自動renderにはまだ届いていません。

4. 複数映像素材のタイムライン合成がない
   - script itemごとのvisual情報は出ますが、FFmpeg背景は最初の素材を全体にループしています。

5. thumbnailとレビュー更新CLIがない
   - 投稿前作業を完結させるには `thumbnail.jpg` 生成と `mark-ready` が必要です。

6. パス安全性の制約がまだ甘い
   - 要件では任意パス読み込みを避け、プロジェクトルート配下に制限する方針です。
   - 現状のBGM/Media manifestは相対パス解決と存在確認はありますが、root配下制限までは徹底していません。

## 次に実装する候補

優先順は以下が妥当です。

1. 実動画の目視品質確認
   - AivisSpeech実音声、BGM、Pexels素材、FFmpegを通した機械的E2Eは完了済みです。
   - 次はユーザー目線で `output.mp4` を見て、字幕位置、BGM音量、素材の違和感を確認する。
   - 必要に応じて字幕スタイル、BGM音量、映像素材選定を調整する。

2. AivisSpeech話者管理
   - `list-speakers` CLIを追加する。
   - `project.youtube.json` のspeakerが利用可能か事前検証する。
   - サンプルprojectをDocker初期モデルで動く話者、またはstyle IDへ更新する。

3. Pexels連携の強化
   - render中の自動取得をオプション化する。
   - Pexels APIのレート制限、0件時fallback、download失敗時の再試行を強化する。
   - Pexelsクレジットを `credits.txt` / `description.txt` により明示的に出す。

4. render結果のDB正規化拡張
   - `render_narration_files`, `render_audio_outputs`, `render_subtitle_items`, `render_ffmpeg_logs`, `render_credits` などへ保存する。
   - raw JSONだけでなく、検索・分析したい項目をDBから引ける状態にする。

5. 映像タイムライン合成
   - script itemごとに選ばれた素材を、それぞれの `video_start_sec` / `video_end_sec` に合わせて切り替える。
   - FFmpeg filter graphを拡張する。
   - 横動画用の `crop_landscape_to_9_16` のログをより正確に残す。

6. レビュー支援
   - `mark-ready`, `mark-reviewed`, `list-renders` CLIを追加する。
   - `render_manual_reviews` と `youtube_uploads` を更新できるようにする。

7. thumbnail生成
   - Pillowを依存に追加する。
   - `thumbnail.jpg` を生成する。
   - レンダー結果とDBへ保存する。

8. 安全性強化
   - BGMと映像素材の読み込みを許可ディレクトリ配下に制限する。
   - 環境変数やAPIキーがGitに入らないことをテスト・READMEで明確にする。

9. YouTube Analytics連携
   - 初期MVP後の課題として扱う。
   - `youtube_metrics_snapshots` への保存と `analytics_summary.json` 出力を追加する。

## 推奨する直近の実装順

次の1手は、実生成済み動画の目視品質確認です。機械的なE2Eは通っているため、字幕位置、BGM音量、Pexels素材の違和感を確認し、調整が必要な箇所を絞ります。

目視確認後は、DB正規化拡張と映像タイムライン合成へ進むのが自然です。Pexelsはすでにキャッシュ型の最小実装があるため、render中自動取得よりも、クレジット強化と0件時fallbackを先に入れる方が安全です。

## よく使う確認コマンド

```powershell
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format . --check
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m src.main validate-project projects\trivia_submarine_black_001\project.youtube.json
.\.venv\Scripts\python.exe -m src.main render projects\trivia_submarine_black_001\project.youtube.json --voice-mode aivis --video-mode ffmpeg --aivis-base-url http://127.0.0.1:10101
.\.venv\Scripts\python.exe -m src.main validate-render renders\trivia_submarine_black_001\rendered.youtube.json
.\.venv\Scripts\python.exe -m src.main check-pexels "deep ocean" --per-page 1
.\.venv\Scripts\python.exe -m src.main fetch-pexels projects\trivia_submarine_black_001\project.youtube.json --per-query 1 --max-downloads 1
docker compose --profile aivis config
docker compose --profile aivis up -d aivis-engine
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:10101/version
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:10101/speakers
```
