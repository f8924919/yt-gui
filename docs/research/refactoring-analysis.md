# リファクタリング候補の調査メモ

調査日: 2026-05-25
対象: `yt_gui/` 配下のソース全体（4,087 行）

[← 研究メモ目次](.)

## 1. 調査の目的・前提

ニコニコ動画コメント機能（フェーズ 1–3, 2026-05-24 完了）追加後のコードベースに対し、以下を整理することを目的とする。

- 重複コード・肥大化した関数・レイヤ越境などの技術的負債の洗い出し
- 各候補の優先度づけ
- 最初に着手すべき箇所と、それを選ぶ根拠

本メモは **採否未決の調査メモ** であり、実装には着手していない。実装に進む際は別途 `docs/task/` にタスク化する。

---

## 2. 全体所見

- 総行数 4,087 行のうち **約 87%（3,640 行）が `app.py` / `original_format_panel.py` / `downloader.py` の 3 ファイルに集中**。
- ドキュメント整備（spec / arch / task）・命名・i18n・スレッド境界などの土台は健全。
- 一方で、上記 3 つの大型ファイルは内部構造に肥大化と重複が蓄積している。直近のフェーズ追加で一段顕在化した。
- テストは `formats / i18n / output_template / settings / utils` のみで純粋関数寄り。**最大かつ最複雑な 3 モジュール (`app`, `downloader`, `original_format_panel`) はテスト 0 件**。

### モジュール別行数

| ファイル | 行数 |
|---|---:|
| `app.py` | 1,447 |
| `original_format_panel.py` | 1,136 |
| `downloader.py` | 657 |
| `settings_dialog.py` | 528 |
| `settings.py` | 84 |
| `log_dialog.py` | 69 |
| `output_template.py` | 55 |
| `formats.py` | 46 |
| その他（`__main__`, `__init__`, `i18n`, `utils`） | 65 |

---

## 3. リファクタリング候補一覧

### A. ダウンロードジョブの「引数バケツ」反パターン【優先度: 高】

同じ 13–16 個のパラメータ群（`format_id`, `format_label`, `format_spec`, `subtitle_opts`, `embed_thumbnail`, `remux_only`, `audio_codec`, `embed_metadata`, `embed_chapters`, `orig_settings`, `video_container`, `audio_only`, `mp3_bitrate`, ...）が手渡しで往復している。

経路:

- `app.py:611 _add_url` → `app.py:718 _start_add_thread` → `app.py:761 _run_fetch_for_add` → `app.py:798 fetch_for_add_done.emit(payload)` → `app.py:815 _on_fetch_for_add_done` → `app.py:919 _enqueue_single` → `_QueueItem` → `app.py:1326 downloader.download_video`
- `app.py:1107 _apply_edit` で同じ集合を独自再構築

`_on_fetch_for_add_done` で `payload.get("audio_only", False)` のように **dict 経由と kwarg 経由で defaulting が散乱**しており、仕様追加時のバグ温床になっている。`_QueueItem` (`app.py:54`) は既に 18 フィールド持つ事実上の DTO なので、ここに同梱情報と実行設定の構造を持たせれば全シグネチャを 1〜2 引数に圧縮できる。

### B. 「format_id → 設定一式」の派生ロジックが 3 箇所で重複【優先度: 高】

「`format_id` が `fmt_original` / `fmt_mp3` / `fmt_720p` / `fmt_best_mp4` / その他のどれかで、対応する `format_spec / embed_thumbnail / audio_codec / mp3_bitrate / video_container / embed_metadata / embed_chapters` を決める」というラダーが下記 3 箇所に重複している。

| 箇所 | 内容 |
|---|---|
| `app.py:625-716` | 追加時 |
| `app.py:1107-1201` | 編集適用時（4 ブランチを明示展開） |
| `app.py:866-916` | プレイリスト追加時の `snap_spec` / `snap_bitrate` |

微妙に挙動が違う:

