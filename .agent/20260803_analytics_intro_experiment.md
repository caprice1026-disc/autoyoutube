# 直近28日分析に基づくCTA付きShorts 10本制作

## 目的

2026-07-06から2026-08-02のYouTube Analytics summaryを基に、平均視聴率を改善する題材・台本構成を検証する。通常イントロ5本と生成AIイントロ5本を作る。全動画に同一の終端CTAを実行時に追加し、CTAの有無が比較を乱さないようにする。

## 分析根拠

- 分析対象60本の加重平均は、平均視聴時間18.88秒、平均視聴率43.87%だった。
- 再生上位には身近な物の疑問があり、維持率上位には橋の伸縮装置、線路の隙間、マンホール、南京錠、ホチキスなど「見える疑問を内部・構造の理由で解く」題材が並ぶ。
- 比較可能な十分な群はまだ0件のため、生成AIイントロの効果は断定せず、今回を次回集計のための統制された追加群とする。

## 実施内容

1. 全台本は、最初の文で答え又は驚きの構造を示し、可視の疑問、内部の理由、日常での効き目の順で短く説明する。
2. 通常イントロ群は、サラダスピナー、チーズグレーター、穴あけパンチ、ドアストッパー、栓抜きという撮影素材で確認できる日用品を使う。完成後、privateでYouTubeへ投稿する。
3. 生成AIイントロ群は、ラチェット、トイレタンクのサイフォン、掃除機のサイクロン、感熱紙、電動歯ブラシを使う。冒頭はストック素材で正確に示しにくい透明断面・粒子・微細層に限る。`generated_intro.mp4`を受け取るまでは投稿しない。
4. 全10本に`-AppendEndCta`を付ける。CTA文言は「おもしろければチャンネル登録と高評価、ぜひお願いします。」であり、元のproject JSONは変更しない。

## 検証

- 10本の`validate-project`を通す。
- 通常イントロ群はPexels取得後にrender、`validate-render`、`evaluate-render`を通し、quality reportのerror/warningを0にする。
- 通常イントロ群はprivate upload記録を確認する。
- 生成AIイントロ群は、5行の`commands/upload_commands.txt`をDryRunし、各プロジェクトに必要な配置先を確認する。

## 実施結果

- 2026-08-03 JSTに`youtube-analytics-summary --days 28`を実行した。対象60本、加重平均の平均視聴時間18.88秒、平均視聴率43.87%を確認した。
- 10本の`validate-project`はすべて成功した。生成AIイントロ5本の`commands/upload_commands.txt`は`-UploadYoutube -AppendEndCta`付き5行としてDryRunに成功した。
- CTAの既定文言を「おもしろければチャンネル登録と高評価、ぜひお願いします。」へ変更し、CTA・生成AIイントロ・アップロードランナーの回帰テスト21件を通した。
- 通常イントロ5本を生成し、いずれも`quality_report.json`が`pass`、error 0、warning 0、レンダーJSON検証成功、CTAがscript index 10に存在することを確認した。private投稿は順に `iYS_Nz7knE8`、`GhT8OjLTc9w`、`-p6BrOCY5Pc`、`Qp96f18WY8o`、`dNeOdIj0SyQ` で完了した。
- 最終検証は `ruff check .` 成功、`pytest -q` は171 passedだった。
