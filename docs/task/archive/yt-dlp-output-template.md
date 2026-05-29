# yt-dlpのOUTPUT TEMPLATEへの対応

## 目的
yt-dlpのOUTPUT TEMPLATE機能を用いてダウンロードされるファイルの名前をユーザーが簡単に設定可能とする。
OUTPUT TEMPLATEに関する情報 : [text](https://github.com/yt-dlp/yt-dlp?tab=readme-ov-file#output-template)

## 要望
以下にこの機能に対する要望を記載する。仕様/実装を検討し課題がないか確認してください。
- 設定画面に新しいタブを追加し、新しいタブの中に動画とプレイリストの設定を追加してほしい。
- 設定変更の反映タイミングは画質・音質タブの設定項目と同様にしたい。
- 設定のデフォルト値は現状と同じでよい。
- ユーザーが簡単にOUTPUT TEMPLATEの文字列を作成可能なUIとしたい。

---

## 設計

### 1. データモデル (`yt_gui/settings.py`)

`Settings` dataclass に2フィールド追加:

| フィールド | 型 | デフォルト | 説明 |
|---|---|---|---|
| `output_template_video` | `str` | `"%(title)s.%(ext)s"` | 単独動画用 |
| `output_template_playlist` | `str` | `"%(playlist_title)s/%(playlist_index)03d - %(title)s.%(ext)s"` | プレイリスト用 |

既存ユーザーの `settings.json` には新フィールドが無いが、`load()` が `Settings.__dataclass_fields__` でフィルタリングするため自動的にデフォルト値が適用される（マイグレーション不要）。

### 2. テンプレート関連の共通モジュール (`yt_gui/output_template.py`、新規)

- `TEMPLATE_FIELDS: list[tuple[str, str]]` — `(挿入文字列, i18nキーのサフィックス)`
- `DEFAULT_VIDEO_TEMPLATE`, `DEFAULT_PLAYLIST_TEMPLATE`
- `SAMPLE_INFO: dict[str, Any]` — プレビュー用サンプル
- `render_preview(template: str) -> str | None` — `template % SAMPLE_INFO` で生成。失敗時 None
- `validate_template(template: str) -> str | None` — `%(ext)s` 必須・`%` 構文エラーをチェック。エラー時に i18n キーを返す
- `YTDLP_OUTPUT_TEMPLATE_DOC_URL` — 公式ドキュメントURL

含めるフィールド（C案・ハイブリッド：よく使うものに絞る）:
- `%(title)s` — 動画タイトル
- `%(uploader)s` — 投稿者
- `%(upload_date)s` — 投稿日 (YYYYMMDD)
- `%(playlist_title)s` — プレイリスト名
- `%(playlist_index)s` — プレイリスト内番号（パディング無し）
- `%(playlist_index)03d` — プレイリスト内番号（3桁ゼロ埋め）
- `%(ext)s` — 拡張子（必須）

### 3. Downloader 改修 (`yt_gui/downloader.py`)

- `__init__` に `output_template_video` / `output_template_playlist` 引数を追加（デフォルトは `DEFAULT_*_TEMPLATE`）
- `download_video()` に `is_playlist: bool = False` 引数を追加
- `outtmpl` 生成:
  ```python
  template = self.output_template_playlist if is_playlist else self.output_template_video
  ydl_opts["outtmpl"] = os.path.join(out_dir, template)
  ```
- 衝突回避ロジック（連番付与）は `prepare_filename` の結果をベースにするため、テンプレートがサブフォルダを含んでも動作する
- yt-dlp の outtmpl はテンプレート内のサブフォルダを自動作成するので追加の `os.makedirs` 不要

### 4. App 改修 (`yt_gui/app.py`)（ネイティブ寄せ）

- `_sanitize_folder_name()` と `_INVALID_PATH_CHARS` を削除
- `_QueueItem.playlist_folder: str | None` → `playlist_title: str | None` にリネーム（ツールチップ表示用）
- プレイリスト追加処理:
  - `playlist_folder = _sanitize_folder_name(...)` → `playlist_title = result.get("title", "")` に置換
  - `output_dir_override = os.path.join(download_path, item.playlist_folder)` の処理を削除（テンプレートに任せる）
- `download_video()` 呼び出しに `is_playlist=bool(item.playlist_title)` を渡す
- `_open_settings()` で `downloader.output_template_video` / `output_template_playlist` を反映（画質設定と同じパターン）
- ツールチップ表示は `qi.playlist_title`（生のプレイリスト名）を表示

### 5. SettingsDialog 改修 (`yt_gui/settings_dialog.py`)

新タブ「**ファイル名**」を追加（既存の「一般」「画質・音質」の後）:

```
┌─ ファイル名 ────────────────────────────┐
│ 単独動画:                                │
│   [%(title)s.%(ext)s          ] [挿入▼] │
│   プレビュー: My Video.mp4               │
│                                         │
│ プレイリスト:                            │
│   [%(playlist_title)s/...    ] [挿入▼] │
│   プレビュー: My Playlist/001 - Video.mp4│
│                                         │
│ [デフォルトに戻す]                       │
│                                         │
│ よく使うフィールド:                      │
│   %(title)s         – 動画タイトル       │
│   %(uploader)s      – 投稿者             │
│   ...                                    │
│   [yt-dlp公式ドキュメントを開く]         │
└─────────────────────────────────────────┘
```

UI 部品:
- `QLineEdit` × 2（動画用、プレイリスト用）
- `QToolButton(text="挿入▼")` × 2 — クリックで `QMenu` を表示、選択時に `QLineEdit.insert()` でカーソル位置に挿入
- プレビュー用 `QLabel` × 2 — `QLineEdit.textChanged` シグナルで更新
- 「デフォルトに戻す」`QPushButton` × 1 — 両 `QLineEdit` をデフォルト値にリセット
- フィールド凡例 `QLabel`（複数行）— `TEMPLATE_FIELDS` から生成
- 公式ドキュメントへのリンク `QPushButton`（`QDesktopServices.openUrl` で開く）

ダイアログサイズ: 現状 `480 × 355` から `480 × 480` 程度に拡大（タブ内容が増えるため）。

バリデーション: `_save()` で `validate_template()` を呼び、エラーがあれば `QMessageBox.warning` を表示してダイアログを閉じない。

### 6. i18n 文字列追加 (`yt_gui/locales/ja.py` `en.py`)

- `tab_output_template`
- `label_template_video`, `label_template_playlist`, `label_template_preview`
- `btn_template_insert`, `btn_template_reset`
- `label_template_fields`, `btn_open_ytdlp_docs`
- `tmpl_field_title`, `tmpl_field_uploader`, `tmpl_field_upload_date`, `tmpl_field_playlist_title`, `tmpl_field_playlist_index`, `tmpl_field_playlist_index_padded`, `tmpl_field_ext`
- `warn_template_no_ext`, `warn_template_invalid`

### 7. ドキュメント更新

- `docs/arch/settings.md` — `Settings` 表に2フィールド追加
- `docs/arch/settings_dialog.md` — 「ファイル名」タブの説明追加
- `docs/arch/downloader.md` — `output_template_*` 引数と `is_playlist` 引数追加
- `docs/arch/index.md` — `output_template.py` を追加
- `docs/spec/settings.md` — 設定項目・反映タイミングの表に追加
- `docs/spec/screens/settings-dialog.md` — タブ仕様・ダイアログサイズ更新
- `docs/task/index.md` — このタスクを `完了` に更新

## 修正対象ファイル

| ファイル | 変更内容 |
|---|---|
| `yt_gui/settings.py` | フィールド2件追加 |
| `yt_gui/output_template.py` | 新規作成 |
| `yt_gui/downloader.py` | `output_template_*`・`is_playlist` 対応 |
| `yt_gui/app.py` | `playlist_folder` 撤去・ネイティブテンプレート利用 |
| `yt_gui/settings_dialog.py` | 「ファイル名」タブ追加 |
| `yt_gui/locales/ja.py`, `en.py` | i18n キー追加 |
| `docs/arch/*.md`, `docs/spec/**/*.md` | ドキュメント更新 |
| `docs/task/index.md` | ステータス更新 |

## 検証方法

1. **Lint**: `uv run ruff check yt_gui/` でエラーが無いこと
2. **Format**: `uv run ruff format yt_gui/` でフォーマット適用
3. **型チェック**: `uv run mypy yt_gui/` でエラーが無いこと
4. **手動動作確認** (`uv run python -m yt_gui`):
   - 設定ダイアログを開き「ファイル名」タブが表示されること
   - テンプレートを変更してプレビューが更新されること
   - 挿入ボタンで変数が QLineEdit に挿入されること
   - `%(ext)s` を含まないテンプレートで保存しようとするとエラーが出ること
   - デフォルトに戻すボタンが動作すること
   - 公式ドキュメントを開くボタンがブラウザを起動すること
   - 単独動画をダウンロードして、デフォルト時は `タイトル.mp4` で保存されること
   - プレイリストをダウンロードして、デフォルト時は `プレイリスト名/001 - タイトル.mp4` 形式で保存されること
   - カスタムテンプレート（例: `%(uploader)s/%(title)s.%(ext)s`）で意図通りに保存されること
