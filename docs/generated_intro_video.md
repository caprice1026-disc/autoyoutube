# 生成AI動画を冒頭に使用するワークフロー

`make-video-with-generated-intro` は、手動で生成した動画を最初の映像区間だけに使用し、その後は既存の `make-video` と同じ処理を行います。

既存の `make-video`、`project.youtube.json` のスキーマ、SQLite DBは変更していません。従来のprojectとコマンドはそのまま利用できます。

## 配置方法

各projectディレクトリの `project.youtube.json` と同じ階層に、生成した動画を1本配置します。

```text
projects/<project_id>/
├─ project.youtube.json
└─ <生成した動画ファイル>
```

`generated_intro.mp4` があれば従来どおり最優先で使用します。存在しない場合は、同じ階層にある唯一の動画ファイル（`.mp4`、`.mov`、`.m4v`、`.webm`、`.avi`、`.mkv`）を自動で使用します。サブディレクトリ内の動画と、レンダリング時に作られる `generated_intro.muted.mp4` は候補に含みません。

動画の長さは固定しません。既存タイムラインの最初のナレーション区間に合わせて、FFmpegがループまたはトリミングします。

同階層に候補動画が複数ある場合は、意図しない動画を選ばないようエラーで停止します。不要な動画を移動するか、`generated_intro.mp4` にリネームするか、`--generated-intro-path` または `-GeneratedIntroPath` を指定してください。明示パスは常に自動検出より優先され、相対パスは `project.youtube.json` のあるディレクトリを基準に解決されます。

## 実行方法

PowerShell:

```powershell
.\scripts\make-video-with-generated-intro.ps1 `
  -ProjectPath "projects\trivia_cat_eyes_glow_dark_001\project.youtube.json" `
  -VideoKeyword "cat eyes reflecting light close up" `
  -PerQuery 6 `
  -MaxDownloads 48
```

Git Bash / WSL:

```sh
scripts/make-video-with-generated-intro.sh \
  projects/trivia_cat_eyes_glow_dark_001/project.youtube.json \
  --video-keyword "cat eyes reflecting light close up" \
  --per-query 6 \
  --max-downloads 48
```

計画だけ確認する場合:

```powershell
.\scripts\make-video-with-generated-intro.ps1 `
  -ProjectPath "projects\trivia_cat_eyes_glow_dark_001\project.youtube.json" `
  -PlanOnly
```

## 音声の扱い

生成AI動画にセリフ、効果音、BGMが含まれていても、レンダリング前にFFmpegで全音声ストリームを削除します。

```text
-map 0:v:0 -c:v copy -an
```

無音化した派生ファイルはprojectディレクトリの `generated_intro.muted.mp4` に作られます。最終動画では、従来どおりAivisSpeechのナレーションと選択されたBGMだけを使用します。

## フォールバック

生成AIイントロの候補が1本もない場合、このコマンドはエラーにせず既存の `make-video` へフォールバックします。

フォールバック時は既存処理がそのまま動作します。

1. Geminiによるシーン別検索クエリ生成
2. Pexels素材の検索・取得
3. ローカル素材を含む候補選定
4. 音声、字幕、BGM、映像のレンダリング
5. inspect、quality評価、自動修復

明示した `--generated-intro-path` が見つからない場合も同じフォールバックになります。自動検出の候補が複数ある場合だけは、選択を曖昧にしないためフォールバックせずエラーにします。

## 後方互換性

- `project.youtube.json` に新しい必須フィールドは追加しません
- DBテーブルや既存カラムは変更しません
- 既存の `scripts/make-video.sh` と `scripts/make-video.ps1` は変更しません
- 生成AI動画は `source: local` の最初のvisualとしてrender結果に記録します
- 2番目以降のvisual選定、credits、品質評価、YouTube uploadは既存処理を利用します

## 運用上の注意

生成AI動画は公開前に、被写体、物理挙動、文字やロゴの混入、破綻した形状を目視確認してください。内部構造や科学的現象を生成した場合は、ナレーションの事実確認とは別に映像自体の正確性も確認します。
