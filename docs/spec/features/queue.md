# ダウンロードキュー

[← 目次](../index.md)

## 概要

yt-gui はダウンロードキューを持ち、URL と形式を複数登録してからまとめて実行できます。`_QueueItem` dataclass がキューの各アイテムを表し、`App` が `_queue_items: list[_QueueItem]` でキュー全体を管理します。

---

## キューアイテムの構造

| フィールド | 型 | 説明 |
|---|---|---|
| `url` | str | ダウンロード対象の URL |
| `format_id` | str | 形式の内部キー（例: `fmt_720p`） |
| `format_label` | str | 形式の表示名（キューの「形式」列に表示） |
| `format_spec` | str \| None | yt-dlp フォーマット文字列（`fmt_720p` / `fmt_original` で使用） |
| `subtitle_opts` | dict \| None | 字幕オプション（オリジナル形式のみ） |
| `title` | str | 動画タイトル |
| `mp3_bitrate` | str \| None | MP3 ビットレート（MP3 形式のみ） |
| `embed_thumbnail` | bool | サムネイル埋め込み |
| `embed_metadata` | bool | メタデータ埋め込み（デフォルト: True） |
| `embed_chapters` | bool | チャプター埋め込み（デフォルト: True） |
| `audio_codec` | str | 音声コーデック（`"mp3"` / `"flac"`） |
| `video_container` | str | 映像コンテナ（`"mp4"` / `"mkv"` / `"webm"`） |
| `orig_settings` | dict \| None | オリジナル形式の詳細設定スナップショット（編集モード復元用） |
| `remux_only` | bool | remux のみフラグ |
| `playlist_folder` | str \| None | プレイリスト用サブフォルダ名 |
| `thumbnail_url` | str \| None | サムネイル画像の URL |
| `status` | str | `waiting` / `downloading` / `done` / `error` / `editing` |
| `tree_item` | QTreeWidgetItem \| None | 対応するツリーウィジェットの行 |

---

## キューへの追加フロー

### 単独 URL

1. 「追加」ボタンをクリック
2. バックグラウンドスレッドで `Downloader.fetch_title_or_entries()` を呼び出す（「取得中...」を表示してボタン無効化）
3. タイトル・サムネイル URL を取得
4. `_QueueItem` を生成してキューに追加、ツリーウィジェットに行を追加
5. URL 入力欄をクリア
6. サムネイルを別スレッドで非同期取得してキャッシュ

### プレイリスト URL

1. 上記 1〜3 と同様
2. `fetch_title_or_entries()` が `type: 'playlist'` を返した場合
3. 「オリジナルの形式」が選択されていた場合は警告を表示して中断（プレイリストは非対応）
4. プレイリストの全エントリを `_QueueItem` として一括生成
5. プレイリスト名をサニタイズ（無効文字を `_` 置換・100 文字截断）して `playlist_folder` に設定
6. 各アイテムのサムネイルを非同期取得

### オリジナル形式（フォーマット取得済みの場合）

フォーマット取得が完了している場合は `fetch_title_or_entries()` を呼び出さず、すでに取得したタイトルで即時エンキュー。

---

## 設定のスナップショット

キューに追加された時点の `audio_codec`・`video_container`・`embed_metadata`・`embed_chapters`・`orig_settings` が `_QueueItem` に保存されます。設定ダイアログで設定を変更しても、既存のキューアイテムは**追加時の設定**でダウンロードされます。

---

## キューの実行

「ダウンロード開始」ボタンで `_worker` スレッドが起動します。

```
_worker() ループ:
  1. キューをロックして次の "waiting" アイテムを取得
  2. 一時停止フラグが立っていれば終了
  3. アイテムを "downloading" に変更
  4. Downloader.download_video() を実行
  5. 完了後 "done" / 失敗後 "error" に変更
  6. 次のアイテムへ
```

実行中でも新しいアイテムをキューに追加できます（追加されたアイテムは次のループで処理されます）。

---

## 一時停止・再開

| 操作 | 動作 |
|---|---|
| 「一時停止」ボタン | `_paused = True` フラグを立てる。現在処理中のアイテムは最後まで完了してから停止 |
| 「ダウンロード開始」ボタン（再開） | `_paused = False` にリセットして `_worker` スレッドを再起動 |

---

## アイテムの削除

「削除」ボタン、またはキーボードの Delete キーで選択中のアイテムを削除できます。

- `downloading`（ダウンロード中）のアイテムは削除不可
- `editing`（編集中）のアイテムは削除不可
- `waiting`・`done`・`error` のアイテムは削除可能

---

## 編集モード

待機中のキューアイテムを右クリック→「形式を変更...」で編集モードに移行します。

### 編集モードの開始

1. 選択アイテムのステータスを `"editing"` に変更
2. URL 入力欄を読み取り専用にしてアイテムの URL を表示
3. 形式コンボを現在の形式に設定
4. 「追加」ボタンを「変更」に変更、「キャンセル」ボタンを表示
5. ダウンロード開始ボタンを無効化
6. オリジナル形式の場合: `_original_panel.restore_from_settings()` で設定を復元してフォーマット再取得を開始

### 複数アイテムの編集

- 複数アイテムを選択して編集モードに入れます
- 「オリジナルの形式」は複数選択時はグレーアウトして選択不可
- URL 入力欄には `{count} 件を選択中` と表示

### 変更の適用（「変更」ボタン）

選択中の形式・各種オプションを全編集アイテムに一括適用し、ステータスを `"waiting"` に戻します。

### 編集のキャンセル（「キャンセル」ボタン）

ステータスを `"editing"` から `"waiting"` に戻し、編集モードを終了します。

---

## ツールチップ

→ [メインウィンドウ — ツールチップ](../screens/main-window.md#ツールチップ) を参照

---

## スレッド安全性

- `_queue_items` の読み書きはすべて `_queue_lock`（`threading.Lock`）で保護
- バックグラウンドスレッドから GUI を更新する場合は `_AppSignals` のシグナルを emit し、メインスレッドのスロットで処理（直接 Qt ウィジェットを操作しない）
