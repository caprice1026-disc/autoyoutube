# make-video

`make-video` は、ローカルの `project.youtube.json` から動画生成までを一括実行するCLIです。Pexels素材取得、render、inspect、evaluate、機械的な再試行をまとめて実行し、採用結果を `renders/<YYYYMMDDHHMM-title>/final/` に保存します。必要なら `--upload-youtube` で final を private upload まで続けます。

`make-video` 自体はYouTubeへ投稿しません。投稿は生成後に `upload-youtube` を使います。

## 入力JSON

入力JSONは `projects/` 配下に置きます。実際に使える記入例として、次のファイルを用意しています。

```powershell
projects\example_project.youtube.json
```

新しい動画を作る場合は、このファイルをコピーして、主に以下を書き換えます。

- `id`: ASCIIの一意なID
- `topic`, `title`, `hook`: 動画のテーマ、タイトル、冒頭の引き
- `voice`: AivisSpeech話者、style ID、読み上げ速度、文間
- `bgm`: BGMの条件。未指定時は既存のデフォルト選定を使う
- `visual_strategy`: Pexels全体検索に使う英語queryとfallback
- `script[]`: 字幕と読み上げ本文。長すぎる文は分割する
- `script[].visual_query`: 各文に対応するPexels検索用の英語query
- `youtube`: private投稿時に使うタイトル、説明文、タグ

## 基本コマンド

計画だけ確認します。Pexels取得、音声生成、動画生成は行いません。

```powershell
.\.venv\Scripts\python.exe -m src.main make-video projects\example_project.youtube.json --plan-only
```

外部副作用を抑えてdry-runします。

```powershell
.\.venv\Scripts\python.exe -m src.main make-video projects\example_project.youtube.json --dry-run --skip-fetch-visuals
```

通常実行します。AivisSpeechを使う場合は、事前に起動しておくか、wrapper scriptを使います。

```powershell
.\.venv\Scripts\python.exe -m src.main make-video projects\example_project.youtube.json
```

private upload まで自動で行う場合は `--upload-youtube` を付けます。`success` だけでなく `success_with_warnings` でも投稿します。`dry-run` と `--video-mode dry-run` の場合は投稿しません。

```powershell
.\.venv\Scripts\python.exe -m src.main make-video projects\example_project.youtube.json --upload-youtube
```

Windowsでは、AivisSpeech未起動時にDocker起動まで行うwrapper scriptを使えます。

```powershell
.\scripts\make-video.ps1 -ProjectPath "projects\example_project.youtube.json"
```

PowerShell wrapper でも `-UploadYoutube` を付けると private upload まで続けます。

## Pexels動画検索キーワードの指定

コマンド実行時に、Pexelsへ投げる動画検索キーワードを追加できます。JSON内の検索語に追加したい場合:

```powershell
.\scripts\make-video.ps1 `
  -ProjectPath "projects\example_project.youtube.json" `
  -VideoKeyword "microwave close up","metal mesh macro"
```

CLIで指定したキーワードだけをPexels検索・素材割り当てに使いたい場合:

```powershell
.\.venv\Scripts\python.exe -m src.main make-video projects\example_project.youtube.json --query-mode override --video-keywords "deep ocean,glowing jellyfish"
```

`--video-keyword` / `--pexels-keyword` は複数指定できます。`--query-mode append` は `project.youtube.json` の `visual_strategy.primary_query`、`script[].visual_query`、`visual_strategy.fallback_queries` にCLIキーワードを追加します。`--query-mode override` はCLIキーワードを `script[].visual_query` に割り当て直し、Pexels検索もそのキーワードだけで行います。`--query-mode fallback` はJSON内の検索語を優先し、候補不足時に使うfallback候補としてCLIキーワードを追加します。

`--upload-youtube` を付けると、render が `success` または `success_with_warnings` のときに final の `rendered.youtube.json` を使って private upload まで進みます。

## 出力

`make-video` は次の構成を作ります。

```text
renders/<YYYYMMDDHHMM-title>/
  inputs/
    project.original.json
    project.attempt_001.json
    project.final.json
  attempts/
    attempt_001/
      output.mp4
      rendered.youtube.json
      quality_report.json
      inspect/
  final/
    output.mp4
    rendered.youtube.json
    quality_report.json
    inspect/
  repair_log.json
  failure_log.json
  visual_assignment.json
```

元の `project.youtube.json` は直接書き換えません。自動改善が必要な場合は、attemptごとの入力JSONを `inputs/` に保存します。

## BGM

`--bgm-id` を指定しない場合は、これまでのデフォルトBGM選定を使います。標準のmanifestでは `No One Here Gets In Alive - National Sweetheart` が `youtube_audio_library` / `mysterious` / `low` として登録されます。

明示的にBGMを選ぶ場合:

```powershell
.\.venv\Scripts\python.exe -m src.main make-video projects\example_project.youtube.json --bgm-id "No One Here Gets In Alive"
```

## YouTube private投稿

`make-video` 後、finalの `rendered.youtube.json` を使って投稿します。

```powershell
.\.venv\Scripts\python.exe -m src.main upload-youtube "renders\YYYYMMDDHHMM-title\final\rendered.youtube.json"
```

アップロードは `private` 基本です。OAuth tokenがない場合は先に実行します。

```powershell
.\.venv\Scripts\python.exe -m src.main youtube-auth
```

## 終端CTA（高評価・チャンネル登録の呼びかけ）

末尾に「おもしろければチャンネル登録と高評価、ぜひお願いします。」という音声・字幕を追加するには、`--append-end-cta` を付けます。CTA用の映像も通常のPexels取得・映像選択フローで用意され、元の `project.youtube.json` は変更されません。

```powershell
.\scripts\make-video.ps1 `
  -ProjectPath "projects\example_project.youtube.json" `
  -AppendEndCta
```

Python CLIでは次のように指定します。

```powershell
.\.venv\Scripts\python.exe -m src.main make-video projects\example_project.youtube.json --append-end-cta
```

生成AI導入動画にも同じフラグを使えます。

```powershell
.\scripts\make-video-with-generated-intro.ps1 `
  -ProjectPath "projects\example_project.youtube.json" `
  -AppendEndCta
```

## Exit code

- `0`: 成功
- `10`: warningあり成功
- `20`: 自動改善attempt上限
- `30`: 自動修正できない品質問題
- `40`: AivisSpeechなどの環境問題
- `50`: Pexelsなどの外部API問題
- `60`: render失敗
- `70`: 文字コード問題
- `80`: upload gateで停止
