# 速度制限（--limit-rate）対応

対応 Issue: [#64](https://github.com/f8924919/yt-gui/issues/64) / PR: [#65](https://github.com/f8924919/yt-gui/pull/65)

## 背景

yt-dlp の `--limit-rate`（Python API の `ratelimit`、bytes/sec）が UI から到達できなかった。[機能ギャップ調査メモ](../research/yt-dlp-feature-gap.md) §4 の未対応項目。回線を専有しないよう帯域を絞りたいユーザー向け。

## 設計判断

- **配置**: 並列フラグメント数と同じ「ダウンロード」タブに行を追加。
- **コントロール**: 値の `QDoubleSpinBox`（範囲 0〜`RATE_LIMIT_VALUE_MAX`、既定 0）+ 単位の `QComboBox`（`KB/s` / `MB/s`）。`0` で無制限。
- **単位**: yt-dlp / `--limit-rate` と同じ 2 進接頭辞（`K` = 1024、`M` = 1024×1024 bytes/sec）。
- **永続化**: `Settings.rate_limit_value: float = 0.0` と `rate_limit_unit: str = "M"`。`build_rate_limit(settings) -> float` で bytes/sec を組み立てる（`build_proxy_url` と同様の純粋関数）。値が 0 以下なら 0（無制限）を返す。
- **反映**: `Downloader.rate_limit`（bytes/sec, 既定 0）を保持し、`_build_ydl_opts` で `> 0` のときだけ `ydl_opts["ratelimit"]` を渡す。`_base_ydl_opts` ではなくダウンロード側に置き、メタデータ取得には付与しない（concurrent_fragments と同方針）。保存時に即時反映し次のダウンロードから有効。

## 変更ファイル

- `yt_gui/settings.py` — `Settings.rate_limit_value` / `rate_limit_unit`、`RATE_LIMIT_UNITS` / `RATE_LIMIT_VALUE_MAX`、`build_rate_limit()`
- `yt_gui/downloader.py` — `__init__` 引数 `rate_limit` + `_build_ydl_opts` で opt 付与
- `yt_gui/settings_dialog.py` — `_build_download_tab` に行追加 + 保存処理
- `yt_gui/app.py` — Downloader 生成引数 + `_open_settings` での反映
- `yt_gui/locales/ja.py` / `en.py` — `label_rate_limit` / `rate_limit_note` / `rate_limit_unit_kb` / `rate_limit_unit_mb`
- docs: spec/settings・spec/screens/settings-dialog・arch/settings・arch/downloader・arch/settings_dialog・research/yt-dlp-feature-gap
- tests: test_settings・test_downloader

## 検証

- ruff / ruff format / mypy / pytest すべて通過
