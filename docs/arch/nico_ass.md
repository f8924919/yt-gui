# yt_gui/nico_ass.py

> 関連仕様: [オリジナル形式パネル — コメント・弾幕グループ](../spec/screens/original-format-panel.md#コメント弾幕グループ)

ニコニコ動画のコメント（yt-dlp が保存する `{stem}.comments.json`）を ASS 字幕の文字列に変換する。Web 表示の再現 OSS [niconicomments](https://github.com/xpadev-net/niconicomments)（MIT、参照コミット `899203436285`）の HTML5 描画の式・定数・色表を移植する。ビリビリの弾幕は対象外で、従来どおり `danmaku2ass` を使う（[downloader.md](downloader.md#コメント弾幕の-ass-変換)）。

移植元の値と行番号の正本は [Issue #387](https://github.com/f8924919/yt-gui/issues/387) の表で、ここには書き写さない。コードには定数ごとに移植元のファイルと行を注記する。

## 公開する関数

- `convert(comments_json, *, width, height, font_scale_percent, opacity, platform, measure, rng) -> ConvertResult`: ASS の文字列と、飛ばしたコメントの件数を返す。ファイルの読み書きはしない。
- `font_candidates(font, platform)`: コマンドのフォント（`defont` / `gothic` / `mincho`）と OS から、フォントの候補を返す純関数。
- 測定器の型は `measure(text, font_name, weight, size_px) -> float`（`size_px` は CSS の em。戻り値は送り幅の px）。
- `pillow_measurer(platform)`: 実行時の測定器を返す。Pillow は関数の中で遅延 import し、`ImportError` なら概算の測定器を返す。結果はモジュール単位でキャッシュする。
- `approx_measurer`: 概算の測定器（全角 1 文字分、半角 0.5 文字分。全角は `unicodedata.east_asian_width` の `F` / `W`）。

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
- ASS の `Fontsize` は、描くフォントの `(usWinAscent + usWinDescent) / unitsPerEm` を em に掛けた値にする（libass はこの高さを `Fontsize` として扱う）。これで測った幅と描く幅が一致する。係数はフォントファイルの OS/2 表から読む。フォントが見つからないときは、#372 の比率（`medium` で動画の高さの 0.09）に戻す。
- この換算はニコニコだけで、ビリビリは #372 の `_comment_font_size` のまま。

## フォント

- `font_candidates` は niconicomments の `fonts.ts` の候補列を、文字の範囲ごとの組に直して返す。Windows の `defont` は英字（Latin）を Arial、それ以外を MS PGothic にする。ほかは 1 つのフォントで描く。
- 幅を測るときも ASS に書くときも、同じ分け方を使う。ASS では区間ごとに `{\fn<名前>\fs<サイズ>}` を書く。フォントごとに係数が違う（Arial 1.117、MS PGothic 1.000 など）ので、`\fs` も区間ごとに、その区間のフォントの係数で求める。Style の `Fontsize` は使わない（仮の値）。
- フォント名は英語のファミリー名（`Arial`、`MS PGothic`、`Yu Gothic`、`Yu Mincho`、`Hiragino Sans` など）。フォントファイルは OS ごとの候補のパスから探し、`.ttc` は `getname()` でフェイスを照合して開く（index を決め打ちしない）。
- 太さは `\b<weight>`（Style の Bold は 0）。測定器にも太さを渡し、太さ別のファイル（Arial Bold など）で測る。
- ASS に書くフォントは変換した PC の OS のもの。MKV を別の OS で再生すると代わりのフォントになる。Linux など「その他」は Pillow で開けないので概算になる。

## 処理の流れ

1. **入力の解釈**: `body`、`commands`、`vposMs`、`isPremium`、`postedAt` を読む。型が合わないコメントと `postedAt` が読めないコメントは飛ばして数える。並びは `vpos`、`postedAt` の昇順（niconicomments と同じ）で、それも同じなら入力の順。
2. **コマンドの解釈**（`parse_commands`）: 小文字にしてから判定する。位置・大きさ・色・フォントは先に出たものが勝ち、`@秒数` は後に出たものが勝つ（niconicomments と同じ）。`#RRGGBB` / `#RGB` は `isPremium` が真のときだけ枠を取る。正規表現に合っても色として不正な値は白。`gulim` / `simsun` はフォントの枠を取り、`defont` として描く。`invisible` と本文が `/` で始まるものは出力しない。未知のコマンドと `nico:` で始まるものは無視する。
3. **大きさと幅**: 上記の文字サイズで行ごとに幅を測り、最大の行幅をコメントの幅にする。
4. **上下固定の縮小**: 幅が上限を超えた `ue` / `shita` は、niconicomments の `_processResizeX` と同じく文字サイズを調整する（調整は最大 20 回）。
5. **配置**（`layout`）: niconicomments の衝突判定を移植する。流れるコメントは左右の判定線（登録は余白 5 を含み、照会は含まない。5 vpos 刻み）と、長さの異なるコメントどうしの軌跡の交差。固定コメントは位置ごとに `long - 20` まで。行が足りないときは `rng` でランダムな位置に置く。乱数を引く回数と順序も niconicomments に合わせ、同じシードなら同じ位置になる。`posY` が負の相手は判定から外す。
6. **ASS の生成**: 1 行を 1 つの `Dialogue` にし、各行の縦位置は niconicomments の行の高さとオフセットから求める（`\N` は使わない）。基準点は `ue` が `\an8`（舞台の中央）、`shita` が `\an2`、流れるコメントが `\an7`。行は niconicomments と同じく枠の中で左揃え。流れるコメントは `\move`、固定は `\pos`。表示の時刻を整数に丸めた後、その時刻の横位置を同じ式から求め直す。開始時刻は 0 未満にしない。

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

## 計算量

素直に移植すると、配置は数千件で数秒以上かかる見込み。実物の大きいフィクスチャで所要時間を測り、結果が同じになることをテストで守ったまま最適化する。変換はワーカースレッドで動き、Qt には触れない。

## 対象外

複数行の縮小、`full` / `ender`、コメントアート、2017-07-12 より前の古い描画方式（#388）。投稿者コメントとニコスクリプト、横位置の反転、`nico:` の拡張コマンド。

## ライセンス

移植した式・定数・色表は niconicomments（MIT、`Copyright (c) 2022 xpadev-net`）による。モジュールの冒頭に著作権表示と許諾表示を置く。PyInstaller の配布物ではコメントが残らないため、`scripts/download_binaries.py` の `COMPONENTS` に許諾表示の全文を持たせ、`licenses/THIRD-PARTY-NOTICES.md` に書き出す（[build.md](../build.md#同梱バイナリのライセンスgplmit-対応)）。
