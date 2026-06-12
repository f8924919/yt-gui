# Qt UI テストのサンドボックス内実行 可否調査

調査日: 2026-05-26
対象: `yt_gui/` の Qt UI モジュール (`app.py` / `original_format_panel.py` / `queue_controller.py` / `settings_dialog.py` / `log_dialog.py` / `thumbnail_cache.py` / `threading_utils.py`)

[← 研究メモ目次](.)

## 1. 調査の目的・前提

[docs/testing/policy.md](../testing/policy.md) の現行ポリシーでは、Qt UI 層・外部 I/O 層は `pytest-qt` 未導入のためテスト対象外 (`×` / `△`) になっている。今回のリファクタリング (フェーズ 1–7, 2026-05-25〜26) で構造は整ったが、Qt UI に対するリグレッション検出機構は依然として存在しない。

本メモは「サンドボックス（および将来の CI 環境）で `pytest-qt` ベースの UI テストを動かせるか」を、**実機で動作確認した結果を含めて** 整理する。採否未決の調査メモであり、実装には着手していない。

## 2. 結論

**動作する。** PySide6 6.11.1 + pytest-qt 4.5.0 + `QT_QPA_PLATFORM=offscreen` で、以下まで実機検証済み:

| 検証項目 | 結果 |
|---|---|
| `QPushButton` クリック → `clicked` シグナルの捕捉 | ✅ `qtbot.mouseClick` + `waitSignal` |
| `QLineEdit` への実キー入力 | ✅ `qtbot.keyClicks` |
| `OriginalFormatPanel` の構築・内部状態 assert | ✅ |
| `App` メインウィンドウのフル構築 | ✅（ダイアログ抑制が必要、§5 参照） |
| 起動直後の UI ステート (`add_button` / `url_entry`) | ✅ |

5 テスト合計の実行時間は **0.22 秒**。テスト 1 件あたりのオーバヘッドは小さく、現行のロジック層テスト 68 件と同じスイートに混ぜても支障ない見込み。

## 3. 動作に必要な要件

### 3.1 OS パッケージ

PySide6 wheel には Qt 本体は同梱されているが、Qt が依存する **C ライブラリは OS 側に必要**。Ubuntu 25.10 (questing) では以下の最小構成で `offscreen` プラットフォームが動く:

```bash
sudo apt-get install -y --no-install-recommends \
    libglib2.0-0t64 libdbus-1-3 libfontconfig1 libfreetype6 \
    libxkbcommon0 libgl1 libegl1 libx11-6
```

これがないと `from PySide6.QtCore import ...` の時点で `libglib-2.0.so.0: cannot open shared object file` で落ちる。

> Ubuntu 24.04 LTS 以降は `glibc` の `time_t` 64bit 化に伴い `libglib2.0-0` → `libglib2.0-0t64` 等にリネームされている。CI 環境の Ubuntu バージョンに合わせて調整が要る。

### 3.2 Python パッケージ

```toml
[dependency-groups.dev]
# 追加
pytest-qt = ">=4.5.0"
```

`pytest-qt` は `qtbot` フィクスチャと `PySide6` / `PyQt6` の自動検出を提供する。

### 3.3 環境変数

```bash
export QT_QPA_PLATFORM=offscreen
```

CI ホストにディスプレイがなくても Qt がウィンドウシステム経由を要求しないモードで動く。テスト固有なら `pyproject.toml` の `[tool.pytest.ini_options].env` か `tests/conftest.py` 先頭の `os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")` で固定するのが手堅い。

## 4. 動作確認に使ったコード

参考用のスニペット（採用時は `tests/test_app_smoke.py` 等として整える）:

```python
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLineEdit, QMessageBox, QPushButton


def _silence_modal_dialogs(monkeypatch):
    """offscreen では QMessageBox.warning/critical/information が無限ブロック
    するので、テスト中は no-op に差し替える。"""
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **kw: QMessageBox.Ok)
    monkeypatch.setattr(QMessageBox, "critical", lambda *a, **kw: QMessageBox.Ok)
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **kw: QMessageBox.Ok)


def test_pushbutton_click_signals(qtbot):
    btn = QPushButton("Click")
    qtbot.addWidget(btn)
    with qtbot.waitSignal(btn.clicked, timeout=500):
        qtbot.mouseClick(btn, Qt.MouseButton.LeftButton)


def test_yt_gui_app_can_construct(qtbot, tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    _silence_modal_dialogs(monkeypatch)
    from yt_gui.app import App

    win = App()
    qtbot.addWidget(win)
    assert win.windowTitle()
    assert win.format_combo.count() > 0
```

## 5. つまずきポイント・回避策

### 5.1 モーダル `QMessageBox` が offscreen で無限ブロック

最大の落とし穴。`QMessageBox.warning/critical/information` をモーダル表示すると `offscreen` プラットフォームではダイアログが返らずプロセスごとハングする。

