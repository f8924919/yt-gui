# ライブ配信を最初から / 配信待ち 機能 調査メモ

[← 目次](index.md)

> ステータス: **調査・設計検討段階**（未起票・未実装）。
> 関連: [yt-dlp CLI 機能ギャップ調査メモ](yt-dlp-feature-gap.md)（§4 で「未対応」として列挙）。

「ライブ配信を最初から（`--live-from-start`）」「配信待ち（`--wait-for-video`）」を yt-gui に追加する場合の
仕様案と、実装上の課題を洗い出す。本メモは設計経緯の記録であり、採否・スコープ確定後に正式版
（`docs/spec/` / `docs/arch/`）へ転記する。

---

## 1. 機能の正体（yt-dlp 裏取り済み）

検証環境: yt-dlp `2026.03.17`（`YoutubeDL` の Python API パラメータとして確認）。

| 機能 | yt-dlp オプション | パラメータ | 型 | 制約 |
|---|---|---|---|---|
| **最初から** | `--live-from-start` | `live_from_start` | `bool` | **実験的・YouTube / Twitch / TVer のみ**。進行中ライブを現在地点ではなく配信開始時点から取得 |
| **配信待ち** | `--wait-for-video` | `wait_for_video` | `tuple[int, int]`（秒） | 予定（upcoming）配信が始まるまでリトライ待機。リトライ間隔の最小〜最大秒。`min` のみ指定時は `(min, min)` 相当 |

- `--no-live-from-start` / `--no-wait-for-video` が既定。**未指定なら従来挙動**で、純粋なオプトイン機能。
- yt-dlp の help 原文:
  - `live_from_start`: "Download livestreams from the start. Currently experimental and only supported for YouTube, Twitch, and TVer"
  - `wait_for_video`: "Wait for scheduled streams to become available. Pass the minimum number of seconds (or range) to wait between retries"

---

## 2. 設計方針（既存パターンへの接続）

区間ダウンロード（`section_*`）と**同一構造**で載せられる。これが最小コストかつ既存実装と一貫する。

- **per-item / 形式非依存**: 「この URL がライブか」はアイテム固有の属性。設定（全 DL 共通）ではなく
  [`JobSpec`](../arch/job_spec.md) に持たせる。
- **`JobSpec` へ追加**: `live_from_start: bool` / `wait_for_video: tuple[int, int] | None`。
  [job_spec.md](../arch/job_spec.md) の `section_*` と同じく `build_job_spec` 末尾で `dataclasses.replace`
  により全 `format_id` の `JobSpec` へ透過する。
- **`_build_ydl_opts` で付与**: 値があるときだけ opt を渡す（`concurrent_fragments` / `ratelimit` と同じ流儀。
  `_base_ydl_opts` には置かない＝メタデータ取得 `fetch_*` には効かせない）。[downloader.md](../arch/downloader.md) 参照。
- **UI**: [メインウィンドウ](../spec/screens/main-window.md) に区間 UI と並ぶチェックボックス。
  `wait_for_video` のリトライ間隔は設定「ダウンロード」タブにグローバルなデフォルト値を置き、per-item は
  ON/OFF のみとするのが落とし所。
