# ニコニコのコメントの複数行の自動縮小と ender / full を再現する

> Issue: [#388](https://github.com/f8924919/yt-gui/issues/388)
> ステータス: 進行中
> ブランチ: `feature/388-nico-resize-full-ender`
> 基点: `03d4b3e`

受け入れ条件の正本は Issue。設計は [arch/nico_ass.md](../arch/nico_ass.md) の「複数行の縮小と `ender` / `full`」。前のタスクは [#387](archive/387-nico-ass-converter.md)・[#391](archive/391-nico-pseudo-bold-width.md)。

## 進捗

- [x] C1 行数の多いコメントの縮小（`isLineBreakResize`） — 証跡: `test_measure_comment_line_break_resize_at_threshold`（3 サイズ）、`test_measure_comment_no_line_break_resize_below_threshold`、`test_measure_comment_trailing_empty_line_counts`、`test_measure_comment_line_break_resize_applies_to_naka`（503d3d7）。Web は下の「C6」の 18.3 秒
- [x] C2 縮小したコメントの上下固定の縮小（`resizedY` の分岐） — 証跡: `test_resize_y_then_x_grow_path_scales_unresized_base`・`…_shrink_path…`・`…_bisect_path…`（503d3d7）。Web は「設計レビューと…」の 42.17 秒と、「C6」の 29.9 秒
- [x] C3 `ender` で複数行の縮小をしない — 証跡: `test_parse_commands_ender_full`、`test_measure_comment_ender_skips_line_break_resize`（3 サイズ、`ender` の有無だけを変えた対照）、`test_measure_comment_ender_keeps_width_resize`（503d3d7）
- [x] C4 `full` で上下固定の幅の上限が 683 — 証跡: `test_measure_comment_full_width_limit`（512 以下・512〜683・683 超）、`…_full_limit_divided_by_font_scale`、`…_full_with_line_break_resize_uses_683`、`test_convert_full_does_not_change_naka`（503d3d7）。Web は「C6」の 79.4 秒の白いブロック
- [x] C5 対象のコメントが無い入力の出力が変わらない — 証跡: `test_convert_output_unchanged_without_multiline_ender_full_windows`（windows、`4c2db41d…`）と、入力から `ender` / `full` を除いた `test_convert_output_unchanged_where_no_pseudo_bold`（macos・other・windows-gothic。#391 の期待値のまま）が、実装の前後とも pass（503d3d7）
- [x] C6 `sm9560870` で焼きこみと Web を見比べる — 証跡: 下の「C6」
- [x] C7 単体テストと変異 → red の死因の表 — 証跡: 下の「テスト先行の red」と「変異 → red」
- [x] C8 spec / arch の更新（コマンドと対象外） — 証跡: `docs/arch/nico_ass.md` の「複数行の縮小と `ender` / `full`」と「対象外」、`docs/spec/screens/original-format-panel.md` の「対応するコマンド」「行数の多いコメント」「再現しない」（233458b、9c92a9b）

## 着手時の調べ（2026-11-15）

- 参照: niconicomments のコミット `899203436285d315b93f7536b7dfa17ff8303af9` の `src/`（`comments/HTML5Comment.ts`、`utils/comment.ts`、`utils/niconico.ts`、`definition/initConfig.ts`）。scratchpad に取得して読んだ（追跡しない）。
- 複数行の縮小: `HTML5Comment.ts:211-224`（`measureText` の `isLineBreakResize` の分岐）、`utils/comment.ts:593-599`（`isLineBreakResize`）、`utils/niconico.ts:24-44`（`getLineHeight` の `resized`）、`definition/initConfig.ts:130-134`（`html5LineCounts.resized`: big 16 / medium 25.4 / small 38）、`:319-323`（`lineBreakCount`: big 3 / medium 5 / small 7）。
- 幅の測定は `utils/niconico.ts` の `measureWidth` が `getFontSizeAndScale(comment.charSize)` で行い、`measureText` が設定する `fontSize.resized` は使わない（`HTML5Comment.ts:232` で `charSize × 0.8` に上書きされる）。描画（`:508`）も文字サイズから出す。
- `full`: `HTML5Comment.ts:250-267`（`_measureComment`）と `:269-` （`_processResizeX`）の幅の上限が `fullWidth`（html5 は 683）。`loc !== "naka"` の分岐の中だけなので、流れるコメントには効かない。
- `ender` / `full` のコマンド: `utils/comment.ts:1110-1176`（`parseCommand`）が小文字にしてから、キーに一致すれば真にする。
- 行数: `HTML5Comment.ts:45-61`（`clampHTML5Content`）。16,384 文字・256 行で切った後の改行の数 + 1。yt-gui の `_body_lines`（`yt_gui/nico_ass.py:1046-1049`、503d3d7 の行番号）と同じ数え方。
- `compatSpacer.html5` は空で、`html5SpecialSpaceCompat` は `false`（`definition/initConfig.ts:253`、`:361-390`）。空白の字幅の補正は既定では無い。
- 古い描画方式（Flash）: 2017-07-12 より前でフォント指定の無いコメントが対象（`utils/comment.ts:1230-1244`、`definition/initConfig.ts:230` の `flashThreshold: 1499871600`）。yt-dlp が取ったコメントの最古は `sm31143779` で 2019-08-20、`sm9560870` で 2018-08-15 で、対象は 0 件（全件の `postedAt` を数えた）。ユーザー判断で対象外。
- コメントアートの層の分離（`utils/commentArt.ts` の `changeCALayer`）は `options.keepCA` が真のときだけ動き、既定は `false`。ユーザー判断で対象外。
- `sm9560870` の 222 件のうち、3 行以上が 105、`ender` が 91、`full` が 15（#391 で取得した JSON を数えた）。
- C5 の基準（`03d4b3e`、`sm31143779` の全件から `ender` / `full` を除いた入力。3 行以上のコメントは 0 件。テストの `fw_measure` / `fake_metrics` / `no_advance`、`random.Random(42)`）: windows `4c2db41db76460aee8a315c0795104483675f93a8eade313eb94badad49bd270`、macos `bd8068d57446073d83494665c4fd56cb18579dcb41e14751d8cd18c1b17c0e8d`、other `76f4b45f17603f942fc96dbdabeca60f60333b6ea5d41ebd52d00db9603f7c15`。

## 設計レビューと、2 つの縮小が両方かかるときの Web（2026-11-15）

- design-review の指摘: 複数行の縮小と上下固定の縮小が両方かかると、niconicomments の 1 ずつ動かす経路（`HTML5Comment.ts:350-353`）は、幅を上限に合わせた比を `resizedY` でない基準に掛けるので、文字が大きくなり、幅は上限のおよそ 1.8〜1.9 倍になる。`sm31143779` と `sm9560870` には当たるコメントが無かった。
- ユーザーが `sm9560870` に当たるコメントを投稿した（2026-11-15。yt-dlp で取り直して確認、全 230 件）: `ue big 184` の「あ」28 字 + 「あ」+「あ」の 3 行（42.17 秒）、`ue medium 184` の「あ」40 字 + 「あ」× 4 の 5 行（29.35 秒、45.72 秒）、1 行の `ue medium`（21.42 秒）。
- 予測（`both_predict.py`、Windows の Pillow の測定と擬似ボールドの増分）: big は、複数行の縮小で文字サイズ 25.98・幅 556 になり、上下固定の縮小に入る。niconicomments の式どおり（B）なら文字サイズ 43.44（font_px 34）・幅 915（キャンバス 2,572 px）、上限に収める式（C）なら 22.93（font_px 18）・幅 503。「あ」1 字の送り幅は、B で舞台 32.672、C で 17.945。
- Web: 内蔵ブラウザ（Chromium 156、devicePixelRatio 1.5）のプレイヤーで、42.605 秒にコメントの canvas（1365 × 768）を写し取った。1 行目は画面の両端からはみ出し、2〜3 行目の「あ」は画面に無い（B では枠の左端が x = −326 で、左揃えの 2〜3 行目は画面の外）。1 行目の字の左端の間隔は 65.3 px（canvas）で、舞台では 65.3 × 683 / 1365 = 32.674。B の 32.672 と一致し、C とは合わない。
- 決定: niconicomments の式どおり（B）に移植する（ユーザーの案 A「投稿して見比べてから決める」の結果）。
- 既存の `test_convert_output_unchanged_where_no_pseudo_bold`（#391）は、入力の `sm31143779` に `ue full` の medium が 2 件あり、#388 で必ず値が変わる。期待値は撮り直さず、入力から `ender` / `full` を取り除く形に変え、C5 の windows の基準も同じテストに入れる。

## テスト先行の red（C7、2026-11-15）

実装前（`9c92a9b`、テストだけを足した作業ツリー）で `tests/test_nico_ass.py` は 20 failed, 264 passed。落ちたテスト:

- `test_parse_commands_ender_full[ender]`
- `test_parse_commands_ender_full[full-upper]`
- `test_parse_commands_ender_full[both]`
- `test_parse_commands_ender_full_default_false`
- `test_measure_comment_line_break_resize_at_threshold[big]`
- `test_measure_comment_line_break_resize_at_threshold[medium]`
- `test_measure_comment_line_break_resize_at_threshold[small]`
- `test_measure_comment_trailing_empty_line_counts`
- `test_measure_comment_ender_skips_line_break_resize[big]`
- `test_measure_comment_ender_skips_line_break_resize[medium]`
- `test_measure_comment_ender_skips_line_break_resize[small]`
- `test_measure_comment_line_break_resize_applies_to_naka`
- `test_resize_y_then_x_grow_path_scales_unresized_base`
- `test_resize_y_then_x_shrink_path_scales_unresized_base`
- `test_resize_y_then_x_bisect_path_measures_scaled_candidates`
- `test_measure_comment_full_width_limit[full-under683]`
- `test_measure_comment_full_width_limit[full-over683]`
- `test_measure_comment_full_limit_divided_by_font_scale`
- `test_measure_comment_full_with_line_break_resize_uses_683`
- `test_convert_multiline_resize_changes_dialogue_font_size`

二分探索の経路のテストは、初めは許容誤差（相対 1e-6）の中で実装前の値（0.79999924）と期待値（0.79999943）が一致して pass したので、相対 1e-9 に絞って red を確かめた。期待値は、niconicomments の式を実装と独立に書き下ろした `ref388.py` の出力（本文は末尾の「プローブの本文」）。

## 変異 → red（C7、abb6d24）

worktree のコピー（`abb6d24`。`503d3d7` から `yt_gui` と `tests` は変わっていない）を 1 つずつ変異させ、`tests/test_nico_ass.py` と `tests/test_downloader.py` を走らせた。無変異のコピーは 438 passed、戻した後も 438 passed、狙ったテストは 16 変異すべてで落ちた（`ALL TARGETED KILLED`）。置換が 1 か所に当たらないときは止まる。script は `mutate388.py`、表は `mut_table.py`（#391 と同じ）でログから作った。

- M1〜M15 は 1 巡目（`503d3d7`）でも回し、狙ったテストは全部落ちた。evaluator 1 巡目の指摘で、閾値未満で縮小しないことのテスト（`test_measure_comment_no_line_break_resize_below_threshold`）を殺す M16（閾値を 1 ずつ下げる）を足して回し直した。

| 変異 | 件数 | 狙ったテスト | 落ちたテスト（全部） |
|---|---|---|---|
| M1 big の閾値 3 → 4 | 9 failed | `test_measure_comment_line_break_resize_at_threshold[big]`（落ちた） | `test_measure_comment_line_break_resize_at_threshold[big]`<br>`test_measure_comment_trailing_empty_line_counts`<br>`test_measure_comment_ender_skips_line_break_resize[big]`<br>`test_measure_comment_line_break_resize_applies_to_naka`<br>`test_resize_y_then_x_grow_path_scales_unresized_base`<br>`test_resize_y_then_x_shrink_path_scales_unresized_base`<br>`test_resize_y_then_x_bisect_path_measures_scaled_candidates`<br>`test_measure_comment_full_with_line_break_resize_uses_683`<br>`test_convert_multiline_resize_changes_dialogue_font_size` |
| M2 行数の判定 >= → > | 13 failed | `test_measure_comment_line_break_resize_at_threshold[medium]`（落ちた） | `test_measure_comment_line_break_resize_at_threshold[big]`<br>`test_measure_comment_line_break_resize_at_threshold[medium]`<br>`test_measure_comment_line_break_resize_at_threshold[small]`<br>`test_measure_comment_trailing_empty_line_counts`<br>`test_measure_comment_ender_skips_line_break_resize[big]`<br>`test_measure_comment_ender_skips_line_break_resize[medium]`<br>`test_measure_comment_ender_skips_line_break_resize[small]`<br>`test_measure_comment_line_break_resize_applies_to_naka`<br>`test_resize_y_then_x_grow_path_scales_unresized_base`<br>`test_resize_y_then_x_shrink_path_scales_unresized_base`<br>`test_resize_y_then_x_bisect_path_measures_scaled_candidates`<br>`test_measure_comment_full_with_line_break_resize_uses_683`<br>`test_convert_multiline_resize_changes_dialogue_font_size` |
| M3 ender の判定を外す | 4 failed | `test_measure_comment_ender_skips_line_break_resize[small]`（落ちた） | `test_measure_comment_ender_skips_line_break_resize[big]`<br>`test_measure_comment_ender_skips_line_break_resize[medium]`<br>`test_measure_comment_ender_skips_line_break_resize[small]`<br>`test_measure_comment_ender_keeps_width_resize` |
| M4 resized の行の高さの式（比を逆に） | 13 failed | `test_measure_comment_line_break_resize_at_threshold[big]`（落ちた） | `test_measure_comment_line_break_resize_at_threshold[big]`<br>`test_measure_comment_line_break_resize_at_threshold[medium]`<br>`test_measure_comment_line_break_resize_at_threshold[small]`<br>`test_measure_comment_trailing_empty_line_counts`<br>`test_measure_comment_ender_skips_line_break_resize[big]`<br>`test_measure_comment_ender_skips_line_break_resize[medium]`<br>`test_measure_comment_ender_skips_line_break_resize[small]`<br>`test_measure_comment_line_break_resize_applies_to_naka`<br>`test_resize_y_then_x_grow_path_scales_unresized_base`<br>`test_resize_y_then_x_shrink_path_scales_unresized_base`<br>`test_resize_y_then_x_bisect_path_measures_scaled_candidates`<br>`test_measure_comment_full_with_line_break_resize_uses_683`<br>`test_convert_multiline_resize_changes_dialogue_font_size` |
| M5 文字サイズを行の高さの比で縮めない | 13 failed | `test_measure_comment_line_break_resize_at_threshold[small]`（落ちた） | `test_measure_comment_line_break_resize_at_threshold[big]`<br>`test_measure_comment_line_break_resize_at_threshold[medium]`<br>`test_measure_comment_line_break_resize_at_threshold[small]`<br>`test_measure_comment_trailing_empty_line_counts`<br>`test_measure_comment_ender_skips_line_break_resize[big]`<br>`test_measure_comment_ender_skips_line_break_resize[medium]`<br>`test_measure_comment_ender_skips_line_break_resize[small]`<br>`test_measure_comment_line_break_resize_applies_to_naka`<br>`test_resize_y_then_x_grow_path_scales_unresized_base`<br>`test_resize_y_then_x_shrink_path_scales_unresized_base`<br>`test_resize_y_then_x_bisect_path_measures_scaled_candidates`<br>`test_measure_comment_full_with_line_break_resize_uses_683`<br>`test_convert_multiline_resize_changes_dialogue_font_size` |
| M6 683 → 512 | 4 failed | `test_measure_comment_full_width_limit[full-under683]`（落ちた） | `test_measure_comment_full_width_limit[full-under683]`<br>`test_measure_comment_full_width_limit[full-over683]`<br>`test_measure_comment_full_limit_divided_by_font_scale`<br>`test_measure_comment_full_with_line_break_resize_uses_683` |
| M7 full を見ない | 4 failed | `test_measure_comment_full_with_line_break_resize_uses_683`（落ちた） | `test_measure_comment_full_width_limit[full-under683]`<br>`test_measure_comment_full_width_limit[full-over683]`<br>`test_measure_comment_full_limit_divided_by_font_scale`<br>`test_measure_comment_full_with_line_break_resize_uses_683` |
| M8 上限を font_scale で割らない | 2 failed | `test_measure_comment_full_limit_divided_by_font_scale`（落ちた） | `test_resize_judges_width_after_font_scale`<br>`test_measure_comment_full_limit_divided_by_font_scale` |
| M9 縮小前の基準を渡さない | 3 failed | `test_resize_y_then_x_grow_path_scales_unresized_base`（落ちた） | `test_resize_y_then_x_grow_path_scales_unresized_base`<br>`test_resize_y_then_x_shrink_path_scales_unresized_base`<br>`test_resize_y_then_x_bisect_path_measures_scaled_candidates` |
| M10 1 ずつの経路の resizedY を外す | 2 failed | `test_resize_y_then_x_shrink_path_scales_unresized_base`（落ちた） | `test_resize_y_then_x_grow_path_scales_unresized_base`<br>`test_resize_y_then_x_shrink_path_scales_unresized_base` |
| M11 二分探索の候補に比を掛けない | 1 failed | `test_resize_y_then_x_bisect_path_measures_scaled_candidates`（落ちた） | `test_resize_y_then_x_bisect_path_measures_scaled_candidates` |
| M12 二分探索の結果に比を掛けない | 1 failed | `test_resize_y_then_x_bisect_path_measures_scaled_candidates`（落ちた） | `test_resize_y_then_x_bisect_path_measures_scaled_candidates` |
| M13 ender を読まない | 6 failed | `test_parse_commands_ender_full[ender]`（落ちた） | `test_parse_commands_ender_full[ender]`<br>`test_parse_commands_ender_full[both]`<br>`test_measure_comment_ender_skips_line_break_resize[big]`<br>`test_measure_comment_ender_skips_line_break_resize[medium]`<br>`test_measure_comment_ender_skips_line_break_resize[small]`<br>`test_measure_comment_ender_keeps_width_resize` |
| M14 full を読まない | 6 failed | `test_parse_commands_ender_full[full-upper]`（落ちた） | `test_parse_commands_ender_full[full-upper]`<br>`test_parse_commands_ender_full[both]`<br>`test_measure_comment_full_width_limit[full-under683]`<br>`test_measure_comment_full_width_limit[full-over683]`<br>`test_measure_comment_full_limit_divided_by_font_scale`<br>`test_measure_comment_full_with_line_break_resize_uses_683` |
| M15 流れるコメントにも full の上限で横の縮小 | 6 failed | `test_convert_full_does_not_change_naka`（落ちた） | `test_resize_not_applied_to_naka`<br>`test_convert_output_unchanged_where_no_pseudo_bold[macos]`<br>`test_convert_output_unchanged_where_no_pseudo_bold[other]`<br>`test_convert_output_unchanged_where_no_pseudo_bold[windows-gothic]`<br>`test_convert_full_does_not_change_naka`<br>`test_convert_output_unchanged_without_multiline_ender_full_windows` |
| M16 閾値を 1 ずつ下げる（big 2 / medium 4 / small 6） | 3 failed | `test_measure_comment_no_line_break_resize_below_threshold[small]`（落ちた） | `test_measure_comment_no_line_break_resize_below_threshold[big]`<br>`test_measure_comment_no_line_break_resize_below_threshold[medium]`<br>`test_measure_comment_no_line_break_resize_below_threshold[small]` |

## C6: `sm9560870` の焼きこみと Web（2026-11-15）

- 焼きこみ: 実装（`503d3d7`。その後の変更は docs だけ）の `convert`（Windows の Pillow の測定・寸法・擬似ボールドの増分、1920 × 1080、不透明度 1.0、`random.Random(0)`）で、#388 の取得（230 件）から ASS を作り、黒地に libass で描いた（`frame388.py`）。インクの外接矩形と字の間隔は `cmp388.py`。
- Web: 内蔵ブラウザ（Chromium 156、devicePixelRatio 1.5）のプレイヤーで、14 秒から再生し、18.301 / 23.204 / 29.905 秒にコメントの canvas（1365 × 768）を一時停止せずに写し取った。同じ判定（白 = RGB とも 200 超、cyan = R 120 未満・G / B 150 超、アルファ 128 超）で、1920 × 1080 に換算した。

| 時刻・コメント | 種類 | Web | 焼きこみ |
|---|---|---|---|
| 18.3 秒「＜ああああああ」（上） | `ue medium`・13 行（15.45 秒開始。複数行の縮小） | x 925.5〜1192.8、y 396.7〜431.8 | x 926〜1196、y 398〜432 |
| 18.3 秒「＜ああああああ」（下） | `ue medium`・12 行（17.76 秒開始。複数行の縮小） | x 827.1〜1094.3、y 603.4〜638.6 | x 825〜1094、y 590〜625 |
| 29.9 秒「真夏の夜の淫夢」 | `ue big ender full`・10 行のコメントアート（舞台の幅 273 で上限に届かず、横の縮小は起きない） | x 580.9〜1337.7、y 527.5〜627.3 | x 580〜1337、y 530〜629 |
| 29.9 秒の投稿コメント | `ue medium`・5 行（閾値ちょうど、2 つの縮小が両方かかる） | 字の間隔 64.7（中央値。1 行目は画面の両端からはみ出す） | 64.59（平均。同じく両端からはみ出す） |
| 23.2 秒「あ」40 字 × 5 段 | 1 行の `ue medium` が 5 件（横の縮小で font_px 12 ほど） | 字の間隔 33.76、x 286.9〜1630.2 | 34.56（+2.4%）、x 272〜1645 |
| 42.17 秒の投稿コメント | `ue big`・3 行（閾値ちょうど、2 つの縮小が両方かかる） | 字の間隔 32.674（舞台） | 32.672（「設計レビューと…」の予測。実装の `measure_comment` も文字サイズ 43.44・font_px 34・幅 915 で予測と同じ） |
| 23.2 秒「アンインストール」 | 22.58 秒の `ue big ender full`・10 行のコメントアート（文字は 6 行目） | x 535.9〜1389.7、上端 y 533.1 | x 536〜1390、上端 y 535 |
| 79.4 秒の白いブロック 3 本 | 78.83 秒の `ue white big mincho full`・1 行 × 3 件（実際の本文（75 文字）から実装の `measure_comment` で計算すると、縮小前の舞台の幅は 2,899。`full` で上限 683 に合わせて 669（文字サイズ 11.599、font_px 10、scale 0.9）、`full` が無ければ上限 512 に合わせて 446（文字サイズ 8.695、font_px 10、scale 0.6）。`full388.py`） | y 828.5〜852.4 / 860.8〜884.7 / 894.6〜917.1、x 423.4〜1763.9 / 〜1713.2 / 〜1637.3 | y 830〜853 / 862〜886 / 895〜918、x 424〜1764 / 〜1713 / 〜1637 |

- 複数行の縮小（18.3 秒）、`full`（79.4 秒の白いブロック）、2 つの縮小が両方かかるとき（29.9 秒・42.17 秒）、`ender` のコメントアート（23.2 秒・29.9 秒）は、幅と字の間隔が Web とおよそ 1% 以内（最大は 18.3 秒の上の行の幅 267.3 と 270 で 1.01%）で合った。
- 行の高さ: 文字のある行が 2 行目以降のコメントでは、文字の上端の y が行の高さ × 行の番号で決まる。18.3 秒の上の行（13 行のうち 8 行目、複数行の縮小の行の高さ 15.02、キャンバスで 1 行 42.2 px）の上端は Web 396.7 / 焼きこみ 398、23.2 秒の「アンインストール」（10 行のうち 6 行目、`ender` で縮小前の行の高さ 45.24、1 行 127.2 px）の上端は Web 533.1 / 焼きこみ 535 で、差は 1.3 px と 1.9 px。行の高さが 1% 違えば、前者で約 3 px、後者で約 6 px ずれる位置。どちらも上固定で、コメントの上端が同じ位置にあるとみなした比較。
- 違い 1: 18.3 秒の下の「＜ああ」（17.76 秒開始）は、焼きこみの y が Web より 13 px 上。原因は調べていない（分からない）。コメントの対応は、焼きこみの ASS の `Dialogue` の開始時刻と `\pos` で確かめた（`at388.py`）。
- 違い 2: 29.9 秒の投稿コメントの縦位置は、Web が上端、焼きこみが y 687。乱数の種を変えると y が 687 / 357 / 26 と動く（`seed388.py`）ので、行が埋まったときのランダム配置で、Web（種の無い乱数）とは原理的に一致しない。
- 違い 3: 23.2 秒の 1 行のコメントの字の間隔が 2.4% 広い。#388 の変更の対象外（1 行のコメントの横の縮小、#387 の経路）。字の大きさが 12px ほどで、Chrome が 22px 以下で幅を 1 字ずつ整数に丸めること（#391 で再現しないと決めた限界）で説明できる差と見ているが、確かめていない。
- 22.58 秒の「アンインストール」は重なった色（赤・黒・cyan）が暗く、色の判定には当たらなかったので、いずれかの色が 60 を超える画素で、「＜ああ」と重ならない y 480〜600 の範囲の外接矩形を比べた（`art388.py`、Web は同じ判定の JS）。
- 追加の撮り直し（evaluator 1 巡目の指摘を受けて、2026-11-15）: Web は 73 秒から再生し、79.446 秒に canvas を写し取った。白いインクを横帯に区切って比べた（`bands388.py`、Web は同じ判定の JS）。焼きこみは同じ時刻を `frame388.py` で描いた。

## 検証ゲート

| 巡 | HEAD | verify | docs-check | evaluator |
|---|---|---|---|---|
| 1 | `abb6d24` | green（944 passed、skip 0） | 限定句 1 件（arch、直した） | FAIL（[欠陥] 2 / [証跡・文言] 3） |
| 2 | `4765152` | green（944 passed） | —（docs だけの変更） | PASS（follow-up あり。[欠陥] 0 / [証跡・文言] 1。78.83 秒の数値の誤りで、この PR で直した。訂正ログ 2 件目で止まり、ユーザーに方針を確認した） |

evaluator 1 巡目の指摘と閉じ方:

| 指摘 | 区分 | 閉じ方 | 証跡 |
|---|---|---|---|
| 1 C6 で行の高さと 22.58 秒のコメントアートを数値で比べていない | 欠陥 | Web の 79.4 秒を撮り直し、`full` を実際に通るコメントで比べた。22.58 秒のコメントアートを数値で比べた。行の高さは、2 行目以降に文字がある 2 件の上端の y で比べた | 「C6」の表の 23.2 秒「アンインストール」と 79.4 秒の行、「行の高さ」の項 |
| 2 閾値未満のテストの red が無い | 欠陥 | 変異 M16（閾値を 1 ずつ下げる）を足した | 「変異 → red（C7、abb6d24）」の M16 |
| 3 29.9 秒の cyan を `full` の確認とした誤り、「1% 以内」、42.17 秒の列 | 証跡・文言 | 表と本文を直し、訂正ログに 1 行足した | 「C6」、訂正ログ |
| 4 spec の「2017-07-12 より前」に限定句が無い | 証跡・文言 | 「2 本の動画で」を足した | `docs/spec/screens/original-format-panel.md` |
| 5 メモの `_body_lines` の行番号が古い | 証跡・文言 | 直した | 「着手時の調べ」 |

## プローブの本文

追跡しない scratchpad の script。`git hash-object` は記録した数値を出したときの本文のもの。証跡の段へ移った日と主張（policy §8.0）: 2026-11-15、arch の「複数行の縮小と `ender` / `full`」の式と、2 つの縮小が両方かかるときに Web がはみ出して描くこと、C6 の数値。

<details><summary>ref388.py（テストの期待値（C1〜C4）、<code>c5ffc9c0cadf9bd9b75b9c820e94d70e56bb4c50</code>）</summary>

```python
"""#388 のテストの期待値を、niconicomments の式（HTML5Comment.ts / niconico.ts）から実装と独立に計算する。

nico_ass を import しない。測定器はテストと同じ形（行の文字数 × font_px × 係数 + 足し分）を自前で持つ。
"""

import math

H = 384
DEFAULT = {"big": 8.4, "medium": 13.1, "small": 21}
RESIZED = {"big": 16, "medium": 25.4, "small": 38}
DOUBLE = {"big": 7.8, "medium": 11.3, "small": 16.6}


def char_size(s):  # niconico.ts getCharSize
    return H / DOUBLE[s]


def line_height(s, resized=False):  # niconico.ts getLineHeight
    lh = H / DOUBLE[s]
    if resized:
        return (H - lh * (DEFAULT[s] / RESIZED[s])) / (RESIZED[s] - 1)
    return (H - lh) / (DEFAULT[s] - 1)


def fsas(c):  # niconico.ts getFontSizeAndScale
    c *= 0.8
    if c < 10:
        if c >= 1:
            c = math.floor(c)
        return 10, c / 10
    return math.floor(c), 1


def make_width(counts, k, offset):
    def width(c):
        fp, sc = fsas(c)
        return max(math.ceil((n * fp * k + offset) * sc) for n in counts)
    return width


def resize_y(s):
    lh0, c0 = line_height(s), char_size(s)
    lh1 = line_height(s, True)
    return c0 * (lh1 / lh0), lh1


def process_resize_x(s, width_at, cur_c, cur_lh, limit, resized_y):  # HTML5Comment.ts:269-430
    base_c, base_lh = char_size(s), line_height(s)
    w = width_at(cur_c)
    scale = limit / w
    current_c = max(1e-6, cur_c)
    current_lh = max(1e-6, cur_lh)
    raw_c, raw_lh = current_c * scale, current_lh * scale
    bc, blh = max(1e-6, raw_c), max(1e-6, raw_lh)
    lc, llh = max(1, raw_c), max(1, raw_lh)
    path = None
    if bc >= 1:
        r, rlh = lc, llh
        res = width_at(r)
        if res > limit:
            path = "shrink"
            it = 20
            while res > limit and r > 1 and it > 0:
                it -= 1
                o = r
                r = max(1, r - 1)
                rlh *= r / o
                res = width_at(r)
        else:
            path = "grow"
            last, lastlh = r, rlh
            it = 20
            while res < limit and it > 0:
                it -= 1
                last, lastlh = r, rlh
                o = r
                r += 1
                rlh *= r / o
                res = width_at(r)
            r, rlh = last, lastlh
        if resized_y:
            k = r / cur_c
            return k * base_c, k * base_lh, path
        return r, rlh, path

    def measured(n):
        n = max(1e-6, n)
        if resized_y:
            return width_at((n / current_c) * base_c)
        return width_at(n)

    best = bc
    if measured(bc) > limit:
        low, high, it = 1e-6, bc, 20
        best = low
        if measured(low) <= limit:
            while it > 0 and low < high:
                it -= 1
                cand = (low + high) / 2
                if measured(cand) <= limit:
                    best, low = cand, cand
                else:
                    high = cand
    else:
        low, high, it = bc, current_c, 20
        while it > 0 and low < high:
            it -= 1
            mid = (low + high) / 2
            if measured(mid) <= limit:
                best, low = mid, mid
            else:
                high = mid
    if resized_y:
        k = best / current_c
        return k * base_c, k * base_lh, "bisect"
    return best, blh * (best / bc), "bisect"


def show(name, s, counts, k, offset, limit=512, multi=True):
    width_at = make_width(counts, k, offset)
    c, lh = resize_y(s) if multi else (char_size(s), line_height(s))
    w = width_at(c)
    print(f"{name}: 縮小前 c={c!r} lh={lh!r} 幅 {w}")
    if w > limit:
        c, lh, path = process_resize_x(s, width_at, c, lh, limit, multi)
        fp, sc = fsas(c)
        n_lines = len(counts)
        print(f"  {path}: c={c!r} lh={lh!r} font_px={fp} scale={sc!r} widths={[math.ceil((n * fp * k + offset) * sc) for n in counts]} height={lh * (n_lines - 1) + c!r}")


for s in ("big", "medium", "small"):
    c, lh = resize_y(s)
    print(s, "char", char_size(s), "lh", line_height(s), "resized char", c, "resized lh", lh, "fsas", fsas(c))
show("C2 grow (big, 30字+1+1, k=1)", "big", [30, 1, 1], 1, 0)
show("C2 shrink (big, 30字+1+1, k=1, +40)", "big", [30, 1, 1], 1, 40)
show("C2 bisect (big, 20字+1+1, k=40)", "big", [20, 1, 1], 40, 0)
show("C4 full (medium 26字, 683)", "medium", [26], 1, 0, limit=683, multi=False)
show("C4 no full (medium 26字, 512)", "medium", [26], 1, 0, limit=512, multi=False)
show("C3 ender ue wide (medium 20字×5行 単一でなく)", "medium", [20, 1, 1, 1, 1], 1, 0, multi=False)
show("C4 full+multi (big 30字+1+1, 683)", "big", [30, 1, 1], 1, 0, limit=683)
show("C4 no full (medium 20字, 512)", "medium", [20], 1, 0, limit=512, multi=False)
show("C4 full 20字 font_scale 1.5 (683/1.5)", "medium", [20], 1, 0, limit=683 / 1.5, multi=False)
```

</details>

<details><summary>both_predict.py（2 つの縮小が両方かかるときの予測、<code>03639cd9fd8d1032f465b4d13e7c4cc5f6afdc5d</code>）</summary>

```python
"""投稿してもらったコメントで、2 つの縮小が両方かかったときの結果を ts どおり（B）と、収まる式（C）で計算する。"""

import math
import sys
from pathlib import Path

sys.path.insert(0, r"C:\Users\f8924\Documents\claude\yt-gui")
from yt_gui import nico_ass as n  # noqa: E402

RESIZED = {"big": 16, "medium": 25.4, "small": 38}
measure = n.pillow_measurer("windows")
advance = n.pseudo_bold_advancer("windows")


def width_at(lines, size_char):
    font_px, scale = n.font_size_and_scale(size_char)
    out = []
    for line in lines:
        total = 0.0
        for t, f in n.font_runs(line, "defont", "windows"):
            total += measure(t, f.name, f.weight, font_px) + sum(advance(ch, f, font_px) for ch in t)
        out.append(math.ceil(total * scale))
    return max(out)


for size, body in (("big", "あ" * 28 + "\nあ\nあ"), ("medium", "あ" * 40 + "\nあ\nあ\nあ\nあ")):
    lines = body.split("\n")
    base_c, base_lh = n.char_size(size), n.line_height(size)
    rlh = (384 - base_c * (n._DEFAULT_LINE_COUNT[size] / RESIZED[size])) / (RESIZED[size] - 1)
    rc = base_c * rlh / base_lh
    w = width_at(lines, rc)
    # legacy 経路（ts の 1 ずつ動かす経路）
    ratio = 512 / w
    r = max(1, rc * ratio)
    res = width_at(lines, r)
    if res > 512:
        it = 20
        while res > 512 and r > 1 and it > 0:
            it -= 1
            r = max(1, r - 1)
            res = width_at(lines, r)
    else:
        last = r
        it = 20
        while res < 512 and it > 0:
            it -= 1
            last = r
            r += 1
            res = width_at(lines, r)
        r = last
    s = r / rc
    b_char, b_lh = s * base_c, s * base_lh
    c = n._COMMENT_SCALE
    print(f"{size}: 縮小前 char {base_c:.2f} / 複数行の縮小後 char {rc:.2f} lh {rlh:.2f} 幅 {w}")
    print(f"  B（ts どおり）: char {b_char:.2f} lh {b_lh:.2f} 幅 {width_at(lines, b_char)} → キャンバス {width_at(lines, b_char) * c:.0f} px、高さ {(b_lh * (len(lines) - 1) + b_char) * c:.0f} px")
    print(f"  C（収まる）  : char {r:.2f} lh {rlh * r / rc:.2f} 幅 {width_at(lines, r)} → キャンバス {width_at(lines, r) * c:.0f} px、高さ {(rlh * r / rc * (len(lines) - 1) + r) * c:.0f} px")
    print(f"  参考: 複数行の縮小なしで上下固定の縮小だけ（#387 の今の動き）")
```

</details>

<details><summary>mutate388.py（変異 → red（C7）、<code>f7f814d86976ac36e082ff5ace188bcc6107a220</code>）</summary>

```python
"""#388 の変異 → red。worktree のコピーを変異させ、落ちたテスト名を集める。

使い方: python mutate388.py <worktree のパス>
無変異のコピーが green でなければ止まる。変異が当たらない（置換 1 件以外）ときも止まる（fail-closed）。
"""

import re
import subprocess
import sys
from pathlib import Path

WT = Path(sys.argv[1])
TESTS = ["tests/test_nico_ass.py", "tests/test_downloader.py"]
F = "yt_gui/nico_ass.py"

MUTANTS = [
    ("M1 big の閾値 3 → 4", F,
     '_LINE_BREAK_COUNT = {"big": 3,', '_LINE_BREAK_COUNT = {"big": 4,',
     "test_measure_comment_line_break_resize_at_threshold[big]"),
    ("M2 行数の判定 >= → >", F,
     "len(lines) >= _LINE_BREAK_COUNT[cmd.size]", "len(lines) > _LINE_BREAK_COUNT[cmd.size]",
     "test_measure_comment_line_break_resize_at_threshold[medium]"),
    ("M3 ender の判定を外す", F,
     "resized_y = not cmd.ender and len(lines)", "resized_y = len(lines)",
     "test_measure_comment_ender_skips_line_break_resize[small]"),
    ("M4 resized の行の高さの式（比を逆に）", F,
     "base * (_DEFAULT_LINE_COUNT[size] / resized)", "base * (resized / _DEFAULT_LINE_COUNT[size])",
     "test_measure_comment_line_break_resize_at_threshold[big]"),
    ("M5 文字サイズを行の高さの比で縮めない", F,
     "cur_char = cur_char * (new_height / cur_height)", "cur_char = cur_char",
     "test_measure_comment_line_break_resize_at_threshold[small]"),
    ("M6 683 → 512", F,
     "_STAGE_FULL_WIDTH = 683", "_STAGE_FULL_WIDTH = 512",
     "test_measure_comment_full_width_limit[full-under683]"),
    ("M7 full を見ない", F,
     "width_limit = _STAGE_FULL_WIDTH if cmd.full else _STAGE_WIDTH", "width_limit = _STAGE_WIDTH",
     "test_measure_comment_full_with_line_break_resize_uses_683"),
    ("M8 上限を font_scale で割らない", F,
     "            width_limit / font_scale,\n", "            width_limit,\n",
     "test_measure_comment_full_limit_divided_by_font_scale"),
    ("M9 縮小前の基準を渡さない", F,
     "unresized=(base_char, base_line_height) if resized_y else None", "unresized=None",
     "test_resize_y_then_x_grow_path_scales_unresized_base"),
    ("M10 1 ずつの経路の resizedY を外す", F,
     "        if unresized is not None:\n            # ts: :350-353", "        if False:\n            # ts: :350-353",
     "test_resize_y_then_x_shrink_path_scales_unresized_base"),
    ("M11 二分探索の候補に比を掛けない", F,
     "        if unresized is not None:\n            # ts: :367-379", "        if False:\n            # ts: :367-379",
     "test_resize_y_then_x_bisect_path_measures_scaled_candidates"),
    ("M12 二分探索の結果に比を掛けない", F,
     "    if unresized is not None:\n        # ts: :416-420", "    if False:\n        # ts: :416-420",
     "test_resize_y_then_x_bisect_path_measures_scaled_candidates"),
    ("M13 ender を読まない", F,
     'elif command == "ender":', 'elif command == "enderx":',
     "test_parse_commands_ender_full[ender]"),
    ("M14 full を読まない", F,
     'elif command == "full":', 'elif command == "fullx":',
     "test_parse_commands_ender_full[full-upper]"),
    ("M15 流れるコメントにも full の上限で横の縮小", F,
     "if cmd.loc != \"naka\" and max_width * font_scale > width_limit:",
     "if max_width * font_scale > width_limit:",
     "test_convert_full_does_not_change_naka"),
    ("M16 閾値を 1 ずつ下げる（big 2 / medium 4 / small 6）", F,
     '_LINE_BREAK_COUNT = {"big": 3, "medium": 5, "small": 7}', '_LINE_BREAK_COUNT = {"big": 2, "medium": 4, "small": 6}',
     "test_measure_comment_no_line_break_resize_below_threshold[small]"),
]


def run_tests() -> tuple[int, list[str], str]:
    p = subprocess.run(
        ["uv", "run", "pytest", *TESTS, "-q", "-p", "no:cacheprovider", "-rf"],
        cwd=WT, capture_output=True, text=True, encoding="utf-8",
    )
    failed = re.findall(r"^FAILED (\S+)", p.stdout, re.M)
    summary = (p.stdout.strip().splitlines() or [""])[-1]
    return p.returncode, failed, summary


code, failed, summary = run_tests()
print("unmutated:", summary)
if code != 0 or failed or "passed" not in summary:
    sys.exit("無変異のコピーが green でない")

ok = True
for name, rel, old, new, target in MUTANTS:
    path = WT / rel
    src = path.read_text(encoding="utf-8")
    if src.count(old) != 1:
        print(f"{name}: 変異が当たらない（{src.count(old)} 件）")
        ok = False
        continue
    path.write_text(src.replace(old, new), encoding="utf-8", newline="\n")
    try:
        code, failed, summary = run_tests()
    finally:
        path.write_text(src, encoding="utf-8", newline="\n")
    names = [f.split("::", 1)[1] for f in failed]
    hit = target in names
    ok = ok and hit and code != 0
    print(f"{name}: {summary} / 狙い {'落ちた' if hit else '落ちない'}: {target}")
    for n in names:
        print(f"    - {n}")

code, failed, summary = run_tests()
print("restored:", summary)
print("ALL TARGETED KILLED" if ok and code == 0 else "NG")
```

</details>

<details><summary>mut_table.py（死因の表（C7）、<code>2fe2ce089b5799bb055090607d35a915573d9281</code>）</summary>

```python
"""mutate391 のログから、死因の表（変異ごとに落ちたテストを全部）を markdown で出す。"""

import re
import sys

lines = open(sys.argv[1], encoding="utf-8").read().splitlines()
rows = []
cur = None
for line in lines:
    m = re.match(r"^(M\d+) (.+?): (\d+) failed.*/ 狙い (\S+): (.+)$", line)
    if m:
        cur = {"id": m[1], "name": m[2], "n": m[3], "hit": m[4], "target": m[5], "tests": []}
        rows.append(cur)
    elif line.startswith("    - ") and cur is not None:
        name = line[6:].encode().decode("unicode_escape") if "\\u" in line else line[6:]
        cur["tests"].append(name)
print("| 変異 | 件数 | 狙ったテスト | 落ちたテスト（全部） |")
print("|---|---|---|---|")
for r in rows:
    assert len(r["tests"]) == int(r["n"]), r["id"]
    target = r["target"].encode().decode("unicode_escape") if "\\u" in r["target"] else r["target"]
    tests = "<br>".join(f"`{t}`" for t in r["tests"])
    print(f"| {r['id']} {r['name']} | {r['n']} failed | `{target}`（{r['hit']}） | {tests} |")
```

</details>

<details><summary>pick388.py（C6 のコメントの選び出し、<code>758c873f5ed9aaf254bd3feeb6480117a89d637d</code>）</summary>

```python
"""C6: sm9560870 のコメントを、複数行の縮小・ender・full・上下固定の縮小の別に並べる。"""

import json
import sys

sys.path.insert(0, r"C:\Users\f8924\Documents\claude\yt-gui")
from yt_gui import nico_ass as n  # noqa: E402

data = json.load(open(sys.argv[1], encoding="utf-8-sig"))
rows = []


def walk(o):
    if isinstance(o, dict):
        if "commands" in o and "body" in o:
            rows.append(o)
        else:
            for v in o.values():
                walk(v)
    elif isinstance(o, list):
        for v in o:
            walk(v)


walk(data)
measure = n.pillow_measurer("windows")
advance = n.pseudo_bold_advancer("windows")
for r in sorted(rows, key=lambda r: r["vposMs"]):
    cmd = n.parse_commands(r["commands"], r["body"], r.get("isPremium", False))
    if cmd.invisible:
        continue
    lines = n._body_lines(r["body"])
    m = n.measure_comment(lines, cmd, platform="windows", measure=measure, advance=advance, font_scale=1)
    ry = not cmd.ender and len(lines) >= n._LINE_BREAK_COUNT[cmd.size]
    if not (ry or cmd.ender or cmd.full) or len(lines) < 2:
        continue
    tag = ("Y" if ry else "-") + ("E" if cmd.ender else "-") + ("F" if cmd.full else "-")
    print(f"{r['vposMs'] / 1000:7.2f} {tag} {cmd.loc:5} {cmd.size:6} {cmd.color:8} 行{len(lines):3} char {m.char_size:6.2f} font {m.font_px:2} 幅 {m.width:7.1f} 高 {m.height:7.1f} {r['body'][:12]!r}")
```

</details>

<details><summary>frame388.py（C6 の焼きこみのフレーム、<code>8f1315377eb823c205b32c800898c398aa2382b2</code>）</summary>

```python
"""C6: sm9560870（#388 の取得）から 1920x1080 の ASS を作り、指定の時刻を黒地に描く。

使い方: python frame388.py <出力先> <comments.json> <時刻>...
"""

import json
import random
import subprocess
import sys
from pathlib import Path

ROOT = Path(r"C:\Users\f8924\Documents\claude\yt-gui")
sys.path.insert(0, str(ROOT))
from yt_gui import nico_ass  # noqa: E402

OUT = Path(sys.argv[1])
OUT.mkdir(exist_ok=True)
FFMPEG = str(ROOT / "bin" / "ffmpeg" / "ffmpeg.exe")
data = json.load(open(sys.argv[2], encoding="utf-8-sig"))
rows = []


def walk(o):
    if isinstance(o, dict):
        if "commands" in o and "body" in o:
            rows.append(o)
        else:
            for v in o.values():
                walk(v)
    elif isinstance(o, list):
        for v in o:
            walk(v)


walk(data)
ass = nico_ass.convert(
    json.dumps(rows, ensure_ascii=False), width=1920, height=1080, font_scale_percent=100,
    opacity=1.0, platform="windows", measure=nico_ass.pillow_measurer("windows"),
    metrics=nico_ass.font_metrics("windows"), advance=nico_ass.pseudo_bold_advancer("windows"),
    rng=random.Random(0),
).ass
(OUT / "sm9560870.ass").write_text(ass, encoding="utf-8-sig")
for t in sys.argv[3:]:
    subprocess.run(
        [FFMPEG, "-y", "-loglevel", "error", "-f", "lavfi", "-i",
         f"color=black:s=1920x1080:d={float(t) + 1}", "-vf", "ass=sm9560870.ass", "-ss", t,
         "-frames:v", "1", f"ours_{t}.png"],
        cwd=OUT, check=True,
    )
    print(OUT / f"ours_{t}.png")
```

</details>

<details><summary>cmp388.py（C6 の外接矩形と字の間隔、<code>28465d2bf82d79b0375ae11708075ed1bbfa08d4</code>）</summary>

```python
"""C6: 焼きこみ（1920x1080 の PNG）で、Web と同じ判定のインクの外接矩形と字の間隔を出す。"""

import sys
from pathlib import Path

from PIL import Image

D = Path(sys.argv[1])


def load(t):
    return Image.open(D / f"ours_{t}.png").convert("RGB")


def box(img, pred, x0, y0, x1, y1):
    px = img.load()
    xs, ys = [], []
    for y in range(y0, y1):
        for x in range(x0, x1):
            if pred(px[x, y]):
                xs.append(x)
                ys.append(y)
    return (min(xs), max(xs), min(ys), max(ys)) if xs else None


def pitch(img, y0, y1):
    px = img.load()
    col = [sum(1 for y in range(y0, y1) if min(px[x, y]) > 200) for x in range(1920)]
    starts, gap = [], 99
    for x, n in enumerate(col):
        if n:
            if gap >= 2:
                starts.append(x)
            gap = 0
        else:
            gap += 1
    diffs = sorted(b - a for a, b in zip(starts, starts[1:]))
    return {"n": len(starts), "median": diffs[len(diffs) // 2], "first": starts[0], "last": starts[-1],
            "mean": round((starts[-1] - starts[0]) / (len(starts) - 1), 2)}


white = lambda p: p[0] > 200 and p[1] > 200 and p[2] > 200  # noqa: E731
cyan = lambda p: p[0] < 120 and p[1] > 150 and p[2] > 150  # noqa: E731
i18, i23, i29 = load("18.3"), load("23.2"), load("29.9")
print("18.3 white upper", box(i18, white, 700, 300, 1300, 520))
print("18.3 white lower", box(i18, white, 700, 520, 1300, 720))
print("23.2 white block", box(i23, white, 0, 0, 1920, 260))
print("29.9 white line (ours y 680-770)", box(i29, white, 0, 680, 1920, 770))
print("29.9 cyan", box(i29, cyan, 0, 400, 1920, 800))
print("23.2 block row1 pitch", pitch(i23, 8, 50))
print("29.9 line pitch (ours y 680-770)", pitch(i29, 680, 770))
```

</details>

<details><summary>seed388.py（C6 のランダム配置の確かめ、<code>92fe93fef3065b1b8c0b8cb4b3e525272b49331d</code>）</summary>

```python
"""C6: 投稿してもらった 29.35 秒の medium・5 行の位置が、乱数の種で変わるか（ランダム配置か）。"""

import json
import random
import re
import sys

sys.path.insert(0, r"C:\Users\f8924\Documents\claude\yt-gui")
from yt_gui import nico_ass as n  # noqa: E402

data = json.load(open(sys.argv[1], encoding="utf-8-sig"))
rows = []


def walk(o):
    if isinstance(o, dict):
        if "commands" in o and "body" in o:
            rows.append(o)
        else:
            for v in o.values():
                walk(v)
    elif isinstance(o, list):
        for v in o:
            walk(v)


walk(data)
for seed in (0, 1, 2):
    ass = n.convert(
        json.dumps(rows, ensure_ascii=False), width=1920, height=1080, font_scale_percent=100,
        opacity=1.0, platform="windows", measure=n.pillow_measurer("windows"),
        metrics=n.font_metrics("windows"), advance=n.pseudo_bold_advancer("windows"),
        rng=random.Random(seed),
    ).ass
    ys = [
        re.search(r"\\pos\(([^)]*)\)", line).group(1)
        for line in ass.splitlines()
        if line.startswith("Dialogue: 0,0:00:29.35") and "あ" * 12 in line
    ]
    print(seed, ys)
```

</details>

<details><summary>at388.py（C6 のコメントの対応、<code>bf97ebab7e4c657f8b10077c665fdd16081f3ed6</code>）</summary>

```python
"""C6: 焼きこみの ASS で、指定の時刻に出ている「＜ああ」の Dialogue を並べる。"""

import re
import sys

ass = open(sys.argv[1], encoding="utf-8-sig").read()
t = float(sys.argv[2])


def sec(v):
    h, m, s = v.split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


for line in ass.splitlines():
    if not line.startswith("Dialogue:"):
        continue
    p = line.split(",", 9)
    if not sec(p[1]) <= t < sec(p[2]):
        continue
    body = re.sub(r"\{[^}]*\}", "", p[9])
    if "ああ" in body and ("＜" in body or "<" in body):
        pos = re.search(r"\\(pos|move)\(([^)]*)\)", p[9])
        an = re.search(r"\\an(\d)", p[9]).group(1)
        print(p[1], p[2], f"an{an}", pos.group(1), pos.group(2), body[:20])
```

</details>

<details><summary>bands388.py（C6 の横帯（79.4 秒）、<code>957dc980da6c13a60734219e7e16aa5e6698f7c6</code>）</summary>

```python
"""C6: 焼きこみの PNG（1920x1080）の白いインクを、横帯ごとに (y0, y1, x0, x1) で出す（Web の canvas と同じ判定）。"""

import sys

from PIL import Image

img = Image.open(sys.argv[1]).convert("RGB")
px = img.load()
W, H = img.size
bands, cur = [], None
for y in range(H):
    xs = [x for x in range(W) if min(px[x, y]) > 200]
    if xs:
        if cur is None:
            cur = [y, y, xs[0], xs[-1]]
        else:
            cur[1] = y
            cur[2] = min(cur[2], xs[0])
            cur[3] = max(cur[3], xs[-1])
    elif cur is not None:
        bands.append(cur)
        cur = None
if cur is not None:
    bands.append(cur)
for b in bands:
    print(b)
```

</details>

<details><summary>art388.py（C6 のコメントアート（23.2 秒）、<code>c213e7340249e76f4f46a0a19890539e20f9700a</code>）</summary>

```python
"""C6: 22.58 秒のコメントアート（10 行、6 行目に文字）のインクの外接矩形（いずれかの色が 60 超、y 480-600）。"""

import sys

from PIL import Image

img = Image.open(sys.argv[1]).convert("RGB")
px = img.load()
xs, ys = [], []
for y in range(480, 600):
    for x in range(300, 1700):
        if max(px[x, y]) > 60:
            xs.append(x)
            ys.append(y)
print(min(xs), max(xs), min(ys), max(ys))
```

</details>

<details><summary>full388.py（C6 の 78.83 秒の幅、<code>121bcd803e8ff74f17fb078beea38be6e00eb0b4</code>）</summary>

```python
"""78.83 秒の `ue white big mincho full` 3 件を、実際の本文で full あり / なし / 縮小前の幅を計算する。"""

import json
import sys

sys.path.insert(0, r"C:\Users\f8924\Documents\claude\yt-gui")
from yt_gui import nico_ass as n  # noqa: E402

data = json.load(open(sys.argv[1], encoding="utf-8-sig"))
rows = []


def walk(o):
    if isinstance(o, dict):
        if "commands" in o and "body" in o:
            rows.append(o)
        else:
            for v in o.values():
                walk(v)
    elif isinstance(o, list):
        for v in o:
            walk(v)


walk(data)
measure = n.pillow_measurer("windows")
advance = n.pseudo_bold_advancer("windows")
for r in rows:
    if r["vposMs"] != 78830:
        continue
    lines = n._body_lines(r["body"])
    print("本文の長さ", len(r["body"]), "行", len(lines))
    for cmds in (r["commands"], [c for c in r["commands"] if c != "full"]):
        cmd = n.parse_commands(cmds, r["body"], False)
        m = n.measure_comment(lines, cmd, platform="windows", measure=measure, advance=advance, font_scale=1)
        print("  full" if cmd.full else "  なし", round(m.char_size, 3), m.font_px, round(m.scale, 3), max(m.line_widths))
    cmd = n.parse_commands(r["commands"], r["body"], False)._replace(loc="naka")
    m = n.measure_comment(lines, cmd, platform="windows", measure=measure, advance=advance, font_scale=1)
    print("  縮小前", max(m.line_widths))
```

</details>

## 訂正ログ

| 日付 | 何を誤って書いたか | 正しくは | どの検査・手順なら捕まえたか |
|---|---|---|---|
| 2026-11-15 | C6 の表の 78.83 秒の行に、縮小前 1,560、`full` で 680（font_px 17）、無しで 480（font_px 12）と書いた | 実際の本文では縮小前 2,899、`full` で 669（font_px 10、scale 0.9）、無しで 446（font_px 10、scale 0.6） | 表示が途中で切れた本文から入力を組み立て直して計算した。実データを読むスクリプト（`full388.py`）の出力から転記すれば捕まえた（evaluator 2 巡目）。1 件目と同じく、数値を一次資料から出さずに書いた。以後、メモの数値は実データを読むスクリプトの出力だけから転記し、単位を出力に含める（ユーザー確認、2026-11-15） |
| 2026-11-15 | C6 の表と進捗に、29.9 秒の「真夏の夜の淫夢」を「上限 683 で横の縮小」とし、`full` の Web での確認として書いた | このコメントは舞台の幅 273 で上限に届かず、`full` は効いていない。`full` が効くのは 78.83 秒の 3 件で、79.4 秒で比べ直した | `pick388.py` が出した幅はキャンバスの単位（`Measured.width`）で、舞台の単位と読み違えた。単位を出力に書くか、上限と比べる値（舞台の幅）を出していれば捕まえた（evaluator 1 巡目） |

## 次にやること

C1〜C8 は証跡つきで完了し、evaluator は 2 巡目で PASS（follow-up あり。指摘 1 件はこの PR で直した）。次は PR。

訂正ログ: 2 件
