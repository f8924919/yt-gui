# テスト

このフォルダはテスト戦略・実行方法・ルールを管理します。コード変更時にデグレードが発生していないかを `uv run pytest` で確認することを日常運用としています。

## 目次

| ドキュメント | 内容 |
|---|---|
| [policy.md](policy.md) | テスト方針・記述ルール・スコープ管理・カバレッジ運用 |

---

## 実行コマンド

```bash
# 全テスト実行
uv run pytest

# 詳細出力
uv run pytest -v

# カバレッジ計測（ターミナル + HTML）
uv run pytest --cov=yt_gui --cov-report=term-missing --cov-report=html

# 特定テストのみ実行
uv run pytest tests/test_formats.py::test_build_best_spec
```

HTML レポートは `htmlcov/index.html` に出力されます。

---

## CI 実行

`pull_request` と `main` への `push` で [`.github/workflows/test.yml`](../../.github/workflows/test.yml) が起動し、Ubuntu ランナー上で `ruff check` / `ruff format --check` / `mypy` / `pytest` を実行します。Python は `requires-python>=3.14` に合わせて `uv python install 3.14` で取得します。

ワークフローには Qt の offscreen 実行に必要な OS 側 C ライブラリ導入と `QT_QPA_PLATFORM=offscreen` を先行して含めており、後続で導入予定の Qt UI テスト（[docs/research/qt-ui-testing-feasibility.md](../research/qt-ui-testing-feasibility.md)）がそのまま乗る構成です。

---

## テストフレームワーク

| ツール | バージョン | 用途 |
|---|---|---|
| `pytest` | `>=8.3.0` | テストランナー |
| `pytest-cov` | `>=6.0.0` | カバレッジ計測（`coverage.py` のラッパー） |

`pyproject.toml` の `[dependency-groups] dev` に登録済みです。`uv sync` で導入されます。

---

## 設定

`pyproject.toml` に以下を記載しています。

| セクション | 内容 |
|---|---|
| `[tool.pytest.ini_options]` | `testpaths = ["tests"]` ・ `addopts = "--strict-markers"` |
| `[tool.coverage.run]` | `source = ["yt_gui"]` ・ `omit` で UI / Downloader / locales を除外 |
| `[tool.coverage.report]` | `show_missing = true` |

カバレッジの計測対象は現時点でロジック層のみです。詳細は [policy.md](policy.md) のスコープ管理を参照してください。

---

## 関連

- 仕様: [docs/spec/](../spec/index.md)
- ドキュメント運用ガイド: [docs/docs-guide.md](../docs-guide.md)
