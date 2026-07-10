# テスト方針

[← 目次](index.md)

## 目的

- 機能追加 / 改修時にデグレードを早期検出する
- `docs/spec/` に記述された振る舞いがコードで満たされているかを継続的に確認する
- 等価な評価項目を複数回行う冗長なテストを避け、テスト全体の保守コストを低く保つ

---

## 1. テスト対象スコープ

ロジック層（UI 非依存・外部ネットワーク非依存）を基本とし、Qt UI 層は **UI に閉じた状態機械・ロジック**に限って `pytest-qt`（ヘッドレス `offscreen`）で対象に含めます。

| 区分 | モジュール | 対象 |
|---|---|---|
| 純粋関数 | `yt_gui/utils.py` | ◯ |
| 純粋関数 | `yt_gui/formats.py` | ◯ |
| 純粋関数 | `yt_gui/job_spec.py` | ◯ |
| 純粋関数 | `yt_gui/output_template.py` | ◯ |
| グローバル状態 | `yt_gui/i18n.py` | ◯ |
| ファイル I/O | `yt_gui/settings.py` | ◯ |
| Qt UI（状態機械・ロジック） | `yt_gui/queue_controller.py`（編集モード状態機械）・ `original_format_panel.py`（トラック選択の排他/論理状態）・ `settings_dialog.py`（タブレイアウト回帰・`_clear_archive`/`_save` の確認/検証分岐・`_browse_*` のファイル選択反映・`_on_archive_toggled` の活性連動）・ `log_dialog.py`（`load`/`append` の表示往復）・ `app.py`（`_QueueTree._edit_targets` の編集対象判定・`_refresh_format_labels` の言語追従・`_open_original_dialog` の追加フロー・`_open_settings` の設定反映ループ・`_open_log_dialog` の起動/再表示など。モーダル `exec()`/`question`/`QFileDialog` は手段B（§2.5）で能動駆動し、フル画面操作の E2E は対象外） | △ |
| スレッドヘルパ | `yt_gui/threading_utils.py`（コールバック順序） | △ |
| 外部 I/O | `yt_gui/downloader.py`（yt-dlp、`omit` 解除済み・#95）・ `thumbnail_cache.py`（HTTP・未） | △ |
| 純粋ヘルパ (downloader) | `Downloader._build_ydl_opts` ほか（`fetch_formats` の分類・`fetch_title_or_entries`・`_resolve_unique_path`・`_progress_hook`・`_YtdlpLogger` 等を `YoutubeDL` スタブでテスト） | ◯ |
| 純粋関数 | `yt_gui/extension_server.py`（`handle_request` / `ExtensionServer` ライフサイクル / `resolve_allow_reuse_address` の bind 排他分岐） | ◯ |
| 純粋関数 | `yt_gui/yt_dlp_update.py`（`parse_latest_version` / `compare_versions` / `check_for_update`。HTTP は `fetch` 引数差し替えでオフライン検証） | ◯ |
| 純粋関数 | `yt_gui/app_update.py`（`parse_latest_version` / `check_for_update` / `should_check_on_startup` / `should_notify`。HTTP は `fetch` 引数差し替えでオフライン検証） | ◯ |
| エントリーポイント | `yt_gui/__main__.py` ・ `main.py` | × |
| 翻訳辞書 | `yt_gui/locales/*.py` | × |

Qt UI（状態機械・ロジック）/ スレッドヘルパ行の `△` は、**UI に閉じた振る舞い**（編集モードの状態遷移とシグナル、トラック選択の排他ロジック、`run_in_thread` のコールバック順序など）に限定し、ウィンドウ全体を巻き取る E2E は対象外とします。モーダルダイアログ（`QMessageBox.question` / `QFileDialog` / `QDialog.exec()`）を経由する経路は **手段B**（§2.5・`QTimer.singleShot` で能動的に閉じる、または静的メソッドを固定値へ差し替える）で「開く→操作→状態反映」までを通しますが、フル画面操作の E2E は引き続き対象外です。実行には `pytest-qt` と `QT_QPA_PLATFORM=offscreen` が必要です（要件・つまずきポイント・手段A〜Dの整理は [docs/research/qt-ui-testing-feasibility.md](../research/qt-ui-testing-feasibility.md) §5・§8 を参照）。