- 編集時は `mp3_bitrate` を計算するが、追加時 (`_add_url` 内 else 分岐) は `_enqueue_single` 側に委譲
- `embed_thumbnail` の決定ルール（`fmt_720p`/`fmt_best_mp4` は常時 True、`fmt_mp3` は `audio_codec == "mp3"` のみチェック値、`fmt_original` は panel から取得）は 2 箇所に重複

**1 つの pure function (`build_job_spec(format_id, settings, panel_snapshot)`) に集約可能**。

### C. テスト不在ゾーンが業務ロジックを丸抱え【優先度: 高】

`tests/` 配下は形式定数・i18n・テンプレート・設定・utils のみ（純粋関数寄り）。実際の挙動を決めている以下は完全未カバー。

- `Downloader.download_video` の yt-dlp opts 組み立て（postprocessor 順序・MKV 自動昇格・json 字幕除外）
- `App._worker` のキュー走行ロジック
- `OriginalFormatPanel.get_format_spec / get_raw_settings / restore_from_settings`
- 「複数音声 → MKV 自動昇格」「`audio_only` との相互作用」

A・B の安全な実施には、まずこれらの代表ケースをテストで固定化すべき。

### D. `App` クラスが God Object（1,447 行 / 30 メソッド超）【優先度: 中】

実質 6 責務を一手に持つ:

1. ウィジェット生成・レイアウト (`_create_widgets`, `_create_menu`)
2. キュー管理・ワーカースレッド (`_start_queue`, `_worker`, `_remove_selected`)
3. サムネイルキャッシュ（HTTP 取得スレッド・dict + Lock）
4. 編集モード状態機械 (`_enter_edit_mode`, `_apply_edit`, `_cancel_edit`, `_exit_edit_mode`)
5. 形式 ↔ パネル可視性 (`_on_format_changed`, `_build_format_display`)
6. ログ管理・ステータス送出・設定リロード

少なくとも **`ThumbnailCache`（独立可能、純粋）** と **`QueueController`（キュー + ワーカー + 編集モード状態機械）** は別クラスに切り出し可能。

### E. `OriginalFormatPanel` のニコニコグループが内部凝集【優先度: 中】

`original_format_panel.py` 1,136 行のうち、ニコニコ動画コメント (ASS / MKV 統合) は以下に散在。

| 区分 | 行範囲 |
|---|---|
| ビルド | 340–420 |
| イベント | 615–685 |
| 復元 | 755–773 |
| 翻訳 | 519–526 |
| リセット | 464–474 |

計 ~200 行。**`_NicoCommentsGroup` という子 `QGroupBox` サブクラスにまとめる**ことで、`OriginalFormatPanel` は本来の映像/音声/字幕の議論に集中できる。フェーズ 1–3 の最新追加分なので境界が新鮮で切り出しやすい。

### F. バックグラウンドスレッド + シグナル の三度書き【優先度: 中】

`threading.Thread(target=..., daemon=True).start()` + `_PanelSignals` / `_AppSignals` で finish/done/failed を emit するパターンが 3 箇所で再実装されている。

| 箇所 | 用途 |
|---|---|
| `App._start_add_thread` / `_run_fetch_for_add` | 追加時のタイトル取得 |
| `App._start_thumbnail_fetch` / `_run_thumbnail_fetch` | サムネイル取得 |
| `OriginalFormatPanel._start_fetch_thread` / `_run_fetch` | フォーマット取得 |

各々が「ボタン disable → 状態文言更新 → 例外時はメッセージ + status update → finally で再 enable」を独自に書いている。共通の `run_in_thread(work, *, on_done, on_failed, on_finished)` ヘルパで吸収できる。

### G. 翻訳済み文字列を比較キーに使っている【優先度: 中】

`_video_combo.currentText() == t("orig_auto")` 形式の比較が `original_format_panel.py` の 538, 602, 691-697, 793-798, 859-884, 935-938 など **8 箇所以上**。`set_language()` 直後にユーザー操作が走ると比較が一時的にズレ得るし、新言語追加時に「auto」「skip」のサロゲートを切らさない要件が暗黙化している。

