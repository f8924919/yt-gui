# コメント・弾幕の ASS フォントサイズを動画の高さに対する比率で決める

> Issue: [#372](https://github.com/f8924919/yt-gui/issues/372)
> ステータス: 完了（2026-11-01）
> ブランチ: `bugfix/372-comment-font-ratio`
> 基点: `6d66c66`

受け入れ条件の正本は Issue。コメント再現度向上の第 1 段階にあたる。

## 進捗

- [x] C1 種別ごとの基準比率で `-fs` を計算する — 証跡: `tests/test_downloader.py::test_comment_font_size_uses_ratio_per_lang`
- [x] C2 横動画で `-fs` ÷ `-s` の高さが一定になる — 証跡: `test_comment_font_size_keeps_ratio_across_resolutions`
- [x] C3 倍率に比例する — 証跡: `test_comment_font_size_is_proportional_to_scale`
- [x] C4 縦動画は `幅 × 9 / 16` を基準にする — 証跡: `test_comment_font_size_base_height_by_orientation`
- [x] C5 `opts` が空のときの既定動作 — 証跡: `test_comment_font_size_defaults_when_opts_empty`
- [x] C6 `get_opts` の `resolution_h` の決まり方 — 証跡: `tests/test_original_format_panel.py::test_nico_get_opts_resolution_h_source`
- [x] C7 倍率指定の UI と ja / en の文言 — 証跡: `test_nico_font_scale_spin_spec`・`_reset_returns_to_default`・`_retranslate_updates_text`
- [x] C8 `font_scale_percent` の往復 — 証跡: `test_nico_font_scale_get_opts_replaces_font_size`・`_round_trip`
- [x] C9 旧 `font_size` を使わない — 証跡: `test_nico_font_scale_restore_ignores_legacy_font_size`・`test_comment_font_size_ignores_legacy_font_size`
- [x] C10 実動画の見比べと比率の確定 — 証跡: 本メモの「実動画の見比べ」。比率と VLC での MKV はユーザーが確認
- [x] C11 焼きこみ・MKV 統合の回帰 — 証跡: 全テスト 641 passed（`3943a5f`）。ビリビリの実動画でも MKV と焼きこみを生成
- [x] C12 原因の 3 点と変異 → red の証跡 — 証跡: 本メモの「原因」「変異 → red」
- [x] C13 spec / arch の更新 — 証跡: `docs/spec/screens/original-format-panel.md`・`docs/arch/downloader.md`・`docs/arch/original_format_panel.md`
- [x] C14 実ダウンロードの解像度を `-s` と `-fs` に使う — 証跡: `test_comment_ass_*`（`-s` と `-fs` を確認）・`test_run_download_returns_extract_info_result`、下記の実動画で手動値 1280×720 から `PlayRes` 1920×1080

## 原因

- コード位置: 基点 `6d66c66` の `yt_gui/downloader.py:1007` の `-fs`。
- 構造: `-s`（同 `:1001`）は既定で動画の実解像度に追従するが、`-fs` は `font_size`（既定 32）の固定値。
- 実値: `bin/danmaku2ass.exe` を `-fs 32` で `-s 1920x1080` / `1280x720` / `640x360` に実行し、`Style:` の Fontsize はすべて 32、`PlayResY` だけが 1080 / 720 / 360 になることを確認した（高さに対して 3.0% / 4.4% / 8.9%）。

## 確認した事実

- `danmaku2ass` の `-fs` は float を受け、ASS では整数に丸める。`-fs 12.6` → `Fontsize` 13、`-fs 75.6` → 76（`bin/danmaku2ass.exe` で実行）。ソースは `'\\fs%.0f'`（`bin/pins.json` の固定 ref の `danmaku2ass.py`）。
- `nico_comments` の設定はディスクに保存されない。`yt_gui/*.py` を `orig_settings|raw_settings|json\.(dump|load)|\.write_text|open\(` で検索し、書き込みは `settings.py` の `asdict(settings)` と `app.py` の一時 cookie のみ。

## 変異 → red

### 実装前の red

`a76b1d8` のテストを基点 `6d66c66` の `yt_gui/` に対して実行し、35 failed、132 passed。FAILED のケース数は次のとおり（最初に書いた時点の実行は基点 `6d66c66` で 29 failed）。実行後に `yt_gui/` を戻し、`git diff --quiet HEAD` を確認した。

| テスト | ケース数 |
|---|---|
| `test_comment_font_size_uses_ratio_per_lang` | 2 |
| `test_comment_font_size_keeps_ratio_across_resolutions` | 8 |
| `test_comment_font_size_is_proportional_to_scale` | 4 |
| `test_comment_font_size_base_height_by_orientation` | 4 |
| `test_comment_font_size_defaults_when_opts_empty` / `_ignores_legacy_font_size` / `_arg_has_no_float_noise` | 各 1 |
| `test_comment_ass_falls_back_when_resolution_unknown` | 5 |
| `test_comment_ass_uses_downloaded_resolution_when_auto` / `_keeps_manual_resolution_when_auto_off` | 各 1 |
| `test_run_download_returns_extract_info_result` | 1 |
| `test_nico_font_scale_spin_spec` / `_get_opts_replaces_font_size` / `_round_trip` / `_restore_ignores_legacy_font_size` / `_reset_returns_to_default` / `_retranslate_updates_text` | 各 1 |

`test_nico_get_opts_resolution_h_source` は既存の挙動を固定するテストなので実装前も green で、下の変異で検出力を確認した。

### 変異

基点 `a76b1d8`。`tests/test_downloader.py` と `tests/test_original_format_panel.py` を実行し、変異ごとに `git checkout` で戻して `git diff --quiet` を確認した。

| 変異 | 結果 | 落ちたテスト |
|---|---|---|
| `:g` を `str` へ | 1 failed | `test_comment_font_size_arg_has_no_float_noise` |
| `auto_resolution` の判定の除去 | 1 failed | `test_comment_ass_keeps_manual_resolution_when_auto_off` |
| `and height` の除去 | 1 failed | `test_comment_ass_falls_back_when_resolution_unknown` |
| `and width` の除去 | 1 failed | `test_comment_ass_falls_back_when_resolution_unknown` |
| `if auto_res` を常に真へ | 1 failed | `test_nico_get_opts_resolution_h_source` |
| `detected` の不使用 | 1 failed | `test_nico_get_opts_resolution_h_source` |
| 基準比率の除去 | 28 failed | `test_comment_font_size_*` の 7 関数と `test_comment_ass_*` の 3 関数（`_uses_ratio_per_lang` を含む） |
| `comments` と `danmaku` の比率の入れ替え | 28 failed | 同上（`_uses_ratio_per_lang` を含む） |
| 縦動画の分岐の除去 | 2 failed | `test_comment_font_size_base_height_by_orientation`・`test_comment_ass_uses_downloaded_resolution_when_auto` |
| 縦判定の `>` を `>=` へ | 1 failed | `test_comment_font_size_base_height_by_orientation` |
| `get_opts` の `font_scale_percent` の除去 | 2 failed | `test_nico_font_scale_get_opts_replaces_font_size`・`test_nico_font_scale_round_trip` |
| 実ダウンロードの解像度の不使用 | 1 failed | `test_comment_ass_uses_downloaded_resolution_when_auto` |

## 実動画の見比べ（C10）

共通の条件: 映像「自動」、倍率 100%、手動値 1280×720、`danmaku2ass` の ref `ced881747670c2eb1c0dbd292c2a567f444b056a`、Windows。Web は未ログイン、devicePixelRatio 1.5、1920×1080 のウィンドウの通常プレイヤーで、Web の再生はビリビリ、ニコニコとも実際の再生解像度（ビリビリ 360p、ニコニコ 540p）。本当の全画面と他の表示倍率は未測定。比較したコミットは `0371bdb`、確定値の確認は `1e31f1c`。

大きさは、高さより安定して測れる漢字の幅（CSS の `font-size` に相当）で比べた。ニコニコの Web はキャンバスから漢字だけを切り出せないので、同じ文全体の幅で代用した。焼きこみの文字幅は、同じ ASS のスタイルで無地の背景へ描いた 10 文字（`测试弹幕大小比例检查`）の幅 ÷ 10 の実測値で、動画のフレーム上の測定ではない。

| 動画 | 比べた時刻 | Web | 焼きこみ |
|---|---|---|---|
| ビリビリ `BV1p5411a7nL`（1920×1080） | 13.96 秒付近 | `--fontSize` 27、漢字の幅 27px、動画枠の高さ 762 の 3.54% | 比率 0.035（`Fontsize` 38）で 29.6px、2.74%。**比率 0.045（`Fontsize` 49）で 38.2px、3.54%** |
| ニコニコ `sm31143779`（960×540） | 2.8 秒付近 | 「中国国営放送も堕ちたな」の幅が高さの 74.1%（キャンバス 569 / 768） | 同じ文で比率 0.07 が 53.1%、0.09 が 68.5%、0.10 が 75.6% |

- 無地の背景の `Fontsize` 50 / 100 で、中国語の漢字は幅 39.0 / 77.9px（係数 0.78）、日本語の漢字は 37.2 / 74.3px（係数 0.74）。
- ニコニコで Web に合う比率は、比較画像からの概算で `INMU-KING` が約 0.08、`再生数が81000おめでとナス！` が約 0.087、上の実測文が約 0.098。文字の種類でフォントが異なるため一律には揃わない。
- **確定値: ニコニコ 0.09、ビリビリ 0.045**（ユーザーの目視確認、2026-11-01）。
- `1e31f1c` の確認: 手動値 1280×720 のビリビリで `PlayRes` 1920×1080、`Fontsize` 49。MKV から取り出した字幕は `Fontsize` 49、Dialogue 360 件で ASS と一致。
- MKV: ユーザーが VLC でビリビリの MKV を再生し、コメントの表示と流れを確認した。`kksk` の幅は画面幅の Web 約 4.6%、VLC 約 4.5%（スクリーンショットからの目測）。
- `big` / `small`: ニコニコの確定値の焼きこみフレームで、`AK-クラス:世界終焉シナリオ進行中`（`s70`）と `諸君、我々は失敗した。`（`s31`）が通常（49）より大きく、または小さく表示されることを確認した。
- 混雑区間: ニコニコの同時表示が最大の時刻の焼きこみフレームで確認した。コメントは画面の上半分に集まって重なる。Web も重なるが、同じ重なり方にはならない。
- 縁取り: 同じフレームで文字の縁取りを確認した。Web より細い。
- 手動値（自動使用 OFF、または解像度を取得できないとき）の実測（無地の背景、`测试弹幕大小比例检查`、コミット `0b03dce`、`ffmpeg version N-124633-gc79dfd29e6-20260525 Copyright (c) 2`、弾幕 XML の sha256 `821d54b0963a`、`danmaku2ass.exe` の sha256 `7c1884388e7b`）: 基準は PlayRes 1920×1080、`-fs` 48.6 を 1920×1080 へ描いた 1 文字の幅 38.2px、字形の縦 35px（幅 ÷ 縦 1.09）。PlayRes 1280×720、`-fs` 32.4 を 1920×1080 へ描くと 37.5px、34px（1.10）で、高さの 3.47%（`Fontsize` の丸めの差のみ）。同じ ASS を 1080×1920 へ描くと 52.9px、59px（0.90）で歪む。spec と arch の「縦横比が異なる場合を除く」はこの結果による。
- サイズ以外の差（後続）: Web のほうが流れが速く見える、Web は太字、行の配置が違う。ビリビリの取得データの不足は [#373](https://github.com/f8924919/yt-gui/issues/373) で扱う。

## 評価ゲートの巡回

| 巡 | 区分 | 指摘（`path:line` は当時） | 閉じ方 | 証跡 |
|---|---|---|---|---|
| 1 | 欠陥 D1 | `tests/test_downloader.py:1723` の `-fs` 整形のテストが確定値の入力で無効 | コード修正 | `a76b1d8`、変異 `:g` を `str` へ |
| 1 | 欠陥 D2 | `test_comment_ass_*` の 2 関数と `test_nico_get_opts_resolution_h_source` に red の証跡なし | 証跡の再取得 | 本メモの変異の表 |
| 1 | 欠陥 D3 | C10 の MKV、混雑、縁取り、`big` / `small` の確認なし | 証跡の再取得 | 本メモの「実動画の見比べ」 |
| 1 | 欠陥 D4 | C14 のテストが `-s` / `-fs` を見ていない | コード修正 | `a76b1d8` |
| 1 | 証跡 S1 | C10 の記録項目の不足（ref、時刻、確定値の比率） | 証跡の再取得・条件改訂 | `73151fb`、Issue #372 の C10 |
| 1 | 証跡 S2 | 残作業の記述が実態より少ない | 文言修正 | `73151fb` |
| 1 | 証跡 S3 | 実装前の red と変異の粒度不足 | 証跡の再取得 | `73151fb` |
| 1 | 証跡 S4 | メモの限定句の不足 | 文言修正 | `73151fb` |
| 1 | 証跡 S5 | 解像度の主張の強さが spec と arch で違う | 文言修正 | `a76b1d8` |
| 1 | 証跡 S6 | 行番号の基点と `_run_download` の戻り値の説明なし | 文言修正 | `73151fb` |
| 2 | 欠陥 D-A | `yt_gui/locales/ja.py:150`・`en.py:150` のツールチップが限定なしで比率の維持を断定 | コード修正 | `0b03dce` で断定をやめ、`3943a5f` で 2 文目を削除 |
| 2 | 証跡 S-A | ニコニコの値が漢字の幅でなく文全体の幅 | 文言修正・条件改訂 | 本メモの注記、Issue #372 の C10 |
| 2 | 証跡 S-B | ビリビリの焼きこみの値が実測か不明 | 文言修正 | 本メモの注記（無地の背景の実測） |
| 2 | 証跡 S-C | フォールバック時の拡大縮小が未確認のまま spec で断定 | 証跡の再取得 | 本メモの手動値の実測、`docs/arch/downloader.md` |
| 2 | 証跡 S-D | 巡回表が無く、evaluator の指摘が訂正ログに載っている | 文言修正 | 本表へ移し、訂正ログを 0 件へ |
| 3 | 欠陥 | `yt_gui/locales/ja.py:150`・`en.py:150` の「動画の解像度に合わせて計算」が手動値の経路で誤り | コード修正 | `3943a5f` |
| 3 | 欠陥 | `docs/spec/screens/original-format-panel.md:154` の除外句が自動使用 OFF を含まない。整数化の差も arch とずれ | 文言修正 | spec、arch、本メモ、Issue #372 の前提 |
| 3 | 証跡 | 巡回表の D-A の証跡にコミットが無い | 文言修正 | 本表 |
| 3 | 証跡 | フォールバックの実測にメタ行と基準値が無い | 証跡の再取得 | 本メモの手動値の実測 |
| 4 | 証跡 | Issue の前提に整数化の差が無い | 文言修正 | Issue #372 の前提 |
| 4 | 証跡 | 「手動値」の語が実際の経路より広い | 文言修正 | `docs/arch/downloader.md`、Issue #372 の前提 |
| 4 | 証跡 | 巡回表の証跡列のコミットとラベル | 文言修正 | 本表 |
| 4 | 証跡 | C11 の証跡の hash が古い | 証跡の再取得 | `3943a5f` で 641 passed |

## 訂正ログ

| 日付 | 何を誤って書いたか | 正しくは | どの検査・手順なら捕まえたか |
|---|---|---|---|

## 次にやること（申し送り）

完了。evaluator は 4 巡目で PASS（欠陥 0 件）。ビリビリの取得データの不足は [#373](https://github.com/f8924919/yt-gui/issues/373) へ。ASS 変換の自作は未起票。

訂正ログ: 0 件