> **段階導入**: テストが存在しないモジュールは当面 `omit` に残し、テスト追加と同時に該当モジュールのみ `omit` から外します（一括解除でカバレッジが急落しないようにするため）。`downloader.py` はネットワーク・subprocess に依存しないロジック（フォーマット分類・パス解決・ログ整形等）を `YoutubeDL` スタブでテストし、`omit` から解除済み（#95）。実 DL・ffmpeg/danmaku2ass の subprocess 正常系は外部 I/O のため引き続きカバレッジ対象外（`△`）。`app.py` / `settings_dialog.py` は #132（PR #133）でモーダル経路を手段Bでテスト化し、#134 で `omit` から解除済み（`pytest-qt` ベースの UI ロジックに限定して計測。ウィンドウ全体の E2E は対象外）。残る Qt UI のウィンドウ統合系（`original_format_panel.py` / `log_dialog.py`）は引き続き段階導入の対象とし、テスト追加と同時に `omit` から外す。

スコープ拡張時は本ドキュメントと `pyproject.toml` の `[tool.coverage.run] omit` を併せて更新してください。

---

## 2. 記述ルール

### 2.1 仕様駆動

- テストは `docs/spec/` に対応する仕様の振る舞いを検証します
- テストモジュールの docstring に **対応する仕様ファイルへのリンク** を書きます
- テスト関数名は **検証する振る舞いが伝わる形** にします（例: `test_load_returns_defaults_when_json_is_corrupt`）
- 対応する `docs/spec/` が存在しないインフラヘルパ（例: `threading_utils.py`）は、例外として `docs/arch/` の該当ファイルへのリンクで代替します。Qt UI 層の状態機械（`queue_controller.py` / `original_format_panel.py`）は `docs/spec/features/queue.md` ・ `docs/spec/screens/original-format-panel.md` の振る舞いに対応づけます。

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
| Qt UI 単体（`qtbot` + `offscreen`） | △ | 状態機械・排他ロジック・コールバック順序など UI に閉じた振る舞いに限定（§1・§2.5） |
| E2E（実ネットワーク / フル画面操作） | × | 導入しない |

### 2.5 Qt UI テストの実行要件（方針）

Qt UI（状態機械・ロジック）行のテストを記述・実行する際の取り決めです。具体の `conftest.py` 実装と `pytest-qt` 導入は後続タスクで行います。

- **ヘッドレス**: `QT_QPA_PLATFORM=offscreen` を前提とする（`conftest.py` で `os.environ.setdefault` 固定、CI は [`test.yml`](../../.github/workflows/test.yml) の env で設定済み）。
- **マーカー分離と skip**: Qt UI テストは `@pytest.mark.qt`（選択用。`--strict-markers` のため `pyproject.toml` に登録）を付ける。マーカーを追加・変更するときは `pyproject.toml` の `[tool.pytest.ini_options] markers` と本節を併せて更新する。Qt 非導入環境での skip はモジュール冒頭の `pytest.importorskip("PySide6")` / `pytest.importorskip("pytestqt")` で行う（import 失敗より前にモジュール単位で skip され、ロジック層テストは従来どおり通る）。
- **副作用の抑制**: `offscreen` ではモーダル `QMessageBox.warning/critical/information/question` が無限ブロックするため no-op 化する（`conftest.py` の `_silence_qt_modal_dialogs` が `qt` マーカー付きテストへ autouse で適用）。`App` 構築時は `Downloader.missing_dependencies()`（PATH 実走査）が走るため、決定性確保のためモックする。
- **モーダル経路の駆動（手段B）**: 分岐や状態反映を検証したい場合は、autouse の no-op を**テスト内で上書き**する。`QMessageBox.question` は `monkeypatch.setattr(..., lambda *a, **kw: QMessageBox.StandardButton.Yes)` で Yes/No を固定し、`QFileDialog.get*` は返却パスを固定値に差し替える。`QDialog.exec()` は `monkeypatch` で no-op 化（即 return）するか、`QTimer.singleShot(0, ...)` で `QApplication.activeModalWidget()` を取得して `accept()`/ボタン押下する。シグナル経由で検証できる箇所（`add_requested` 等）は `exec()` を介さず `_make_*` でダイアログを生成してシグナルを直接 emit する方を優先する。
- **イベントループ / 後始末**: `qtbot.waitSignal` / `qtbot.waitUntil` で条件待ちする。`run_in_thread` は daemon スレッドで Qt シグナルをキュー発火するため、受信側 QObject がテスト終了時に破棄されないよう、シグナル受信を待ち切ってからテストを終える。
- 要件の詳細・つまずきポイントは [docs/research/qt-ui-testing-feasibility.md](../research/qt-ui-testing-feasibility.md) を参照。

