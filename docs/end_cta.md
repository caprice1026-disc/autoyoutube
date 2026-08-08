# 終端CTA

`make-video` と `make-video-with-generated-intro` は、任意の終端CTAを追加できます。CTAは動画の末尾で読み上げられ、字幕にも表示されます。

標準の文言は次の一文です。

> おもしろければチャンネル登録と高評価、ぜひお願いします。

通常動画では、Python CLIに `--append-end-cta` を付けます。

```powershell
.\.venv\Scripts\python.exe -m src.main make-video projects\example_project.youtube.json --append-end-cta
```

PowerShellラッパーでは `-AppendEndCta` を使います。

```powershell
.\scripts\make-video.ps1 `
  -ProjectPath "projects\example_project.youtube.json" `
  -AppendEndCta
```

生成AI導入動画でも同じ意味のフラグを使えます。

```powershell
.\scripts\make-video-with-generated-intro.ps1 `
  -ProjectPath "projects\example_project.youtube.json" `
  -AppendEndCta
```

バッチ用のUnix形式コマンドでは `--append-end-cta` を指定します。`scripts/run-upload-command-list.ps1` は自動で `-AppendEndCta` へ変換します。

CTAは実行時のプロジェクトコピーにだけ追加されます。元の `project.youtube.json` は変更されません。台本がすでに18項目あるプロジェクトには追加できないため、既存項目をまとめてから実行してください。
