# yt-dlp 更新 Phase A: バージョン表示＋更新チェック＋通知

- 関連 Issue: [#178](https://github.com/f8924919/yt-gui/issues/178)（親: [#119](https://github.com/f8924919/yt-gui/issues/119)）
- ステータス: 完了（PR [#182](https://github.com/f8924919/yt-gui/pull/182) マージ済み）
- ブランチ: `feature/178-ytdlp-update-phase-a`

## ゴール

実体更新は行わず、yt-gui / yt-dlp のバージョン表示と「より新しい yt-dlp が
あるか」の通知に徹する（Phase A）。実体の最新化は既存の週次 Dependabot →
再リリース配信で対応する。

## 設計判断（ユーザー確認済み）

- **メニュー構成**: ヘルプメニュー配下に **1 項目「バージョン情報 / 更新を確認」**
  に統合（バージョン併記＋更新照会を 1 フローに）。
- **結果表示 UI**: `QMessageBox`（カスタム `QDialog` は使わない）。
- **リリース導線**: 古い場合は yt-dlp の **GitHub releases**
  （`https://github.com/yt-dlp/yt-dlp/releases`）を既定ブラウザで開く。

## 実装方針

- 新規 `yt_gui/yt_dlp_update.py` に UI 非依存の純関数を切り出す。
  - `parse_latest_version(payload)` — PyPI JSON の `info.version` を取り出す。
  - `compare_versions(current, latest)` — `packaging.version` で比較し
    `UpdateStatus` を返す。
  - `check_for_update(current, *, fetch=...)` — PyPI 照会＋解析＋比較。HTTP は
    `fetch` 引数で差し替え可能（オフライン単体テスト用）。
- `yt_gui/__init__.py` に `get_yt_dlp_version()` を追加（`get_version()` 近傍）。
- `yt_gui/app.py` にヘルプメニュー＋ダイアログ・照会フローを追加。照会は
  `run_in_thread` でバックグラウンド実行し結果は Signal/Slot 経由で UI へ。
- i18n キーを ja/en に追加。

## 成果物

- spec: [docs/spec/features/yt-dlp-update.md](../../spec/features/yt-dlp-update.md)（Phase A 節を確定）
- arch: [docs/arch/yt_dlp_update.md](../../arch/yt_dlp_update.md)（Phase A 節・影響範囲表を確定）
- code: `yt_gui/yt_dlp_update.py`（新規）・`yt_gui/__init__.py`・`yt_gui/app.py`・`yt_gui/locales/{ja,en}.py`
- test: `tests/test_yt_dlp_update.py`（純関数のオフライン単体テスト）

## 受け入れ条件（Issue #178）

- [ ] yt-dlp / アプリの現バージョンを表示する。
- [ ] PyPI JSON API から最新版を照会し「最新／より新しい版あり」を通知する。
- [ ] 照会はメニューからの明示操作起点（起動時の自動通信なし）。
- [ ] 照会失敗を穏当に通知しアプリは継続（クラッシュしない）。
- [ ] ヘルプメニュー＋「バージョン情報 / 更新を確認」を追加する。
- [ ] 文言はすべて i18n 翻訳キー経由（ja/en 両対応）。
- [ ] 照会はバックグラウンドスレッド、結果は Signal/Slot でメインスレッドへ。
- [ ] 照会・比較ロジックは UI 非依存の純関数として切り出しオフライン単体テスト可能。
