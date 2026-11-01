# コメント・弾幕の ASS フォントサイズを動画の高さに対する比率で決める

> Issue: [#372](https://github.com/f8924919/yt-gui/issues/372)
> ステータス: 進行中
> ブランチ: `bugfix/372-comment-font-ratio`
> 基点: `6d66c66`

受け入れ条件の正本は Issue。コメント再現度向上の第 1 段階にあたる。

## 進捗

- [ ] C1 種別ごとの基準比率で `-fs` を計算する — 証跡: 未
- [ ] C2 横動画で `-fs` ÷ `-s` の高さが一定になる — 証跡: 未
- [ ] C3 倍率に比例する — 証跡: 未
- [ ] C4 縦動画は `幅 × 9 / 16` を基準にする — 証跡: 未
- [ ] C5 `opts` が空のときの既定動作 — 証跡: 未
- [ ] C6 `get_opts` の `resolution_h` の決まり方 — 証跡: 未
- [ ] C7 倍率指定の UI と ja / en の文言 — 証跡: 未
- [ ] C8 `font_scale_percent` の往復 — 証跡: 未
- [ ] C9 旧 `font_size` を使わない — 証跡: 未
- [ ] C10 実動画の見比べと比率の確定 — 証跡: 未
- [ ] C11 焼きこみ・MKV 統合の回帰 — 証跡: 未
- [ ] C12 原因の 3 点と変異 → red の証跡 — 証跡: 未
- [ ] C13 spec / arch の更新 — 証跡: 未
- [ ] C14 実ダウンロードの解像度を `-s` と `-fs` に使う — 証跡: 未

## 原因

- コード位置: `yt_gui/downloader.py:1007` の `-fs`。
- 構造: `-s`（`downloader.py:1001`）は既定で動画の実解像度に追従するが、`-fs` は `font_size`（既定 32）の固定値。
- 実値: `bin/danmaku2ass.exe` を `-fs 32` で `-s 1920x1080` / `1280x720` / `640x360` に実行し、`Style:` の Fontsize はすべて 32、`PlayResY` だけが 1080 / 720 / 360 になることを確認した（高さに対して 3.0% / 4.4% / 8.9%）。

## 確認した事実

- `danmaku2ass` の `-fs` は float を受け、ASS では整数に丸める。`-fs 12.6` → `Fontsize` 13、`-fs 75.6` → 76（`bin/danmaku2ass.exe` で実行）。ソースは `'\\fs%.0f'`（`bin/pins.json` の固定 ref の `danmaku2ass.py`）。
- `nico_comments` の設定はディスクに保存されない。`yt_gui/*.py` を `orig_settings|raw_settings|json\.(dump|load)|\.write_text|open\(` で検索し、書き込みは `settings.py` の `asdict(settings)` と `app.py` の一時 cookie のみ。

## 訂正ログ

| 日付 | 何を誤って書いたか | 正しくは | どの検査・手順なら捕まえたか |
|---|---|---|---|

## 次にやること（申し送り）

1. テストを先に書く（C1〜C9、C11、C14）。
2. 実装して green にし、変異 → red を取る。
3. ユーザーからニコニコとビリビリの動画 URL を受け取り、C10 の見比べで比率を確定する。

訂正ログ: 0 件
