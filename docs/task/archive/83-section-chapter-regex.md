# 区間ダウンロード: チャプター名の正規表現指定（#83）

対応 Issue: [#83](https://github.com/f8924919/yt-gui/issues/83)

## 確定した設計方針（ユーザー確認済み 2026-07-11）

- **方式**: 既存のフル取得 → ローカル ffmpeg 切り出し方式を踏襲（ネイティブ `download_ranges` は引き続き不使用）。Issue 当初の前提（ネイティブ `download_range_func` 使用中）は誤りだったため Issue 本文を訂正済み。
- **複数マッチ**: マッチした各チャプターを個別ファイル（`動画タイトル - チャプター名.ext`）に分割出力。1 件以上成功で原本削除。
- **マッチ 0 件 / チャプター情報なし**: フル動画を残して警告ログ（非致命）。
- **時間範囲との関係**: 排他（UI はラジオでモード切り替え）。`force_keyframes` は共通。

## 実装メモ

- `JobSpec.section_chapter_regex: str | None` を追加（[arch/job_spec.md](../arch/job_spec.md)）。
- チャプター情報は `_resolve_unique_path` のドライラン `extract_info` から取得（追加フェッチなし。[arch/downloader.md](../arch/downloader.md#チャプター名指定83)）。
- マッチは yt-dlp `download_range_func` と同じ `re.search` セマンティクス（`.venv` の `yt_dlp/utils/_utils.py::download_range_func.__call__` で裏取り済み）。
- 既存テスト `test_section_omits_native_download_ranges` の意図（ネイティブ opts を渡さない）は維持する。

## 進捗

- [x] investigate / criteria-review / 設計方針のユーザー確認
- [x] docs 先行（spec / arch / feature-gap / task）
- [x] design-review（§5.5 トリガ該当・推奨 yes）→ 指摘 3 点（ニコ後処理スキップ・章メタデータ除去・排他の多層防御）をユーザー確認のうえ採用
- [x] テスト先行
- [x] 実装 → green（455 passed / ruff / mypy）
- [x] verify-gate → PR
