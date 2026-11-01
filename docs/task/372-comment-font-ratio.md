# コメント・弾幕の ASS フォントサイズを動画の高さに対する比率で決める

> Issue: [#372](https://github.com/f8924919/yt-gui/issues/372)
> ステータス: 進行中
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
- [ ] C10 実動画の見比べと比率の確定 — 証跡: 未
- [x] C11 焼きこみ・MKV 統合の回帰 — 証跡: 全テスト 641 passed（`0371bdb`）。ビリビリの実動画でも MKV と焼きこみを生成
- [x] C12 原因の 3 点と変異 → red の証跡 — 証跡: 本メモの「原因」「変異 → red」
- [ ] C13 spec / arch の更新 — 証跡: 未
- [x] C14 実ダウンロードの解像度を `-s` と `-fs` に使う — 証跡: `test_comment_ass_*`・`test_run_download_returns_extract_info_result`、下記の実動画で手動値 1280×720 から `PlayRes` 1920×1080

## 原因

- コード位置: `yt_gui/downloader.py:1007` の `-fs`。
- 構造: `-s`（`downloader.py:1001`）は既定で動画の実解像度に追従するが、`-fs` は `font_size`（既定 32）の固定値。
- 実値: `bin/danmaku2ass.exe` を `-fs 32` で `-s 1920x1080` / `1280x720` / `640x360` に実行し、`Style:` の Fontsize はすべて 32、`PlayResY` だけが 1080 / 720 / 360 になることを確認した（高さに対して 3.0% / 4.4% / 8.9%）。

## 確認した事実

- `danmaku2ass` の `-fs` は float を受け、ASS では整数に丸める。`-fs 12.6` → `Fontsize` 13、`-fs 75.6` → 76（`bin/danmaku2ass.exe` で実行）。ソースは `'\\fs%.0f'`（`bin/pins.json` の固定 ref の `danmaku2ass.py`）。
- `nico_comments` の設定はディスクに保存されない。`yt_gui/*.py` を `orig_settings|raw_settings|json\.(dump|load)|\.write_text|open\(` で検索し、書き込みは `settings.py` の `asdict(settings)` と `app.py` の一時 cookie のみ。

## 変異 → red

基点 `0371bdb`。`tests/test_downloader.py` と `tests/test_original_format_panel.py` を実行し、変異ごとに `git checkout` で戻して `git diff --quiet` を確認した。実装前の red は基点 `6d66c66` で 29 failed。

| 変異 | 結果 | 狙ったテスト |
|---|---|---|
| 基準比率の除去 | 21 failed | `test_comment_font_size_uses_ratio_per_lang` ほか |
| `comments` と `danmaku` の比率の入れ替え | 21 failed | `test_comment_font_size_uses_ratio_per_lang` ほか |
| 縦動画の分岐の除去 | 1 failed | `test_comment_font_size_base_height_by_orientation[1080-1920-42.525]` |
| 縦判定の `>` を `>=` へ | 1 failed | `test_comment_font_size_base_height_by_orientation[1080-1080-75.6]` |
| `get_opts` の `font_scale_percent` の除去 | 2 failed | `test_nico_font_scale_get_opts_replaces_font_size`・`test_nico_font_scale_round_trip` |
| 実ダウンロードの解像度の不使用 | 1 failed | `test_comment_ass_uses_downloaded_resolution_when_auto` |

## 実動画の見比べ（C10・途中）

条件: コミット `0371bdb`、ビリビリ `BV1p5411a7nL`（36 秒）、映像「自動」（`30077+30280`、1920×1080）、倍率 100%、手動値 1280×720、`danmaku2ass` は `bin/pins.json` の ref、Windows。ニコニコは未実施（`sm46647529` はセンシティブ判定でログイン必須のため）。

| 対象 | 値 |
|---|---|
| Web（未ログイン、devicePixelRatio 1.5、動画枠 1354×762） | `--fontSize` 27、漢字 1 文字の幅 27px、高さの 3.54% |
| 焼きこみ `Fontsize` 38（比率 0.035） | 漢字 1 文字の幅 29.6px、高さの 2.74% |
| 焼きこみ `Fontsize` 50 / 100（無地の背景） | 中国語の漢字 39.0 / 77.9px（係数 0.78）、日本語の漢字 37.2 / 74.3px（係数 0.74） |

ASS の `Fontsize` は 1 文字の幅（CSS の `font-size` に相当）の約 1.3 倍にあたる。同じ見た目にする比率の候補はビリビリ 0.045、ニコニコ 0.09。係数はレンダラが選ぶフォントに依存する。ユーザーの目視確認で確定する。

## 訂正ログ

| 日付 | 何を誤って書いたか | 正しくは | どの検査・手順なら捕まえたか |
|---|---|---|---|

## 次にやること（申し送り）

1. ユーザーに比較画像を確認してもらい、基準比率（候補 0.045 / 0.09）を確定する。ニコニコはログイン不要の動画 URL をもらう。
2. 確定値をコード、テスト、spec、arch、Issue に反映する。旧値 0.035 / 0.07 の語で伝播先を洗う。
3. `/verify-gate` から PR へ。

訂正ログ: 0 件
