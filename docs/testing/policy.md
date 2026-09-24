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
| 開発ツール（Claude Code hook） | `.claude/hooks/block_main_commit.py`（コマンド解析・実効ディレクトリ解決のロジック。**全件をスクリプトとして起動して検証する**（`sys.executable` で hook の `.py` を直接叩く）。**この方式を選んだ理由は一次資料で裏取りできていない**ので、ここには書かない（調べた範囲と結論は #337 と[タスクメモ](../task/337-hook-test-method.md)）。ブランチ判定は一時 git リポジトリで検証。`--cov=yt_gui` の範囲外につきカバレッジ計測対象外・#240 / #337） | ◯ |
| 開発ツール（Claude Code hook） | `.claude/hooks/block_main_edit.py`・`.claude/hooks/session_task_status.py`・`.claude/hooks/format_edited_file.py`（ブロック判定・表の抽出/整形・整形対象の判定。**判定ロジックは in-process で検証する** — パッケージ外なので `importlib` で hook を読み、`monkeypatch` で `sys.stdin` と `REPO_ROOT` 等の定数を差し替えて `main()` を直接呼ぶ。**スクリプトとしての起動経路は `block_main_edit.py` のフェイルオープン系だけ**が subprocess で確認しており、`session_task_status.py` と `format_edited_file.py` には**起動するテストが無い**。`--cov=yt_gui` の範囲外につきカバレッジ計測対象外・#285 / #337） | ◯ |
| ビルドスクリプト | `scripts/download_binaries.py`（pins 検証・リトライ/診断・notices 生成のロジック。HTTP は `_download` の monkeypatch ＋ `retries`/`sleep` 注入でオフライン検証・#265。`importlib` で読み込み、`--cov=yt_gui` の範囲外につきカバレッジ計測対象外。実ダウンロードは対象外） | ◯ |
| CI ワークフロー定義 | `.github/workflows/update-binaries.yml`（PR 作成トークンの設定＝`PIN_UPDATE_TOKEN` の指定・`GITHUB_TOKEN` へのフォールバック・未設定時の警告と PR 本文注記。設定が失われても既存テストは素通りし CI 未発火の症状へ静かに戻るため、yml をパースして構造を検証する・#284。`--cov=yt_gui` の範囲外につきカバレッジ計測対象外。ワークフローの実行そのものは対象外） | ◯ |

