# yt_gui/locales/

> 関連仕様: [多言語対応](../spec/i18n.md)

各言語の文字列辞書。`STRINGS: dict[str, str]` を定義する。

## 現行ファイル

| ファイル | 言語 |
|----------|------|
| `ja.py` | 日本語 |
| `en.py` | 英語 |

## テンプレート文字列キー

以下のキーはプレースホルダーを含むテンプレート文字列で、`App._build_format_display()` が値を埋めて表示名を生成する。

| キー | プレースホルダー |
|------|----------------|
| `fmt_720p` | `{resolution}` |
| `fmt_mp3` | `{bitrate}` |
| `fmt_best_mp4` | `{container}` |
| `fmt_flac` | なし（FLAC 選択時に `fmt_mp3` の代わりに使用） |

## コンテキストメニュー項目

`ctx_copy_url`・`ctx_edit_format` など、右クリックメニューのラベルもここに定義する。

## 新言語を追加する手順

1. `yt_gui/locales/xx.py` を作成し `STRINGS: dict[str, str]` を定義する
2. `yt_gui/i18n.py` の `_LANGUAGES` に `"xx": xx.STRINGS` を追加する
3. 全ロケールファイルに `"lang_xx": "表示名"` を追加する
