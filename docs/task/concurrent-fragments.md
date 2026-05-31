# 並列フラグメントダウンロード対応

対応 Issue: [#53](https://github.com/f8924919/yt-gui/issues/53)

## 背景

yt-dlp の `--concurrent-fragments`（`-N`）を UI から指定できず、フラグメント分割動画（DASH / HLS）の高速化ができなかった。[機能ギャップ調査メモ](../research/yt-dlp-feature-gap.md) の優先候補 2 位。

## 設計判断

- **配置**: 設定ダイアログに新規「ダウンロード」タブを新設。今後の速度制限・リトライ等（調査メモ §5.5）の受け皿も兼ねる。
- **コントロール**: `QSpinBox`（範囲 1〜16、既定 1）。yt-dlp の `all` 指定は過負荷リスクのため UI からは外す。
- **反映**: プロキシ / OUTPUT TEMPLATE と同類のダウンロード時オプション。`Downloader.concurrent_fragments` 属性として保持し、次のダウンロードから既存キューにも反映（キュー追加時スナップショットには含めない）。
- `N=1` は yt-dlp 既定と同じなので `concurrent_fragment_downloads` opt は渡さない。`_base_ydl_opts` ではなくダウンロード側 `_build_ydl_opts` に置き、メタデータ取得には付与しない。

## 変更ファイル

- `yt_gui/settings.py` — `Settings.concurrent_fragments: int = 1`、`CONCURRENT_FRAGMENTS_MIN/MAX`
- `yt_gui/downloader.py` — `__init__` 引数 + `_build_ydl_opts` で opt 付与
- `yt_gui/settings_dialog.py` — `_build_download_tab` + 保存処理
- `yt_gui/app.py` — Downloader 生成引数 + `_open_settings` での反映
- `yt_gui/locales/ja.py` / `en.py` — `tab_download` / `label_concurrent_fragments` / `concurrent_fragments_note`
- docs: spec/settings・spec/screens/settings-dialog・arch/downloader・arch/settings_dialog・research/yt-dlp-feature-gap
- tests: test_settings・test_downloader

## 検証

- ruff / ruff format / mypy / pytest すべて通過
