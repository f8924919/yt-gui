# リファクタリング フェーズ 6: `download_video` 分割 + 依存チェック公開化

[← タスク一覧](index.md) / [← 全体計画](refactor-overview.md)

> 対応候補: [refactoring-analysis.md §I, §J](../research/refactoring-analysis.md)
> ブランチ: `refactor/downloader-split`
> 前提: フェーズ 1 ([refactor-job-spec.md](refactor-job-spec.md)) 完了

## 背景

### I. `Downloader.download_video` が 1 関数 ~190 行

`downloader.py:336-526` の単一関数で以下 7 つの責務を持っている。

1. format spec 決定 (357–371)
2. 出力テンプレート決定 (376–386)
3. `ydl_opts` 組み立て (392–443) — オーディオ系/映像系で内部分岐
4. 字幕 PP 追加 (445–466)
5. ファイル名衝突回避 (473–493) — `extract_info(download=False)` を 2 度引き
6. PP 順序操作 + ダウンロード実行 (503–511) — `ydl._pps["post_process"]` プライベート属性へ直接 `insert`
7. ニコニコ後処理 (513–526)

これらは概念的に独立しており、ヘルパに分割可能。**(6) の `ydl._pps[...]` 直接操作は yt-dlp 内部 API 依存**で、yt-dlp upgrade で壊れ得る既知の負債。

### J. レイヤ越境のプライベート属性アクセス

`app.py:269-274` で `self.downloader._ffmpeg_path / _ffprobe_path / _deno_path` を直接読んで存在確認している。`Downloader.missing_dependencies() -> list[str]` を公開 API として生やすべき。

## ゴール

- `download_video` を `_build_ydl_opts` / `_resolve_unique_path` / `_run_download` の 3 ヘルパに分割
- `ydl._pps["post_process"]` 直接 mutate に代わる公式 API への置換（yt-dlp が提供する `add_post_processor` 系を確認）
- `Downloader.missing_dependencies() -> list[str]` を公開し、`app.py` のプライベート属性アクセスを撤廃

## 着手手順

### ステップ 1: ヘルパ分割（振る舞い不変）

`downloader.py` 内に private ヘルパを追加。

```python
def _build_ydl_opts(self, job: JobSpec, output_template: str) -> dict:
    """ydl_opts dict を組み立てる。subtitle PP 追加もここに集約。"""

def _resolve_unique_path(self, ydl_opts: dict, url: str) -> str:
    """ファイル名衝突回避（extract_info(download=False) で予測）。"""

def _run_download(self, ydl_opts: dict, url: str, job: JobSpec) -> None:
    """ydl を起動してダウンロード実行。PP 順序操作もここに集約。"""

def _postprocess_nico_comments(self, ...) -> None:
    """ニコニコ動画コメント JSON → ASS → MKV 統合。"""
```

`download_video()` 本体は上記 4 ヘルパを順に呼ぶだけにする（~30 行）。

### ステップ 2: `ydl._pps["post_process"]` の置換調査

yt-dlp の公開 API を確認:

- `YoutubeDL.add_post_processor(pp, when="post_process")` が利用可能か
- PP 順序が必要な場合の正規手段（`when` パラメータの種類）
- 既存の strip 動作 (`_StripJsonOnlySubsBeforeEmbedPP`) を順序通りに挿入できるか

公開 API で代替可能なら置き換え、不可能なら**コメントで「yt-dlp 内部 API 依存」と明記**し、yt-dlp バージョン upgrade 時のチェックリストに入れる。

### ステップ 3: `missing_dependencies()` 公開化

`Downloader` に追加。

```python
def missing_dependencies(self) -> list[str]:
    """同梱バイナリのうち存在しないものの名前を返す。

    返り値: ['ffmpeg', 'ffprobe', 'deno'] のサブセット。
    空リストならすべて揃っている。
    """
    missing = []
    if not self._ffmpeg_path or not Path(self._ffmpeg_path).exists():
        missing.append("ffmpeg")
    if not self._ffprobe_path or not Path(self._ffprobe_path).exists():
        missing.append("ffprobe")
    if not self._deno_path or not Path(self._deno_path).exists():
        missing.append("deno")
    return missing
```

`app.py:269-274` の `self.downloader._ffmpeg_path` などへの直接アクセスを撤廃し、`if missing := self.downloader.missing_dependencies():` 経由に置換。

### ステップ 4: テスト追加

フェーズ 1 で導入した `tests/test_job_spec.py` をベースに、`_build_ydl_opts` の I/O をテーブルテスト化する。

- `JobSpec` 入力 → 生成される `ydl_opts` の主要キー (`format`, `outtmpl`, `postprocessors`, `writesubtitles`, ...) を assert
- 「複数音声 → MKV 自動昇格」「`audio_only` との相互作用」のケースを確実にカバー

## ドキュメント更新

- `docs/arch/downloader.md` — 関数構造を `_build_ydl_opts` / `_resolve_unique_path` / `_run_download` / `_postprocess_nico_comments` の分割で反映、`missing_dependencies()` 公開 API を追記
- `docs/arch/app.md` — 起動時の依存チェック手段が公開 API 経由に変わった旨を反映
- `docs/testing/policy.md` — `downloader` の `_build_ydl_opts` ヘルパをテスト対象に追加

## 範囲外

- yt-dlp バージョンの upgrade — 別タスク
- `_StripJsonOnlySubsBeforeEmbedPP` 自体の挙動変更 — 振る舞い不変

## ステータス

未着手
