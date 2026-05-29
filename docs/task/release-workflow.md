# GitHub Actions によるリリース自動化

対応 Issue: #5

## 背景

リリースバイナリのビルドはローカルで `uv run pyinstaller yt-gui.spec` を手動実行しており、クロスビルド非対応のため OS ごとに手作業が必要だった。バージョン更新からリリース公開までを自動化する。

## 方針

`pyproject.toml` の `[project] version` を単一ソースとし、`main` への push でこれを読み取り、`v{version}` タグの有無でリリース要否を判定する（コミット差分ではなくタグ有無で冪等判定）。

### ワークフロー構成（単一ワークフロー）

```
on: push (branches: main)
├ version-gate : pyproject.toml の version を読み、v{version} タグ未存在なら should_release=true
├ tag          : (should_release) v{version} タグを作成・push
├ build        : matrix(windows-latest / macos-latest / ubuntu-22.04) でビルド
└ release      : 成果物を集約し gh release create v{version} に添付
```

### 設計上のポイント

- **冪等性**: リリース可否を `v{version}` タグの有無で判定。再実行・バージョン無関係の push では `should_release=false` で②以降をスキップ。
- **PAT 不要**: `GITHUB_TOKEN` で作成したタグは別ワークフローを再トリガーしない仕様のため、`tag` → `build` → `release` を `needs` で同一実行内に連結する。
- **GPL 同意の自動化**: ビルド前に `uv run python scripts/download_binaries.py --yes` を実行。spec 内の再呼び出しは既存ファイルありでプロンプトをスキップする。
- **Linux 追加パッケージ**: `binutils`（objdump）・`file`（appimagetool）を apt で導入（[version-single-source.md](version-single-source.md) の検証メモ参照）。

### OS ごとの成果物パッケージング

| OS | ランナー | 成果物 | パッケージ方法 |
|---|---|---|---|
| Windows x64 | `windows-latest` | `yt-gui-{version}-windows-x64.zip` | `Compress-Archive dist/yt-gui/*` |
| macOS arm64 | `macos-latest` | `yt-gui-{version}-macos-arm64.zip` | `ditto -c -k --keepParent dist/yt-gui.app` |
| Linux x64 | `ubuntu-22.04` | `yt-gui-{version}-x86_64.AppImage` | spec が生成（そのまま添付） |

`ubuntu-22.04` を採用するのは glibc 互換性のため（より新しい glibc でビルドした AppImage は古い環境で起動しない）。

## 対象ファイル

- `.github/workflows/release.yml`（新規）
- `docs/build.md`（CI / リリース節を追記）

## 留意点

- **コード署名なし**: Windows は SmartScreen 警告、macOS は Gatekeeper でブロックされる。署名・公証は別タスク。
- **ffmpeg の取得**: サンドボックスでは取得元が HTTP 403 だったが、実 GitHub Actions ランナーからは到達可能なため特別な対応は不要。
- **Python 3.14**: `requires-python>=3.14` のため `uv python install 3.14` で明示取得する。

## 進捗 / 再開メモ（2026-05-29）

### 完了済み

- Issue #5 起票済み: https://github.com/f8924919/yt-gui/issues/5
- ブランチ `feature/5-release-workflow` を作成し、以下 4 ファイルをローカルコミット済み（**未 push**）。`Closes #5`。
  - `.github/workflows/release.yml`（新規）
  - `docs/build.md`（CI / リリース節を追記）
  - `docs/task/release-workflow.md`（新規・本ファイル） / `docs/task/index.md`（追記）
- `release.yml` の YAML 構文は検証済み（jobs: version-gate / tag / build / release）。

### ブロッカー（再起動の理由）

- `git push` がリモート拒否された: `refusing to allow a Personal Access Token to create or update workflow .github/workflows/release.yml without workflow scope`。
- 認証トークンに **`workflow` スコープ** が無いため、`.github/workflows/` 配下を push できない。
- → ユーザーが **`workflow` スコープ付き PAT を再発行**するためサンドボックスを再起動する。

### 次セッションの再開手順

1. トークンに `workflow` スコープが付いていることを確認（`gh auth status`）。
2. ブランチ確認: `git checkout feature/5-release-workflow`（ローカルコミット `617a0c6` が残っているはず）。
3. **コミット時の注意（重要・環境固有）**: `/c/` マウント FS は `O_TRUNC`（`>` 上書き）が効かず、`.git/COMMIT_EDITMSG` に旧メッセージのしっぽが残留し、新コミットへ混入する（実害確認済み）。加えて locale が `POSIX` のため heredoc 経由だと日本語が壊れる。日本語メッセージは必ず次の手順でコミットすること:
   1. メッセージを `/tmp/`（linux 側 FS）にファイルとして用意（Write ツール推奨）。
   2. **`rm -f .git/COMMIT_EDITMSG`** で削除（truncate は効かないので `rm` する）。
   3. `LC_ALL=C.UTF-8 git commit -F /tmp/msg.txt` でコミット。
   4. `git cat-file -p HEAD | tail` で末尾に余分なバイトが無いか必ず確認。
4. `git push -u origin feature/5-release-workflow`。
5. `gh pr create --base main`（本文は日本語、`Closes #5`）で PR 作成。
6. **ユーザー承認後**にマージし、ブランチ削除。マージ後に本タスクを「完了」へ更新。

### 動作確認（マージ後）

- ワークフローは `main` への push がトリガーのため、マージ自体ではバージョン据え置き（`v0.1.0` タグ未作成なら）で初回起動する点に注意。`pyproject.toml` の version が既存タグと同じならスキップ、新しければタグ作成〜リリースまで走る想定。初回は version を上げてから動作を確認するのが安全。
