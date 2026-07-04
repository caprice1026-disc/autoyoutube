# multi-visual render

Phase 4では、`rendered.visuals[]` に含まれる複数の映像素材を、scriptタイミングに合わせてつなぎ、1本の背景タイムラインとして合成します。

## 目的

従来のFFmpeg renderは、`visuals[]` のうち最初に見つかった有効素材を背景動画として使っていました。

Phase 4では、以下のように文ごとに異なる映像素材を使えるようにします。

```text
script[1] 0.0s - 3.5s -> asset A
script[2] 3.7s - 7.2s -> asset B
script[3] 7.4s - 11.0s -> asset C
```

## 処理の流れ

`render --video-mode ffmpeg` 実行時に、`visuals[]` から複数の有効素材が見つかった場合、次の中間ファイルを生成します。

```text
renders/{project_id}/video_segments/
  segment_001.mp4
  segment_002.mp4
  segment_003.mp4
  concat.txt

renders/{project_id}/video/
  background_timeline.mp4
```

その後、従来どおり `background_timeline.mp4` に対して、音声・BGM・字幕を重ねて `output.mp4` を生成します。

```text
visuals[]
  ↓
segment_001.mp4, segment_002.mp4, ...
  ↓
background_timeline.mp4
  ↓
output.mp4
```

## セグメント生成

各visualは次の情報を使います。

```text
local_file_path
used_start_sec
used_duration_sec
video_start_sec
video_end_sec
index
```

各素材はFFmpegで次のように正規化されます。

```text
scale=1080:1920:force_original_aspect_ratio=increase
crop=1080:1920
fps=target.fps
no audio
pix_fmt=target.video_format.pix_fmt
```

素材が短い場合でも、`-stream_loop -1` により必要尺までループできます。

## フォールバック

有効素材が0件の場合:

```text
従来どおり単色背景を使う
```

有効素材が1件だけの場合:

```text
従来どおりその1素材を背景動画として使う
```

有効素材が2件以上の場合:

```text
video_segments/ を生成して background_timeline.mp4 を作る
```

## ログ

最終的な `ffmpeg_command.txt` には、セグメント生成、concat、最終renderのコマンドをまとめて出力します。

各セグメントやconcatのstderrは、以下のように個別ログとして保存されます。

```text
renders/{project_id}/logs/
  segment_001_stderr.log
  segment_002_stderr.log
  background_timeline_stderr.log
  ffmpeg_stderr.log
```

## Phase 3との関係

Phase 3の `fetch-visuals` は、Pexels候補を取得して `visual_plan.json` を作ります。

Phase 4では、DBに登録済みのmedia assetsを既存のmedia selectorで選び、`visuals[]` に割り当てた後、その割り当て結果を実際の動画タイムラインとして合成します。

## 今後の拡張

今後は次の改善が考えられます。

```text
- visual_plan.json の selected_asset_id を明示的にrenderへ反映する
- segmentごとのtransitionを追加する
- low-motion / too-dark などの品質検査をsegment単位で行う
- background_timeline.mp4 のパスを rendered.youtube.json に記録する
```
