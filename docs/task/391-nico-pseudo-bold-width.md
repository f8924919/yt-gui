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
- fixture の `advances` は、1 字ずつ `600 {px}px "MS PGothic"` と `400 {px}px "MS PGothic"` の差を測った 63 点（9 字 × 10 / 18 / 22 / 23 / 27 / 39 / 100）。値は字の種類で 3 通りなので、作る script（`make_fixture.py`、`git hash-object` `939deea0`、scratchpad）は種類ごとに書き写し、実測の出力の 8 点と一致することを確かめた。fixture の sha256 は `30f3135216bf4b72…`。
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

## 変異 → red（C4、2d5bf96）

worktree のコピー（`2d5bf96`）を 1 つずつ変異させ、`tests/test_nico_ass.py` と `tests/test_downloader.py` を走らせた。無変異のコピーは 408 passed、戻した後も 408 passed。script は `mutate391.py`（`git hash-object` `be47dec1`）。置換が 1 か所に当たらないときは止まる。

| 変異 | 結果 | 狙ったテスト（落ちた） |
|---|---|---|
| M1 境目 `<=` → `<` | 7 failed | `test_pseudo_bold_advance_matches_chrome[U+6F22@22]` |
| M2 `Cf` を 0 にしない | 14 failed | `test_pseudo_bold_advance_matches_chrome[U+200B@39]` |
| M3 空白を 0 にしない | 8 failed | `test_pseudo_bold_advance_matches_chrome[U+3000@39]` |
| M4 比 5/256 → 1/50 | 21 failed | `test_pseudo_bold_advance_matches_chrome[U+6F22@39]` |
| M5 OS の判定を外す | 2 failed | `test_pseudo_bold_advancer_targets_only_windows_ms_pgothic_600[mac-mspg600]` |
| M6 太さを見ない | 1 failed | `…_600[win-mspg400]` |
| M7 フォントの有無を見ない | 1 failed | `test_pseudo_bold_advancer_is_zero_when_font_not_found` |
| M8 測定に増分を足さない | 3 failed | `test_measure_comment_adds_advance_before_ceil` |
| M9 増分に縮小前の 39 を渡す | 2 failed | `test_measure_comment_advance_uses_resized_font_px` |
| M10 `\fsp` を書かない | 3 failed | `test_convert_writes_fsp_per_advance_value` |
| M11 `\fsp` を常に書く | 17 failed | `test_convert_output_unchanged_where_no_pseudo_bold[macos]` |
| M12 `\fsp` に `scale` を掛けない | 1 failed | `test_convert_fsp_value_uses_shrink_scale` |
| M13 `\fsp` に `k` を掛けない | 1 failed | `test_convert_fsp_scales_with_font_scale_and_resolution` |
| M14 増分の違う字で分けない | 1 failed | `test_convert_writes_fsp_per_advance_value` |
| M15 downloader が `advance` を渡さない | 6 failed | `test_convert_comments_passes_options` |

テストファーストの red: 実装前（`7b3868a`）は `nico_ass.no_advance` が無く、`tests/test_nico_ass.py` の収集で `AttributeError: module 'yt_gui.nico_ass' has no attribute 'no_advance'`。

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

## 訂正ログ

| 日付 | 何を誤って書いたか | 正しくは | どの検査・手順なら捕まえたか |
|---|---|---|---|
| 2026-11-14 | Issue 本文の「着手時に分かったこと」に「全角スペースは増えない」と大きさの条件なしで書いた。arch の初版には「ゼロ幅の文字（`Mn` / `Me` / `Cf`）は 0」と書いた | 22px 以下は空白も 1 増える（23px 以上は 0）。結合文字（`Mn`）は増える。0 なのは `Cf` | 39px の測定だけから一般化した。18px と 39px の両方で、字の種類ごとに測ってから書けば捕まえた（design-review の指摘で追加測定） |

## 次にやること

C1〜C7 は証跡つきで完了。次は `/verify-gate`（verify → docs-check → evaluator）→ PR。

訂正ログ: 1 件
