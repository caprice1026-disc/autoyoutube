# inspect-render

`inspect-render` は、FFmpegで生成済みの `output.mp4` から、Codexや人間レビューが確認しやすいPNGアーティファクトを生成するコマンドです。

Phase 1では、timeline PNG生成はまだ行わず、以下の静止画を生成します。

```text
renders/{project_id}/inspect/
  opening.png
  middle.png
  ending.png
  subtitle_001.png
  subtitle_002.png
  ...
  inspect_report.json
```

## 使い方

```powershell
.\.venv\Scripts\python.exe -m src.main inspect-render renders\trivia_xxx\rendered.youtube.json
```

FFmpegがPATHにない場合は、明示的に指定します。

```powershell
.\.venv\Scripts\python.exe -m src.main inspect-render renders\trivia_xxx\rendered.youtube.json --ffmpeg-path "C:\path\to\ffmpeg.exe"
```

## 生成される画像

- `opening.png`: 冒頭付近の確認用フレーム
- `middle.png`: 動画中央付近の確認用フレーム
- `ending.png`: 終盤付近の確認用フレーム
- `subtitle_XXX.png`: `subtitles.items[]` の中央時刻で抽出した字幕確認用フレーム

## quality_report連携

`evaluate-render` は、`renders/{project_id}/inspect/` に存在するPNGを検出して、`quality_report.json` の `artifacts` に追加します。

```json
{
  "artifacts": {
    "inspect_dir": "renders/trivia_xxx/inspect",
    "screenshot_paths": [
      "renders/trivia_xxx/inspect/opening.png",
      "renders/trivia_xxx/inspect/middle.png",
      "renders/trivia_xxx/inspect/ending.png"
    ],
    "subtitle_frame_paths": [
      "renders/trivia_xxx/inspect/subtitle_001.png"
    ],
    "timeline_png_path": null
  }
}
```

`timeline_png_path` はPhase 2で追加予定です。

## 想定するレビュー観点

- 冒頭が黒画面や無意味なフレームになっていないか
- 字幕が背景に埋もれていないか
- 字幕位置が下に寄りすぎていないか
- フォントやoutlineが読みやすいか
- 明るすぎる背景で白文字が負けていないか
- 暗すぎる背景で映像内容が分からなくなっていないか
