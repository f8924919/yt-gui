# テスト方針

[← 目次](index.md)

## 目的

- 機能追加 / 改修時にデグレードを早期検出する
- `docs/spec/` に記述された振る舞いがコードで満たされているかを継続的に確認する
- 等価な評価項目を複数回行う冗長なテストを避け、テスト全体の保守コストを低く保つ

---

## 1. テスト対象スコープ

ロジック層（UI 非依存・外部ネットワーク非依存）に限定します。

| 区分 | モジュール | 対象 |
|---|---|---|
| 純粋関数 | `yt_gui/utils.py` | ◯ |
| 純粋関数 | `yt_gui/formats.py` | ◯ |
| 純粋関数 | `yt_gui/job_spec.py` | ◯ |
| 純粋関数 | `yt_gui/output_template.py` | ◯ |
| グローバル状態 | `yt_gui/i18n.py` | ◯ |
| ファイル I/O | `yt_gui/settings.py` | ◯ |
| Qt UI | `yt_gui/app.py` ・ `original_format_panel.py` ・ `settings_dialog.py` ・ `log_dialog.py` ・ `queue_controller.py` ・ `threading_utils.py` | × |
| 外部 I/O | `yt_gui/downloader.py`（yt-dlp）・ `thumbnail_cache.py`（HTTP） | △ |
| 純粋ヘルパ (downloader) | `Downloader._build_ydl_opts` | ◯ |
| エントリーポイント | `yt_gui/__main__.py` ・ `main.py` | × |
| 翻訳辞書 | `yt_gui/locales/*.py` | × |

スコープ拡張時は本ドキュメントと `pyproject.toml` の `[tool.coverage.run] omit` を併せて更新してください。

---

## 2. 記述ルール

### 2.1 仕様駆動

- テストは `docs/spec/` に対応する仕様の振る舞いを検証します
- テストモジュールの docstring に **対応する仕様ファイルへのリンク** を書きます
- テスト関数名は **検証する振る舞いが伝わる形** にします（例: `test_load_returns_defaults_when_json_is_corrupt`）

### 2.2 1 spec = 1 test を原則とする

冗長なテストを避けるため、以下を守ります。

- **同じ振る舞いを複数のテストケースで重ねて検証しない**
- 入力パターンを変えるだけのケースは `@pytest.mark.parametrize` で 1 関数にまとめる（テスト内で `if` 分岐を増やさない）
- **下位の純粋関数の網羅は下位レイヤのテストでのみ行う**。上位レイヤのテストで間接的に再検証しない
  - 例: `formats.build_best_spec` のコンテナ別出力は `test_formats.py` でのみ網羅し、これを呼び出すコードのテストでは再検証しない

### 2.3 境界でのみ I/O を扱う

- 純粋関数（モジュール）はモック禁止。入力と出力の比較のみで検証する
- ファイル I/O は `tmp_path` フィクスチャを用いて実ファイルで検証する（`SettingsManager` の round-trip など）
- グローバル状態（例: `i18n._current_lang`）を変更するテストは fixture で **前後の値を復元** する（`tests/conftest.py` の `_restore_language` が autouse で適用される）

### 2.4 テストの粒度

| 粒度 | 採用 | 備考 |
|---|---|---|
| 単体テスト（関数・クラス単位） | ◯ | 本ポリシーの基本単位 |
| 結合テスト（モジュール跨ぎ） | △ | 純粋関数の組み合わせで価値がある場合のみ |
| E2E / UI スモーク | × | 現スコープでは導入しない |

---

## 3. ディレクトリ・ファイル構成

```
tests/
├── __init__.py
├── conftest.py            ← 共有フィクスチャ（i18n のグローバル状態復元）
├── test_utils.py
├── test_formats.py
├── test_job_spec.py
├── test_output_template.py
├── test_i18n.py
└── test_settings.py
```

**命名規則**

| 種別 | 規則 |
|---|---|
| テストファイル | `test_{対象モジュール名}.py`（対象モジュール 1 つにつき 1 ファイル） |
| テスト関数 | `test_{対象}_{検証する振る舞い}` |
| parametrize の `ids` | 各ケースを 1 単語で表すラベル |

---

## 4. 新規仕様 / 改修時のフロー

1. `docs/spec/` を更新する
2. 対応する `tests/test_*.py` にテストを追加 / 修正する
3. 実装する
4. `uv run pytest` が pass することを確認する
5. `uv run pytest --cov=yt_gui --cov-report=term-missing` でカバレッジを確認する
6. 仕様の削除 / 統合時は **対応するテストも併せて削除** する

---

## 5. カバレッジ運用

- **数値閾値は初期は設けません**（計測のみ）
- 数サイクル運用後、実績値からプロジェクト全体・モジュール別に最低ラインを設定します
- 計測対象は `yt_gui` 全体ですが、UI / Downloader / locales は `omit` で除外し **ロジック層のみが対象** になります
- カバレッジが急に下がった場合、テスト未追加の改修が無いかをレビューで確認します

---

## 6. テスト対象を広げるとき

将来 Qt UI や `downloader.py` までスコープを広げる場合の判断材料です（現時点では未導入）。

| 対象拡張 | 必要なツール | 留意点 |
|---|---|---|
| Qt UI | `pytest-qt` | ヘッドレス環境で `QT_QPA_PLATFORM=offscreen` 等の設定が必要 |
| Downloader（yt-dlp ラッパー） | `pytest-mock` 等 | 実ネットワークは使わず `YoutubeDL` をモックし `ydl_opts` / `format spec` の構築を検証 |

拡張時は本ポリシーの 1 章と `pyproject.toml` の `omit` を更新してください。
