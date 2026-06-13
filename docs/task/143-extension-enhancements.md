# ブラウザ拡張の改善と README 更新（#143）

- Issue: #143
- ブランチ: `feature/143-extension-enhancements`
- 関連 spec: [browser-extension.md](../spec/features/browser-extension.md)
- 関連 arch: [extension_server.md](../arch/extension_server.md)
- 前タスク: [#140 browser-extension](archive/browser-extension.md)

## ゴール

ブラウザ拡張（`extension/`）の以下を改善し、あわせて README を現状に合わせる。

1. オプション画面の多言語化（ブラウザ UI 言語に追従、日本語/英語）
2. `manifest.json` の `name` / `description` を英語化
3. 拡張バージョンを `pyproject.toml` と同期（リリース時注入・単一ソース）
4. 拡張アイコンをアプリ本体（`assets/icon.png`）と統一
5. リリースで拡張 zip（`yt-gui-extension-{version}.zip`）を生成・添付
6. README をブラウザ拡張連携を含む現状に更新

## 設計メモ

### 多言語（要件 1・2）

- Chrome 標準の `_locales/<lang>/messages.json` + `chrome.i18n.getMessage()` を採用。
  ブラウザの UI 言語に自動追従し、未対応言語は `default_locale`（en）へフォールバック。
- `manifest.json` に `default_locale: "en"` を追加。
- `manifest.json` の `name` / `description` は英語固定（`__MSG_*__` は使わない＝要件 2）。
- `options.html` は文言を `data-i18n` 属性でマークし、`options.js` 読込時に
  `chrome.i18n.getMessage()` で差し替える。`<html lang>` も実言語へ更新。

### バージョン同期（要件 3）

- 単一ソースは `pyproject.toml` の `[project] version`。
- `scripts/sync_extension_version.py` が pyproject の version を読み、
  `extension/manifest.json` の `version` を書き換える（冪等）。
- `release.yml` の build ジョブで zip 化の前に実行し、配布 zip の version を一致させる。
- コミット済み manifest も本スクリプトで現行 version に揃える。
- テストは同期関数の単体（pyproject → manifest 反映）で担保。実行時の動的同期は行わない。

### アイコン（要件 4）

- `assets/icon.png`（589×589 RGBA）から 16/32/48/128 の PNG を生成。
- `scripts/build_extension_icons.py` で Pillow を用いて生成し `extension/icons/` に配置。
  生成物はコミットする（拡張は unpacked / zip 配布で同梱が必要なため）。
- `manifest.json` の `icons` と `action.default_icon` に各サイズを設定。

### リリース zip（要件 5）

- `release.yml` に拡張 zip 生成を追加。OS 非依存のため Linux ジョブ（または独立 step）で
  `extension/`（`_locales` / `icons` 含む）を `yt-gui-extension-{version}.zip` に固める。
- version 注入後に zip 化し、Release アセットへ添付。

## 受け入れ確認

- `uv run pytest` green / `ruff check .` / `ruff format --check` / `mypy yt_gui/`
- manifest が妥当な MV3（`default_locale` / `icons` / `action.default_icon`）
- 拡張 zip 生成 step が release.yml に存在し version と一致
- README に拡張連携の記載と現状反映
