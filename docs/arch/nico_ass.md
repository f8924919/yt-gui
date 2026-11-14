# yt_gui/nico_ass.py

> 関連仕様: [オリジナル形式パネル — コメント・弾幕グループ](../spec/screens/original-format-panel.md#コメント弾幕グループ)

ニコニコ動画のコメント（yt-dlp が保存する `{stem}.comments.json`）を ASS 字幕に変換する。Web 表示の再現 OSS [niconicomments](https://github.com/xpadev-net/niconicomments)（MIT、参照コミット `899203436285`）の HTML5 描画の式・定数・色表を移植する。ビリビリの弾幕は対象外で、従来どおり `danmaku2ass` を使う（[downloader.md](downloader.md#コメント弾幕の-ass-変換)）。

移植元の値と行番号の正本は [Issue #387](https://github.com/f8924919/yt-gui/issues/387) の表で、ここには書き写さない。コードには定数ごとに移植元のファイルと行を注記する。

## 座標系

計算は niconicomments と同じ 1920 × 1080 のキャンバス（以下「キャンバス」）で行い、最後に ASS の `PlayRes`（動画の解像度）へ換算する。

- 基準の高さ `H0` は [#372](../task/archive/372-comment-font-ratio.md) と同じく、動画の高さ（縦動画は `幅 × 9 / 16`）。
- 換算の倍率は `k = H0 / 1080`。キャンバスを `1920k × 1080k` の舞台として動画の中央に置く。4:3 などで舞台が動画より広いときは、はみ出した部分が映らない。
- 時間はキャンバスの単位（10ms、`vpos`）で計算し、ASS の時刻（1/100 秒）へ換算する。`vpos = floor(vposMs / 10)`。

## 文字サイズと ASS の Fontsize

niconicomments の文字サイズ（キャンバスの px、CSS の `font-size` 相当）は、文字の幅の測定と配置に使う。ASS の `Fontsize` は CSS より文字が小さく描かれるため、[#372](../task/archive/372-comment-font-ratio.md) で確定した比率に合うよう、`Fontsize = CSS の文字サイズ × 換算係数` とする。換算係数は `downloader._COMMENT_FONT_RATIO["comments"]`（0.09）を niconicomments の中サイズの比率（27 / 384）で割った値で、`medium` のとき #372 と同じ `Fontsize` になる。倍率（`font_scale_percent`）は両方に掛ける。

## 処理の流れ

`convert(comments_json, *, width, height, font_scale_percent, platform, measure, rng) -> (ass_text, skipped)`

1. **入力の解釈**: `body`、`commands`、`vposMs`、`isPremium` を読む。型が合わないコメントは飛ばし、件数を `skipped` に数える。並びは `vpos` の昇順で、同じ `vpos` は入力の順を保つ（安定ソート）。
2. **コマンドの解釈**（純関数 `parse_commands`）: 小文字にしてから判定し、位置・大きさ・色・フォントは先に出たものが勝つ。`@秒数` は `long`（秒 × 100、0 以下や数値でないときは既定、上限あり）。`#RRGGBB` / `#RGB` は `isPremium` が真のときだけ。`invisible` と本文が `/` で始まるものは出力しない。未知のコマンドと `nico:` で始まるものは無視する。
3. **大きさと行の高さ**: niconicomments の `charSize`・`lineHeight`・`fontSize` の計算を移植する。改行を含むコメントは行ごとに描き、高さは `lineHeight × (行数 - 1) + charSize`。行数による縮小はしない（#388）。
4. **幅の測定**: `measure(text, font, size) -> float` で行ごとの幅を測り、最大の行幅をコメントの幅にする。
5. **上下固定の縮小**: 幅が上限を超えた `ue` / `shita` は、niconicomments の `_processResizeX` と同じく文字サイズを調整する。
6. **配置**（`layout`）: niconicomments の衝突判定（流れるは左右の判定線、固定は位置ごと）を移植する。行が足りないときは `rng` でランダムな位置に置く。
7. **ASS の生成**: 流れるコメントは `\move`、固定は `\pos`。表示の開始時刻は 0 未満にしない（0 で切った場合は横位置を同じ式で求め直す）。

## 幅の測定

`measure` は差し替えられる関数にする。

- 実行時は `pillow_measurer(platform)`。ASS に指定するフォント名に対応するフォントファイルを OS ごとの候補から探し、Pillow の `ImageFont.truetype(...).getlength()` で測る。同じ文字列・フォント・サイズの結果はキャッシュする。
- フォントが見つからない、または開けないときは `approx_measurer` に戻す（全角 1 文字分、半角 0.5 文字分。全角の判定は `unicodedata.east_asian_width` の `F` / `W`）。
- テストでは決定的な概算の測定器を渡し、Pillow とフォントの有無に依存させない。

## フォントと描画

- フォントは `font_for(font, platform) -> (name, weight)` で引く。`platform` は `sys.platform` を渡す純関数で、Windows / macOS / その他の表を持つ。ASS に書くフォント名は変換した PC の OS のものになる。
- 太さは `\b<weight>` で書く（libass は 100〜900 の太さを受け付ける）。
- 文字の不透明度は `_live` で 0.5。縁取りは黒（文字色が `#000000` のときだけ白）で不透明度 0.4。niconicomments は線を文字の上下に半分ずつ描くので、ASS の `\bord` は線幅の半分を `k` で換算した値にする。
- ASS は `WrapStyle: 2`（自動の折り返しをしない）。本文の `{`、`}`、`\` はエスケープし、改行は `\N` にする。

## エラーの扱い

- 型が合わないコメントは飛ばし、変換は続ける（`skipped`）。
- JSON 全体が読めないときや、それ以外の例外は呼び出し元へ送る。`downloader._convert_nico_comments_to_ass` が警告を出して `danmaku2ass` に切り替える。
- 出力は一時ファイルへ書いてから置き換え、途中まで書かれたファイルを残さない。コメントが 0 件でもヘッダだけの ASS を出す。

## 対象外

複数行の縮小、`full` / `ender`、コメントアート、2017-07-12 より前の古い描画方式（#388）。投稿者コメントとニコスクリプト、横位置の反転、`nico:` の拡張コマンド。

## ライセンス

移植した式・定数・色表は niconicomments（MIT、`Copyright (c) 2022 xpadev-net`）による。モジュールの冒頭に著作権表示と許諾表示を置き、`scripts/download_binaries.py` の `COMPONENTS` に載せて `licenses/THIRD-PARTY-NOTICES.md` に出す（[build.md](../build.md#同梱バイナリのライセンスgplmit-対応)）。