→ コンボの `userData` (`QComboBox.setItemData`) に内部 sentinel (`"__auto__"`, `"__skip__"`) を持たせて比較する設計に変えれば、表示文字列と論理状態が完全分離できる。

### H. AUTO/SKIP オフセット `±2` のマジックナンバー散在【優先度: 中】

`_AudioListWidget` の物理行 (AUTO=0, SKIP=1, audio=2+) を呼び出し側が直接知っている。

- `original_format_panel.py:730 audio_idx = row - 2`
- `original_format_panel.py:880 setCurrentIndex(i + 2)`
- `original_format_panel.py:899 rows.append(i + 2)`
- `original_format_panel.py:1012 return idx - 2`

カプセル化漏れ。`_AudioListWidget` 側に `audio_row(i: int) -> int` / `audio_index_from_row(row: int) -> int | None` を提供すれば解消。

### I. `Downloader.download_video` が 1 関数 ~190 行【優先度: 中】

`downloader.py:336-526` の単一関数で 7 つの責務:

1. format spec 決定 (357–371)
2. 出力テンプレート決定 (376–386)
3. `ydl_opts` 組み立て (392–443) — オーディオ系/映像系で内部分岐
4. 字幕 PP 追加 (445–466)
5. ファイル名衝突回避 (473–493) — `extract_info(download=False)` を 2 度引き
6. PP 順序操作 + ダウンロード実行 (503–511) — `ydl._pps["post_process"]` プライベート属性へ直接 `insert`
7. ニコニコ後処理 (513–526)

これらは概念的に独立しており、`_build_ydl_opts` / `_resolve_unique_path` / `_run_download` の 3 ヘルパに割れる。**(6) の `ydl._pps[...]` 直接操作は yt-dlp 内部 API 依存**で、yt-dlp upgrade で壊れ得る既知の負債。

### J. レイヤ越境のプライベート属性アクセス【優先度: 低】

- `app.py:269-274` で `self.downloader._ffmpeg_path / _ffprobe_path / _deno_path` を直接読んで存在確認。`Downloader.missing_dependencies() -> list[str]` を生やすべき。
- 上記 (I-6) の `ydl._pps["post_process"]` 直接 mutate も同カテゴリ。

### K. `_QueueTree._is_editing` / `_get_*_cb` の素朴な属性差し込み【優先度: 低】

`app.py:512-515` で外から 4 つのコールバックを直接代入 (`self._queue_tree._get_item_cb = ...`)。Qt のシグナル/スロットで揃えれば一貫する。

### L. `App._open_settings` の重複ロジック【優先度: 低】

`app.py:1385-1416` で「言語が変わった時」と「変わらなかった時」の `format_combo` / `original_panel.retranslate` の再構築を二度書きしている (`_retranslate_ui` 側と部分重複)。

---

## 4. 優先度サマリ

| # | 項目 | 優先度 | 理由 |
|---|---|---|---|
| A | `JobSpec` dataclass で引数バケツ解消 | **高** | 5 関数横断のシグネチャ重複・defaulting 散乱の元 |
| B | `format_id → 設定派生`ラダーを 1 関数に集約 | **高** | 同じラダーの 3 箇所コピー、編集と追加で挙動分岐の温床 |
| C | downloader / app / panel の代表ケースをテスト化 | **高** | A/B/D を安全に進める前提 |
| D | App を `ThumbnailCache` / `QueueController` に分割 | 中 | 1,447 行 6 責務、状態機械が他責務と絡む |
| E | `_NicoCommentsGroup` を子ウィジェットに切り出し | 中 | 最新追加で境界が新鮮、200 行が 4 メソッドに散在 |
| F | バックグラウンドスレッド+シグナルの共通化 | 中 | 3 箇所で同じ「disable / run / signal / re-enable」 |
| G | コンボの sentinel 化（翻訳済み文字列比較の排除） | 中 | i18n 切替・新言語追加で壊れやすい |
| H | AUTO/SKIP `±2` オフセットのカプセル化 | 中 | `_AudioListWidget` の内部表現が漏れている |
| I | `download_video` 内部分割 + `ydl._pps` 直触り解消 | 中 | yt-dlp upgrade で壊れる可能性のある内部 API 依存 |
| J | downloader の依存チェックを公開 API 化 | 低 | 局所的なレイヤ漏れ |
| K | `_QueueTree` のコールバック差し込みをシグナル化 | 低 | 一貫性のみ |
| L | `_open_settings` と `_retranslate_ui` の重複 | 低 | 局所的 |

