# オリジナル形式パネルでの複数音声トラック対応（フェーズ 1）

[← タスク一覧](index.md)

## 背景

現状、1 ダウンロードあたり 1 音声トラックしか選択できない。YouTube の Multi-Audio 動画やニコニコの多重音声など、複数言語の音声が同一動画に同梱されているケースで「日本語＋英語の両方を含む 1 ファイルが欲しい」というニーズに応えられない。

調査の詳細・代替案・課題は [docs/research/multi-audio-download.md](../research/multi-audio-download.md) を参照。本タスクは同調査のフェーズ 1（動画 + 複数音声を 1 MKV にマージ）のみを対象とする。
音声のみモードでの複数ファイル出力（フェーズ 2 相当）は本タスクには含めず、`fmt_mp3` の簡易モードにも変更を入れない。

## 仕様

### UI 変更（OriginalFormatPanel）

- 既存の音声 `QComboBox` を **multi-select リスト** に置き換える。
  - 字幕リストと同じ `_ToggleListWidget` ベース。ただし排他ルールが追加されるため `_AudioListWidget` として新設する。
  - 既定の選択モードは `ExtendedSelection`（Ctrl/Shift で複数選択）。
- 並び順は従来どおり「自動 (最良を選択) → ダウンロードしない → 取得した音声トラック一覧」。
- リスト高さは字幕リストと揃える（最小 96px、4 行表示目安）。
- パネル全体の `setFixedSize` を使っている場合は最小高さを再計算する（実装時に確認）。

#### 排他ロジック

| 操作 | 動作 |
|---|---|
| 「自動」を選択 | 他の全行（「ダウンロードしない」と各音声 ID）を選択解除 |
| 「ダウンロードしない」を選択 | 「自動」と各音声 ID を選択解除 |
| 音声 ID を選択 | 「自動」「ダウンロードしない」を選択解除 |
| 複合フォーマット（★）の映像選択時 | リスト全体を `setEnabled(False)`（現行の `映像に含まれます` 表示と同等の挙動） |
| 「音声のみ」出力モード時 | 映像コンボは無効化のまま（現行と同じ）。リストは有効、複数選択も可能だが本タスクではフォーマット文字列上 1 トラック扱い（後述） |

#### コンテナの MKV 自動昇格

- 複数音声 ID（2 件以上）が選ばれた状態でキューに追加するときに、**MP4 / WebM 結合が選択されていれば MKV に自動昇格する**。
  - 出力モードラジオの選択値そのものは変更しない（次に単一音声に戻したとき元のラジオ選択が活きる）。
  - キュー追加時のステータスバーに通知メッセージを出す（`status_multi_audio_mkv_promoted` 相当・新規 i18n キー）。
  - 「remux のみ」「音声のみ」モード時は MKV 昇格対象外（remux は元コンテナを尊重、音声のみは本タスク対象外）。
- 設定の動画コンテナ自体は変更しない（あくまでこのアイテム単位での昇格）。

### フォーマット文字列生成

`OriginalFormatPanel.get_format_spec()` の戻り値を以下のように拡張する。

| 映像 | 音声選択数 | 生成される文字列 |
|---|---|---|
| 自動 | 0（自動） | `bestvideo+bestaudio/best` |
| 自動 | 1 | `bestvideo+{aid}` |
| 自動 | 2 以上 | `bestvideo+{aid1}+{aid2}+...` |
| 特定 ID | 0（自動） | `{vid}+bestaudio` |
| 特定 ID | 1 | `{vid}+{aid}` |
| 特定 ID | 2 以上 | `{vid}+{aid1}+{aid2}+...` |
| 複合（★） | — | `{vid}` のみ |
| ダウンロードしない | 1 | `{aid}` |
| ダウンロードしない | 2 以上 | フェーズ 1 では未対応 → 単一トラック相当の警告にせず、`{aid1}+{aid2}+...` を返す（音声多重マージとして MKV に出力） |
| 特定 ID | ダウンロードしない | `{vid}` のみ |

