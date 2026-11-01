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
- [ ] C10 実動画の見比べと比率の確定 — 証跡: 本メモの「実動画の見比べ」。比率はユーザー確認済み、MKV のプレイヤー確認のみ未
- [x] C11 焼きこみ・MKV 統合の回帰 — 証跡: 全テスト 641 passed（`1e31f1c`）。ビリビリの実動画でも MKV と焼きこみを生成
- [x] C12 原因の 3 点と変異 → red の証跡 — 証跡: 本メモの「原因」「変異 → red」
- [x] C13 spec / arch の更新 — 証跡: `docs/spec/screens/original-format-panel.md`・`docs/arch/downloader.md`・`docs/arch/original_format_panel.md`
- [x] C14 実ダウンロードの解像度を `-s` と `-fs` に使う — 証跡: `test_comment_ass_*`・`test_run_download_returns_extract_info_result`、下記の実動画で手動値 1280×720 から `PlayRes` 1920×1080

## 原因

- コード位置: `yt_gui/downloader.py:1007` の `-fs`。
- 構造: `-s`（`downloader.py:1001`）は既定で動画の実解像度に追従するが、`-fs` は `font_size`（既定 32）の固定値。
- 実値: `bin/danmaku2ass.exe` を `-fs 32` で `-s 1920x1080` / `1280x720` / `640x360` に実行し、`Style:` の Fontsize はすべて 32、`PlayResY` だけが 1080 / 720 / 360 になることを確認した（高さに対して 3.0% / 4.4% / 8.9%）。

## 確認した事実

- `danmaku2ass` の `-fs` は float を受け、ASS では整数に丸める。`-fs 12.6` → `Fontsize` 13、`-fs 75.6` → 76（`bin/danmaku2ass.exe` で実行）。ソースは `'\\fs%.0f'`（`bin/pins.json` の固定 ref の `danmaku2ass.py`）。
- `nico_comments` の設定はディスクに保存されない。`yt_gui/*.py` を `orig_settings|raw_settings|json\.(dump|load)|\.write_text|open\(` で検索し、書き込みは `settings.py` の `asdict(settings)` と `app.py` の一時 cookie のみ。

## 変異 → red

基点 `1e31f1c`（確定値）。`tests/test_downloader.py` と `tests/test_original_format_panel.py` を実行し、変異ごとに `git checkout` で戻して `git diff --quiet` を確認した。実装前の red は基点 `6d66c66` で 29 failed。

| 変異 | 結果 | 狙ったテスト |
|---|---|---|
| 基準比率の除去 | 21 failed | `test_comment_font_size_uses_ratio_per_lang` ほか |
| `comments` と `danmaku` の比率の入れ替え | 21 failed | `test_comment_font_size_uses_ratio_per_lang` ほか |
| 縦動画の分岐の除去 | 1 failed | `test_comment_font_size_base_height_by_orientation[1080-1920-54.675]` |
| 縦判定の `>` を `>=` へ | 1 failed | `test_comment_font_size_base_height_by_orientation[1080-1080-97.2]` |
| `get_opts` の `font_scale_percent` の除去 | 2 failed | `test_nico_font_scale_get_opts_replaces_font_size`・`test_nico_font_scale_round_trip` |
| 実ダウンロードの解像度の不使用 | 1 failed | `test_comment_ass_uses_downloaded_resolution_when_auto` |

## 実動画の見比べ（C10）

共通の条件: 映像「自動」、倍率 100%、手動値 1280×720、`danmaku2ass` は `bin/pins.json` の ref、Windows。Web は未ログイン、devicePixelRatio 1.5、1920×1080 のウィンドウの通常プレイヤー。比較したコミットは `0371bdb`、確定値の確認は `1e31f1c`。

| 動画 | 解像度 | Web | 焼きこみ |
|---|---|---|---|
| ビリビリ `BV1p5411a7nL` | 1920×1080 | `--fontSize` 27、漢字の幅 27px、動画枠の高さ 762 の 3.54% | `Fontsize` 38 で漢字の幅 29.6px、高さの 2.74% |
| ニコニコ `sm31143779` | 960×540 | 「中国国営放送も堕ちたな」の幅が高さの 74.1%（キャンバス 569 / 768） | 同じ文で比率 0.07 が 53.1%、0.09 が 68.5%、0.10 が 75.6% |

- 無地の背景の `Fontsize` 50 / 100 で、中国語の漢字は幅 39.0 / 77.9px（係数 0.78）、日本語の漢字は 37.2 / 74.3px（係数 0.74）。
- ニコニコで Web に合う比率は、比較画像からの概算で `INMU-KING` が約 0.08、`再生数が81000おめでとナス！` が約 0.087、上の実測文が約 0.098。
- **確定値: ニコニコ 0.09、ビリビリ 0.045**（ユーザーの目視確認、2026-11-01）。
- `1e31f1c` の確認: 手動値 1280×720 のビリビリで `PlayRes` 1920×1080、`Fontsize` 49。ニコニコの ASS で通常 49 に対し `big` 70、`small` 31。MKV から取り出した字幕は `Fontsize` 49、Dialogue 360 件で ASS と一致。
- サイズ以外の差（段階 2 以降）: Web のほうが流れが速く見える、Web は太字、行の配置が違う。ビリビリの Web にある巨大なオレンジの文字は弾幕 XML に無い（XML は mode 1 / 4 / 5 の 360 件のみ）。

## 訂正ログ

| 日付 | 何を誤って書いたか | 正しくは | どの検査・手順なら捕まえたか |
|---|---|---|---|

## 次にやること（申し送り）

1. ユーザーに MKV をプレイヤーで確認してもらう（C10 の残り）。
2. `/verify-gate` から PR へ。完了時に archive へ移す。

訂正ログ: 0 件
