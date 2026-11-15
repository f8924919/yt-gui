# ニコニコのコメントの複数行の自動縮小と ender / full を再現する

> Issue: [#388](https://github.com/f8924919/yt-gui/issues/388)
> ステータス: 進行中
> ブランチ: `feature/388-nico-resize-full-ender`
> 基点: `03d4b3e`

受け入れ条件の正本は Issue。設計は [arch/nico_ass.md](../arch/nico_ass.md) の「複数行の縮小と `ender` / `full`」。前のタスクは [#387](archive/387-nico-ass-converter.md)・[#391](archive/391-nico-pseudo-bold-width.md)。

## 進捗

- [ ] C1 行数の多いコメントの縮小（`isLineBreakResize`） — 証跡: 未
- [ ] C2 縮小したコメントの上下固定の縮小（`resizedY` の分岐） — 証跡: 未
- [ ] C3 `ender` で複数行の縮小をしない — 証跡: 未
- [ ] C4 `full` で上下固定の幅の上限が 683 — 証跡: 未
- [ ] C5 対象のコメントが無い入力の出力が変わらない — 証跡: 未
- [ ] C6 `sm9560870` で焼きこみと Web を見比べる — 証跡: 未
- [ ] C7 単体テストと変異 → red の死因の表 — 証跡: 未
- [ ] C8 spec / arch の更新（コマンドと対象外） — 証跡: 未

## 着手時の調べ（2026-11-15）

- 参照: niconicomments のコミット `899203436285d315b93f7536b7dfa17ff8303af9` の `src/`（`comments/HTML5Comment.ts`、`utils/comment.ts`、`utils/niconico.ts`、`definition/initConfig.ts`）。scratchpad に取得して読んだ（追跡しない）。
- 複数行の縮小: `HTML5Comment.ts:211-224`（`measureText` の `isLineBreakResize` の分岐）、`utils/comment.ts:593-599`（`isLineBreakResize`）、`utils/niconico.ts:24-44`（`getLineHeight` の `resized`）、`definition/initConfig.ts:130-134`（`html5LineCounts.resized`: big 16 / medium 25.4 / small 38）、`:319-323`（`lineBreakCount`: big 3 / medium 5 / small 7）。
- 幅の測定は `utils/niconico.ts` の `measureWidth` が `getFontSizeAndScale(comment.charSize)` で行い、`measureText` が設定する `fontSize.resized` は使わない（`HTML5Comment.ts:232` で `charSize × 0.8` に上書きされる）。描画（`:508`）も文字サイズから出す。
- `full`: `HTML5Comment.ts:250-267`（`_measureComment`）と `:269-` （`_processResizeX`）の幅の上限が `fullWidth`（html5 は 683）。`loc !== "naka"` の分岐の中だけなので、流れるコメントには効かない。
- `ender` / `full` のコマンド: `utils/comment.ts:1110-1176`（`parseCommand`）が小文字にしてから、キーに一致すれば真にする。
- 行数: `HTML5Comment.ts:45-61`（`clampHTML5Content`）。16,384 文字・256 行で切った後の改行の数 + 1。yt-gui の `_body_lines`（`yt_gui/nico_ass.py:995-998`）と同じ数え方。
- `compatSpacer.html5` は空で、`html5SpecialSpaceCompat` は `false`（`definition/initConfig.ts:253`、`:361-390`）。空白の字幅の補正は既定では無い。
- 古い描画方式（Flash）: 2017-07-12 より前でフォント指定の無いコメントが対象（`utils/comment.ts:1230-1244`、`definition/initConfig.ts:230` の `flashThreshold: 1499871600`）。yt-dlp が取ったコメントの最古は `sm31143779` で 2019-08-20、`sm9560870` で 2018-08-15 で、対象は 0 件（全件の `postedAt` を数えた）。ユーザー判断で対象外。
- コメントアートの層の分離（`utils/commentArt.ts` の `changeCALayer`）は `options.keepCA` が真のときだけ動き、既定は `false`。ユーザー判断で対象外。
- `sm9560870` の 222 件のうち、3 行以上が 105、`ender` が 91、`full` が 15（#391 で取得した JSON を数えた）。
- C5 の基準（`03d4b3e`、`sm31143779` の全件から `ender` / `full` を除いた入力。3 行以上のコメントは 0 件。テストの `fw_measure` / `fake_metrics` / `no_advance`、`random.Random(42)`）: windows `4c2db41db76460aee8a315c0795104483675f93a8eade313eb94badad49bd270`、macos `bd8068d57446073d83494665c4fd56cb18579dcb41e14751d8cd18c1b17c0e8d`、other `76f4b45f17603f942fc96dbdabeca60f60333b6ea5d41ebd52d00db9603f7c15`。

## 訂正ログ

| 日付 | 何を誤って書いたか | 正しくは | どの検査・手順なら捕まえたか |
|---|---|---|---|

## 次にやること

設計を arch / spec に書いた。次は design-review（investigate の推奨は yes）→ テスト先行 → 実装。

訂正ログ: 0 件
