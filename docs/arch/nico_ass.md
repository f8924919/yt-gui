# yt_gui/nico_ass.py

> 関連仕様: [オリジナル形式パネル — コメント・弾幕グループ](../spec/screens/original-format-panel.md#コメント弾幕グループ)

ニコニコ動画のコメント（yt-dlp が保存する `{stem}.comments.json`）を ASS 字幕の文字列に変換する。Web 表示の再現 OSS [niconicomments](https://github.com/xpadev-net/niconicomments)（MIT、参照コミット `899203436285`）の HTML5 描画の式・定数・色表を移植する。ビリビリの弾幕は対象外で、従来どおり `danmaku2ass` を使う（[downloader.md](downloader.md#コメント弾幕の-ass-変換)）。

移植元の値と行番号の正本は [Issue #387](https://github.com/f8924919/yt-gui/issues/387) の表で、ここには書き写さない。コードには定数ごとに移植元のファイルと行を注記する。

## 公開する関数

- `convert(comments_json, *, width, height, font_scale_percent, opacity, platform, measure, metrics, rng) -> ConvertResult`: ASS の文字列（`ConvertResult.ass`）と、飛ばしたコメントの件数（`ConvertResult.skipped`）を返す。`comments_json` は JSON の文字列。ファイルの読み書きはしない。`platform` は `"windows"` / `"macos"` / `"other"`。`rng` は `random()` を持つオブジェクト（`random.Random` など）。
- `font_candidates(font, platform) -> tuple[FontFace, ...]`: コマンドのフォント（`defont` / `gothic` / `mincho`）と OS から、フォントの候補を返す純関数。`FontFace(name, weight)`。
- `font_runs(text, font, platform) -> list[tuple[str, FontFace]]`: 1 行の文字列を、描くフォントごとの区間に分ける（隣り合う同じフォントの文字はまとめる）。
- 測定器の型は `measure(text, font_name, weight, size_px) -> float`（`size_px` は CSS の em。戻り値は送り幅の px）。
- 寸法の型は `metrics(font_name, weight) -> FontMetrics | None`。`FontMetrics(ascent, descent)` は `usWinAscent / unitsPerEm` と `usWinDescent / unitsPerEm`。`None` はフォントが見つからないとき。
- `pillow_measurer(platform)` / `font_metrics(platform)`: 実行時の測定器と寸法を返す。Pillow は関数の中で遅延 import し、`ImportError` なら概算の測定器と、常に `None` を返す寸法を返す。結果はモジュール単位でキャッシュする。
- `approx_measurer`: 概算の測定器（全角 1 文字分、半角 0.5 文字分。全角は `unicodedata.east_asian_width` の `F` / `W`）。

## 内部の継ぎ目（テストが固定する形）

テストは次の関数を直接呼ぶ。単位は、`stage` が舞台（高さ 384）、`canvas` がキャンバス（1920 × 1080）。

- `parse_commands(commands, body, is_premium) -> Command`。`Command(loc, size, color, font, long, live, invisible)`。`loc` は `naka` / `ue` / `shita`、`size` は `big` / `medium` / `small`、`font` は `defont` / `gothic` / `mincho`（`gulim` / `simsun` は `defont`）、`long` は vpos 単位の整数、`color` は niconicomments と同じく大文字の文字列（色名は表の値、`#RGB` は `#RGB` のまま）。既定は `naka` / `medium` / `#FFFFFF` / `defont` / 300。
- `ass_color(color) -> str`: `&HBBGGRR&`。`#RGB` は各桁を 2 回並べて広げ、16 進として読めない値は白。
- `char_size(size)` / `line_height(size)`: 舞台の単位。`char_size = 384 / doubleResized`、`line_height = (384 - char_size) / (default - 1)`。
- `font_size_and_scale(char_size) -> (font_px, scale)`: niconicomments の `getFontSizeAndScale`。`char_size × 0.8` が 10 未満なら `(10, floor(char_size × 0.8) / 10)`（1 未満は floor しない）、それ以外は `(floor(char_size × 0.8), 1)`。
- `measure_comment(lines, cmd, *, platform, measure, font_scale) -> Measured`: 行ごとの幅（舞台の単位、`ceil(送り幅の合計 × scale)`）を測り、上下固定の縮小を行う。`Measured(char_size, line_height, font_px, scale, line_widths, width, height)` の `width` / `height` はキャンバスの単位（舞台の値 × `1920 / 683` × `font_scale`）。`font_scale` は `font_scale_percent / 100`。縮小の判定は「舞台の幅 × `font_scale` > 512」。
- `naka_speed(width, long)` / `naka_x(width, long, elapsed)`: キャンバスの単位。`elapsed` は `vpos` からの経過。
- `layout(items, rng) -> list[float]`: `LayoutItem(loc, vpos, long, width, height, commands)`（キャンバスの単位、`commands` は元のコマンドの列）の並びに、キャンバスの `posY` を返す。`shita` の `posY` は下からの距離（niconicomments と同じ）。乱数は `floor(rng.random() × (1080 - height))` で引く。
## 座標系

計算は niconicomments と同じ 1920 × 1080 のキャンバス（以下「キャンバス」）で行い、最後に ASS の `PlayRes`（動画の解像度 `W` × `H`）へ換算する。

- 基準の高さ `H0` は [#372](../task/archive/372-comment-font-ratio.md) と同じく `H`（縦動画は `W × 9 / 16`）。換算の倍率は `k = H0 / 1080`。
- キャンバスの点 `(x, y)` は `PlayRes` の `((W - 1920k) / 2 + kx, (H - 1080k) / 2 + ky)` に置く。4:3 などで舞台が動画より広いときは、はみ出した部分が映らない。
- 流れるコメントが画面に入る・出る時刻は、舞台の端ではなく動画の端（`PlayRes` の `0` と `W`）で決める。16:9 より横長の動画でも、端から入って端へ出る。
- 時間はキャンバスの単位（10ms、`vpos`）で計算する。ASS の時刻（1/100 秒）と単位が同じなので、丸めずに使える。`vpos = floor(vposMs / 10)`。
- 丸めは JavaScript に合わせる（`Math.round` は `floor(x + 0.5)`、`Math.floor` は `math.floor`）。

## 文字サイズ

- niconicomments の `charSize`、`lineHeight`、`fontSize`（CSS の `font-size` 相当）を、舞台の高さ 384 の単位で移植し、キャンバスへは `1920 / 683` 倍で換算する。倍率（`font_scale_percent`）はキャンバスの文字サイズに掛ける。幅の上限（512）の判定は倍率を掛けた後の幅で行う。
- 幅は、測った文字サイズ（CSS の em）での幅とする。小さいサイズのヒンティングの丸めを避けるため、大きいサイズ（100px）で測って比例で縮める。
- ASS の `Fontsize` は、描くフォントの `(usWinAscent + usWinDescent) / unitsPerEm` を em に掛けた値にする（libass はこの高さを `Fontsize` として扱う）。これで測った幅と描く幅が一致する（Windows・`bin/ffmpeg` の libass・Pillow 13 の 4 フォントで 0.2% 以内を確認。macOS は未確認。記録は[タスクメモ](../task/387-nico-ass-converter.md)）。係数はフォントファイルの OS/2 表から読む。フォントが見つからないときは、#372 の比率（`medium` で動画の高さの 0.09）に戻す。
- この換算はニコニコだけで、ビリビリは #372 の `_comment_font_size` のまま。

## フォント

- `font_candidates` は niconicomments の `fonts.ts` の候補列を、文字の範囲ごとの組に直して返す。Windows の `defont` は英字（Latin）を Arial、それ以外を MS PGothic にする。ほかは 1 つのフォントで描く。
- 「英字」は U+0000〜U+024F（Basic Latin から Latin Extended-B まで）とする。ブラウザは Arial にある文字（ギリシャ文字、`…` など）も Arial で描くが、ここでは扱わない（幅の差は小さい）。
- 候補（名前, 太さ）: Windows は `defont` が `Arial` 600 と `MS PGothic` 600、`gothic` が `Yu Gothic` 400、`mincho` が `Yu Mincho` 400。macOS（niconicomments の `mac10_11`）は `defont` が `Hiragino Sans` 600、`gothic` が `YuGothic` 400、`mincho` が `YuMincho` 400（macOS の英語のファミリー名。Mac での確認は未）。その他は `sans-serif` 600、`sans-serif` 400、`serif` 400。
- niconicomments のフォントごとの縦のずれ（`offset`、舞台で 0.05 px 以下）は扱わない。
- 幅を測るときも ASS に書くときも、同じ分け方を使う。ASS では区間ごとに `{\fn<名前>\fs<サイズ>}` を書く。フォントごとに係数が違う（Arial 1.117、MS PGothic 1.000 など）ので、`\fs` も区間ごとに、その区間のフォントの係数で求める。Style の `Fontsize` は使わない（仮の値）。
- フォント名は英語のファミリー名（`Arial`、`MS PGothic`、`Yu Gothic`、`Yu Mincho`、`Hiragino Sans` など）。フォントファイルは OS ごとの候補のパスから探し、`.ttc` は `getname()` でフェイスを照合して開く（index を決め打ちしない）。
- 太さは `\b<weight>`（Style の Bold は 0）。測定器にも太さを渡し、太さ別のファイル（Arial Bold など）で測る。
- ASS に書くフォントは変換した PC の OS のもの。MKV を別の OS で再生すると代わりのフォントになる。Linux など「その他」は Pillow で開けないので概算になる。

## 処理の流れ

1. **入力の解釈**: `body`、`commands`、`vposMs`、`isPremium`、`postedAt` を読む。型が合わないコメントと `postedAt` が読めないコメントは飛ばして数える。並びは `vpos`、`postedAt`（秒に切り捨てた UNIX 時刻。負は読めないものとして飛ばす）の昇順（niconicomments と同じ）で、それも同じなら入力の順。`invisible` のコメントは配置にも出力にも使わない。
2. **コマンドの解釈**（`parse_commands`）: 小文字にしてから判定する。位置・大きさ・色・フォントは先に出たものが勝ち、`@秒数` は後に出たものが勝つ（niconicomments と同じ）。`#RRGGBB` / `#RGB` は `isPremium` が真のときだけ枠を取る。正規表現に合っても色として不正な値は白。`gulim` / `simsun` はフォントの枠を取り、`defont` として描く。`invisible` と本文が `/` で始まるものは出力しない。未知のコマンドと `nico:` で始まるものは無視する。
3. **大きさと幅**: 上記の文字サイズで行ごとに幅を測り、最大の行幅をコメントの幅にする。
4. **上下固定の縮小**: 幅が上限を超えた `ue` / `shita` は、niconicomments の `_processResizeX` と同じく文字サイズを調整する（調整は最大 20 回）。
5. **配置**（`layout`）: niconicomments の衝突判定を移植する。流れるコメントは左右の判定線（登録は余白 5 を含み、照会は含まない。5 vpos 刻み）と、長さの異なるコメントどうしの軌跡の交差。固定コメントは位置ごとに `long - 20` まで。行が足りないときは `rng` でランダムな位置に置く。乱数を引く回数と順序も niconicomments に合わせ、同じシードなら同じ位置になる。`posY` が負の相手は判定から外す。
6. **ASS の生成**: 1 行を 1 つの `Dialogue` にし（`\N` は使わない）、下の「行の置き方」で位置を決める。流れるコメントは `\move`、固定は `\pos`。

## 行の置き方

キャンバスの単位で、コメントの枠の上端を `top`（`naka` / `ue` は `posY`、`shita` は `1080 - posY - height`）、左端を `left`（固定は `(1920 - width) / 2`、流れるコメントは `naka_x`）とする。`c = 1920 / 683 × font_scale`。

- **ベースライン**: `i` 行目（0 始まり）の文字のベースラインは `top + (line_height × (i + 1) + (char_size - line_height) / 2 - 0.16 × line_height) × c`（niconicomments の `_generateTextImage` は `textBaseline = "alphabetic"` で描き、`paddingTop` は描く位置のずらしと打ち消し合う）。
- **em**: キャンバスの em は `font_px × scale × c`。区間 `r` の `\fs` は `em × k × (ascent_r + descent_r)`。
- **ASS の基準点**: libass は行の上端からその行の最大の `ascent × em` 下にベースラインを置く。`\an7` / `\an8` は行の上端を `ベースライン - em × max(ascent_r)`、`\an2` は行の下端を `ベースライン + em × max(descent_r)` に置く。
- **基準点と横位置**: `ue` は `\an8`、`shita` は `\an2`、流れるコメントは `\an7`。行は niconicomments と同じく枠の中で左揃えなので、固定は `x = left + 行の幅 / 2`（行の幅は `line_widths[i] × c`）、流れるコメントは `x = left`。
- **寸法が無いとき**（`metrics` が `None`）: `FontMetrics(ascent=1.0, descent=0.280625)` とみなす（合計の 1.280625 は #372 の比率 0.09 を `medium` の em で割った値: `0.09 × 1080 / (27 × 1920 / 683)`）。
- **時刻**: 固定は `vpos` から `vpos + long`。流れるコメントは、枠の左端が動画の右端（キャンバスの `(W / k + 1920) / 2`）に来る時刻 `t1` と、枠の右端が動画の左端（`(1920 - W / k) / 2`）に来る時刻 `t2` を `naka_x` から解き、`floor(t1)` から `ceil(t2)` とする（両端で画面の外）。開始が 0 未満なら 0 にする。横位置は丸めた後の時刻で `naka_x` から求め直す。
- **PlayRes への換算**: 上の「座標系」のとおり `((W - 1920k) / 2 + kx, (H - 1080k) / 2 + ky)`。`\bord` などの長さは `k` 倍。数値は小数 2 桁までで書く。

## 色と不透明度

- 色は `&HBBGGRR&`（BGR 順）。縁取りは黒（文字色が `#000000` と完全に一致するときだけ白。`#000` は黒のまま）。
- 不透明度は、設定の `opacity` を全体に掛ける。文字は `opacity`、`_live` では `opacity × 0.5`。縁取りは `opacity × 0.4`、`_live` では `opacity × 0.4 × 0.5`。ASS の alpha は `round(255 × (1 - 不透明度))`。
- 縁取りの太さ `\bord` は、niconicomments の線幅 `2.8 × (1920 / 683) × 文字の縮小率` の半分を `k` で換算した値（線は字の内外に半分ずつ描かれるため）。

## ASS の形

- UTF-8（BOM 付き）。`[Script Info]` に `PlayResX` / `PlayResY`、`WrapStyle: 2`（自動で折り返さない）、`ScaledBorderAndShadow: yes`、`YCbCr Matrix: None`。
- Style は 1 つ（Bold 0、影 0）。フォント、太さ、色、縁取りは各 `Dialogue` のタグで書く。
- 本文の `{` と `}` は全角の `｛` `｝` に、`\` は全角の `＼` に置き換える。行頭と行末の空白はそのまま残すため、半角空白は `\h` にする。

## エラーと書き込み

- 型が合わないコメントは飛ばし、変換は続ける（`skipped`）。
- JSON 全体が読めないときや、それ以外の変換の例外は呼び出し元へ送る。`downloader._convert_nico_comments_to_ass` が警告を出して `danmaku2ass` に切り替える。
- ファイルの書き込みは `downloader` が受け持つ。`{stem}.comments.ass.part` へ書いてから置き換え、中断時の掃除の対象にする。書き込みの `OSError` は警告だけにし、`danmaku2ass` には回さない。
- コメントが 0 件でもヘッダだけの ASS を出す。
- 入力の上限と細かい扱い（niconicomments に合わせたものと、ASS のために決めたもの）: 本文は 16,384 文字・256 行で切る（`HTML5Comment.ts:34-35`、文字数は Python の文字数）、コマンドは先頭 64 個・各 128 文字まで読む（`comment.ts:66-67`）、本文の CR は落とす（ASS の行が壊れるため）、本文の対になっていないサロゲート（JSON の `\udXXX`）は U+FFFD に置き換える（UTF-8 に書けないため）、タイムゾーンの無い `postedAt` は UTC とみなす、空の行と、解像度の都合で終了が開始以前になる行は `Dialogue` を出さない（`skipped` には数えない）、`font_scale_percent` が 0 以下なら `ValueError`。

## 計算量

配置は niconicomments をそのまま移植し、最適化はしていない（実物 1,432 件で 1 秒未満。測定の記録は [タスクメモ](../task/387-nico-ass-converter.md)）。遅くなったら、結果が同じになることをテストで守ったまま最適化する。変換はワーカースレッドで動き、Qt には触れない。

## 対象外

複数行の縮小、`full` / `ender`、コメントアート、2017-07-12 より前の古い描画方式（#388）。投稿者コメントとニコスクリプト、横位置の反転、`nico:` の拡張コマンド。

## ライセンス

移植した式・定数・色表は niconicomments（MIT、`Copyright (c) 2022 xpadev-net`）による。モジュールの冒頭に著作権表示と許諾表示を置く。PyInstaller の配布物ではコメントが残らないため、`scripts/download_binaries.py` の `COMPONENTS` に許諾表示の全文を持たせ、`licenses/THIRD-PARTY-NOTICES.md` に書き出す（[build.md](../build.md#同梱バイナリのライセンスgplmit-対応)）。
