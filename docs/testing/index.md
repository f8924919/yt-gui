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

`pull_request` と `main` への `push` で [`.github/workflows/test.yml`](../../.github/workflows/test.yml) が起動し、2 つのジョブを実行します（#227）。Python はいずれも `requires-python>=3.14` に合わせて `uv python install 3.14` で取得します。

- **`test`（ubuntu-latest）**: `ruff check` / `ruff format --check` / `mypy` / `pytest`（`--cov` 付き）を実行する。lint / format / 型チェックは OS 非依存のため Ubuntu 単体でのみ実行する。
- **`test-windows`（windows-latest）**: `pytest` のみを実行する。`extension_server.py` のソケット bind（#201 で Windows 実機のみ再現した退行の検出経路）や `settings.py` の `APPDATA` 分岐など、OS ネイティブ挙動に依存する箇所を Windows 上で検証する。

pytest は `test` ジョブでのみ `--cov=yt_gui --cov-report=term-missing` 付きで実行され、カバレッジを自動計測します（実行ログで `TOTAL` 行を含む表を確認できます）。計測の正本を 1 つに保つため `test-windows` では計測しません。閾値（`--cov-fail-under`）は設けておらず、pytest ステップの pass/fail はテスト結果のみで決まります（[policy.md](policy.md) §5 の「計測のみ」方針。#210）。

Qt の offscreen 実行のため、両ジョブとも `QT_QPA_PLATFORM=offscreen` を設定します。Ubuntu では offscreen 実行に必要な OS 側 C ライブラリを apt-get で導入します（Windows は追加ライブラリ不要）。後続で導入予定の Qt UI テスト（[docs/research/qt-ui-testing-feasibility.md](../research/qt-ui-testing-feasibility.md)）がそのまま乗る構成です。

`main` への branch protection では `test` / `test-windows` の両ジョブを必須チェックとします（`test-windows` は #227 の初回 CI green 確認後に追加）。

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
| `[tool.coverage.run]` | `source = ["yt_gui"]` ・ `omit` でテスト未追加の `thumbnail_cache.py`・`__main__.py`・`locales` を除外（`downloader.py` / `app.py` / `settings_dialog.py` / `original_format_panel.py` / `log_dialog.py` は解除済み） |
| `[tool.coverage.report]` | `show_missing = true` |

カバレッジの計測対象はロジック層に加えて Qt UI 層の一部（`app.py` / `settings_dialog.py` / `original_format_panel.py` / `log_dialog.py`）も含みます。詳細は [policy.md](policy.md) のスコープ管理を参照してください。

---

## 関連

- 仕様: [docs/spec/](../spec/index.md)
- ドキュメント運用ガイド: [docs/docs-guide.md](../docs-guide.md)
