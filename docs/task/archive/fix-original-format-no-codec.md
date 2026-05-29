# codec 情報を返さない動画でのオリジナル形式取得不具合の修正

## 背景

一部の動画（例: xvideos の `https://www.xvideos.com/video.<id>/...` 形式）で「オリジナルの形式」を選択し「形式の取得」を実行すると、**プレイリストURLからは形式を取得できません** と警告が出てフォーマットを取得できない。同 URL を MP4/MP3 等の他形式でダウンロードする経路は正常に動作する。

## 原因

1. yt-dlp の `XVideosIE` は `_real_extract()` で生成する `formats` に `vcodec` / `acodec` を設定せず、URL と `format_id` だけを格納する（`flv` / `urllow` / `urlhigh` の経路）。
2. `yt_gui/downloader.py:fetch_formats` の分類ロジックは `vcodec == "none"` かつ `acodec == "none"` の format を映像にも音声にも追加せず、結果として返却 `video=[]`, `audio=[]` となる。
3. `yt_gui/original_format_panel.py:_on_fetch_done` は映像/音声が空の場合に `warn_fetch_formats_playlist`（プレイリストURL向け警告）を表示していたため、プレイリストではない URL でも誤ったメッセージが出ていた。

## 修正内容

- **`yt_gui/downloader.py`**: `vcodec` / `acodec` が両方とも `"none"`（未設定）の format を muxed メディアとみなし、映像リストに `has_audio=True` で登録する。コーデック名が無い場合はラベルでコンテナ拡張子を代用。
- **`yt_gui/original_format_panel.py`**: フォーマット取得は成功したが映像/音声 0 件だった場合の警告を、新設の中立メッセージ `warn_fetch_formats_no_formats` に切り替え。プレイリスト向け警告は `_run_fetch` 例外ハンドラ側（メッセージに `playlist` を含むケース）でのみ使用するよう責務を分離。
- **`yt_gui/locales/ja.py` / `yt_gui/locales/en.py`**: `warn_fetch_formats_no_formats` を追加。
- **`docs/arch/downloader.md` / `docs/arch/original_format_panel.md`**: 分類規則と取得結果の分岐表を追記。

## 検証

- `uv run ruff check yt_gui/` — 警告なし。
- `uv run ruff format --check yt_gui/` — 差分なし。
- `uv run mypy yt_gui/` — エラーなし。
- ロジックの単体動作: vcodec/acodec を返さない疑似フォーマット 3 件 + HLS 1 件 + audio-only 1 件のケースで、映像 4 件（codec 不明 3 件は ★ 付き）/ 音声 1 件として分類されることを確認。

## ステータス

完了（2026-05-17）。
