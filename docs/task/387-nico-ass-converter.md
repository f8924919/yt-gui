# ニコニコのコメントの ASS 変換を自作し、コマンドと表示時間を Web に合わせる

> Issue: [#387](https://github.com/f8924919/yt-gui/issues/387)
> ステータス: 進行中
> ブランチ: `feature/387-nico-ass-converter`
> 基点: `6a6a034`

受け入れ条件と移植元の値の正本は Issue。設計は [arch/nico_ass.md](../arch/nico_ass.md)。コメント再現度向上の第 2 段階の前半で、後半は #388。

## 進捗

- [x] C1 ニコニコは新しい変換、ビリビリは danmaku2ass — 証跡: `test_convert_comments_uses_new_converter_without_danmaku2ass`（danmaku2ass 不在でも ASS ができる）、ビリビリは `test_convert_danmaku_uses_bilibili_format_and_xml_input`（642b50e）
- [x] C2 入力のキーと vpos の換算、並び順と決定性 — 証跡: `tests/test_nico_ass.py` の `test_convert_orders_by_vpos_then_posted_then_input`・`test_convert_vpos_ms_floors_to_centiseconds`・`test_convert_real_excerpt_is_deterministic`（642b50e）
- [x] C3 位置と ASS の基準点 — 証跡: `tests/test_nico_ass.py` の `test_convert_ue_position_time_and_font`（`\an8`）・`test_convert_shita_anchors_bottom`（`\an2`）・`test_convert_naka_moves_between_video_edges`（`\an7` と `\move`）（642b50e）
- [x] C4 コマンドの小文字化、先勝ちと後勝ち、無視するコマンド — 証跡: `tests/test_nico_ass.py` の `test_parse_commands_*`（小文字化・先勝ち・`@秒数` の後勝ち 10 通り・gulim/simsun・未知と `nico:`）。変異 `loc-first-wins` で red（下の表）
- [x] C5 大きさ（CSS の文字サイズ） — 証跡: `tests/test_nico_ass.py` の `test_char_size_and_line_height`・`test_font_size_and_scale`・`test_measure_comment_sizes`・`test_convert_size_font_size`・`test_convert_font_scale_percent`（642b50e）
- [x] C6 色名 27 色、プレミアムだけの `#RRGGBB`、BGR 順 — 証跡: `tests/test_nico_ass.py` の `test_parse_commands_color_names`（27 キー）・`test_parse_commands_color_code_only_for_premium`・`test_ass_color`。変異 `premium-check`・`bgr-order` で red
- [x] C7 `invisible` と `/` で始まる本文 — 証跡: `tests/test_nico_ass.py` の `test_parse_commands_invisible`・`test_convert_invisible_not_output_and_not_placed`（642b50e）
- [x] C8 不透明度（設定、`_live`、縁取り） — 証跡: `tests/test_nico_ass.py` の `test_convert_opacity`。変異 `stroke-0.4`・`live-0.5` で red
- [x] C9 OS ごとのフォントと Windows の `defont` の分割 — 証跡: `tests/test_nico_ass.py` の `test_font_candidates`（3 OS × 3）・`test_font_runs_*`・`test_convert_windows_defont_runs_use_each_font_coefficient`。変異 `latin-range` で red
- [x] C10 縁取り — 証跡: `tests/test_nico_ass.py` の `test_convert_colors_and_stroke_color`・`test_convert_border_width`・`test_convert_border_width_follows_min_font_scale`。変異 `black-stroke` で red
- [x] C11 表示時間、`@秒数`、横長の動画の出入り — 証跡: `tests/test_nico_ass.py` の `test_naka_speed`・`test_naka_x`・`test_parse_commands_long`・`test_convert_naka_*`（丸め・0 未満・横長と 4:3）。変異 `speed-0.95`・`range-1530`・`start-floor`・`end-ceil` で red
- [x] C12 配置と衝突判定、行が足りないとき — 証跡: `tests/test_nico_ass.py` の `test_layout_*`（固定の `long - 20`、判定線と余白と 5 刻み、左の判定線だけ、長さの違う軌跡の交差、行が足りないときの乱数の回数、負の posY）。変異 `long-20`・`query-step-5`・`padding-5`・`left-line-off`・`analytic-off` で red
- [x] C13 改行を含むコメント（1 行 1 Dialogue） — 証跡: `tests/test_nico_ass.py` の `test_measure_comment_multiline_uses_max_width_and_total_height`・`test_convert_multiline_one_dialogue_per_line_left_aligned`。変異 `fixed-left-align` で red
- [x] C14 上下固定の幅の縮小 — 証跡: `tests/test_nico_ass.py` の `test_resize_*`（ちょうど 512・1 超過・大きく超過・増やす側の止め方・倍率の後の判定）。変異 `stage-512`・`grow-keeps-last`・`resize-after-scale` で red
- [x] C15 Pillow の実測と概算への切り替え — 証跡: 凍結した環境での確認は下の「実動画との見比べ」。`tests/test_nico_ass.py` の `test_pillow_measurer_*`（Pillow なしと未知のフォントで概算、実フォントは関係で検査。Windows で skip されずに pass）。配布物に Pillow が入るかはビルドで未確認（次にやること）
- [x] C16 フォントの寸法からの文字サイズ換算 — 証跡: `tests/test_nico_ass.py` の `test_convert_windows_defont_runs_use_each_font_coefficient`・`test_convert_missing_metrics_falls_back_to_372_ratio`。実フォントの寸法と、libass で描いた幅・位置の測定は下の「確認した事実」
- [x] C17 ASS の形とエスケープ — 証跡: `tests/test_nico_ass.py` の `test_convert_header`・`test_convert_escapes_braces_backslash_and_spaces`、BOM は `test_convert_comments_uses_new_converter_without_danmaku2ass`（642b50e）
- [x] C18 不正なコメント、失敗時の danmaku2ass、書き込み、0 件 — 証跡: `tests/test_nico_ass.py` の `test_convert_skips_invalid_rows_and_counts`・`test_convert_raises_when_whole_json_unreadable`、`tests/test_downloader.py` の `test_convert_comments_*`（件数の警告・読めない JSON と例外で danmaku2ass・書き込みの失敗は警告だけ・`.part` から置き換え・0 件）。変異 `dl-no-fallback`・`dl-no-skip-log`・`dl-direct-write` で red
- [x] C19 「表示時間」の UI — 証跡: `tests/test_original_format_panel.py` の `test_nico_duration_*`（無効とツールチップ、切り替えても無効、ビリビリで有効、取り直しで追従、ja / en の文言）。変異 `panel-ignore-nico`・`panel-sticky-nico` で red
- [x] C20 テストの収集、変異 → red の表、実物のフィクスチャ、所要時間 — 証跡: 下の「変異 → red」と「所要時間」。`uv run pytest -q -rs` は 801 passed・skip 0（642b50e）
- [x] C21 実動画との見比べ — 証跡: 下の「実動画との見比べ」。ユーザーが並べた画像を目視で確認して確定（2026-11-14）。幅の差は [#391](https://github.com/f8924919/yt-gui/issues/391) へ回した
- [x] C22 MIT の著作権表示と許諾表示の全文 — 証跡: `tests/test_download_binaries.py` の `test_third_party_notices_include_niconicomments_mit_full_text`（モジュールの `NICONICOMMENTS_LICENSE` と `COMPONENTS` の全文が一致し、告知に載る）
- [ ] C23 spec / arch の更新 — 証跡: 未

> **コミットの読み替え（2026-11-14）**: push 前に、公開リポジトリへ `userId` を含む実物のデータを残さないため（ユーザー判断）履歴を作り直した。以下の記録にある `642b50e`・`c19668e`・`702b973`・`83e0d14`・`498055a` は、いまの `1b9c6e2`（実装とテスト）と `125712a`（このメモ）にまとめた。`yt_gui/` と `scripts/` は `c19668e` と同一（`git diff c19668e 1b9c6e2 -- yt_gui scripts` が空）。テストの違いは、実物のデータから `userId` などを除いて sha256 の期待値を変えたことと、`_ass_cmd` の docstring だけ。データを変えた後も、全件の変換の ASS の sha256 の先頭は `757dd6de606832ed` のままで、`uv run pytest -q` は 803 passed。

## 確認した事実

- 移植元は niconicomments のコミット `899203436285`。Issue の表の値は、取得したソースの該当行で確認した（色名は `colors.ts` のキーを数えて 27）。
- 上下固定の縮小は `HTML5Comment.ts:255-345`。幅の上限 512 を超えたら文字サイズを `512 ÷ 幅` 倍にし、収まる最大まで 1 ずつ調整する。

- 文字サイズの換算の前提（探索、2026-11-14、Windows、`bin/ffmpeg` の libass、Pillow 13）: 係数 `(usWinAscent + usWinDescent) / unitsPerEm` で `Fontsize` を決めて描いた幅と、Pillow で 100px の em で測った幅の比は Arial 0.987（係数 1.117）、MS PGothic 0.989（1.000）、Yu Gothic 0.990（1.287）、Yu Mincho 0.993（1.287）。インクの範囲で比較した。Yu Gothic の係数は #372 で測った「ASS は CSS の約 1.28 分の 1 に描かれる」と一致する。

- 実物のフィクスチャ（2026-11-14 取得、yt-dlp `--write-subs --sub-langs comments`）: `sm31143779.comments.json` は 1,432 件、sha256 `884247fc3e957b13a453d19fba3bc9f7368064d30d5c3e29192f7e51d027ed78`。全体と 30 件の抜粋を、どちらも `no` / `vposMs` / `body` / `commands` / `isPremium` / `postedAt` だけ残して（`userId` などは公開リポジトリに置かないため除く。ユーザー判断 2026-11-14）`tests/data/sm31143779.comments.json.gz` と `tests/data/sm31143779.comments.excerpt.json` に置いた。リポジトリの全体の sha256（展開後）は `2118f138cc63234970e301adeeac10bc111f564ae27c162eb031e46e44f38c79`。実物には複数行・`#RRGGBB`・`_live`・`invisible`・フォント指定が無いので、それらは合成の入力でテストする。前の申し送りの「約 1,433 件」は取り直しで 1,432 件になった（コメントは日々変わるので、以後の C20 / C21 はこのファイルを使う）。
- テスト先行の red（2026-11-14、実装前の HEAD `0fd2506`、テストが import できるだけのスタブで実行）: `uv run pytest tests/test_nico_ass.py -q` → `141 failed, 2 passed`。passed の 2 件は実装を呼ばないデータの確認（`test_color_table_has_27_names`、`test_full_fixture_matches_recorded_hash`）。失敗はすべてスタブの `NotImplementedError`（`-rf` の理由を数えて 141 件）。
- 接続・UI・告知のテストの red（2026-11-14、同じ HEAD `0fd2506`、`-k "nico_ass or convert_comments or nico_duration or niconicomments"`）: `15 failed, 3 passed`。失敗の実際の例外: 新しい変換が無いので `.comments.ass` が無い（`FileNotFoundError` 2 件）、`warn_nico_ass_skipped` が無い、`yt_gui.downloader.nico_ass` / `_nico_ass_platform` が無い（`ImportError` 5 件）、danmaku2ass が呼ばれる / 呼ばれない（3 件）、表示時間のスピンが有効のまま（2 件）、文言のキーが無い（`KeyError` 2 件）、`COMPONENTS` に niconicomments が無い（`StopIteration`）。passed の 3 件は既存の挙動の守り（ビリビリで有効、取り直しで有効、`.part` が掃除の対象）で、取り直しの 1 件は実装の後に変異で確かめる。

- 実装（2026-11-14、642b50e）: 本体は `implementer` へ委譲し、主エージェントが全件を回し直した（`uv run pytest -q -rs` 801 passed・skip 0、`ruff check .`・`ruff format --check .`・`mypy` が exit 0）。ASS の生成（`convert`）と配置（`layout`）は arch と移植元を行ごとに突き合わせた。
- 実フォントの寸法（`font_metrics("windows")`、ascent / descent）: Arial 600 は 0.9053 / 0.2119、MS PGothic 600 は 0.8594 / 0.1406、Yu Gothic 400 は 0.9849 / 0.3022、Yu Mincho 400 は 0.9951 / 0.2920。合計は上の探索の係数（1.117 / 1.000 / 1.287 / 1.287）と一致する。
- 所要時間（C20、2026-11-14、c19668e、Windows、実物の全件 1,432 件、Pillow の測定器と実フォントの寸法、`random.Random(0)`）: 0.285 / 0.227 / 0.223 秒、`skipped` 0、Dialogue 1,432 行、3 回とも ASS の sha256 の先頭 `757dd6de606832ed`。最適化はしていない。
- `implementer` が設計に無く決めた挙動（受け入れた）: 本文の CR を落とす、本文は 16,384 文字・256 行で切る（Python の文字数）、解像度の都合で終了が開始以前になる行は出さない、空の行は出さない、`font_scale_percent <= 0` は `ValueError`、タイムゾーンの無い `postedAt` は UTC、コマンドは先頭 64 個・各 128 文字まで（`comment.ts:66-67`）。`\bord` は arch の式どおり `font_scale` を掛けない。macOS のフォントファイル名は推測で、Mac では未確認。

- 配布物（C15、2026-11-14、702b973、Windows、`uv run pyinstaller yt-gui.spec --noconfirm` が exit 0）: `dist/yt-gui/_internal/PIL/_imaging.cp314-win_amd64.pyd` と `_imagingft.cp314-win_amd64.pyd` が入り、`build/yt-gui/PYZ-00.toc` に `PIL.ImageFont` がある（関数の中の遅延 import も解析に拾われた）。実行時に Pillow で測られるかは C21 で確かめる。

- libass で描いた位置と幅（C16 / C3、2026-11-14、83e0d14、Windows、`bin/ffmpeg` の libass、Pillow 13）: 1 件だけの ASS（縁取り 0）を黒の 1920 × 1080 に焼き、白のインクの外接矩形を測った（スクリプトの `git hash-object` `9e2068c5ae4fe3c41af438d27bd2b716b5b625d2`）。
  - 幅: libass のインク幅と、同じフォント・同じ em で Pillow が描いたインク幅の比は、Arial Bold「HHHHHHHH」0.9996、MS PGothic「漢」× 8 は 1.0018（big は 1.0015。擬似ボールドの分で約 1 px 広い）、Yu Gothic 0.9995、Yu Mincho 0.9996。測った幅と描く幅は 0.2% 以内で一致する。
  - 縦: Arial「H」のインクの下端（= ベースライン）は `ue` で 75（想定 75.41）、`shita` で 1060（想定 1059.88）、2 行目で 157（想定 156.73）。キャップハイトから見た上端も合う。`n8` / `n2` と行の上端・下端の換算は libass で成り立つ。
  - 横: 2 行のコメントは両行のインクの左端が同じ（747）で、枠の中の左揃えになる。
  - フォント: 測定器は `msgothic.ttc` の index 2（`MS PGothic`）を開く（等幅の MS Gothic なら半角カナ 5 字が 250 のところ 304）。
  - 実物の全件（1,432 件）の ASS を libass で 700 秒分描いても、警告は出ない（exit 0）。

### 変異 → red（C20）

2026-11-14。`git worktree` に置いたコピー（基点 642b50e、2 行目だけ c19668e）を書き換え、対象のテストファイルを流し、毎回元に戻して `git diff --quiet` を確かめた（追跡下の作業ツリーは触らない）。先に無変異で green を確かめた。ハーネスの `git hash-object`: `6b4af9c4da2ae675237b55bf0dfd6113f6c02fca`（1 回目）、`b831b2159c361c67e8a177eff99cfb8486be8f1e`（生き残り 2 件の再実行）。

| 変異 | 落ちた件数 | 狙ったテスト |
|---|---|---|
| `long-20`（固定の判定を `long - 19` まで） | 1 | `test_layout_fixed_collision_ends_at_long_minus_20[released]` |
| `query-step-5`（照会を 6 刻み） | 1 | `test_layout_naka_right_line_with_padding[released]` |
| `padding-5`（余白 0） | 1 | `test_layout_naka_right_line_with_padding[rightline]` |
| `speed-0.95`（1.0） | 8 | `test_naka_speed[wide]` ほか |
| `range-1530`（1531） | 10 | `test_naka_speed[zero]` ほか |
| `left-line-off`（左の判定線を見ない） | 1 | `test_layout_naka_left_line_only_collision` |
| `analytic-off`（軌跡の交差を見ない） | 1 | `test_layout_naka_different_long_trajectories_cross` |
| `stage-512`（513） | 3 | `test_resize_one_over_steps_down_by_one` ほか |
| `grow-keeps-last`（`<` を `<=`） | 0 → 1 | 生き残ったので `test_resize_grow_stops_before_reaching_limit` を足し（c19668e）、再実行で red |
| `baseline-0.16`（0.15） | 9 | `test_convert_ue_position_time_and_font` ほか |
| `stroke-0.4`（0.5） | 2 | `test_convert_opacity[normal]`・`[live]` |
| `live-0.5`（0.6） | 1 | `test_convert_opacity[live]` |
| `black-stroke`（`#000` も白に） | 1 | `test_convert_colors_and_stroke_color[shortblack]` |
| `premium-check`（プレミアムを見ない） | 2 | `test_parse_commands_color_code_only_for_premium[nonpremium]` ほか |
| `loc-first-wins`（後勝ち） | 1 | `test_parse_commands_first_wins_for_loc_size_color_font` |
| `latin-range`（U+007F まで） | 1 | `test_font_runs_windows_defont_splits_latin` |
| `bgr-order`（RGB 順） | 4 | `test_ass_color[red]` ほか |
| `start-floor`（ceil） | 3 | `test_convert_naka_moves_between_video_edges` ほか |
| `end-ceil`（floor） | 1 | `test_convert_naka_moves_between_video_edges` |
| `fixed-left-align`（中央揃え） | 1 | `test_convert_multiline_one_dialogue_per_line_left_aligned` |
| `resize-after-scale`（倍率の前の幅で判定） | 1 | `test_resize_judges_width_after_font_scale` |
| `dl-no-fallback`（例外でも danmaku2ass に回さない） | 18 | `test_convert_comments_unreadable_json_falls_back_to_danmaku2ass`・`test_convert_comments_converter_exception_falls_back` ほか |
| `dl-no-skip-log`（件数の警告を出さない） | 1 | `test_convert_comments_warns_skipped_count` |
| `dl-direct-write`（`.part` を使わない） | 0 → 1 | 生き残ったので `test_convert_comments_writes_part_then_replaces` を足し（c19668e）、再実行で red |
| `panel-ignore-nico`（ニコニコでも有効） | 2 | `test_nico_duration_disabled_for_niconico_with_tooltip` ほか |
| `panel-sticky-nico`（取り直しで戻らない） | 1 | `test_nico_duration_follows_latest_fetch` |

### 実動画との見比べ（C21・C15 の残り、2026-11-14、Windows で 1 本の動画を確認した結果）

- 対象: `sm31143779`（2026-11-14 取得）。アプリと同じ経路（`Downloader.download_video`、焼きこみ ON、解像度の自動追従 ON → 960 × 540、不透明度 0.8、倍率 100%）で取得した。コミットは `78785e5`。取得したコメントの sha256 は `884247fc…27ed78`（フィクスチャの元ファイルと同一）。ログは `[コメント] SCP-114514.comments.ass を生成しました` で、danmaku2ass は使われていない。焼きこみまで 38.9 秒。
- C15（実行時に Pillow で測られるか）: PyInstaller で `nico_ass` を含めて凍結した確認用の実行ファイル（同じ PyInstaller、同じフック）でも、MS PGothic の半角カナ 5 文字の幅は 304.3（概算なら 250）で、同じコメントから同じ ASS（sha256 `5fdf56e8…61b0f2`。アプリの出力と一致、フィクスチャの 1920 × 1080 では `757dd6de…`）ができた。アプリ本体の exe を直接動かしたのではない（GUI のため）。
- Web 側: 内蔵ブラウザ（Chromium 156、Windows、devicePixelRatio 1.5）のニコニコ動画のプレイヤー。コメントの canvas（1364 × 768）の画素を、再生が目標の時刻に達した瞬間に止めて読んだ。`video` を直接シークするとコメントの層が追従しないので、`?from=` で数秒前から自然に再生させた。焼きこみ側は、同じ ASS の文字だけ不透明にした写しを黒地に描いたフレーム。どちらも色ごとのインクの外接矩形を 960 × 540 に換算して比べた。

| 時刻 | 種類 | コメント | 焼きこみ x / y | Web x / y | 幅の差 |
|---|---|---|---|---|---|
| 14.5 秒 | 上固定・big・黄 | 野獣先輩 | 374–586 / 12–59 | 371.6–588.4 / 8.4–58.4 | −2.2% |
| 14.5 秒 | 下固定・big・赤 | 日本支部はもう臭い | 260–707 / 482–531 | 254.1–712.3 / 480.0–529.3 | −2.4% |
| 20.5 秒 | 下固定・medium・青 | 「Ticonderoga(タイコンデロガ)」の方が良い | 141–821 / 442–479 | 126.0–834.7 / 442.0–481.4 | −4.0% |
| 20.5 秒 | 下固定・big・赤 | オブジェクトクラスをケテルに修正しろ | 130–827 / 492–531 | 121.8–836.1 / 490.6–531.4 | −2.4% |
| 94.0 秒 | 流れる・medium・赤 | ボロクソで草 | 391–587 / 102–135 | 375.1–577.1 / 127.4–161.9 | −3.0% |
| 266.5 秒 | 下固定・big・シアン | アメリカ合衆国 | 314–643 / 482–531 | 309.0–647.5 / 479.3–529.3 | −2.8% |
| 356.7 秒 | 下固定・big・紫 | イキスギィ! | 358–601 / 206–253 | 354.0–603.9 / 203.4–254.1 | −2.8% |
| 356.7 秒 | 下固定・small・cyan2 | この結論に至るまでに大分時間がかかってしまったようだ。 | 172–782 / 455–476 | 152.0–801.6 / 456.8–478.6 | −6.1% |

- 表示時間: 上固定の「野獣先輩」（13.64 秒から 3 秒）は、Web で 13.60 秒に無く 13.70 秒に有り、16.60 秒に有り 16.70 秒に無い。ASS は 13.64〜16.64 秒で、差は 0.1 秒以内（目安 ±0.5 秒）。流れる「ボロクソで草」の 94.0 秒の横位置の差は中心で 13 px（540p の速さ 2.39 px / 1/100 秒で約 0.05 秒分）。
- 縦位置: 固定コメントは、行も重なり方（266.5 秒の行が足りずに重なる所を含む）も Web と同じで、差は ±4 px 以内。流れるコメントは一部の段が Web と違う（94.0 秒の「ボロクソで草」は Web が 1 段下。356.7 秒にも違う段がある）。
- 幅の差の原因: Chrome は太字の無い MS PGothic を太さ 600 で描くとき擬似ボールドをかけ、送り幅も広げる。ブラウザの canvas の `measureText` で、100px の「漢」× 10 は 400 で 1000、600 で 1019.5、カナ混じり 18 文字は 1564.8 → 1600（1 文字あたり約 +2%）。Arial は本物の Bold があるので変わらない（「H」× 10 は 400 / 600 / 700 とも 722.2）。yt-gui の測定（Pillow）と libass はこの増分を持たないので、Windows の `defont` の日本語は Web より 2〜3% 細く、small では約 6% 細い（増分が文字の大きさに比例しないと見られる。未確認）。流れるコメントの段の違いは、幅の差で衝突判定の結果が変わるためと見ている（未確認）。
- 確定: ユーザーが並べた画像（5 時刻）を目視で確認し、C21 を確定した（2026-11-14）。幅の差は #388 ではなく新しい [#391](https://github.com/f8924919/yt-gui/issues/391) に回した（ユーザー判断。#388 は縮小とコメントアートで、内容が違うため）。
- `_live`: この動画に `_live` のコメントは無く、見比べていない。擬似ボールド: 焼きこみ（libass）も Web も太く見え、見た目の差は上の幅の差だけ。
- 並べた画像（左が焼きこみ、右が Web）は、ユーザーに送った `compare.png`（scratchpad、追跡しない）。

## 訂正ログ

| 日付 | 何を誤って書いたか | 正しくは | どの検査・手順なら捕まえたか |
|---|---|---|---|

## 次にやること（申し送り・2026-11-14 時点）

C1〜C22 は証跡つきで完了（C21 はユーザーの目視で確定）。残りは C23 の点検と PR。

1. `/verify-gate`（verify → docs-check → evaluator）を回す。C23 は docs-check の結果で確定する。
2. push と PR はユーザーの確認を取ってから。PR 本文に変異の表と C21 の表を引き、#391 を「関連」に書く。
3. 完了したら、このメモを `docs/task/archive/` へ移す（docs-guide §4.2。PR に同梱）。

訂正ログ: 0 件