- **テスト**: `_build_ydl_opts` は純関数なので [`tests/test_downloader.py`](../testing/index.md) の表テストにケース追加で固定化できる。
  `build_job_spec` の透過は [`tests/test_job_spec.py`](../arch/job_spec.md#テスト) に追加。

---

## 3. 課題（難所順）

### 🔴 課題1: 「配信待ち」中はキャンセル（一時停止）が効かない ← 最重要

[downloader.md の中断仕様](../arch/downloader.md#ダウンロードの中断)のとおり、**唯一の協調的キャンセルポイントは
`progress_hook`**（`_progress_hook` 先頭で `DownloadCancelled` を投げる）。ところが `wait_for_video` の待機は
yt-dlp 内部の sleep ループで **ダウンロード開始前**＝`progress_hook` が一切発火しない。

→ 「一時停止」を押してもワーカースレッドが待機 sleep に張り付き、`QueueController.pause()` の
`request_cancel()` が次の hook まで届かない。予定配信が数時間後なら、その間ずっとアプリが見かけ上ハングしたように見える。

**対策候補:**

- **(A) ベストエフォートと割り切り**: 「メタデータ抽出中と同様、待機中はキャンセルが遅延する」と仕様明記。
  実装コスト最小だが UX が悪い。
- **(B) 自前ポーリング**: yt-dlp の待機を使わず、短い `wait_for_video` 上限でリトライしつつ各リトライ境界で
  `_cancel_requested` を確認する。実装重いが待機中も中断できる。
- **(C) 開始検知**: 定期 `extract_info(download=False)` で「開始したか」を自前判定し、開始後に
  `live_from_start` で DL 開始。最も制御しやすいが既存フローから外れる。

→ **推奨は (A) で初版を出し、不満が出たら (B)**。ただしハングに見えないよう、待機中はステータスバー／
キュー行に「配信開始待ち…」表示（課題6）を必ず入れる。**※初版での扱いはユーザー保留中。**

### 🟡 課題2: `_resolve_unique_path` のドライラン抽出が upcoming で不安定

DL 前に [`_resolve_unique_path`](../arch/downloader.md) が `extract_info(download=False)` を呼んでファイル名と
`final_ext` を予測する。予定配信は**フォーマット未確定**のことがあり、`prepare_filename` の拡張子予測が外れる／
例外になる可能性がある。`extract_info(download=False)` は待機しないため、待機前の状態で評価される点にも注意。

→ ライブ系オプション有効時は ext 予測フォールバック（`merge_output_format` ベース）を用意するか、
衝突回避をベストエフォート化する検討が必要。

### 🟡 課題3: 一時停止 → 再開で「最初から」が失われる

中断時 [`_cleanup_partial_files`](../arch/downloader.md#部分ファイル字幕の削除-_cleanup_partial_files) が `.part`
を削除し、再 DL は先頭からやり直す設計。ライブで `live_from_start` 取得を中断すると部分ファイルが消え、
再開時には配信が進んでおり**「最初から」が取得不能**（YouTube のライブ巻き戻しウィンドウを超過）になりうる。

→ ライブ取得アイテムは「中断＝先頭から再取得」が成立しないことを仕様明記。`.part` を残す例外運用は影響範囲が
広いので初版では非対応が無難。

### 🟢 課題4: 進捗・ETA が出ない

ライブは `total_bytes` 不明 → [`_progress_hook`](../arch/downloader.md) の `else` 分岐で「処理中」表示・進捗 0%。
既存ロジックで破綻はしないが、プログレスバーは無意味。仕様注記レベル。

### 🟢 課題5: 区間ダウンロードとの排他

区間 DL は「フル取得後ローカル切り出し」。ライブ進行中は終端未確定で区間指定は無意味。

→ ライブ系オプションと区間 UI は**相互排他**（片方 ON で他方をグレーアウト）にする。

### 🟢 課題6: 待機・ライブ状態の可視化（新ステータス検討）

キューは `waiting / downloading / done / error / editing / skipped`（[queue.md](../spec/features/queue.md#ステータス)）。
「配信開始待ち」を `downloading` に丸めると見分けがつかない。

→ 表示専用の新ステータス（例 `waiting_stream`）追加 or ステータスバー文言のみで対応。前者は
`_STATUS_KEY_MAP` / `_STATUS_COLORS` / i18n キー追加が必要。初版はステータスバー文言で軽く始めるのが妥当。

### 🟢 課題7: 抽出器の対応制限

`live_from_start` は YouTube / Twitch / TVer のみ。非対応サイトで ON にしても黙って無視 or エラー。

→ 自動判定（`fetch_title_or_entries` で `info["live_status"]`＝`is_live` / `is_upcoming` / `was_live` / `post_live`
を読んで UI を出し分け）まで作り込むかは要判断。初版は手動トグル＋非対応時はログ警告で十分。

---

## 4. 影響ファイル（見積もり）

| 層 | ファイル | 変更 |
|---|---|---|
| DTO | `yt_gui/job_spec.py` | `JobSpec` フィールド 2 つ＋`build_job_spec` 透過 |
| DL | `yt_gui/downloader.py` | `_build_ydl_opts` で opt 付与（＋課題1/2 の対策） |
| UI | `yt_gui/app.py` | チェックボックス・区間との排他・状態表示配線 |
| 設定 | `yt_gui/settings.py` / `settings_dialog.py` | `wait_for_video` デフォルト間隔（採用時） |
| i18n | `yt_gui/locales/` | ラベル・ログ・状態文言 |
| docs | `download-behavior.md` / `downloader.md` / `job_spec.md` / `main-window.md` / `queue.md` | 仕様反映 |
| test | `tests/test_job_spec.py` / `tests/test_downloader.py` | 表テスト追加 |

---

## 5. 初版スコープ案（叩き台・未確定）

> ※ 課題1 の扱い・初版スコープはユーザー保留中。以下は検討の出発点。

1. per-item の ON/OFF トグル ＋ `_build_ydl_opts` 付与
2. 待機中はキャンセル遅延を仕様明記（課題1＝対策 A）
3. 区間 UI との相互排他（課題5）
4. 待機状態はステータスバー文言で表示（課題6）
5. 課題2 は ext 予測フォールバックで対処
6. ライブ状態の自動判定（課題7）は初版では入れず、手動トグル＋非対応時ログ警告

確定後、GitHub Issue 起票（背景・受け入れ条件・対象ファイル・関連 spec/arch リンク）→ docs 先・テストファーストで着手する。