> **hook のテストの方式**（実測と経緯は [#337](https://github.com/f8924919/yt-gui/issues/337) と[タスクメモ](../task/337-hook-test-method.md)。**件数はここに書きません** — 木が育つと腐るので、数えるコマンドはタスクメモ側に置いてあります）:
> - **新規の hook テストは原則 in-process** にします。`block_main_commit.py` の全件スクリプト起動は **#232 / PR #233 由来の歴史的経緯であって、新規の模範ではありません**。
> - **in-process を原則にする理由**: `monkeypatch` で `REPO_ROOT`・`shutil.which`・`subprocess.run` を差し替えられるので、**分岐に入ったこと自体**を見るテストが書けます（§8.1 A2。実例は `format_edited_file.py` のフェイルオープンの各分岐・#334）。スクリプト起動ではこれらを差し替えられません。
> - **スクリプトとしての起動経路で見るもの**: stdin が空・閉じている場合や、`REPO_ROOT` を差し替えずに実際のリポジトリへ当てたときのフェイルオープン（`block_main_edit.py` のフェイルオープン系）。`if __name__ == "__main__":` を通る経路そのものは in-process では担保できません。
> - **`settings.json` に登録された `uv run --no-sync --project … python <path>` の起動形式そのものは、いずれのテストも検証していない（実地確認に委ねる）。** 過去に実際に踏んだ不発火（shell form のままで素の `git commit` が deny されなかった・#235 / PR #236）は、pytest ではなく**セッション内の実地 smoke** で見つかっています。**「subprocess で検証しているから登録も大丈夫」とは読まないでください。**

Qt UI（状態機械・ロジック）/ スレッドヘルパ行の `△` は、**UI に閉じた振る舞い**（編集モードの状態遷移とシグナル、トラック選択の排他ロジック、`run_in_thread` のコールバック順序など）に限定し、ウィンドウ全体を巻き取る E2E は対象外とします。モーダルダイアログ（`QMessageBox.question` / `QFileDialog` / `QDialog.exec()`）を経由する経路は **手段B**（§2.5・`QTimer.singleShot` で能動的に閉じる、または静的メソッドを固定値へ差し替える）で「開く→操作→状態反映」までを通しますが、フル画面操作の E2E は引き続き対象外です。実行には `pytest-qt` と `QT_QPA_PLATFORM=offscreen` が必要です（要件・つまずきポイント・手段A〜Dの整理は [docs/research/qt-ui-testing-feasibility.md](../research/qt-ui-testing-feasibility.md) §5・§8 を参照）。

> **段階導入**: テストが存在しないモジュールは当面 `omit` に残し、テスト追加と同時に該当モジュールのみ `omit` から外します（一括解除でカバレッジが急落しないようにするため）。`downloader.py` はネットワーク・subprocess に依存しないロジック（フォーマット分類・パス解決・ログ整形等）を `YoutubeDL` スタブでテストし、`omit` から解除済み（#95）。実 DL・ffmpeg/danmaku2ass の subprocess 正常系は外部 I/O のため引き続きカバレッジ対象外（`△`）。`app.py` / `settings_dialog.py` は #132（PR #133）でモーダル経路を手段Bでテスト化し、#134 で `omit` から解除済み（`pytest-qt` ベースの UI ロジックに限定して計測。ウィンドウ全体の E2E は対象外）。`original_format_panel.py` / `log_dialog.py` もテスト追加済みのため #224 で `omit` から解除済み。残る `omit` はテスト未追加の `thumbnail_cache.py` とエントリーポイント・翻訳辞書のみ。

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
- **マーカー分離と skip**: Qt UI テストは `@pytest.mark.qt`（選択用。`--strict-markers` のため `pyproject.toml` に登録）を付ける。マーカーを追加・変更するときは `pyproject.toml` の `[tool.pytest.ini_options] markers` と本節を併せて更新する。Qt 非導入環境での skip はモジュール冒頭の `pytest.importorskip("PySide6")` / `pytest.importorskip("pytestqt")` で行う（import 失敗より前にモジュール単位で skip され、ロジック層テストは通る）。
- **副作用の抑制**: `offscreen` ではモーダル `QMessageBox.warning/critical/information/question` が無限ブロックするため no-op 化する（`conftest.py` の `_silence_qt_modal_dialogs` が `qt` マーカー付きテストへ autouse で適用）。`App` 構築時は `Downloader.missing_dependencies()`（PATH 実走査）が走るため、決定性確保のためモックする。
- **モーダル経路の駆動（手段B）**: 分岐や状態反映を検証したい場合は、autouse の no-op を**テスト内で上書き**する。`QMessageBox.question` は `monkeypatch.setattr(..., lambda *a, **kw: QMessageBox.StandardButton.Yes)` で Yes/No を固定し、`QFileDialog.get*` は返却パスを固定値に差し替える。`QDialog.exec()` は `monkeypatch` で no-op 化（即 return）するか、`QTimer.singleShot(0, ...)` で `QApplication.activeModalWidget()` を取得して `accept()`/ボタン押下する。シグナル経由で検証できる箇所（`add_requested` 等）は `exec()` を介さず `_make_*` でダイアログを生成してシグナルを直接 emit する方を優先する。
- **イベントループ / 後始末**: `qtbot.waitSignal` / `qtbot.waitUntil` で条件待ちする。`run_in_thread` は daemon スレッドで Qt シグナルをキュー発火するため、受信側 QObject がテスト終了時に破棄されないよう、シグナル受信を待ち切ってからテストを終える。
- **遅延破棄の決定論化（#246）**: ウィジェットの `deleteLater()` による破棄イベント（`DeferredDelete`）を**テスト境界を越えて漏らさない**。pytest-qt は `pytest_runtest_teardown` フック（fixture finalizer より前）で登録ウィジェットの close / `deleteLater()` と `processEvents()` を行うが、Qt は DeferredDelete を loop-level ガードで遅延させるため `processEvents()` では消化されないことがある。積み残しが後続テストのイベントループ処理中に実行されると、Python GC と C++ デストラクタ連鎖の順序次第で二重解放（SIGABRT）を起こしうる。`conftest.py` の autouse フィクスチャ（`qt` マーカー限定）が teardown ——fixture finalizer は qtbot のフック後に走るため必ず close / `deleteLater()` の後になる——で `QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)`（event_type 明示によりガードを迂回して強制 flush）により確実に消化する。これにより、参照サイクル等で生き残っている wrapper については C++ 側の破棄が Python 側 GC より先行する順序が保証される。flush 機構自体の動作は `tests/test_conftest.py` で決定論的に検証する。
- **`qt` マーカーの付与は必須**: qtbot・ウィジェット・`QApplication` を使うテストには必ず `@pytest.mark.qt`（モジュール単位なら `pytestmark`）を付ける。上記の遅延破棄 flush と `_silence_qt_modal_dialogs` は `qt` マーカー限定で適用されるため、付け忘れると保護の対象外になる。
- 要件の詳細・つまずきポイントは [docs/research/qt-ui-testing-feasibility.md](../research/qt-ui-testing-feasibility.md) を参照。

### 2.6 足した検出器が効くことを確かめる

**不具合を直して回帰テストを足したら、修正を一時的に戻してそのテストが落ちることを確認します。** 落ちなければ、そのテストは対象を見ていません。**通ることの確認だけでは、何も見ていないテストと区別が付きません。**

- **テストに限りません。** lint ルール・静的検査・hook のスモークなど、**「これを足したから今後は検出できる」と言うもの全部**が対象です。
- **書いた時点では正しく見えます。** 「折り返しを検出するつもりの条件が、実は折り返していない状態でも常に落ちる」「最長のケースで一度も走っておらず、対象を狭めても緑のまま通る」といった誤りは、**レビューでは捕まらず、壊して確かめて初めて分かります**。
- **壊す前にコミットします。** 確認のあと `git checkout <file>` で戻すと、**同じファイルの未コミットの作業ごと消えます**。検出器を足した時点でいったんコミットし、**それから壊します**。
- **壊す作業を自動化するなら、追跡下のファイルを書き換えない設計にします。** 手で 1 か所ずつ壊して `git checkout` で戻すのは上の手順どおりでかまいませんが、スクリプトで繰り返し壊すなら対象のコピーを作ってそちらを変異させ、終了後に原本が無傷であることを確かめます。変異ハーネスを重ねて起動して互いの復元を潰し合い、変異が作業ツリーに残ったまま `git add -A` に拾われかけた事例があります（雛形 claude-templates の採用プロジェクトでの事例）。
- **テストファーストで書いたテストは、実装前に red だったことが同じ証跡になります。** 新機能のテストは [git-workflow.md](../git-workflow.md) §5 step 5 で実装より先に書くので、実装前に走らせた FAILED 行と、そのときの HEAD のコミット（red のテストは単独でコミットしないため「実装前の HEAD」）を記録すれば、改めて壊す必要はありません。回帰テスト・hook・判定ロジックのように「直してから戻して red を見る」ものは、上の手順どおり壊します。
- **変異 → red のログは、タスクメモ（`docs/task/<slug>.md`）か PR 本文に貼ります。** 「確認した」という言葉やチャット上の出力は証跡になりません。`evaluator` は貼られていなければ ❌ にします（評価軸 5・§8.1 A1）。

---

## 3. ディレクトリ・ファイル構成

```
tests/
├── __init__.py
├── conftest.py            ← 共有フィクスチャ（i18n 復元・offscreen 固定・QMessageBox 抑制・遅延破棄 flush）
├── test_conftest.py       ← Qt（@pytest.mark.qt）。conftest 共有ヘルパ（遅延破棄 flush）の検証
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
├── test_update_binaries_workflow.py ← .github/workflows/update-binaries.yml の PR 作成トークン設定
├── test_block_main_commit.py      ← .claude/hooks/block_main_commit.py
├── test_block_main_edit.py        ← .claude/hooks/block_main_edit.py
├── test_session_task_status.py    ← .claude/hooks/session_task_status.py
├── test_format_edited_file.py     ← .claude/hooks/format_edited_file.py
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
- 計測対象は `yt_gui` 全体ですが、テスト未追加の `thumbnail_cache.py`・エントリーポイント（`__main__.py`）・翻訳辞書（`locales`）は `omit` で除外しています。`downloader.py` はロジック部分をテスト済みのため `omit` から外しています（#95）。`app.py` / `settings_dialog.py` は #134、`original_format_panel.py` / `log_dialog.py` は #224 で `omit` から解除し計測対象に含めています
- #224 の解除で実測 TOTAL は約 86% → 約 81% に低下しました（ほぼ全量が `original_format_panel.py` 単体・実測約 63% によるもの。`log_dialog.py` は約 86%）。これは omit 解除に伴う既知の事象であり、テスト未追加の改修によるものではありません。`original_format_panel.py` の未到達は `app.py`（単体約 66%）と同様にウィンドウ構築・UI 配線部分が中心で、テスト追加で段階的に引き上げます
- カバレッジが急に下がった場合、テスト未追加の改修が無いかをレビューで確認します

---

## 6. テスト対象を広げるとき

スコープ拡張の判断材料です。

| 対象拡張 | 必要なツール | 状態 | 留意点 |
|---|---|---|---|
| Qt UI（状態機械・ロジック） | `pytest-qt` | 方針格上げ済み（§1・§2.5）／実装は後続 | ヘッドレス環境で `QT_QPA_PLATFORM=offscreen`・マーカー分離・副作用抑制が必要 |
| Downloader（yt-dlp ラッパー） | `pytest-mock` 等 | 一部導入済み（`tests/test_downloader.py`） | 実ネットワークは使わず `YoutubeDL` をモックし `ydl_opts` / `format spec` の構築を検証 |

拡張時は本ポリシーの 1 章と `pyproject.toml` の `omit` を更新してください。

---

## 7. 実行環境差の検証（権限・昇格）

自動テスト（pytest）では再現できない**実行環境の権限差**に起因する不具合への取り決めです。

- **背景（#275）**: python-tuf の `os.symlink` が Windows の非昇格ユーザーで `WinError 1314`（特権不足）となり、自己更新の検証が一般ユーザーでは必ず失敗した。開発時の E2E は**昇格（管理者）セッションで実行されていたため全て偽陰性**となり、リリース後にユーザー環境で初めて露見した（経緯は [docs/research/app-update.md](../research/app-update.md) の Phase B 撤去節）。
- **ルール**: **権限・環境差に敏感な操作**（symlink / junction 作成・ACL 変更・保護フォルダやレジストリへの書き込み・特権 API 等）を含む機能は、リリース前検証に**非昇格コンテキストでの E2E**を必ず含める。昇格セッションでの成功をもって完了と判定しない。
- **手段**: 昇格済みシェルからでも `runas /trustlevel:0x20000 <script.cmd>` で**制限トークン**（Administrators が deny-only・`IsUserAnAdmin()=False`）のプロセスを対話なしで起動でき、#275 の `WinError 1314` はこの方法で再現できることを確認済み（2026-07-18）。実行内容は `.cmd` に書き出し、結果はファイル経由で受け取る（引数の引用符入れ子は壊れやすい）。それでも再現できない環境要因が疑われる場合のみ、ユーザー本人の実環境での確認を依頼する。

---

## 8. 観測と原因報告の規律

不具合の調査・検証の整備で**同じ形の誤りが繰り返される**ことが分かっています（雛形 claude-templates の記述による。採用プロジェクトの完了タスクを棚卸しした結果、下の 3 型がそれぞれ繰り返し見つかった）。「慎重に判断せよ」は読んだ側の判断力に依存して繰り返しに効かなかったため、**何を見て、何を出すか**まで固定します。各項目は「見るもの → 出すもの」の 2 欄で書き、**報告に「出すもの」が無ければ項目未達**と判定できるようにしてあります（`evaluator` の評価軸 5、`criteria-review` の定型点検、`/start-task` 手順 3.5 がこの表を参照します）。

> 項目番号（A1〜A12〈**A11 は欠番**〉/ B1〜B4 / C1〜C6）は雛形と揃えてあります。中身は yt-gui の実態（pytest・Windows 主体・検査スクリプトの一括ランナーを持たない）に読み替えています。

### 8.1 型 A: 検出器が壊れているのに green（偽 PASS）

テスト・hook・判定ロジックは測定器で、壊れた測定器は red ではなく **PASS** を出します。

| # | 見るもの | 出すもの |
|---|---|---|
| A1 | 判定ロジックを足した／変えたら、**対象を壊して red になるか**（§2.6） | 変異 → red のログ（手で壊したときの FAILED 行。テストファーストの新しいテストなら実装前の FAILED 行、§2.6）と、**壊す前（または実装前）のコミット hash**。**タスクメモか PR 本文に貼る**（scratchpad に置いたままにしない）。**変異を複数入れたら、各変異でどのテストが落ちたかの対応（死因）も表にする**（件数だけにしない）。hash があれば、記録の後に検出器が動いたか（証跡の鮮度）を `git log <hash>..HEAD -- <検出器のファイル>` で判定できる。**変異の作業自体が失敗した回は fail-closed にする** — 変異が当たらなかった（置換対象が見つからない）・テストが起動しない・収集が 0 件、の回を「死亡（red）」と数えず、ハーネスの失敗として止める。黙って飛ばすと、前の変異の状態のまま走って偽の死因が出る |
| A2 | 終了コード**だけ**で合否を見ている検査 | 出力の**内容まで照合**していること。2 つの分岐がどちらも同じ終了コードに落ちる検査は、片方を完全に壊しても PASS になる（例: hook の「通す」と「フェイルオープンで通す」はどちらも無出力・exit 0 なので、分岐ごとに別のテストで見る） |
| A3 | テストの期待値を、**検査対象と同じ理解**で書いていないか（合成データ・自作の見本） | **実物**（実際の出力・実際の入力ファイル）と突き合わせた結果。実物が無ければ skip と明示する（黙って飛ばさない）。例: `test_repository_task_index_is_parsable` は実物の `docs/task/index.md` を読む |
| A4 | 変異の作業が追跡下のファイルを書き換えていないか | 手で壊したなら、壊す前のコミットと `git checkout` での復元（§2.6）。自動化したならコピーを変異させる設計と、終了後に原本が無傷であることの確認 |
| A5 | 診断メッセージの行き先 | 撮れない・読めないときに**黙らない**こと（例外を握りつぶしていないか、パイプやサブプロセスに吸われて失敗が見えなくなっていないか） |
| A6 | 新しいテストを足した | **pytest が収集する名前**（`tests/test_*.py` のファイル・`test_` で始まる関数）になっていて、**passed に数えられていること**（skipped / deselected ではない。`pytest -q -rs` の件数と skip 理由）。収集されない名前のテストは一度も走らず、何も言わない。Qt のテストはモジュール単位の `importorskip` で丸ごと skip されうる（§3）ので、収集されただけでは足りない |
| A7 | **変異を入れる前に、無変異の状態が green か**（対照） | 対照の結果。**red なら変異を 1 つも入れずに止める**（撃墜数が意味を持たないため）。手で壊すなら、次の変異の前に `git diff --quiet -- <file>` で戻っていることも確かめる。複製を変異させるなら、**無変異の複製で green を先に出す**（複製の置き場所で hook の git ルート判定などが変わると、全部が落ちる側に倒れる） |
| A8 | **検査の対象集合が、意図した集合になっているか**（列挙が静かに欠けていないか） | 対象件数と、**含む側・含まない側の両方**を固定したテスト。**0 件でないこと**も見る（壊れた列挙は「対象なし」で無害に見える）。列挙を旧実装へ戻すと red になる証跡 |
| A9 | **同じ事実が複数箇所に書かれていないか**（件数・検査名・出力書式・既定値。片方だけ直して隣が残る） | ツールが権威を持つ事実は**正本 1 か所**に置き、他所からはリンクで参照する。**コードのコメントに実測値を書かない**。正本と実物の一致を機械で照合できるなら、そのテストを置く |
| A10 | **測っている間に、測定が使う成果物が変わっていないか**（並行して走るビルド・同じ出力先を使う別の実行） | 評価・測定の開始時と終了時の `git rev-parse HEAD` と `git status --porcelain` が同じであること。違えば**症状ではなく前提の不備**として扱い、測り直す。yt-gui で実際に起きる形は、`docs-check` の作業ツリー修正と `evaluator` の `git` 参照の干渉（`/verify-gate` が直列化している理由）と、worktree 隔離で走るサブエージェント。ビルド成果物など作業ツリー外の入力を使う測定では、入口でハッシュを記録する |
| A11 | （**欠番**） | 雛形の A11「**雛形自身の木が、採用先の木の代表になっているか**」は、**雛形が自分をコピー元として配る**という前提の上に立つ項目で、採用先である yt-gui には対応する前提が無い。番号を詰めずに空けてあるのは、雛形との突き合わせで番号がずれないようにするため（下の「雛形との違い」） |
| A12 | **docs が「〜できます」と約束した挙動に、それを踏むテストがあるか** | **約束ごとにテストを 1 本持つ**こと。約束は docs にしか無く実装のどこにも錨が無いので、**壊しても誰も気づかない**（lint も型も pytest も反応しない）。実例: [`.claude/hooks/format_edited_file.py`](../../.claude/hooks/format_edited_file.py) の docstring は「ruff・対象ファイルのいずれかが見つからない場合や整形が失敗した場合も**黙って通す**（フェイルオープン）」と約束しているのに、`tests/test_format_edited_file.py` が `shutil.which` が `None` を返す分岐も `except OSError, subprocess.SubprocessError` の分岐も**踏んでいなかった** — **フェイルオープンの挙動だけを変えても**（`which` 不在で例外を送出する／整形失敗の握りつぶしを外す）lint / 型 / pytest がすべて green のまま通っていた。**早期 return そのものを消すと mypy が気づくが、それは型の網であって挙動の錨ではない**（`executable` が `str \| None` のまま渡る）。[#334](https://github.com/f8924919/yt-gui/issues/334) で錨を足した（`test_main_is_silent_when_formatter_is_missing` と `test_main_is_silent_when_format_fails`）。**約束の言葉づかいまで錨にすること** — 「黙って」は stdout だけでなく stderr も含む、と読んでテストを書いたので、stderr へ書く退行も red になる。**A8 と対** — A8 は「対象集合が欠けている」、A12 は「約束に錨が無い」 |

> **雛形との違い**（次回の突き合わせ用）: A1 — 雛形は一括ランナーが死因と `カバー N / M` を機械検査し、fail-closed は「ビルドを伴う変異テストはビルドの失敗で止める」。yt-gui は変異ごとの落ちたテスト名の表で、テストファーストの red も認め、fail-closed は「変異の適用・テストの起動・収集の失敗を死亡と数えない」に読み替えた。A6 — 雛形は「一括ランナーの登録簿に足す」。yt-gui は pytest の収集規則（同じ「足した検査が一度も走らない」型）。A7 — 雛形は `identity-control=ok` のトークン。yt-gui は手順としての対照。A10 — 雛形は成果物ハッシュと `pgrep` 禁止。yt-gui は HEAD と作業ツリーの一致。雛形の「shell で検査器を書く場合の既知の罠」の注記は、yt-gui の検査が Python なので持ち込んでいない。A11 — 雛形の A11（雛形の木は採用先の代表か）と、その共有フィクスチャ `scripts/adopter_tree.py` は取り込んでいない。yt-gui は**採用先**なので「自分の木が採用先の代表でない」という前提を持たず、雛形の A11 直後の blockquote（雛形の木が退化したインスタンスであること）も同じ理由で持ち込んでいない。**番号は詰めずに欠番**にしてある。A12 — 雛形は行末に「A11 と対」と書くが、A11 を取り込まないので yt-gui では「A8 と対」に読み替えた。
>
> **A1 の「撃墜数」だけでは足りない。** 「N/N 撃墜」は**「N 個の変異が red になった」**でしかなく、**狙ったテストを落としたか**は別問題である。変異が別の場所に当たっていたり、対象のテストに到達する前に落ちていたりしても「死亡」と出る。**各変異で落ちたテスト名を並べ、狙ったテストが含まれているかを見る。**
>
> **A7 は A1・A4 と別物である。** A1 は「対象を壊したら red になるか」（片側）、A4 は「追跡下のファイルを壊していないか」（無傷性）を見る。**どちらも「全部落ちる」側を見ていない。** 変異と無関係な理由で必ず落ちる状態（依存が無い・前の変異が戻っていない等）だと、**どんな変異も「死亡」と報告される**。
>
> **A8 は「見ているつもりの範囲が実際より狭い」を防ぐ。** 検査そのものが正しくても、**対象が欠けていれば green は「問題が無い」ではなく「見ていない」**を意味する。典型は `git ls-files` による列挙（追跡済みしか返さないので**未追跡の新規ファイルが初コミットまで素通り**する。`--cached --others --exclude-standard` にする）。

### 8.2 型 B: 「観測できない」を「起きていない」と読む

観測手段の側に穴があるのに、対象側の不在として結論する形です（ログの出力先が違う・キャッシュがあると出ない行を待っていた・観測のために付けたオプションが挙動を変えていた、など）。

| # | 見るもの | 出すもの |
|---|---|---|
| B1 | 「〜が出ない／起きない」と書こうとしている箇所 | **同じ事象を別経路で見た結果**（ログとデバッガ、出力ファイルと実行時トレース、のように 2 つ目の観測路）。1 経路なら「観測できなかった」と書き、「起きていない」とは書かない |
| B2 | 否定形の主張 | **独立に実行した run 3 回以上**の一致。run 数を報告に書く |
| B3 | 観測手段が対象に影響しうるか（ブレークポイント・トレース・タイミングを変えるオプション） | 観測手段の有無で結果が変わらないことを確かめた run、または「観測が対象を変えうる」注記 |
| B4 | 「前は出ていたのに出なくなった」 | 比較 2 run の**条件表**（入力のハッシュ・対象のコミット・オプション・環境）。1 軸でも突き合わせていなければ比較は成立しない |

### 8.3 型 C: 3 点が揃う前に原因を宣言する

原因の同定は **(1) コード位置 (2) 判定の構造（何と何を比べてどう分岐したか） (3) 判定対象の実値** の 3 点が揃って初めて言えます。揃う前に宣言して外した例が繰り返されています（雛形 claude-templates の採用プロジェクトでの事例。古いコミットメッセージの説明を信じて 2 回誤る・条件の違う run を「退行」と読む）。

| # | 見るもの | 出すもの |
|---|---|---|
| C1 | 「原因は〜」と書く箇所 | 3 点それぞれの所在（`path:line`／擬似コード／実値）。**1 点でも欠けていれば「仮説」と書く** |
| C2 | 過去のコミットメッセージ・タスクメモ・docs に書かれた説明を根拠にする箇所 | **現在のコードで再確認した結果**（説明は書かれた時点の理解であり、その後の変更で成立しなくなっていることがある） |
| C3 | 分岐表・場合分け（「A なら X、B なら Y」）を作った後で、道具（ビルド・入力・スクリプト）の前提が変わった | **表を引き直した**こと（古い表に新しい観測を当てると、存在しない分岐に入れて誤る） |
| C4 | 決定実験（判定対象だけを変えて症状が消える／現れる）ができるか | 実験の結果。できない場合はその理由 |
| C5 | 測定のたびの記録 | ログ先頭のメタ行（対象のコミットハッシュ・入力のハッシュ・主要オプション）。**メタ行が無いログは比較の根拠に使わない**。**貼るハッシュは「表を書いた時点の HEAD」ではなく「その数値を出した実行の作業ツリー」**（コミットハッシュ。未コミットの変更があればその旨。測定・変異の実行の**直後に控える**） |
| C6 | **数・件数・回数**を、受け入れ条件・Issue 本文・タスクメモへ書く箇所。**出所は問わない** — サブエージェントの報告から引く数も、自分が暗算した数も、自分で流したコマンドの出力を読んだ数も同じに扱う（書き先はこの 3 か所で、PR 本文・Issue のコメントは対象にしない） | **一次資料（index・一覧・コマンドの出力などの機械出力）を自分で数えたコマンドとその出力**（回数・経緯は数えるのではなく、示された `path:line` を開いて確かめた旨）と、**数えた時点**（コミットハッシュ。未コミットの変更があればその旨）。**足した本数からの暗算・記憶・目視で書かない。** 数え方の道具は**1 行に複数ある一致を落とさないもの**を選び、**使う前に 1 行に複数一致する行で確かめて、プローブのコマンドと出力を証跡に残す**（**特定のコマンドを名指しで禁止にはしない** — **道具の癖は版に依存する**ので、性質と確かめ方で書く。確かめ方は「同じパターンで**一致数と当たった行数の両方**を採り、**一致数の方が多いこと**」。そういう道具が無い環境では、同じ正規表現を走らせて一致を並べて数える）。**行数と一致数を区別する。** 報告者の視野がそのまま母集団になる事故が繰り返し起きた（雛形 claude-templates の採用プロジェクトでの事例）— 「兄弟 5 本」を調査役が**その 5 本だけ見て**「前提はずれていない」と返し、一次資料を数えたら 16 本だった。**自分が書く数も同じように外れる** — yt-gui では [#326 のタスクメモ](../task/archive/326-template-backport.md)に「上流スモークのケースを『14 件』と書いた → `CASES` は 13 件（数えずに転記した）」が残っている |

> **C6 の適用範囲**: **出所を問わない**（上記）。サブエージェント側では `investigate` に限らず**報告一般**に掛かる（`criteria-review` / `design-review` / `implementer` / `verify` / `docs-check` / `evaluator`）。**「出所を添える」項目を agent 定義に置いてあるのは [`investigate`](../../.claude/agents/investigate.md) と [`implementer`](../../.claude/agents/implementer.md) の 2 本**で、前者は**母集団を数えることがジョブの中心**だから、後者は**報告に件数（実行したテストの件数・触ったファイルの数など）が必ず含まれる**から（他は評価・助言が主目的で、数はその副産物）。**副産物の数の転記事故は、受け手側であるこの C6 が拾う。** **主エージェント自身が書く数に対応する agent 側の項目は無い** — 報告する相手がいないので、C6 がそのまま唯一の歯止めになる。
>
> **§8.1 A9 との違い**: A9 は**書く場所**の規則（同じ事実を 2 か所に書かない・正本へリンクする）で、**C6 は書く前の手順**である — **数を書くなら、その数を自分で数えてから書く**。A9 に従ってそもそも書かないなら C6 は発火せず、A9 に反しない形で数を書く場面（受け入れ条件・Issue 本文・タスクメモ）では C6 が掛かる。
>
> **[Git 運用ルール](../git-workflow.md) §5.2「実装の委譲」の義務 2・4 との違い**: 義務 2 は「委譲した実装の対応表を件数の一致で済ませない」、義務 4 は「自分が分割したブリーフどうしの境界をまたぐ引用を洗う」、**C6 は「数そのものを、出所にかかわらず書く前に数え直す」**。義務 2 が最も近いが、**義務 2 は自分が渡した仕事の成果物を検証する場面**、**C6 は数を書く場面**である（報告から引くときも、自分で数えたつもりのときも同じに掛かる）。