---

## 5. まず着手すべき箇所と理由

**「A: `JobSpec` dataclass の導入」と「B: `build_job_spec(format_id, settings, panel_snapshot)` への集約」をワンセットで最初に行う**のが最も投資効果が高い。その前提として **C: 該当ロジックの代表ケースに pytest を入れる**ことを同時並行で進める。

### 5.1 理由

1. **波及範囲が広く、後続全部を簡単にする**
   A/B を済ませると、`_add_url` / `_start_add_thread` / `_run_fetch_for_add` / `_on_fetch_for_add_done` / `_enqueue_single` / `_apply_edit` / `download_video` の **7 つの関数シグネチャと内部実装が一斉に縮む**。D (App 分割) の「`ThumbnailCache` や `QueueController` を切り出す」作業も、データの流れが 1 つの DTO で表現されている方が遥かに簡単。

2. **テスト先行が自然にできる**
   `build_job_spec` は **UI に依存しない pure function** にできる（入力: `format_id`, `Settings`, panel が返す snapshot dict）。リファクタ着手前に「ORIGINAL × `audio_only` × multi_audio = MKV 昇格 + `audio_codec` 反映」のような既存挙動の表をテストで固定でき、I/J の `download_video` 分割や G のコンボ sentinel 化に進む際の安全網になる。

3. **直近の負債が一番濃い場所**
   ニコニコ動画コメント（フェーズ 1–3）と `audio_only` / multi-audio の追加で、 `_QueueItem` のフィールドと kwarg list は一気に膨らんだ。`_on_fetch_for_add_done` で `payload.get("audio_only", False)` のような後方互換 default が混入し始めており、ここは早めに止めないと毎フェーズで負債が積み上がる構造になっている。

4. **影響範囲が docs と整合する単位**
   [`docs/spec/features/download-formats.md`](../spec/features/download-formats.md) / [`docs/spec/features/download-behavior.md`](../spec/features/download-behavior.md) と 1:1 で対応するため、`build_job_spec` の振る舞いがそのまま仕様の参照実装になり、CLAUDE.md の「spec ↔ arch ↔ コード」運用にも乗りやすい。

### 5.2 着手手順の目安

1. `tests/test_downloader_jobspec.py`（仮）に、現在の `_add_url` / `_apply_edit` から逆算した「入力 → 期待される実行パラメータ」のテーブルを 8〜12 ケース書いて固定化する（**コード変更なし**）。
2. `JobSpec` dataclass と `build_job_spec()` を新規追加し、テストを通す。
3. `_add_url` / `_apply_edit` / `_enqueue_single` を `build_job_spec()` 呼び出しに置換、`_QueueItem` を `JobSpec` 構成にスリム化、`download_video` のシグネチャを `JobSpec` 1 引数に縮める。
4. その後で D / E / I に進む。

---

## 6. 関連ドキュメント

- [`docs/arch/index.md`](../arch/index.md) — モジュール構成
- [`docs/spec/features/download-formats.md`](../spec/features/download-formats.md) — 形式定義・spec 生成ロジック
- [`docs/spec/features/download-behavior.md`](../spec/features/download-behavior.md) — ダウンロード時の挙動
- [`docs/spec/features/queue.md`](../spec/features/queue.md) — キューの仕様
- [`docs/testing/policy.md`](../testing/policy.md) — テスト方針
