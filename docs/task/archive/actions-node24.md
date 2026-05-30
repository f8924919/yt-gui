# chore(ci): GitHub Actions を Node24 対応バージョンへ更新

対応 Issue: #24

## 背景

ランナーで `actions/checkout@v4` / `astral-sh/setup-uv@v5` が Node.js 20 上で動作し、非推奨 annotation が出ていた（2026-06-16 以降 Node24 強制、2026-09-16 に Node20 削除予定）。`test.yml`・`release.yml` の両方で更新する。

## 調査: 最新メジャーと入力互換

`gh api repos/<action>/releases/latest` で最新メジャーを確認し、使用中の入力が各最新メジャーの `action.yml` に残っていることを確認した。

| アクション | 旧 | 新（最新メジャー） | 使用中の入力（存在確認済み） |
|---|---|---|---|
| actions/checkout | v4 | **v6** | `ref` |
| astral-sh/setup-uv | v5 | **v7** | `enable-cache` |
| actions/upload-artifact | v4 | **v7** | `name` / `path` / `if-no-files-found` |
| actions/download-artifact | v4 | **v8** | `path` / `merge-multiple` |

- アーティファクト系は v4 で API バックエンドが刷新されて以降同一バックエンドのため、upload v7 ↔ download v8 も相互運用可能。
- setup-uv は cache を明示 `enable-cache: true`（test.yml）で使用し、release.yml では未使用。`uv python install 3.14` は run ステップなのでアクション入力変更の影響なし。

## 実施内容

- `.github/workflows/test.yml`: checkout v4→v6 / setup-uv v5→v7
- `.github/workflows/release.yml`: checkout v4→v6（×3）/ setup-uv v5→v7 / upload-artifact v4→v7 / download-artifact v4→v8

> **注意**: `astral-sh/setup-uv` は最新リリースが v8.1.0 だが **`v8` の移動 major タグが未公開**で、`@v8` 指定は CI で `unable to find version v8` になる（実際に発生）。維持されている major エイリアスの最新は **v7**（`runs.using: node24` を確認済み）なので v7 を採用する。checkout は v6、artifact 系は upload v7 / download v8 の major タグが存在。各 `action.yml` の `runs.using` が node24 であることを確認済み。

## 検証

- 両ファイルの YAML 構文 OK。
- `test.yml` は本 PR の CI 実行で checkout@v6 + setup-uv@v8 の動作と Node20 annotation 消失を確認する。
- `release.yml` は release 実行を伴わないため YAML と入力存在確認まで（実動作は次回リリース時に確認）。

## 対象ファイル

- `.github/workflows/test.yml` / `.github/workflows/release.yml`
- `docs/task/actions-node24.md`（本ファイル） / `docs/task/index.md`

## 次アクション

1. コミット → push → `gh pr create --base main`（`Closes #24`）。
2. ユーザー承認後マージ。マージ後、本タスクを archive へ移動。