`App` 初期化では `QTimer.singleShot(0, self._check_dependencies)` が遅延発火し、ffmpeg/ffprobe/deno が見つからないテスト環境では `QMessageBox.warning` が出る → `qtbot` 後始末でイベントループが回るタイミングでハング、という現象を実機で再現済み。

**回避策**: テスト側で `monkeypatch.setattr(QMessageBox, "warning", lambda *a, **kw: QMessageBox.Ok)` 等で no-op 差し替え。`conftest.py` の autouse fixture にまとめれば 1 箇所で済む。

### 5.2 `qtbot.addWidget()` だけではイベントループは回らない

ボタンクリックのスロットが `QTimer.singleShot` を仕込んだり、`run_in_thread` でワーカースレッドを起動する場合、テスト側で以下のいずれかが必要:

- `qtbot.waitSignal(signal, timeout=...)` でシグナル待ち
- `qtbot.waitUntil(lambda: predicate, timeout=...)` で条件待ち
- 最終手段: `QApplication.processEvents()` を手で回す

### 5.3 サンドボックス再起動でライブラリが消える

今回 `apt-get install` で入れた C ライブラリは `/etc/sandbox-persistent.sh` には載せていない。サンドボックス再起動で失われるため、継続利用するならセットアップスクリプトとして別管理にする必要がある（CLAUDE.md のルール上、shell completion 系を `/etc/sandbox-persistent.sh` に入れることは禁止、export 系のみ可）。

### 5.4 PR テンプレ・CI

GitHub Actions の `ubuntu-latest` (24.04) には今回必要なライブラリの大半がプリインストールされているが、`libegl1` 等が欠けていることがある。CI に乗せる場合はワークフローで `apt-get install` を明示するのが安全。

## 6. テスト対象として価値の高い箇所

`App` 全体を巻き取る E2E ではなく、**状態機械・分岐・データ変換** に絞るのが投資効率が良い。優先候補:

| 対象 | 検証したい振る舞い | 備考 |
|---|---|---|
| `QueueController` の編集モード遷移 | `enter_edit_mode` → UI 状態 → `apply_edit` / `cancel_edit` の遷移と `edit_mode_entered` / `edit_mode_exited` シグナル | フェーズ 2 で切り出し済み |
| `OriginalFormatPanel` の sentinel 経由選択 | AUTO/SKIP/format_id の `currentData()` ベース取得、言語切替後の論理状態維持 | フェーズ 5 で sentinel 化済み |
| `_AudioListWidget` の排他ロジック | AUTO ↔ SKIP ↔ 音声 ID の `_enforce_exclusivity` | sentinel 化と一緒に検証 |
| `threading_utils.run_in_thread` | 成功 (`on_done`) / 失敗 (`on_failed`) / 常時 (`on_finished`) のコールバック順序 | フェーズ 4 で作った helper、テスト未追加 |
| `_QueueTree` のコンテキストメニュー | `edit_format_requested` シグナル発火条件 (`waiting` のみかつ `is_editing()` が False) | フェーズ 7 でシグナル化済み |
| `_open_settings` / `_refresh_format_labels` | 言語変更あり/なしで `format_combo` が正しく再構築される | フェーズ 7 で集約済み |

これらは **構造を整えた直後で意図がコードに残っているうち** に書くと固定化しやすい。

**避けるべき領域**:
- ネットワーク I/O を伴う `Downloader.fetch_*` / `download_video` — pytest-qt の出る幕ではなく、yt-dlp を pytest-mock 等でモックする別アプローチが必要
- `ThumbnailCache` の HTTP 取得 — 同上、URL ライブラリのモックが必要
- ファイル衝突回避ロジック (`_resolve_unique_path`) — `tmp_path` で実 I/O テストする方が早い

## 7. 採否・次アクション (採否未決)

導入する場合の最小ステップ:

1. `uv add --group dev pytest-qt`
2. `tests/conftest.py` に `os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")` と `QMessageBox` 抑制 autouse fixture を追加
3. `docs/testing/policy.md` の Qt UI 行を `△` (部分対象) に格上げし、テスト対象スコープを明記
4. `pyproject.toml` の `[tool.coverage.run] omit` から対象モジュール (e.g. `queue_controller.py`) を外す
5. §6 の優先候補を 1–2 件ずつタスク化 (`docs/task/qt-ui-tests-{slug}.md`)
6. CI ワークフローに `apt-get install` の追加（必要なら）

導入しない場合の根拠としては「Qt UI 層の振る舞いは手動 QA でカバーしており、自動化コスト > リグレッション発生コスト」のときに限る。本リポジトリは個人開発の Windows/macOS デスクトップアプリで、変更頻度が落ち着けばその判断もあり得る。

## 8. モーダル UI 挙動のテスト手段と xvfb の採否（2026-06-12 追記）

§5.1 で触れた「モーダル `QMessageBox` が offscreen で無限ブロックする」問題を、**実 UI 挙動（ダイアログの開閉・ボタン押下・押下後の状態変化）まで検証したい**場合にどの手段があるか整理する。`xvfb` を使えば解決するか、という観点を含む。

