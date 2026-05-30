# Qt UI テスト導入 (1): テスト実行 CI ワークフローの新設

対応 Issue: #17

## 背景

`docs/research/qt-ui-testing-feasibility.md` で Qt UI テストの実機検証は完了している。UI テストを追加するにあたり「追加で検討が必要な観点」を洗い出した結果、最重要の前提が **CI にテスト実行ジョブがそもそも存在しない**（`.github/workflows/` は `release.yml` のビルド/リリース専用）点だった。UI テストの価値はリグレッション検出だが、ローカル実行依存のままでは検出機会が限定される。

本タスクは Qt UI テスト導入の 3 系統のうち (1) を扱う。

- **(1) 本タスク**: テスト実行 CI ワークフローの新設（A・F）＋ UI テストが乗る土台（apt 依存・offscreen 設定）
- (2) `docs/testing/policy.md` の Qt UI 行格上げ・`docs/spec/` 整合（B）
- (3) `pytest-qt` 導入・`conftest.py` 副作用抑制・`@pytest.mark.qt` 分離・UI テスト本体（C〜H）

## 方針

`pull_request` と `main` への `push` で `ruff check` / `ruff format --check` / `mypy` / `pytest` を回す単一ジョブ `test.yml` を新設する。

### 設計上のポイント

- **Python 取得**: `requires-python>=3.14` のため `uv python install 3.14` で明示取得（`release.yml` と同方針）。
- **Qt offscreen 土台の先行投入**: 現状の対象テストは UI 非依存だが、後続 (3) の pytest-qt 製テストが同ワークフローに無改修で乗るよう、apt での C ライブラリ導入と `QT_QPA_PLATFORM=offscreen` を今のうちに入れておく。
- **ランナーと apt パッケージ名**: `ubuntu-latest`（現状 24.04）は `time_t` 64bit 化で `libglib2.0-0t64` 等の *t64 名。調査メモ §3.1 のリストを採用。ランナーの Ubuntu が変わったら名前を見直す。
- **`concurrency`**: 同一 ref への連続 push では古い実行をキャンセル（`release` ジョブとは別グループ）。
- **トリガー重複の回避**: `push` は `main` のみに限定（PR は `pull_request` でカバー）。

## 対象ファイル

- `.github/workflows/test.yml`（新規）
- `docs/testing/index.md`（CI 実行節を追記）
- `docs/task/qt-ui-test-ci.md`（本ファイル・新規） / `docs/task/index.md`（追記）

## 検証結果（ローカル）

- YAML 構文 OK（`jobs: [test]`, 9 steps）。
- `uv run ruff check yt_gui/` → All checks passed
- `uv run ruff format --check yt_gui/` → 19 files already formatted
- `uv run mypy yt_gui/` → Success: no issues found in 19 source files
- `uv run pytest` → 74 passed in 0.31s

## 留意点 / ブロッカー

- **`.github/workflows/` の push にはトークンの `workflow` スコープが必要**。`release.yml` 導入時（#5/#6）は、サンドボックスの egress プロキシが注入する固定トークンに `workflow` スコープが無く push が拒否された経緯がある（[archive/release-workflow.md](archive/release-workflow.md) の完了メモ参照）。現在は `gh auth status` 上 `workflow` スコープありを確認済みだが、実 push 時に拒否されたらホスト側 / Web UI 経由での push が必要。
- 日本語コミットは `/c/` マウント FS の `O_TRUNC` 不具合・locale 問題があるため、`rm -f .git/COMMIT_EDITMSG` → `/tmp` のメッセージファイル → `LC_ALL=C.UTF-8 git commit -F` の手順で行う。

## 次アクション

1. ローカルコミット → `git push -u origin feature/17-ci-test-workflow`。
2. `gh pr create --base main`（本文日本語・`Closes #17`）。
3. ユーザー承認後マージ。マージ後、本タスクを「完了」へ更新し archive へ移動。
4. 後続 (2)(3) を Issue 化して着手。
