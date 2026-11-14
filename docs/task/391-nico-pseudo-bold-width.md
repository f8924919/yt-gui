# ニコニコのコメントの MS Pゴシックの幅を Chrome の擬似ボールドに合わせる

> Issue: [#391](https://github.com/f8924919/yt-gui/issues/391)
> ステータス: 進行中
> ブランチ: `feature/391-nico-pseudo-bold-width`
> 基点: `3df961e`

受け入れ条件の正本は Issue。設計は [arch/nico_ass.md](../arch/nico_ass.md) の「擬似ボールドの増分」。前のタスクは [#387](archive/387-nico-ass-converter.md)。

## 進捗

- [x] C1 増分の決まり方を Chrome の実測で確かめ、JS・生の出力・環境を記録する — 証跡: 下の「Chrome の実測」。値は fixture `tests/data/nico_chrome_widths.json` の `advances`（63 点）にし、`test_pseudo_bold_advance_matches_chrome` で規則と突き合わせる（2d5bf96）
- [x] C2 固定の文字列の集合で、計算した送り幅と Chrome の `measureText` の差が全点で ±1% 以内 — 証跡: `test_pillow_width_with_pseudo_bold_matches_chrome_within_1pct`（21 点、Windows で skip されずに pass）。最大 0.57%（下の「C2 の表」）。プレイヤーで描いた幅（参考）は下の「実動画との見比べ」
- [x] C3 `\fsp` を足した後の libass の幅が、測った幅と 0.2% 程度で一致する（(n−1) 字分） — 証跡: 下の「libass で描いた幅（C3）」。比 1.0008〜1.0027
- [x] C4 Arial・`gothic` / `mincho`・macOS / その他・概算の測定器の出力が変わらない（テストと変異の記録） — 証跡: `test_convert_output_unchanged_where_no_pseudo_bold`（#391 の前の出力の sha256 と一致）、`test_pseudo_bold_advancer_targets_only_windows_ms_pgothic_600`、`test_pseudo_bold_advancer_is_zero_when_font_not_found`、`test_convert_no_fsp_on_lines_without_advance`。変異は下の「変異 → red（C4）」
- [x] C5 流れるコメントの段の違いを、#387 と同じ時刻で見比べて記録する — 証跡: 下の「実動画との見比べ」
- [x] C6 `_live` の縁取りを `sm9560870` の 6.31 秒で見比べて記録する — 証跡: 下の「`_live`（C6）」
- [x] C7 spec / arch に、増分の規則・適用範囲・限界を書く — 証跡: `docs/arch/nico_ass.md` の「擬似ボールドの増分」、`docs/spec/screens/original-format-panel.md` の「ニコニコのコメントの変換」、`docs/arch/downloader.md`、`docs/testing/policy.md` の §3（b5944b8、7b3868a、fc063ff と次のコミット）

証跡の段へ移った日と主張（policy §8.0）: 2026-11-14、増分の規則（arch の「擬似ボールドの増分」）、C2〜C6 の数値、spec の「ランダムな位置に置くコメントは Web と位置が違う」。それを支える scratchpad の script の本文と `git hash-object` は末尾の「プローブの本文」。

## Chrome の実測（C1、2026-11-14）

環境: 内蔵ブラウザ（`Chrome/156.0.8078.75`、Windows 11、devicePixelRatio 1.5）。ニコニコ動画のページ上で、切り離した canvas の `measureText` を測った。devicePixelRatio は変えられないので、1.5 以外は確かめていない。

太さ 400 と 600 の差を、10 字の文字列で 1 字あたりに直した値（抜粋）。

```js
const c = document.createElement('canvas').getContext('2d');
for (const px of [8, 10, 12, 15, 20, 24, 30, 39, 40, 48, 60, 80, 100, 200, 400]) {
  c.font = `400 ${px}px "MS PGothic"`; const a = c.measureText('漢'.repeat(10)).width;
  c.font = `600 ${px}px "MS PGothic"`; const b = c.measureText('漢'.repeat(10)).width;
  row.push(`${px}:${((b - a) / 10).toFixed(3)}`);
}
```

```text
"MS PGothic" kan 8:1.000 10:1.000 12:1.000 15:1.000 20:1.000 24:0.469 30:0.586 39:0.762 40:0.781 48:0.938 60:1.172 80:1.563 100:1.953 200:3.906 400:7.813
Arial kan 8:0.000 10:0.000 12:0.000 15:0.000 20:0.000 24:0.000 30:0.000 39:0.000 40:0.000 48:0.000 60:0.000 80:0.000 100:0.000 200:0.000 400:0.000
```

- 10〜45 の整数では、22 以下が 1.000、23 以上が `px × 5/256`（23: 0.449、27: 0.527、39: 0.762）。漢字・かな・句読点の 3 種で同じ値。100px の比 `(b − a) / 10 × 51.2 / px` は 25〜128 で 1.00000（51.2 は 1.00001）。
- MS PGothic（`msgothic.ttc` の index 2）の unitsPerEm は 256（`head` 表）。埋め込みビットマップ（EBLC）の大きさは 7〜22。22 / 23 の境目はこれと一致する（原因は断定しない）。
- 空白とゼロ幅の文字: 「漢 + 文字 + 漢」の増分は、18px で U+3000 / U+2001 / U+2003 が 3（空白も +1）、U+200B が 2（ゼロ幅は 0）。39px ではどれも 1.5234（= 2 × 0.762。空白は 0）。
- Arial は 400 と 600 の差が全サイズで 0（本物の Bold がある）。
- 字の種類ごと（design-review の指摘を受けて追加で測った。「漢 + 字 + 漢」の増分から両端の漢字の分を引いた値、18px / 39px）:
  - 0 / 0: U+200B、U+200D、U+FEFF（ゼロ幅の書式文字）、U+3164・U+115F・U+1160・U+FFA0（ハングルの埋め字）、U+2800（点字の空白）、U+1F600（絵文字）
  - 1 / 0: U+3000、U+2001（空白）
  - 1 / 0.7617: U+3099、U+0301（結合文字。MS PGothic では幅のある字として描かれる）、U+20BB7（CJK 拡張 B）
  - ハングルの埋め字・点字・絵文字は MS PGothic に無く、Chrome が別のフォントで描く。増分はそのフォントによる。
- 22 以下では、太さ 400 の幅も Chrome が 1 字ずつ整数に丸めている。半角カナ 1 字の幅は Pillow の比例とも、埋め込みビットマップの送り幅とも一致しない（例: 「ｱ」の 22px は Chrome 14、ビットマップ 12、比例 13.58）。ふつうの文で 0.1% 程度、半角カナ・句読点だけの文字列では ±2〜7% ずれる。本 Issue では再現しない（ユーザー判断、2026-11-14）。
- fixture の `advances` は 63 点（9 字 × 10 / 18 / 22 / 23 / 27 / 39 / 100）。作る前に、1 字ずつ `600 {px}px "MS PGothic"` と `400 {px}px "MS PGothic"` の差を 63 点とも Chrome で測った。値は字の種類で 3 通りなので、作る script（`make_fixture.py`、`git hash-object` `939deea0`、scratchpad）は種類ごとに書き写し、作った時点でその実測と照合したのは 8 点だけ。全点の照合は下の「63 点の測り直し」で行った。fixture の sha256 は `30f3135216bf4b72…`。
- **63 点の測り直し（evaluator 1 巡目の欠陥 3 を受けて、2026-11-14）**: fixture の `advances` を 1 字ずつ Chrome で測り直し、全点が fixture と一致した（食い違い 0）。fixture は種類ごとに書き写して作ったが、値は全点の実測と同じ。

  ```js
  // F は fixture の advances を [字, px, 値] に並べたもの（63 点）
  const c = document.createElement('canvas').getContext('2d');
  for (const [ch, px, want] of F) {
    c.font = `400 ${px}px "MS PGothic"`; const a = c.measureText(ch).width;
    c.font = `600 ${px}px "MS PGothic"`; const b = c.measureText(ch).width;
    const got = +(b - a).toFixed(6);
    if (Math.abs(got - want) > 1e-5) bad++;
    out.push(`U+${ch.codePointAt(0).toString(16).toUpperCase()}@${px}=${got}`);
  }
  ```

  ```text
  ua=Chrome/156.0.8078.75 dpr=1.5 n=63 mismatches=0
  U+6F22@10=1 U+6F22@18=1 U+6F22@22=1 U+6F22@23=0.449219 U+6F22@27=0.527344 U+6F22@39=0.761719 U+6F22@100=1.953125 U+3042@10=1 U+3042@18=1 U+3042@22=1 U+3042@23=0.449219 U+3042@27=0.527344 U+3042@39=0.761719 U+3042@100=1.953125 U+FF71@10=1 U+FF71@18=1 U+FF71@22=1 U+FF71@23=0.449219 U+FF71@27=0.527344 U+FF71@39=0.761719 U+FF71@100=1.953125 U+3001@10=1 U+3001@18=1 U+3001@22=1 U+3001@23=0.449219 U+3001@27=0.527344 U+3001@39=0.761719 U+3001@100=1.953125 U+3000@10=1 U+3000@18=1 U+3000@22=1 U+3000@23=0 U+3000@27=0 U+3000@39=0 U+3000@100=0 U+2001@10=1 U+2001@18=1 U+2001@22=1 U+2001@23=0 U+2001@27=0 U+2001@39=0 U+2001@100=0 U+200B@10=0 U+200B@18=0 U+200B@22=0 U+200B@23=0 U+200B@27=0 U+200B@39=0 U+200B@100=0 U+FEFF@10=0 U+FEFF@18=0 U+FEFF@22=0 U+FEFF@23=0 U+FEFF@27=0 U+FEFF@39=0 U+FEFF@100=0 U+3099@10=1 U+3099@18=1 U+3099@22=1 U+3099@23=0.449219 U+3099@27=0.527344 U+3099@39=0.761719 U+3099@100=1.953125
  ```

  空白（U+3000・U+2001）の 22 / 23 の境目も、この実測で確かめた（22 で 1、23 で 0）。
- fixture の `widths` は、`600 {px}px Arial, "MS PGothic"` で文字列全体を測った 21 点（#387 の 8 点、small / medium / big のふつうの文、縮小後の 10 / 12 / 15 / 20 / 23 / 31px）。

## C2 の表（2d5bf96、実装の `pillow_measurer` + `pseudo_bold_advancer`）

script は `c2table.py`（scratchpad）。テストの判定は `pytest.approx(rel=0.01)`。

| px | 文字列 | Chrome | 増分なし | 増分あり |
|---|---|---|---|---|
| 39 | 野獣先輩 | 159.05 | -1.92% | +0.00% |
| 39 | 日本支部はもう臭い | 336.68 | -2.04% | +0.00% |
| 27 | 「Ticonderoga(タイコンデロガ)」の方が良い | 509.31 | -1.45% | -0.00% |
| 39 | オブジェクトクラスをケテルに修正しろ | 624.00 | -2.20% | +0.00% |
| 27 | ボロクソで草 | 147.02 | -2.15% | +0.00% |
| 39 | アメリカ合衆国 | 246.64 | -2.16% | +0.00% |
| 39 | イキスギィ! | 184.68 | -2.06% | -0.00% |
| 18 | この結論に至るまでに大分時間がかかってしまったようだ。 | 470.00 | -5.86% | -0.11% |
| 18 | 今日はいい天気ですね | 185.00 | -5.10% | +0.31% |
| 27 | 今日はいい天気ですね | 268.63 | -1.96% | +0.00% |
| 39 | 今日はいい天気ですね | 388.02 | -1.96% | +0.00% |
| 27 | ここすき　わかる | 190.69 | -1.94% | +0.00% |
| 27 | 8888888888 | 150.16 | -0.01% | -0.01% |
| 18 | 草生える www | 119.00 | -3.55% | -0.18% |
| 39 | うぽつです！ | 219.98 | -2.08% | +0.00% |
| 12 | 長いコメントを上に固定するときは文字が縮む | 251.00 | -8.29% | +0.08% |
| 15 | 長いコメントを上に固定するときは文字が縮む | 307.00 | -6.27% | +0.57% |
| 20 | 長いコメントを上に固定するときは文字が縮む | 404.00 | -5.03% | +0.17% |
| 23 | 長いコメントを上に固定するときは文字が縮む | 450.66 | -2.09% | +0.00% |
| 31 | 長いコメントを上に固定するときは文字が縮む | 607.41 | -2.09% | +0.00% |
| 10 | 長いコメントを上に固定するときは文字が縮む | 213.00 | -9.94% | -0.08% |

最大 0.57%（15px）。22px 以下の残りは、太さ 400 の整数への丸め（再現しない）による。

## libass で描いた幅（C3、2d5bf96）

`bin/ffmpeg` の libass で、実装の `convert`（Pillow の測定・寸法・増分）が作った 1 行（`ue`、「漢」× 8、`\bord0`）を 1920 × 1080 の黒地に描き、インクの外接矩形を測った。script は `libass391.py`（`git hash-object` `47500936`）。

| 大きさ | `\fs` | `\fsp` | libass（`\fsp` あり） | libass（`\fsp` なし） | 差（期待 (n−1) × `\fsp`） | Pillow のインク + (n−1) × `\fsp` | 比 |
|---|---|---|---|---|---|---|---|
| big | 109.63 | 2.14 | 880 | 866 | 14（14.98） | 879.0 | 1.0012 |
| medium | 75.9 | 1.48 | 610 | 600 | 10（10.36） | 608.4 | 1.0027 |
| small | 50.6 | 2.81 | 419 | 399 | 20（19.67） | 418.7 | 1.0008 |

- 比は #387 の `\fsp` 無しの値（MS PGothic 1.0018 など。libass 側の太字化で約 1 px 広い）と同じ程度。
- 行末の字の後ろの `\fsp`: `\fsp` を 40 に誇張して `\an8` で描くと、インクの左端は `\fsp0` より 160 px 左へずれた（含むなら n × 40 / 2 = 160、含まないなら 140）。libass は行末の `\fsp` も中央揃えの幅に含める。Chrome も増分を含めた幅の枠の中央に置くので、固定コメントの横位置はずれない（script `trail391.py`、`53c25964`）。

## 変異 → red（C4、2389c35）

worktree のコピー（`2389c35`）を 1 つずつ変異させ、`tests/test_nico_ass.py` と `tests/test_downloader.py` を走らせた。無変異のコピーは 409 passed、戻した後も 409 passed、狙ったテストは 18 変異すべてで落ちた（`ALL TARGETED KILLED`）。置換が 1 か所に当たらないときは止まる。script は `mutate391.py`、表は `mut_table.py` でログから作った（本文と hash は末尾の「プローブの本文」）。

- M1〜M15 は 1 巡目（`2d5bf96`、`mutate391.py` の旧版 `be47dec1…`）でも回し、狙ったテストは全部落ちた。evaluator 1 巡目の指摘で M16（フォント名を見ない）・M17（downloader が `no_advance` を渡す。macos の検査では `no_advance` と見分けられなかった）・M18（本番の増分が常に 0。C2 のしきい値のテストの red）を足し、落ちたテストを全部並べる形にして回し直した。M17 を殺す `test_convert_comments_passes_pseudo_bold_advancer_of_platform` は `2389c35` で足した。
- M18 で、C2 の 20 点と `win-mspg600` が落ちる（21 failed。足す前の差は −1.45〜−9.94%）。C2 の残る「8888888888」は MS PGothic を通らないので M18 では落ちず、M16 で落ちる。

| 変異 | 件数 | 狙ったテスト | 落ちたテスト（全部） |
|---|---|---|---|
| M1 境目 <= → < | 7 failed | `test_pseudo_bold_advance_matches_chrome[U+6F22@22]`（落ちた） | `test_pseudo_bold_advance_matches_chrome[U+6F22@22]`<br>`test_pseudo_bold_advance_matches_chrome[U+3042@22]`<br>`test_pseudo_bold_advance_matches_chrome[U+FF71@22]`<br>`test_pseudo_bold_advance_matches_chrome[U+3001@22]`<br>`test_pseudo_bold_advance_matches_chrome[U+3000@22]`<br>`test_pseudo_bold_advance_matches_chrome[U+2001@22]`<br>`test_pseudo_bold_advance_matches_chrome[U+3099@22]` |
| M2 Cf を 0 にしない | 14 failed | `test_pseudo_bold_advance_matches_chrome[U+200B@39]`（落ちた） | `test_pseudo_bold_advance_matches_chrome[U+200B@10]`<br>`test_pseudo_bold_advance_matches_chrome[U+200B@18]`<br>`test_pseudo_bold_advance_matches_chrome[U+200B@22]`<br>`test_pseudo_bold_advance_matches_chrome[U+200B@23]`<br>`test_pseudo_bold_advance_matches_chrome[U+200B@27]`<br>`test_pseudo_bold_advance_matches_chrome[U+200B@39]`<br>`test_pseudo_bold_advance_matches_chrome[U+200B@100]`<br>`test_pseudo_bold_advance_matches_chrome[U+FEFF@10]`<br>`test_pseudo_bold_advance_matches_chrome[U+FEFF@18]`<br>`test_pseudo_bold_advance_matches_chrome[U+FEFF@22]`<br>`test_pseudo_bold_advance_matches_chrome[U+FEFF@23]`<br>`test_pseudo_bold_advance_matches_chrome[U+FEFF@27]`<br>`test_pseudo_bold_advance_matches_chrome[U+FEFF@39]`<br>`test_pseudo_bold_advance_matches_chrome[U+FEFF@100]` |
| M3 空白を 0 にしない | 8 failed | `test_pseudo_bold_advance_matches_chrome[U+3000@39]`（落ちた） | `test_pseudo_bold_advance_matches_chrome[U+3000@23]`<br>`test_pseudo_bold_advance_matches_chrome[U+3000@27]`<br>`test_pseudo_bold_advance_matches_chrome[U+3000@39]`<br>`test_pseudo_bold_advance_matches_chrome[U+3000@100]`<br>`test_pseudo_bold_advance_matches_chrome[U+2001@23]`<br>`test_pseudo_bold_advance_matches_chrome[U+2001@27]`<br>`test_pseudo_bold_advance_matches_chrome[U+2001@39]`<br>`test_pseudo_bold_advance_matches_chrome[U+2001@100]` |
| M4 比 5/256 → 1/50 | 21 failed | `test_pseudo_bold_advance_matches_chrome[U+6F22@39]`（落ちた） | `test_pseudo_bold_advance_matches_chrome[U+6F22@23]`<br>`test_pseudo_bold_advance_matches_chrome[U+6F22@27]`<br>`test_pseudo_bold_advance_matches_chrome[U+6F22@39]`<br>`test_pseudo_bold_advance_matches_chrome[U+6F22@100]`<br>`test_pseudo_bold_advance_matches_chrome[U+3042@23]`<br>`test_pseudo_bold_advance_matches_chrome[U+3042@27]`<br>`test_pseudo_bold_advance_matches_chrome[U+3042@39]`<br>`test_pseudo_bold_advance_matches_chrome[U+3042@100]`<br>`test_pseudo_bold_advance_matches_chrome[U+FF71@23]`<br>`test_pseudo_bold_advance_matches_chrome[U+FF71@27]`<br>`test_pseudo_bold_advance_matches_chrome[U+FF71@39]`<br>`test_pseudo_bold_advance_matches_chrome[U+FF71@100]`<br>`test_pseudo_bold_advance_matches_chrome[U+3001@23]`<br>`test_pseudo_bold_advance_matches_chrome[U+3001@27]`<br>`test_pseudo_bold_advance_matches_chrome[U+3001@39]`<br>`test_pseudo_bold_advance_matches_chrome[U+3001@100]`<br>`test_pseudo_bold_advance_matches_chrome[U+3099@23]`<br>`test_pseudo_bold_advance_matches_chrome[U+3099@27]`<br>`test_pseudo_bold_advance_matches_chrome[U+3099@39]`<br>`test_pseudo_bold_advance_matches_chrome[U+3099@100]`<br>`test_pseudo_bold_advancer_targets_only_windows_ms_pgothic_600[win-mspg600]` |
| M5 OS の判定を外す | 2 failed | `test_pseudo_bold_advancer_targets_only_windows_ms_pgothic_600[mac-mspg600]`（落ちた） | `test_pseudo_bold_advancer_targets_only_windows_ms_pgothic_600[mac-mspg600]`<br>`test_pseudo_bold_advancer_targets_only_windows_ms_pgothic_600[other-mspg600]` |
| M6 太さを見ない | 1 failed | `test_pseudo_bold_advancer_targets_only_windows_ms_pgothic_600[win-mspg400]`（落ちた） | `test_pseudo_bold_advancer_targets_only_windows_ms_pgothic_600[win-mspg400]` |
| M7 フォントの有無を見ない | 1 failed | `test_pseudo_bold_advancer_is_zero_when_font_not_found`（落ちた） | `test_pseudo_bold_advancer_is_zero_when_font_not_found` |
| M8 測定に増分を足さない | 3 failed | `test_measure_comment_adds_advance_before_ceil`（落ちた） | `test_measure_comment_adds_advance_before_ceil`<br>`test_measure_comment_passes_char_face_and_font_px_to_advance`<br>`test_measure_comment_advance_uses_resized_font_px` |
| M9 増分に縮小前の 39 を渡す | 2 failed | `test_measure_comment_advance_uses_resized_font_px`（落ちた） | `test_measure_comment_passes_char_face_and_font_px_to_advance`<br>`test_measure_comment_advance_uses_resized_font_px` |
| M10 \fsp を書かない | 3 failed | `test_convert_writes_fsp_per_advance_value`（落ちた） | `test_convert_writes_fsp_per_advance_value`<br>`test_convert_fsp_scales_with_font_scale_and_resolution`<br>`test_convert_fsp_value_uses_shrink_scale` |
| M11 \fsp を常に書く | 17 failed | `test_convert_output_unchanged_where_no_pseudo_bold[macos]`（落ちた） | `test_convert_ue_position_time_and_font`<br>`test_convert_scales_to_playres`<br>`test_convert_size_font_size[big]`<br>`test_convert_size_font_size[small]`<br>`test_convert_font_scale_percent`<br>`test_convert_windows_defont_runs_use_each_font_coefficient`<br>`test_convert_gothic_weight_and_font`<br>`test_convert_missing_metrics_falls_back_to_372_ratio`<br>`test_convert_escapes_braces_backslash_and_spaces`<br>`test_convert_orders_by_vpos_then_posted_then_input`<br>`test_convert_orders_by_vpos_before_posted`<br>`test_convert_replaces_lone_surrogates`<br>`test_convert_no_fsp_on_lines_without_advance`<br>`test_convert_default_no_advance_writes_no_fsp`<br>`test_convert_output_unchanged_where_no_pseudo_bold[macos]`<br>`test_convert_output_unchanged_where_no_pseudo_bold[other]`<br>`test_convert_output_unchanged_where_no_pseudo_bold[windows-gothic]` |
| M12 \fsp に scale を掛けない | 1 failed | `test_convert_fsp_value_uses_shrink_scale`（落ちた） | `test_convert_fsp_value_uses_shrink_scale` |
| M13 \fsp に k を掛けない | 1 failed | `test_convert_fsp_scales_with_font_scale_and_resolution`（落ちた） | `test_convert_fsp_scales_with_font_scale_and_resolution` |
| M14 増分の違う字で分けない | 1 failed | `test_convert_writes_fsp_per_advance_value`（落ちた） | `test_convert_writes_fsp_per_advance_value` |
| M15 downloader が advance を渡さない | 7 failed | `test_convert_comments_passes_options`（落ちた） | `test_convert_comments_uses_new_converter_without_danmaku2ass`<br>`test_convert_comments_writes_part_then_replaces`<br>`test_convert_comments_zero_comments_writes_header_only`<br>`test_convert_comments_warns_skipped_count`<br>`test_convert_comments_passes_options`<br>`test_convert_comments_passes_pseudo_bold_advancer_of_platform`<br>`test_convert_comments_write_failure_only_warns` |
| M16 フォント名を見ない（太さだけ比べる） | 4 failed | `test_pseudo_bold_advancer_targets_only_windows_ms_pgothic_600[win-arial]`（落ちた） | `test_pseudo_bold_advancer_targets_only_windows_ms_pgothic_600[win-arial]`<br>`test_pillow_width_with_pseudo_bold_matches_chrome_within_1pct[27px-「Ticon]`<br>`test_pillow_width_with_pseudo_bold_matches_chrome_within_1pct[27px-888888]`<br>`test_pillow_width_with_pseudo_bold_matches_chrome_within_1pct[18px-草生える` |
| M17 downloader が no_advance を渡す | 1 failed | `test_convert_comments_passes_pseudo_bold_advancer_of_platform`（落ちた） | `test_convert_comments_passes_pseudo_bold_advancer_of_platform` |
| M18 本番の増分が常に 0 | 21 failed | `test_pillow_width_with_pseudo_bold_matches_chrome_within_1pct[18px-この結論に至]`（落ちた） | `test_pseudo_bold_advancer_targets_only_windows_ms_pgothic_600[win-mspg600]`<br>`test_pillow_width_with_pseudo_bold_matches_chrome_within_1pct[39px-野獣先輩]`<br>`test_pillow_width_with_pseudo_bold_matches_chrome_within_1pct[39px-日本支部はも]`<br>`test_pillow_width_with_pseudo_bold_matches_chrome_within_1pct[27px-「Ticon]`<br>`test_pillow_width_with_pseudo_bold_matches_chrome_within_1pct[39px-オブジェクト]`<br>`test_pillow_width_with_pseudo_bold_matches_chrome_within_1pct[27px-ボロクソで草]`<br>`test_pillow_width_with_pseudo_bold_matches_chrome_within_1pct[39px-アメリカ合衆]`<br>`test_pillow_width_with_pseudo_bold_matches_chrome_within_1pct[39px-イキスギィ!]`<br>`test_pillow_width_with_pseudo_bold_matches_chrome_within_1pct[18px-この結論に至]`<br>`test_pillow_width_with_pseudo_bold_matches_chrome_within_1pct[18px-今日はいい天]`<br>`test_pillow_width_with_pseudo_bold_matches_chrome_within_1pct[27px-今日はいい天]`<br>`test_pillow_width_with_pseudo_bold_matches_chrome_within_1pct[39px-今日はいい天]`<br>`test_pillow_width_with_pseudo_bold_matches_chrome_within_1pct[27px-ここすき　わ]`<br>`test_pillow_width_with_pseudo_bold_matches_chrome_within_1pct[18px-草生える`<br>`test_pillow_width_with_pseudo_bold_matches_chrome_within_1pct[39px-うぽつです！]`<br>`test_pillow_width_with_pseudo_bold_matches_chrome_within_1pct[12px-長いコメント]`<br>`test_pillow_width_with_pseudo_bold_matches_chrome_within_1pct[15px-長いコメント]`<br>`test_pillow_width_with_pseudo_bold_matches_chrome_within_1pct[20px-長いコメント]`<br>`test_pillow_width_with_pseudo_bold_matches_chrome_within_1pct[23px-長いコメント]`<br>`test_pillow_width_with_pseudo_bold_matches_chrome_within_1pct[31px-長いコメント]`<br>`test_pillow_width_with_pseudo_bold_matches_chrome_within_1pct[10px-長いコメント]` |

テストファーストの red: 実装前（`7b3868a`）は `nico_ass.no_advance` が無く、`tests/test_nico_ass.py` の収集で `AttributeError: module 'yt_gui.nico_ass' has no attribute 'no_advance'`。C2 のしきい値のテストの判定としての red は M18。

## 実動画との見比べ（C2 の参考・C5、2026-11-14）

- 対象: `sm31143779`。こちらは `tests/data/sm31143779.comments.json.gz`（#387 と同じ 1,432 件）から、実装（`2d5bf96`）の `convert` で 960 × 540 の ASS を作り、黒地に libass で描いた（`frame391.py`、`a0341548`）。Web は内蔵ブラウザのプレイヤーで、目標の 12 秒ほど前から自然に再生させ、コメントの canvas（1365 × 768）を目標の時刻で写し取って黒地に重ねた（94.007 秒、356.702 秒）。
- プレイヤーで描いた幅（参考）: #387 の 8 点（Web の値は #387 の表の canvas の実測）と、こちらの焼きこみのインクの幅（`eight391.py`、`75a92f3e`）。

| 時刻 | コメント | Web | 増分なし | 増分あり |
|---|---|---|---|---|
| 14.5 秒 | 野獣先輩（big） | 216.8 | 212（−2.2%） | 215（−0.8%） |
| 14.5 秒 | 日本支部はもう臭い（big） | 458.2 | 447（−2.4%） | 457（−0.3%） |
| 20.5 秒 | 「Ticonderoga(タイコンデロガ)」の方が良い（medium） | 708.7 | 681（−3.9%） | 689（−2.8%） |
| 20.5 秒 | オブジェクトクラスをケテルに修正しろ（big） | 714.3 | 697（−2.4%） | 713（−0.2%） |
| 94.0 秒 | ボロクソで草（medium） | 202.0 | 197（−2.5%） | 201（−0.5%） |
| 266.5 秒 | アメリカ合衆国（big） | 338.5 | 329（−2.8%） | 337（−0.4%） |
| 356.7 秒 | イキスギィ!（big） | 249.9 | 243（−2.8%） | 247（−1.2%） |
| 356.7 秒 | この結論に至るまでに…（small） | 649.6 | 611（−5.9%） | 648（−0.2%） |

  「Ticonderoga」の行は送り幅（C2 の表）では Chrome と 0.00% で一致するので、残る −2.8% は送り幅ではなくインクの描き方の差（英字の多い行。Arial Bold の描画）と見ている（未確認）。

- 段（C5）: 増分の有無で ASS の段がどう変わるか（`rows391.py`、`ff11748f`）と、Web の写しを見比べた。
  - 356.7 秒: #387 で Web と違っていた流れるコメントのうち、「草」（5 分 55.75 秒開始。y 217.6 → 435.0）と「(収容プロトコル)生き返れ生き返れ…」（y 433.2 → 481.0）は、増分を足して Web と同じ段になった。固定コメントは全体に 1.17 px 下がり、行の並びは Web と同じ。「ふぁっ！？」（こちらは上から 2 段目、Web は「まずいですよ！」の段）と「完全敗北してて草」（こちらは y 339、Web は「ダメみたいですね」の下）は違うまま。どちらも乱数の種を変えても y が動かない（`seed391.py`、`172a48d3`）ので、ランダム配置ではない。原因は分からない。
  - 94.0 秒: 増分の有無で段は変わらない（`rows391.py` が「段が変わった」と出した「駄目みたいですね…」「初めて淫夢見た時の…」「ステハゲって何」の 3 件は、開始が 0.01 秒ずれて増分なしの行と対応づけられなかっただけで、y は同じ。ASS の `Dialogue` を直接見て確かめた）。「ボロクソで草」の段は Web と違うまま。この時刻は行が埋まっていて、「暴露後の数十秒で…」と「二言目には…」がランダムに置かれ、ほかの段がそれに押される。乱数の種を変えると、この 2 件と「ボロクソで草」の y が変わる（種 0 で 100.6、種 1 で 67.9）。Web は種の無い乱数で置くので、原理的に一致しない。
- 横位置: 「ボロクソで草」の x は Web 384〜588（写しの縮尺から換算）に対して、こちらは 388〜589。

## `_live`（C6、2026-11-14）

- 対象: `sm9560870` の 6.31 秒の `test`（commands `_live 184`、ユーザーが投稿）。比較用に同じ動画のふつうのコメント（`shita red 184` の「あああああ」と、Web では白の「<ああああああ」）。
- Web: 広告をスキップしてから 2 秒から自然に再生させ、8.005 秒でコメントの canvas を写し取った。灰色（128）の地に重ねた明るさは、`_live` の文字が最大 192、縁取りが最小 91・下位 1% が 102。ふつうのコメントは文字 255、縁取り最小 77。canvas のアルファでは、`_live` の文字が 128（0.5）、縁取りの中央値 44（ふつうのコメントは 86）。
- 焼きこみ: 実装の `convert`（不透明度 1.0、1920 × 1080）で 1 件だけの ASS を作り、灰色（128）の地に libass で描いた（`live391.py`、`a74e1a78`。コメントの JSON の sha256 は `741813d56c25ef13…`）。`_live` の文字が最大 190、縁取りが最小 102。ふつうのコメントの縁取りは 74（赤の文字は 126）。
- 結論: 文字は 190 と 192、縁取りは 102 と下位 1% が 102 で、見え方は一致する。Web の縁取りの最小 91 は、線の重なる所が濃くなるためと見ている（未確認）。

## 検証ゲート

| 巡 | HEAD | verify | docs-check | evaluator |
|---|---|---|---|---|
| 1 | `a8bbcb7` | green（914 passed、skip 0） | 指摘なし | FAIL（[欠陥] 3 / [証跡・文言] 3） |
| 2 | `d0a238d` | green（915 passed） | — （docs の変更はメモと spec の 1 行だけ） | PASS（follow-up あり。[欠陥] 0 / [証跡・文言] 2。2 件ともメモの文言で、この PR で直した） |

evaluator 1 巡目の指摘と閉じ方:

| 指摘 | 区分 | 閉じ方 | 証跡 |
|---|---|---|---|
| 1 本番の配線のテストが `no_advance` と見分けられない（`tests/test_downloader.py:1713`） | 欠陥 | テストを足した（Windows で番兵を返す `pseudo_bold_advancer` に差し替え、同一性を見る） | `2389c35` の `test_convert_comments_passes_pseudo_bold_advancer_of_platform`、変異 M17 |
| 2 C2 のしきい値のテストが red を示していない | 欠陥 | 変異を足した（本番の増分が常に 0） | 変異 M18（C2 の 20 点が落ちる） |
| 3 fixture の `advances` の出どころが実測と一致しない | 欠陥 | 63 点を Chrome で測り直し、JS と生の出力を貼った（食い違い 0） | 「Chrome の実測」の「63 点の測り直し」 |
| 4 spec の「Chrome と同じだけ広げる」に限定句が無い | 証跡・文言 | spec に限定句を足した | `ed1503b` |
| 5 死因の表が 1 変異 1 テスト、フォント名の比較の変異が無い | 証跡・文言 | 落ちたテストを全部並べ、M16 を足した | 「変異 → red（C4、2389c35）」 |
| 6 プローブの本文・完全な hash・証跡の段へ移る 1 行が無い | 証跡・文言 | 貼った | 「プローブの本文」、「Chrome の実測」の前の 1 行 |

## プローブの本文

追跡しない scratchpad の script。`git hash-object` は記録した数値を出したときの本文のもの。

<details><summary>make_fixture.py（fixture を作った（C1）、<code>939deea0a2b795157ec7a760a046ee86ab94a090</code>）</summary>

```python
"""tests/data/nico_chrome_widths.json を、Chrome で測った値から作る（探索の段の転記用）。"""

import json
import sys

rows = json.load(open(sys.argv[1], encoding="utf-8"))
chars = ["漢", "あ", "ｱ", "、", "　", " ", "​", "﻿", "゙"]
sizes = [10, 18, 22, 23, 27, 39, 100]
# Chrome の測定値（600 − 400、"MS PGothic" だけ）。同じ大きさなら字の種類で値が 3 通りしかないので、
# 種類ごとに書き写し、実測の出力（タスクメモ）と突き合わせる
ink = {10: 1, 18: 1, 22: 1, 23: 0.449219, 27: 0.527344, 39: 0.761719, 100: 1.953125}
blank = {10: 1, 18: 1, 22: 1, 23: 0, 27: 0, 39: 0, 100: 0}
zero = {px: 0 for px in sizes}
kind = {
    "漢": ink, "あ": ink, "ｱ": ink, "、": ink, "゙": ink,
    "　": blank, " ": blank,
    "​": zero, "﻿": zero,
}
advances = [
    {"ch": ch, "font_px": px, "increment": kind[ch][px]} for ch in chars for px in sizes
]
out = {
    "measured": {
        "date": "2026-11-14",
        "browser": "Chrome/156.0.8078.75 (Claude desktop built-in browser)",
        "os": "Windows 11",
        "device_pixel_ratio": 1.5,
        "method": "canvas 2d measureText. advances: font '600 {px}px \"MS PGothic\"' minus '400 {px}px \"MS PGothic\"' for one character. widths: font '600 {px}px Arial, \"MS PGothic\"' for the whole text.",
    },
    "advances": advances,
    "widths": rows,
}
open(sys.argv[2], "w", encoding="utf-8", newline="\n").write(
    json.dumps(out, ensure_ascii=True, indent=1) + "\n"
)
print(len(advances), len(rows))
```

</details>

<details><summary>c2table.py（C2 の表、<code>4a1ee7db4c50bfe04fce84006676bd8b22255dfb</code>）</summary>

```python
"""C2 の表: fixture の 21 点で、実装（pillow_measurer + pseudo_bold_advancer）の送り幅と Chrome の差。"""

import json
import sys
from pathlib import Path

ROOT = Path(r"C:\Users\f8924\Documents\claude\yt-gui")
sys.path.insert(0, str(ROOT))
from yt_gui import nico_ass  # noqa: E402

rows = json.loads((ROOT / "tests/data/nico_chrome_widths.json").read_text(encoding="utf-8"))["widths"]
measure = nico_ass.pillow_measurer("windows")
advance = nico_ass.pseudo_bold_advancer("windows")
worst = 0.0
for r in rows:
    px = r["font_px"]
    base = plus = 0.0
    for t, f in nico_ass.font_runs(r["text"], "defont", "windows"):
        base += measure(t, f.name, f.weight, px)
        plus += sum(advance(ch, f, px) for ch in t)
    d0 = (base / r["width"] - 1) * 100
    d1 = ((base + plus) / r["width"] - 1) * 100
    worst = max(worst, abs(d1))
    print(f"| {px} | {r['text']} | {r['width']:.2f} | {d0:+.2f}% | {d1:+.2f}% |")
print(f"最大 {worst:.2f}%")
```

</details>

<details><summary>libass391.py（libass で描いた幅（C3）、<code>47500936d37c4bbfbc8c68ac870104df286a8108</code>）</summary>

```python
"""C3: \\fsp を足した ASS を bin/ffmpeg の libass で描き、インク幅を測った幅と比べる。

1) 同じ 1 行を \\fsp あり / なしで描き、インクの左端・右端の差から、libass が 1 字ごとに
   \\fsp を足すか、末尾の字の後ろの \\fsp を行の幅（\\an8 の中央揃え）に含めるかを見る。
2) 期待するインク幅 = Pillow で同じ em に描いたインク幅 + (n − 1) × \\fsp と比べる。
"""

import json
import random
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(r"C:\Users\f8924\Documents\claude\yt-gui")
sys.path.insert(0, str(ROOT))
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

from yt_gui import nico_ass  # noqa: E402

OUT = Path(sys.argv[1])
OUT.mkdir(exist_ok=True)
FFMPEG = ROOT / "bin" / "ffmpeg" / "ffmpeg.exe"
W, H = 1920, 1080
FONT = r"C:\Windows\Fonts\msgothic.ttc"


def ass_for(body: str, size: str) -> str:
    rows = [{"body": body, "commands": ["ue", size], "vposMs": 0, "isPremium": False,
             "postedAt": "2020-01-01T00:00:00+09:00"}]
    res = nico_ass.convert(
        json.dumps(rows, ensure_ascii=False), width=W, height=H, font_scale_percent=100,
        opacity=1.0, platform="windows", measure=nico_ass.pillow_measurer("windows"),
        metrics=nico_ass.font_metrics("windows"),
        advance=nico_ass.pseudo_bold_advancer("windows"), rng=random.Random(0),
    )
    return re.sub(r"\\bord[0-9.]+", r"\\bord0", res.ass)


def render(ass: str, name: str) -> tuple[int, int]:
    path = OUT / f"{name}.ass"
    path.write_text(ass, encoding="utf-8-sig")
    png = OUT / f"{name}.png"
    rel = path.name
    subprocess.run(
        [str(FFMPEG), "-y", "-loglevel", "error", "-f", "lavfi", "-i",
         f"color=black:s={W}x{H}:d=1", "-vf", f"ass={rel}", "-ss", "0.5",
         "-frames:v", "1", png.name],
        cwd=OUT, check=True,
    )
    img = Image.open(png).convert("L").point(lambda v: 255 if v > 96 else 0)
    box = img.getbbox()
    assert box, name
    return box[0], box[2]


def pillow_ink(text: str, em: float) -> float:
    font = ImageFont.truetype(FONT, round(em * 64) / 64, index=2)
    img = Image.new("L", (int(em * len(text) * 1.5) + 50, int(em * 2)), 0)
    ImageDraw.Draw(img).text((10, 10), text, fill=255, font=font)
    box = img.point(lambda v: 255 if v > 96 else 0).getbbox()
    return box[2] - box[0]


for size, n in (("big", 8), ("medium", 8), ("small", 8)):
    body = "漢" * n
    ass = ass_for(body, size)
    fsp = float(re.search(r"\\fsp([0-9.]+)", ass).group(1))
    em = float(re.search(r"\\fs([0-9.]+)\\fsp", ass).group(1))  # MS PGothic は係数 1.0
    with_l, with_r = render(ass, f"{size}_fsp")
    no_l, no_r = render(re.sub(r"\\fsp[0-9.]+", "", ass), f"{size}_nofsp")
    ink_with = with_r - with_l
    ink_no = no_r - no_l
    trailing = "含む" if abs((no_l - with_l) - n * fsp / 2) < abs((no_l - with_l) - (n - 1) * fsp / 2) else "含まない"
    expected = pillow_ink(body, em) + (n - 1) * fsp
    print(
        f"{size}: em={em} fsp={fsp} n={n} | libass あり {ink_with} / なし {ink_no} "
        f"差 {ink_with - ink_no} (期待 (n-1)fsp={(n - 1) * fsp:.2f}) | 左端のずれ {no_l - with_l} "
        f"(n fsp/2={n * fsp / 2:.2f}, (n-1) fsp/2={(n - 1) * fsp / 2:.2f}) → 末尾を{trailing} | "
        f"Pillow+fsp {expected:.1f} 比 {ink_with / expected:.4f}"
    )
```

</details>

<details><summary>trail391.py（行末の `\fsp` と中央揃え（C3）、<code>53c259647e19f6802823815e5b90d73e6d598df5</code>）</summary>

```python
"""libass が末尾の字の後ろの \\fsp を \\an8 の中央揃えの幅に含めるか（\\fsp を 40 に誇張して見る）。"""

import re
import subprocess
import sys
from pathlib import Path

from PIL import Image

OUT = Path(sys.argv[1])
SRC = (OUT / "big_fsp.ass").read_text(encoding="utf-8-sig")
FFMPEG = Path(r"C:\Users\f8924\Documents\claude\yt-gui\bin\ffmpeg\ffmpeg.exe")


def left(ass: str, name: str) -> int:
    (OUT / f"{name}.ass").write_text(ass, encoding="utf-8-sig")
    subprocess.run(
        [str(FFMPEG), "-y", "-loglevel", "error", "-f", "lavfi", "-i",
         "color=black:s=1920x1080:d=1", "-vf", f"ass={name}.ass", "-ss", "0.5",
         "-frames:v", "1", f"{name}.png"],
        cwd=OUT, check=True,
    )
    box = Image.open(OUT / f"{name}.png").convert("L").point(lambda v: 255 if v > 96 else 0).getbbox()
    return box[0]


n = SRC.count("漢")
base = left(re.sub(r"\\fsp[0-9.]+", r"\\fsp0", SRC), "t_fsp0")
big = left(re.sub(r"\\fsp[0-9.]+", r"\\fsp40", SRC), "t_fsp40")
print(f"n={n} 左端のずれ {base - big}  含むなら {n * 40 / 2}  含まないなら {(n - 1) * 40 / 2}")
```

</details>

<details><summary>mutate391.py（変異 → red（C4）、<code>73750d8f1ec7936ce0f8e5398dfcb2df2c428199</code>）</summary>

```python
"""#391 の変異 → red。worktree のコピーを変異させ、落ちたテスト名を集める。

使い方: python mutate391.py <worktree のパス>
無変異のコピーが green でなければ止まる。変異が当たらない（置換 0 件）ときも止まる（fail-closed）。
"""

import re
import subprocess
import sys
from pathlib import Path

WT = Path(sys.argv[1])
TESTS = ["tests/test_nico_ass.py", "tests/test_downloader.py"]

MUTANTS = [
    ("M1 境目 <= → <", "yt_gui/nico_ass.py",
     "if font_px <= _PSEUDO_BOLD_BITMAP_MAX_PX:", "if font_px < _PSEUDO_BOLD_BITMAP_MAX_PX:",
     "test_pseudo_bold_advance_matches_chrome[U+6F22@22]"),
    ("M2 Cf を 0 にしない", "yt_gui/nico_ass.py",
     'if unicodedata.category(ch) == "Cf":\n        return 0.0', 'if False:\n        return 0.0',
     "test_pseudo_bold_advance_matches_chrome[U+200B@39]"),
    ("M3 空白を 0 にしない", "yt_gui/nico_ass.py",
     "if ch.isspace():\n        return 0.0\n    return font_px", "if False:\n        return 0.0\n    return font_px",
     "test_pseudo_bold_advance_matches_chrome[U+3000@39]"),
    ("M4 比 5/256 → 1/50", "yt_gui/nico_ass.py",
     "_PSEUDO_BOLD_EM_RATIO = 5 / 256", "_PSEUDO_BOLD_EM_RATIO = 1 / 50",
     "test_pseudo_bold_advance_matches_chrome[U+6F22@39]"),
    ("M5 OS の判定を外す", "yt_gui/nico_ass.py",
     'if platform != "windows":\n        return no_advance', 'if False:\n        return no_advance',
     "test_pseudo_bold_advancer_targets_only_windows_ms_pgothic_600[mac-mspg600]"),
    ("M6 太さを見ない", "yt_gui/nico_ass.py",
     "if run_face != face:", "if run_face.name != face.name:",
     "test_pseudo_bold_advancer_targets_only_windows_ms_pgothic_600[win-mspg400]"),
    ("M7 フォントの有無を見ない", "yt_gui/nico_ass.py",
     "if _resolve_font(platform, face.name, face.weight) is None:\n        return no_advance",
     "if False:\n        return no_advance",
     "test_pseudo_bold_advancer_is_zero_when_font_not_found"),
    ("M8 測定に増分を足さない", "yt_gui/nico_ass.py",
     "return width + sum(advance(ch, face, font_px) for ch in text)", "return width",
     "test_measure_comment_adds_advance_before_ceil"),
    ("M9 増分に縮小前の 39 を渡す", "yt_gui/nico_ass.py",
     "return width + sum(advance(ch, face, font_px) for ch in text)",
     "return width + sum(advance(ch, face, 39) for ch in text)",
     "test_measure_comment_advance_uses_resized_font_px"),
    ("M10 \\fsp を書かない", "yt_gui/nico_ass.py",
     "spaced = any(adv for run in pieces for _, adv in run)", "spaced = False",
     "test_convert_writes_fsp_per_advance_value"),
    ("M11 \\fsp を常に書く", "yt_gui/nico_ass.py",
     "spaced = any(adv for run in pieces for _, adv in run)", "spaced = True",
     "test_convert_output_unchanged_where_no_pseudo_bold[macos]"),
    ("M12 \\fsp に scale を掛けない", "yt_gui/nico_ass.py",
     "_num(adv * m.scale * c * k)", "_num(adv * c * k)",
     "test_convert_fsp_value_uses_shrink_scale"),
    ("M13 \\fsp に k を掛けない", "yt_gui/nico_ass.py",
     "_num(adv * m.scale * c * k)", "_num(adv * m.scale * c)",
     "test_convert_fsp_scales_with_font_scale_and_resolution"),
    ("M14 増分の違う字で分けない", "yt_gui/nico_ass.py",
     "if pieces and pieces[-1][1] == adv:", "if pieces:",
     "test_convert_writes_fsp_per_advance_value"),
    ("M15 downloader が advance を渡さない", "yt_gui/downloader.py",
     "                advance=nico_ass.pseudo_bold_advancer(platform),\n", "",
     "test_convert_comments_passes_options"),
    ("M16 フォント名を見ない（太さだけ比べる）", "yt_gui/nico_ass.py",
     "if run_face != face:", "if run_face.weight != face.weight:",
     "test_pseudo_bold_advancer_targets_only_windows_ms_pgothic_600[win-arial]"),
    ("M17 downloader が no_advance を渡す", "yt_gui/downloader.py",
     "advance=nico_ass.pseudo_bold_advancer(platform),", "advance=nico_ass.no_advance,",
     "test_convert_comments_passes_pseudo_bold_advancer_of_platform"),
    ("M18 本番の増分が常に 0", "yt_gui/nico_ass.py",
     "        return pseudo_bold_advance(ch, font_px)\n", "        return 0.0\n",
     # pytest は -rf の ID の非 ASCII を \uXXXX で出す
     "test_pillow_width_with_pseudo_bold_matches_chrome_within_1pct[18px-\\u3053\\u306e\\u7d50\\u8ad6\\u306b\\u81f3]"),
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

<details><summary>mut_table.py（死因の表（C4）、<code>2fe2ce089b5799bb055090607d35a915573d9281</code>）</summary>

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

<details><summary>frame391.py（実動画の ASS とフレーム（C5）、<code>a0341548ec16a375f7260049a1503b369d891a9b</code>）</summary>

```python
"""sm31143779 の全件から 960x540 の ASS を作り（増分あり / なし）、指定の時刻のフレームを黒地に描く。"""

import gzip
import random
import subprocess
import sys
from pathlib import Path

ROOT = Path(r"C:\Users\f8924\Documents\claude\yt-gui")
sys.path.insert(0, str(ROOT))
from yt_gui import nico_ass  # noqa: E402

OUT = Path(sys.argv[1])
OUT.mkdir(exist_ok=True)
FFMPEG = ROOT / "bin" / "ffmpeg" / "ffmpeg.exe"
text = gzip.decompress((ROOT / "tests/data/sm31143779.comments.json.gz").read_bytes()).decode()

for tag, advance in (("new", nico_ass.pseudo_bold_advancer("windows")), ("old", nico_ass.no_advance)):
    ass = nico_ass.convert(
        text, width=960, height=540, font_scale_percent=100, opacity=1.0,
        platform="windows", measure=nico_ass.pillow_measurer("windows"),
        metrics=nico_ass.font_metrics("windows"), advance=advance, rng=random.Random(0),
    ).ass
    (OUT / f"{tag}.ass").write_text(ass, encoding="utf-8-sig")
    for t in sys.argv[2:]:
        subprocess.run(
            [str(FFMPEG), "-y", "-loglevel", "error", "-f", "lavfi", "-i",
             f"color=black:s=960x540:d={float(t) + 1}", "-vf", f"ass={tag}.ass", "-ss", t,
             "-frames:v", "1", f"{tag}_{t}.png"],
            cwd=OUT, check=True,
        )
        print(OUT / f"{tag}_{t}.png")
```

</details>

<details><summary>eight391.py（#387 の 8 点の幅（C2 の参考）、<code>75a92f3e3d24f082a20dc7a9edc48ae3faf56a1f</code>）</summary>

```python
"""#387 の 8 点（Web は #387 のタスクメモの表の canvas の実測値）を、増分あり / なしの焼きこみの
インクの外接矩形の幅と比べる。色と y の範囲でコメントを切り出す（960 × 540）。"""

import subprocess
import sys
from pathlib import Path

from PIL import Image

D = Path(sys.argv[1])
FFMPEG = r"C:\Users\f8924\Documents\claude\yt-gui\bin\ffmpeg\ffmpeg.exe"

# 時刻, 名前, 色の判定, y の範囲, Web の x0, x1（#387 の表）
CASES = [
    ("14.5", "野獣先輩 big yellow", lambda p: p[0] > 200 and p[1] > 200 and p[2] < 80, (0, 70), 371.6, 588.4),
    ("14.5", "日本支部はもう臭い big red", lambda p: p[0] > 200 and p[1] < 60 and p[2] < 60, (470, 540), 254.1, 712.3),
    ("20.5", "Ticonderoga medium blue", lambda p: p[0] < 60 and p[1] < 60 and p[2] > 200, (430, 490), 126.0, 834.7),
    ("20.5", "オブジェクト big red", lambda p: p[0] > 200 and p[1] < 60 and p[2] < 60, (485, 540), 121.8, 836.1),
    ("94.0", "ボロクソで草 medium red", lambda p: p[0] > 200 and p[1] < 60 and p[2] < 60, (0, 540), 375.1, 577.1),
    ("266.5", "アメリカ合衆国 big cyan", lambda p: p[0] < 60 and p[1] > 200 and p[2] > 200, (470, 540), 309.0, 647.5),
    ("356.7", "イキスギィ! big purple", lambda p: p[0] > 120 and p[1] < 80 and p[2] > 180, (195, 265), 354.0, 603.9),
    ("356.7", "この結論… small cyan2", lambda p: p[0] < 90 and p[1] > 150 and p[2] > 150, (450, 485), 152.0, 801.6),
]


def frame(tag, t):
    png = D / f"{tag}_{t}.png"
    if not png.exists():
        subprocess.run(
            [FFMPEG, "-y", "-loglevel", "error", "-f", "lavfi", "-i",
             f"color=black:s=960x540:d={float(t) + 1}", "-vf", f"ass={tag}.ass", "-ss", t,
             "-frames:v", "1", png.name],
            cwd=D, check=True,
        )
    return Image.open(png).convert("RGB")


def width(img, pred, yr):
    px = img.load()
    xs = [x for y in range(*yr) for x in range(960) if pred(px[x, y])]
    return min(xs), max(xs)


for t, name, pred, yr, wx0, wx1 in CASES:
    web = wx1 - wx0
    n0, n1 = width(frame("new", t), pred, yr)
    o0, o1 = width(frame("old", t), pred, yr)
    print(f"{t:>6} {name:28} Web {web:6.1f} | 増分なし {o1 - o0:4d} ({((o1 - o0) / web - 1) * 100:+.1f}%) | 増分あり {n1 - n0:4d} ({((n1 - n0) / web - 1) * 100:+.1f}%) x {n0}–{n1}")
```

</details>

<details><summary>rows391.py（段の比較（C5）、<code>ff11748f52c0378d841621304392e0987b1fd24d</code>）</summary>

```python
"""C5: sm31143779 の全件から 960x540 の ASS を作り、指定の時刻に流れているコメントの段（y）を出す。

増分あり（今の実装）と増分なし（no_advance、#387 と同じ）の両方で出し、段が変わったものに印を付ける。
"""

import gzip
import json
import random
import re
import sys
from pathlib import Path

ROOT = Path(r"C:\Users\f8924\Documents\claude\yt-gui")
sys.path.insert(0, str(ROOT))
from yt_gui import nico_ass  # noqa: E402

text = gzip.decompress((ROOT / "tests/data/sm31143779.comments.json.gz").read_bytes()).decode()


def build(advance):
    return nico_ass.convert(
        text, width=960, height=540, font_scale_percent=100, opacity=0.8,
        platform="windows", measure=nico_ass.pillow_measurer("windows"),
        metrics=nico_ass.font_metrics("windows"), advance=advance, rng=random.Random(0),
    ).ass


def at(ass, t):
    out = {}
    for line in ass.splitlines():
        if not line.startswith("Dialogue:"):
            continue
        parts = line.split(",", 9)
        s, e = parts[1], parts[2]

        def sec(v):
            h, m, x = v.split(":")
            return int(h) * 3600 + int(m) * 60 + float(x)

        if not sec(s) <= t < sec(e):
            continue
        body = re.sub(r"\{[^}]*\}", "", parts[9])
        mv = re.search(r"\\move\(([^)]*)\)", parts[9])
        pos = re.search(r"\\pos\(([^)]*)\)", parts[9])
        kind = "naka" if mv else "fixed"
        y = float((mv or pos).group(1).split(",")[1])
        out[(body, sec(s))] = (kind, y)
    return out


new = build(nico_ass.pseudo_bold_advancer("windows"))
old = build(nico_ass.no_advance)
for t in map(float, sys.argv[1:]):
    a, b = at(old, t), at(new, t)
    print(f"--- {t} 秒: {len(b)} 件")
    for key in sorted(b, key=lambda k: b[k][1]):
        kind, y = b[key]
        oy = a.get(key, (None, None))[1]
        mark = "" if oy is not None and abs(oy - y) < 0.01 else f"  ← 段が変わった（前 {oy}）"
        print(f"  {kind:5} y={y:7.2f} {key[0][:24]}{mark}")
```

</details>

<details><summary>seed391.py（乱数の種と段（C5・spec）、<code>172a48d3b10b10a7a279da38dd1a9c8a16f49957</code>）</summary>

```python
"""残った段の違いが、行が埋まったときのランダム配置かを見る（乱数の種を変えて y が動くか）。"""

import gzip
import random
import re
import sys
from pathlib import Path

ROOT = Path(r"C:\Users\f8924\Documents\claude\yt-gui")
sys.path.insert(0, str(ROOT))
from yt_gui import nico_ass  # noqa: E402

text = gzip.decompress((ROOT / "tests/data/sm31143779.comments.json.gz").read_bytes()).decode()
WATCH = ["ふぁっ！？", "完全敗北してて草", "暴露後の数十秒", "二言目には", "ボロクソで草", "草", "(収容プロトコル)"]


def ys(seed):
    ass = nico_ass.convert(
        text, width=960, height=540, font_scale_percent=100, opacity=1.0, platform="windows",
        measure=nico_ass.pillow_measurer("windows"), metrics=nico_ass.font_metrics("windows"),
        advance=nico_ass.pseudo_bold_advancer("windows"), rng=random.Random(seed),
    ).ass
    out = {}
    for line in ass.splitlines():
        if not line.startswith("Dialogue:"):
            continue
        p = line.split(",", 9)
        body = re.sub(r"\{[^}]*\}", "", p[9]).replace("\\h", " ")
        start = p[1]
        for w in WATCH:
            if body.startswith(w) and (start.startswith("0:01:3") or start.startswith("0:05:5")):
                y = float(re.search(r"\\(?:move|pos)\(([^)]*)\)", p[9]).group(1).split(",")[1])
                out.setdefault(w, []).append((start, round(y, 1)))
    return out


a, b = ys(0), ys(1)
for w in WATCH:
    print(w, "seed0", a.get(w), "| seed1", b.get(w))
```

</details>

<details><summary>live391.py（`_live`（C6）、<code>a74e1a78b6d9c2e66c804b51a02ce5ca1d729d65</code>）</summary>

```python
"""C6: sm9560870 の `_live` の `test`（と比較用のふつうのコメント）を、不透明度 1.0 の ASS にして
灰色（128）の地に libass で描き、文字（最大）と縁取り（最小・下位 1%）の明るさを出す。"""

import json
import random
import subprocess
import sys
from pathlib import Path

ROOT = Path(r"C:\Users\f8924\Documents\claude\yt-gui")
sys.path.insert(0, str(ROOT))
from PIL import Image  # noqa: E402

from yt_gui import nico_ass  # noqa: E402

D = Path(sys.argv[1])
FFMPEG = str(ROOT / "bin" / "ffmpeg" / "ffmpeg.exe")
data = json.load(open(D / "sm9560870.comments.json", encoding="utf-8-sig"))


def rows():
    out = []

    def walk(o):
        if isinstance(o, dict):
            if "commands" in o and "body" in o:
                out.append(o)
            else:
                for v in o.values():
                    walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(data)
    return out


def render(row, name):
    one = dict(row, vposMs=0)
    ass = nico_ass.convert(
        json.dumps([one], ensure_ascii=False), width=1920, height=1080, font_scale_percent=100,
        opacity=1.0, platform="windows", measure=nico_ass.pillow_measurer("windows"),
        metrics=nico_ass.font_metrics("windows"),
        advance=nico_ass.pseudo_bold_advancer("windows"), rng=random.Random(0),
    ).ass
    (D / f"{name}.ass").write_text(ass, encoding="utf-8-sig")
    subprocess.run(
        [FFMPEG, "-y", "-loglevel", "error", "-f", "lavfi", "-i",
         "color=0x808080:s=1920x1080:d=3", "-vf", f"ass={name}.ass", "-ss", "1.5",
         "-frames:v", "1", f"{name}.png"],
        cwd=D, check=True,
    )
    img = Image.open(D / f"{name}.png").convert("L")
    vals = sorted(v for v in img.getdata() if v != 128)
    print(f"{name}: {row['commands']} {row['body']!r} 文字 最大 {vals[-1]} / 縁取り 最小 {vals[0]}, 下位 1% {vals[len(vals) // 100]}")


rs = rows()
live = next(r for r in rs if r["body"] == "test" and "_live" in r["commands"])
normal = next(r for r in rs if "ああああ" in r["body"] and "_live" not in r["commands"])
render(live, "live_test")
render(normal, "normal")
```

</details>

## 訂正ログ

| 日付 | 何を誤って書いたか | 正しくは | どの検査・手順なら捕まえたか |
|---|---|---|---|
| 2026-11-14 | Issue 本文の「着手時に分かったこと」に「全角スペースは増えない」と大きさの条件なしで書いた。arch の初版には「ゼロ幅の文字（`Mn` / `Me` / `Cf`）は 0」と書いた | 22px 以下は空白も 1 増える（23px 以上は 0）。結合文字（`Mn`）は増える。0 なのは `Cf` | 39px の測定だけから一般化した。18px と 39px の両方で、字の種類ごとに測ってから書けば捕まえた（design-review の指摘で追加測定） |

## 次にやること

C1〜C7 は証跡つきで完了。evaluator は 2 巡目で PASS（follow-up あり。指摘 2 件はメモの文言で、この PR で直した）。次は PR。

訂正ログ: 1 件