### 8.1 現行 UI に存在するモーダル系

実装裏取り（2026-06-12 時点）:

| 種別 | 箇所 | 駆動形態 |
|---|---|---|
| `QMessageBox.warning/critical/information/question` | `app.py` / `settings_dialog.py` / `original_format_panel.py` / `original_format_dialog.py` 多数 | 静的メソッド（ネストイベントループ） |
| `QFileDialog.getSaveFileName / getExistingDirectory / getOpenFileName` | `settings_dialog.py:499,675,680` | 静的メソッド・既定でネイティブ |
| `QDialog.exec()` | `app.py:785,1087`（設定・オリジナル形式ダイアログ） | モーダル `exec()` |
| `QMenu.exec()` | `app.py:140`（キュー右クリック） | モーダル `exec()`。発火条件は `edit_format_requested` 等の**シグナルに切り出し済み**（§6） |
| クリップボード | `app.py:143` | 非モーダル |

D&D・システムトレイ・スクリーンショット用途は**コード上に存在しない**。

### 8.2 核心: xvfb はモーダルのブロックを解決しない

`exec()` / `getSaveFileName()` 等は「ユーザー操作を待つネストイベントループ」であり、**待つ相手がいないのは offscreen でも xvfb でも同じ**。ブロックは描画の問題ではなく論理（入力待ち）の問題なので、**xvfb に替えてもダイアログは自動では閉じない**。どの環境でも「プログラムから能動的に閉じる仕掛け」が別途要る。したがって論点は *offscreen vs xvfb* ではなく **モーダルをどう駆動するか** にある。

### 8.3 手段の比較

| 手段 | 概要 | テストできること | 追加コスト |
|---|---|---|---|
| **A: offscreen + 静的メソッド monkeypatch（現状）** | `QMessageBox.*` を no-op 化し戻り値固定、`QFileDialog.get*` も canned 値を返す（`conftest.py` の `_silence_qt_modal_dialogs` が前者を実施） | ダイアログ呼び出し**後の分岐ロジック**（Yes→削除実行、パス選択→設定反映 等） | なし・高速。**ダイアログ自体の描画/実クリックは不可** |
| **B: offscreen + `QTimer` でモーダルを能動的に閉じる**（推奨ゾーン） | `exec()` の**前**に `QTimer.singleShot(0, ...)` で `QApplication.activeModalWidget()` を取得→ボタン click / `accept()`。`QFileDialog` は `DontUseNativeDialog` で Qt ウィジェット版にして `qtbot` で操作 | 「ダイアログが**実際に開くか**」「ボタン押下で**状態がどう変わるか**」まで **offscreen のまま**到達（`QMessageBox` / `QDialog` サブクラス / 非ネイティブ `QFileDialog`） | **xvfb 不要・OS 依存増なし**。要求の大半をここで満たせる |
| **C: xvfb + xcb プラットフォーム** | `Xvfb :99` 起動・`DISPLAY` 付与・`QT_QPA_PLATFORM=xcb`（または `xvfb-run -a`） | **実描画が要る場合のみ**: スクリーンショット/ビジュアル回帰、ネイティブ `QFileDialog` そのもの、WM 依存挙動（フォーカス・`activateWindow()`・ジオメトリ・raise／要・軽量 WM） | **大**: `libxcb-*` 一式（icccm/image/keysyms/randr/render-util/shape/xinerama/xfixes・xkbcommon-x11 等）・起動が遅く flaky 化しやすい・CI に `xvfb-run`。**モーダル駆動は B と同じく別途必要** |
| **D: xvfb 上でフル E2E** | アプリ全体を起動し通し操作 | — | [policy.md](../testing/policy.md) §2.4 が **`×`（導入しない）**。§6 の方針（状態機械・分岐に絞る）とも矛盾 |

### 8.4 本リポジトリでの結論

- 既存設計は**意図的に `exec()` を避ける方向**（コンテキストメニューはシグナル化済み）。追加で押さえたい UI 挙動（設定ダイアログ保存・`question` 分岐・ファイル選択後の状態反映）は **手段 B で offscreen のまま到達できる**ものがほとんど。
- **xvfb を入れる正当な理由は「スクリーンショット/ビジュアル回帰」か「ネイティブダイアログそのものの検証」に限られる**。個人向けデスクトップアプリの現状では投資対効果は低い。
- 推奨順序: **(1)** 手段 B を追加依存ゼロで導入 → **(2)** ビジュアル回帰が必要になった時点で初めて手段 C（xvfb）を検討。

## 9. 参考

- pytest-qt: <https://pytest-qt.readthedocs.io/>
- Qt offscreen platform: <https://doc.qt.io/qt-6/qpa.html>
- 本リポジトリの既存テスト方針: [docs/testing/policy.md](../testing/policy.md)
- 検証対象モジュール: [docs/arch/index.md](../arch/index.md)
