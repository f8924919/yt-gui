# 設定管理

[← 目次](index.md)

> 関連実装: [yt_gui/settings.py](../arch/settings.md)

## 概要

アプリの設定は `Settings` dataclass と `SettingsManager` クラスで管理されます（`settings.py`）。設定は OS 標準の設定ディレクトリに JSON 形式で永続保存されます。

---

## 設定項目

`Settings` dataclass のフィールドと対応する設定ダイアログの項目です。

| フィールド | 型 | デフォルト | 設定ダイアログの項目 |
|---|---|---|---|
| `download_path` | str | `""` | 一般タブ — 保存フォルダ（空欄の場合 `~/Downloads`） |
| `cookies_path` | str | `""` | 一般タブ — Cookies（ファイル指定時） |
| `cookies_browser` | str | `""` | 一般タブ — Cookies（ブラウザ指定時） |
| `language` | str | `"ja"` | 一般タブ — 言語 |
| `video_resolution` | str | `"720"` | 画質・音質タブ — 解像度上限 |
| `video_container` | str | `"mp4"` | 画質・音質タブ — 動画コンテナ |
| `audio_format` | str | `"mp3"` | 画質・音質タブ — 音声形式 |
| `mp3_bitrate` | str | `"192"` | 画質・音質タブ — MP3 ビットレート |
| `output_template_video` | str | `"%(title)s.%(ext)s"` | ファイル名タブ — 単独動画用 OUTPUT TEMPLATE |
| `output_template_playlist` | str | `"%(playlist_title)s/%(playlist_index)03d - %(title)s.%(ext)s"` | ファイル名タブ — プレイリスト用 OUTPUT TEMPLATE |

### Cookies の優先順位

`cookies_browser` が空でない場合はブラウザから取得し、`cookies_path` は無視されます。両方空の場合は Cookies を使用しません。

---

## 保存先パス

| OS | パス |
|---|---|
| Windows | `%APPDATA%\yt-gui\settings.json` |
| macOS | `~/Library/Application Support/yt-gui/settings.json` |
| Linux | `~/.config/yt-gui/settings.json`（XDG_CONFIG_HOME が未設定の場合） |

---

## 読み込みロジック

`SettingsManager.load()` の動作:

1. 設定ファイルが存在しない場合: デフォルト値の `Settings()` を返す
2. JSON の読み込みに失敗した場合: デフォルト値の `Settings()` を返す
3. JSON に未知のキーが含まれる場合: `Settings.__dataclass_fields__` に含まれるキーのみを使用（無視して続行）

---

## 保存ロジック

`SettingsManager.save(settings)` の動作:

1. 設定ディレクトリを作成（存在しない場合）
2. `dataclasses.asdict(settings)` で dict 変換
3. `ensure_ascii=False, indent=2` で JSON として書き込み

---

## 設定変更の反映タイミング

設定ダイアログで「保存」を押すと、以下の処理が行われます。

| 変更内容 | 反映タイミング |
|---|---|
| 保存フォルダ | 次のダウンロードから即座に反映 |
| Cookies | 次のダウンロードから即座に反映 |
| 解像度上限 | 次のキュー追加から反映（既存アイテムには影響しない） |
| 動画コンテナ | 次のキュー追加から反映（既存アイテムには影響しない） |
| 音声形式・ビットレート | 次のキュー追加から反映（既存アイテムには影響しない） |
| OUTPUT TEMPLATE | 次のダウンロードから即座に反映（既存キューアイテムにも適用される） |
| 言語 | 即座に反映（再起動不要） |

既存のキューアイテムは追加時のスナップショット（`audio_codec`・`video_container`・`embed_metadata`・`embed_chapters`）でダウンロードされます。

---

## 起動時のデフォルト Cookies

設定に Cookies が未設定の場合、アプリリソースディレクトリの `cookies.txt` が存在すれば自動的に設定します。これは開発・デバッグ用の便宜的な動作で、ビルド済みバイナリには `cookies.txt` を同梱しません。
