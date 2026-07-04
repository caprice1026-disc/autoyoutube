# 複数動画タイムライン再実装とYouTube private upload CLI 実装計画

## 目的

現在のソースコードを前提に、削除されている複数動画タイムライン合成を再実装し、生成済みShorts動画をYouTubeへ `private` としてアップロードするCLIを追加する。最後にREADMEを現状へ合わせ、AivisSpeechとFFmpegで動画を1本レンダーして動作確認する。

## 前提と制約

- YouTube Shorts向けの `1080x1920` / `mp4` / `H.264` / `AAC` を維持する。
- YouTubeアップロードは初期実装では `private` 固定にする。`public` と `unlisted` は受け付けない。
- `manual_review.checked=true`、`quality_report.json` の `error_count=0`、`output.mp4` / `description.txt` / `credits.txt` の存在をアップロード前提にする。
- `.env`、OAuthクライアントシークレット、トークン、DB、Pexels素材、BGM音源、render outputsはコミットしない。
- 実装はテストから進め、Ruffとpytestを通してからレンダー検証する。

## 実装方針

### 1. 字幕の見切れ回避

- `src/defaults.py` の `MAX_SUBTITLE_CHARS` を32から24へ下げる。
- `tests/test_defaults.py` を更新する。
- `tests/test_render_project_ffmpeg.py` に、長い日本語字幕は `\N` で改行され、ユーザーが示した安全な長さの文は改行されないテストを追加する。

### 2. レンダーディレクトリ名

- `src/pipeline/render_project.py` で `renders/<project_id>` 固定ではなく、`YYYYMMDDHHMM-タイトル` のディレクトリへ出力する。
- タイトルはWindowsで使えない文字を置換し、同分内の重複時は `-2`、`-3` のように連番を付ける。
- `created_at` / `render_id` は同じレンダー開始時刻から作る。
- テストで出力パスが新形式になることを確認する。

### 3. 複数動画タイムライン合成

- `src/render/ffmpeg_renderer.py` に `FfmpegVideoSegment` を追加し、`FfmpegRenderRequest` が複数背景動画セグメントを受け取れるようにする。
- `visuals[]` から、実ファイルがある素材だけを `video_start_sec` / 次visualの開始時刻 / `video_end_sec` で区切ったセグメントに変換する。
- 2件以上のセグメントがある場合は、各入力を `stream_loop -1` で読み込み、`trim`、`setpts`、`scale`、`crop`、`fps` をかけた後、`concat` で1本の背景動画として扱う。
- 1件だけの場合は従来どおり単一背景動画、0件なら単色背景にフォールバックする。
- BGMあり/なし双方で、映像出力と音声mixの `filter_complex` / `map` が破綻しないようにテストする。

### 4. YouTube private upload CLI

- 依存関係に `google-api-python-client`、`google-auth-oauthlib`、`google-auth-httplib2` を追加する。
- `src/youtube/metadata.py` で `rendered.youtube.json`、`description.txt`、`credits.txt` からアップロード用メタデータを構築する。
- `src/youtube/auth.py` で `secrets/client_secret.json` と `data/youtube_token.json` を使ったOAuthを実装する。
- `src/youtube/uploader.py` で `videos().insert(part="snippet,status", body=..., media_body=MediaFileUpload(..., resumable=True))` を呼び、成功時に `rendered.youtube.json` の `youtube.upload` を更新する。
- `src/main.py` に `youtube-auth` と `upload-youtube` を追加する。
- CLIは `--privacy private` のみ許可し、前提条件を満たさない場合は `AppError` で停止する。
- `.gitignore` に `secrets/` と `data/youtube_token.json` を追加する。

### 5. README更新

- 複数素材タイムライン合成、日時付きレンダーディレクトリ、YouTube private upload CLI、OAuth秘密情報の非コミットルールを追記する。
- 旧説明の「最初に選定された動画をループ利用」を現状に合わせて修正する。

### 6. 検証

- 追加テストを個別に失敗させる。
- 実装後に該当テスト、全体pytest、Ruffを実行する。
- AivisSpeechが起動していなければDockerで起動し、`--voice-mode aivis --video-mode ffmpeg` で動画を1本レンダーする。
- 生成された `rendered.youtube.json` を `validate-render` し、可能なら `evaluate-render` まで実行する。