---

## 3. ディレクトリ・ファイル構成

```
tests/
├── __init__.py
├── conftest.py            ← 共有フィクスチャ（i18n 復元・offscreen 固定・QMessageBox 抑制）
├── test_utils.py
├── test_formats.py
├── test_job_spec.py
├── test_output_template.py
├── test_i18n.py
├── test_settings.py
├── test_downloader.py
├── test_download_binaries.py
├── test_refresh_pins.py           ← scripts/refresh_pins.py の純粋ロジック
├── test_extension_server.py       ← 純粋ロジック（handle_request / ExtensionServer）
├── test_yt_dlp_update.py          ← 純粋ロジック（yt-dlp 更新チェック）
├── test_app_update.py             ← 純粋ロジック（アプリ本体更新チェック）
├── test_extension.py              ← scripts/sync_extension_version.py・extension/ 整合性
├── test_threading_utils.py        ← Qt（@pytest.mark.qt）
├── test_queue_controller.py       ← Qt（@pytest.mark.qt）
├── test_original_format_panel.py  ← Qt（@pytest.mark.qt）
├── test_original_format_dialog.py ← Qt（@pytest.mark.qt）
├── test_settings_dialog.py        ← Qt（@pytest.mark.qt）
├── test_log_dialog.py             ← Qt（@pytest.mark.qt）
└── test_app.py                    ← Qt（@pytest.mark.qt）
```

Qt UI テスト（`@pytest.mark.qt`）は冒頭で `pytest.importorskip("PySide6")` / `pytest.importorskip("pytestqt")` を呼び、Qt 非導入環境ではモジュールごと skip します（§2.5）。

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
5. `uv run pytest --cov=yt_gui --cov-report=term-missing` でカバレッジを確認する（CI でも同オプションで自動計測される。§5）
6. 仕様の削除 / 統合時は **対応するテストも併せて削除** する

---

## 5. カバレッジ運用

- **数値閾値は初期は設けません**（計測のみ）
- CI（[`test.yml`](../../.github/workflows/test.yml)）の pytest は `--cov=yt_gui --cov-report=term-missing` 付きで実行され、実行ログでカバレッジ表を確認できます（#210）。`--cov-fail-under` は指定しないため、pytest ステップの pass/fail はテスト結果のみで決まります
- 数サイクル運用後、実績値からプロジェクト全体・モジュール別に最低ラインを設定します
- 計測対象は `yt_gui` 全体ですが、UI ウィンドウ統合のうち `original_format_panel.py` / `log_dialog.py`・`thumbnail_cache.py`・`locales` は `omit` で除外し **ロジック層が対象** になります。`downloader.py` はロジック部分をテスト済みのため `omit` から外しています（#95）。`app.py` / `settings_dialog.py` も #134 で `omit` から解除し計測対象に含めています
- **§1 で `△`（対象）に格上げ済みでも `omit` には残している**モジュールがあります（`log_dialog.py`）。これは段階導入（§1 ノート）の方針で、テストは追加しつつ一括解除によるカバレッジ急落を避けるための意図的な据え置きです。`app.py` / `settings_dialog.py` は #134 で `omit` から解除済みで、解除後の実測 TOTAL は約 85%（`app.py` 単体は約 66%）です。`app.py` の未到達はウィンドウ構築・各種スロット等の UI 配線部分が中心で、テスト追加で段階的に引き上げます
- カバレッジが急に下がった場合、テスト未追加の改修が無いかをレビューで確認します

---

## 6. テスト対象を広げるとき

スコープ拡張の判断材料です。

| 対象拡張 | 必要なツール | 状態 | 留意点 |
|---|---|---|---|
| Qt UI（状態機械・ロジック） | `pytest-qt` | 方針格上げ済み（§1・§2.5）／実装は後続 | ヘッドレス環境で `QT_QPA_PLATFORM=offscreen`・マーカー分離・副作用抑制が必要 |
| Downloader（yt-dlp ラッパー） | `pytest-mock` 等 | 一部導入済み（`tests/test_downloader.py`） | 実ネットワークは使わず `YoutubeDL` をモックし `ydl_opts` / `format spec` の構築を検証 |

拡張時は本ポリシーの 1 章と `pyproject.toml` の `omit` を更新してください。
