# リファクタリング フェーズ 1: `JobSpec` 集約 + テスト先行

[← タスク一覧](index.md) / [← 全体計画](refactor-overview.md)

> 対応候補: [refactoring-analysis.md §A, §B, §C](../research/refactoring-analysis.md)
> ブランチ: `refactor/job-spec`

## 背景

`format_id` から派生する設定値（`format_spec`, `embed_thumbnail`, `audio_codec`, `mp3_bitrate`, `video_container`, `embed_metadata`, `embed_chapters` など）を組み立てるラダーが以下 3 箇所に重複している。

| 箇所 | 内容 |
|---|---|
| `app.py:625-716` | 追加時 (`_add_url` 内) |
| `app.py:1107-1201` | 編集適用時 (`_apply_edit`) — 4 ブランチを明示展開 |
| `app.py:866-916` | プレイリスト追加時の `snap_spec` / `snap_bitrate` |

また同じ 13–16 個のパラメータ群が `_add_url` → `_start_add_thread` → `_run_fetch_for_add` → `fetch_for_add_done.emit` → `_on_fetch_for_add_done` → `_enqueue_single` → `_QueueItem` → `download_video` の 7 関数を**手渡しで往復**しており、`payload.get("audio_only", False)` のような defaulting が dict 経由と kwarg 経由で散乱している。

これらを「`build_job_spec(format_id, settings, panel_snapshot) -> JobSpec`」という pure function と `JobSpec` dataclass に集約することで、7 関数のシグネチャを 1〜2 引数に圧縮し、編集・追加・プレイリストでの挙動差を解消する。

なお、変更前に C: テスト先行 を実施し、リファクタ前後で振る舞いが変わらないことを保証する。

## ゴール

1. **C (テスト先行)**: `build_job_spec` の I/O を固定化する pytest を 8〜12 ケース書く（コード変更なし）。
2. **A + B (集約)**: `JobSpec` dataclass と `build_job_spec()` を新規追加し、`_add_url` / `_apply_edit` / `_enqueue_single` / `download_video` を新 API に置換する。
3. **完了後**: 上記 7 関数群のシグネチャが縮み、`format_id` 派生ラダーがコード内に 1 箇所のみ存在する状態にする。

## 着手手順

### ステップ 1: テスト先行 (C)

`tests/test_job_spec.py`（新規）に以下のケースを記述する。`build_job_spec` は未実装なので、まず**期待値テーブル**だけ書いて xfail / skip にしておき、ステップ 2 で実装と同時に通す。

| ケース | format_id | 入力 | 期待される `JobSpec` 主要項目 |
|---|---|---|---|
| 1 | `fmt_best_mp4` | (基本) | `format_spec='bv*+ba/b'`, `audio_only=False`, `embed_thumbnail=True`, `video_container='mp4'` |
| 2 | `fmt_720p` | (基本) | `format_spec='bv*[height<=720]+ba/b[height<=720]'`, `embed_thumbnail=True` |
| 3 | `fmt_mp3` | `mp3_bitrate=192` | `audio_only=True`, `audio_codec='mp3'`, `mp3_bitrate=192`, `embed_thumbnail=True` |
| 4 | `fmt_mp3` | `audio_codec='flac'` | `audio_codec='flac'`, `embed_thumbnail=False`, `mp3_bitrate=None` |
| 5 | `fmt_original` | panel: 単一映像 + 単一音声 | `video_container='mp4'` (or MKV), `audio_only=False` |
| 6 | `fmt_original` | panel: 複数音声 → MKV 昇格 | `video_container='mkv'`, `embed_thumbnail=False` |
| 7 | `fmt_original` | panel: `audio_only=True` | `audio_only=True`, `video_container=None` |
| 8 | `fmt_original` | panel: 字幕 `live_chat` + `comments` | `subtitle_opts.subtitleslangs=['live_chat','comments']`, `embed=False`（json は埋め込み不可） |
| 9 | `fmt_original` | panel: 字幕埋め込み ON + MKV | `subtitle_opts.embed=True`, json 系は strip 対象 |
| 10 | `fmt_best_mp4` | プレイリスト URL | `snap_spec` / `snap_bitrate` 系が追加時と同一値になる |

テストは `Settings` と panel snapshot dict を引数に取る pure function 前提で書く（UI 依存 0）。

### ステップ 2: `JobSpec` dataclass の導入

`yt_gui/job_spec.py`（新規）を作成し、以下を定義する。

- `@dataclass(frozen=True) class JobSpec`: `_QueueItem` の 18 フィールドのうち**実行設定** (`format_spec`, `subtitle_opts`, `embed_thumbnail`, `remux_only`, `audio_codec`, `embed_metadata`, `embed_chapters`, `video_container`, `audio_only`, `mp3_bitrate`, `orig_settings`) を持つ
- `build_job_spec(format_id: str, settings: Settings, panel_snapshot: Mapping | None) -> JobSpec`: 上記ラダーを 1 箇所に集約
- `panel_snapshot` は `OriginalFormatPanel.get_raw_settings()` の返り値 dict

`_QueueItem` (`app.py:54`) は `JobSpec` + キュー固有情報 (`url`, `title`, `output_dir`, `status`, ...) に分割する。

### ステップ 3: 呼び出し側の置換

- `app.py:611 _add_url` → `JobSpec` を 1 度生成して受け渡す
- `app.py:761 _run_fetch_for_add` / `app.py:798 fetch_for_add_done.emit` → payload を `JobSpec` 化
- `app.py:815 _on_fetch_for_add_done` の `payload.get(...)` defaulting を撤廃
- `app.py:919 _enqueue_single` → `JobSpec` 1 引数化
- `app.py:1107 _apply_edit` → 4 ブランチ展開を撤廃し `build_job_spec()` 1 行に
- `app.py:866 _enqueue_playlist` の `snap_spec` / `snap_bitrate` も同関数経由に統一
- `downloader.download_video()` のシグネチャを `(url, output_dir, job: JobSpec)` に縮める

## ドキュメント更新

- `docs/arch/index.md` — 新モジュール `job_spec` を追記
- `docs/arch/job_spec.md`（新規）— `JobSpec` の責務と `build_job_spec` の I/O を記述、`docs/spec/features/download-formats.md` への関連リンクを先頭に置く
- `docs/arch/app.md` — `_QueueItem` の構成変更と「`format_id` 派生は `job_spec` に集約」の旨を反映
- `docs/arch/downloader.md` — `download_video()` シグネチャ変更を反映
- `docs/testing/policy.md` — `job_spec` をテスト対象モジュール表に追加
- `pyproject.toml` — `[tool.coverage.run] omit` に変更がないか確認

## 範囲外

- `App` クラスの分割 (D, フェーズ 2)
- `OriginalFormatPanel` のニコニコグループ切り出し (E, フェーズ 3)
- `download_video` 内部の 7 責務分割 (I, フェーズ 6)
- panel が返す snapshot dict のフィールド名変更 — 既存の `get_raw_settings()` 出力をそのまま使う

## 想定リスク

- **`_QueueItem` の互換性**: シリアライズに使われていないため後方互換不要。grep で外部参照を確認すれば安全。
- **編集モードの復元**: `_apply_pending_restore` の経路は panel snapshot 経由で再構築できる前提。テスト ケース 5–9 でカバーする。
- **`download_video` シグネチャ変更**: 内部 API のため後方互換不要。

## ステータス

完了 (2026-05-25)
