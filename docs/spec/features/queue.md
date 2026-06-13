# ダウンロードキュー

[← 目次](../index.md)

> 関連実装: [yt_gui/app.py](../../arch/app.md) ・ [yt_gui/queue_controller.py](../../arch/queue_controller.md)

## 概要

yt-gui はダウンロードキューを持ち、URL と形式を複数登録してからまとめて実行できます。各アイテムはキュー項目（`_QueueItem`）として表され、キュー全体の所有・走行・状態遷移は `QueueController` が管理します（実装は [arch/queue_controller.md](../../arch/queue_controller.md)）。

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
| `cookies_path` | str \| None | アイテム固有の cookies.txt パス（ブラウザ拡張連携で付与）。`None` ならグローバル設定の Cookies を使用 |
| `status` | str | `waiting` / `downloading` / `done` / `error` / `editing` / `skipped` |
| `progress` | float | ダウンロード進捗（0〜100）。`downloading` 中に進捗フックで更新され、行のステータス列に表示される |
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

「ダウンロード開始」ボタンで `_worker` スレッドが起動します。**同時ダウンロード数**（設定の[ダウンロードタブ](../screens/settings-dialog.md#ダウンロードタブ) `max_concurrent_downloads`、既定 1）の数だけワーカースレッドを起動し、各ワーカーが `waiting` を取り出して並行に処理します。

```
各 _worker() ループ:
  1. キューをロックして次の "waiting" アイテムを取得（取り出しは排他制御）
  2. 一時停止フラグが立っていれば終了
  3. アイテムを "downloading" に変更
  4. Downloader.download_video() を実行（ワーカーごとに独立した Downloader）
  5. 完了後 "done" / 失敗後 "error" に変更
  6. 次のアイテムへ。waiting が尽きたらワーカー終了
```

- **同時実行数**: 既定 `1` のときは単一ワーカーの逐次実行（従来どおり）。`N>1` のとき最大 N 件が同時に `downloading` になります。
- **取り出しの排他**: `waiting` の取り出しとステータス遷移は `_lock` 下で行うため、同じアイテムが複数ワーカーに二重処理されることはありません。
- **ワーカーごとに独立した Downloader**: 進捗コールバック・中断フラグがアイテム間で混線しないよう、各ワーカーは専用の `Downloader` インスタンスを使います（[arch/queue_controller.md](../../arch/queue_controller.md) / [arch/downloader.md](../../arch/downloader.md)）。
- 実行中でも新しいアイテムをキューに追加できます。ただし `waiting` が尽きて終了したワーカーは再起動しないため、走行中に追加した分は残存ワーカー数で処理されます（「同時に最大 N」の best-effort）。全ワーカーが終了済みなら「ダウンロード開始」で再走行できます。
- **Cookies の解決**: ワーカーはアイテム固有の `cookies_path` があればそれを優先し、無ければグローバル設定（`cookies_path` / `cookies_browser`）にフォールバックします（[ブラウザ拡張連携](browser-extension.md) / [ダウンロード動作 — Cookies](download-behavior.md#cookies)）。

### 行単位の進捗表示

`downloading` 中のアイテムは、キューの**ステータス列**に進捗 %（例: `ダウンロード中 45.2%`）を表示します。進捗フックが `_QueueItem.progress` を更新し、該当行だけを再描画します。同時ダウンロード時も各行が独立して自分の進捗を示します。

ステータスバーのプログレスバーは個別アイテムではなく**キュー全体の進捗**（完了数 / 総数）を示します（[メインウィンドウ — ステータスバー](../screens/main-window.md#ステータスバー)）。「完了」は `done` / `error` / `skipped` の合計、「総数」は `waiting` / `downloading` / `done` / `error` / `skipped` の合計です。

### ステータス

`done`（完了）/ `error`（エラー）のほか、ダウンロードアーカイブ（[ダウンロード動作 — ダウンロードアーカイブ](download-behavior.md#ダウンロードアーカイブ)）が有効で対象が記録済みの場合は `skipped`（スキップ（アーカイブ済み））になります。`skipped` は `error` 化せず、実ダウンロードも記録も行いません。

---

## 一時停止・再開

| 操作 | 動作 |
|---|---|
| 「一時停止」ボタン | `_paused = True` フラグを立て、**進行中の全ダウンロードを即座に中断**する。同時ダウンロード時は走行中の全ワーカーの `Downloader` に中断を要求する。中断されたアイテムは `waiting` に戻り（`error` にはしない）、各 `_worker` スレッドが停止する |
| 「ダウンロード開始」ボタン（再開） | `_paused = False` にリセットして設定の同時ダウンロード数だけ `_worker` スレッドを再起動。`waiting` に戻ったアイテムを含め先頭から再走行する |

### 進行中ダウンロードの中断

「一時停止」を押すと、現在進行中のダウンロードを途中で中断できる。同時ダウンロード時は **in-flight の全アイテム**が対象になる。

- 中断は yt-dlp の `progress_hook` 内で `DownloadCancelled` を投げる**協調的**な仕組み。フラグメント DL 中は概ね即時、メタデータ抽出中やポストプロセス中は当該フェーズ完了後に効く（ベストエフォート）。各ワーカーの `Downloader` は独立した中断フラグを持つため、走行中の全ワーカーに対して個別に中断を要求する。
- 中断されたアイテムのステータスは `error` ではなく **`waiting` に戻り**、再度「ダウンロード開始」で最初からやり直せる。
- 中断時、当該アイテムの**部分ファイル（`.part` / `.ytdl` / 中間フォーマットファイル等）は削除**される。再ダウンロードは先頭からになる。
- 待機中アイテムに対する一時停止（処理中アイテムが無いとき次アイテムへ進まない）は従来どおり。

---

## アイテムの削除

「削除」ボタン、またはキーボードの Delete キーで選択中のアイテムを削除できます。

- `downloading`（ダウンロード中）のアイテムは削除不可
- `editing`（編集中）のアイテムは削除不可
- `waiting`・`done`・`error`・`skipped` のアイテムは削除可能

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

- キュー本体の読み書きはすべて単一のロック（`threading.Lock`）で保護される。同時ダウンロード時は複数ワーカーが同じロックで `waiting` の取り出し・ステータス遷移を直列化するため、二重処理や競合は起きない
- バックグラウンドスレッドから GUI を更新する場合はシグナルを emit し、メインスレッドのスロットで処理する（直接 Qt ウィジェットを操作しない）。具体的なロック名・シグナル一覧は [arch/queue_controller.md](../../arch/queue_controller.md) を参照