「音声のみ」出力モードはフェーズ 2 のスコープのため、**本タスクでは音声のみモードで複数選択された場合も先頭の 1 件のみを使用**し、それ以外は無視する。UI 上は複数選択を許容するが、ステータス通知で「音声のみモードでは先頭のトラックのみが使用されます」と注意喚起する。

### ダウンローダ（downloader.py）

- `Downloader.download_video()` の `format_spec` に `+` が 2 個以上含まれる場合、`ydl_opts` に以下を追加する。
  - `"allow_multiple_audio_streams": True`
  - `"merge_output_format": "mkv"` を強制（既存の `video_container` 設定よりも優先）
  - サムネイル埋め込み判定の `_THUMBNAIL_EMBED_CONTAINERS` は `mkv` を既に含むため変更不要
- `+` が 0〜1 個（従来パターン）は既存ロジックのまま。
- カンマ構文（`,`）は本タスクでは生成されないため対応不要。

### キュー / 編集モード

- `_QueueItem` の `orig_settings` 内 `audio_id: str | None` を `audio_ids: list[str]` に置き換える。
- `OriginalFormatPanel.get_raw_settings()` / `restore_from_settings()` を `audio_ids` 配列対応に更新。
- `_apply_pending_restore()` は配列内の各 ID に対応する行を順次 `setSelected(True)` する。
- キューアイテムツールチップの「形式仕様」フィールドに、複数音声選択時は連結された format 文字列をそのまま表示する（追加ラベルなし、調査の §7.3 にあった「(+ audio-multistreams)」表記はスコープ外）。

### i18n

- `ja.py` / `en.py` に以下を追加（キー名は実装時に最終決定）。
  - `status_multi_audio_mkv_promoted` — 「複数音声選択のため MKV に切り替えました」相当
  - `status_multi_audio_audio_only_truncated` — 「音声のみモードでは先頭の音声のみが使用されます」相当
- 既存キーで現存する `orig_audio_included` 等は据え置き。

### ドキュメント

- `docs/spec/screens/original-format-panel.md`
  - レイアウト図の音声コンボをリスト表示に書き換え
  - 「音声リスト」節を新設（字幕リストと同様の操作感の記述）
  - 「フォーマット文字列生成ロジック」表に複数音声パターンを追記
  - MKV 自動昇格の挙動を記載
- `docs/spec/features/download-formats.md`
  - 「オリジナル形式」節に複数音声時の format 文字列例（`bestvideo+251+140`）を追記
- `docs/arch/original_format_panel.md`
  - `audio_id` → `audio_ids` の戻り値変更を反映
  - 新クラス `_AudioListWidget` の役割を追記
- `docs/arch/downloader.md`
  - `allow_multiple_audio_streams` 自動付与・MKV 強制の条件を追記
- `CLAUDE.md` の「主要コマンド」セクションに変更はない見込み

### テスト

`tests/` に以下を追加する想定。

- `OriginalFormatPanel.get_format_spec()` の単体テスト
  - 音声選択 0 / 1 / 2 / 3 件のそれぞれで期待文字列が出ること
  - 「自動」と特定 ID が同時選択にならない（排他ロジック）こと
  - 複合フォーマット選択時にリスト全体が無効化されること
- `_AudioListWidget` の選択挙動テスト（モックなしで実 QListWidget を用いる既存パターンを踏襲）
- `Downloader` 側は `+` 2 個以上の format_spec を受けたときに `allow_multiple_audio_streams` と `merge_output_format='mkv'` が `ydl_opts` に入ることを確認するテスト（YoutubeDL を組み立て前の opts dict 比較で検証）

実機での `--audio-multistreams` 動作確認は **YouTube** を主対象とし、ニコニコ動画・Twitch VOD は **動作確認程度** にとどめる（リサーチの §13 参照）。

## 非対応（フェーズ 2 以降）

以下は本タスクでは扱わない。必要になった時点で別タスクを起こす。

- 音声のみモードでの複数音声 → 言語別ファイル出力（カンマ構文 + outtmpl 拡張）
- 「すべての音声を含める」ショートカット（`bv*+mergeall[vcodec=none]`）
- `fmt_mp3` 簡易モードへの複数音声対応
- OUTPUT TEMPLATE 設定タブへの「複数音声時テンプレート」追加

## ステータス

未着手
