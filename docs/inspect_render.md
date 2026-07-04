# inspect-render

`inspect-render` は、FFmpegで生成済みの `output.mp4` から、Codexや人間レビューが確認しやすいPNGアーティファクトを生成するコマンドです。

Phase 2では、静止画に加えて `timeline.png` を生成します。`timeline.png` は、フレームストリップ、音声波形、字幕タイムラインを縦に並べたレビュー用画像です。

```text
renders/{project_id}/inspect/
  opening.png
  middle.png
  ending.png
  subtitle_001.png
  subtitle_002.png
  ...
  timeline.png
  timeline_parts/
    frames.png
    waveform.png
    subtitles.png
    timeline_frame_001.png
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
- `timeline.png`: フレームストリップ、波形、字幕ブロックをまとめた確認用画像

## timeline.png の構成

```text
上段:
  動画全体から等間隔に抽出したフレームストリップ

中段:
  final_audio.wav をもとにした音声波形

下段:
  subtitles.items[] の start_sec / end_sec を使った字幕ブロック
  CPSが高い字幕は警告色で表示
```

Python画像ライブラリを増やさないため、波形と字幕帯は標準ライブラリでPNG生成し、最終的な縦結合はFFmpegで行います。

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
    "timeline_png_path": "renders/trivia_xxx/inspect/timeline.png"
  }
}
```

## 想定するレビュー観点

- 冒頭が黒画面や無意味なフレームになっていないか
- 字幕が背景に埋もれていないか
- 字幕位置が下に寄りすぎていないか
- フォントやoutlineが読みやすいか
- 明るすぎる背景で白文字が負けていないか
- 暗すぎる背景で映像内容が分からなくなっていないか
- 波形上で冒頭や文間の無音が長すぎないか
- 字幕ブロックが詰まりすぎていないか
- CPSが高い字幕が集中していないか
