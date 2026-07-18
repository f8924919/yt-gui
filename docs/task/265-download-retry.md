# #265 download_binaries: 取得リトライと診断情報の追加

- Issue: [#265](https://github.com/f8924919/yt-gui/issues/265)（背景・確定方針・受け入れ条件の正本）
- ブランチ: `feature/265-download-retry`
- 設計の正本: [build.md](../build.md) 「台帳 `bin/pins.json`」節（リトライ挙動の追記）

## 主要判断

| 論点 | 判断 |
|---|---|
| 適用範囲 | `_download_verified` 経由の 4 系統（deno / ffmpeg-win / ffmpeg-mac zip / ffmpeg-linux）。mac arm64 の `verify: binary` 経路は対象外（発端の障害と無関係・必要時に拡張） |
| リトライ対象 | `_download` の例外全般＋sha256 不一致。**sha256 未設定（設定エラー）は即時中断・リトライなし** |
| 診断情報 | 毎試行の失敗時に print（サイズ・Content-Length・先頭 16 バイト hex）。`_verify_sha256` が不一致時にファイルを削除するため照合**前**に取得 |
| `_download` | `urlretrieve` → `urlopen` チャンク書き込みへ変更し Content-Length を返す。**timeout=300・UA ヘッダーを付与**（refresh_pins.py と同イディオム。同一ランナーで refresh_pins のみ成功した観測に基づく design-review 指摘）。試行前に部分ファイルを `unlink(missing_ok=True)` で削除 |
| テスト注入 | `retries` / `backoff_initial_sec` / `sleep` を引数注入。`_download` は monkeypatch。実待機なし |
| design-review | investigate 推奨 yes（共通経路への影響・実装候補複数）→ 実施 |

## 進捗

- [x] Issue 更新・受け入れ条件の具体化（criteria-review 指摘反映）
- [x] docs 先行（build.md・testing/policy.md スコープ表）
- [x] design-review（指摘反映: timeout 必須・UA/実装イディオムを refresh_pins に整合・分岐は `expected` 真偽＋相互参照コメント・バックオフは最終試行後に sleep しない）
- [x] テスト先行（リトライ成功/全滅/取得エラー/未設定即中断/診断出力×2 の 6 件・red 確認済み）
- [x] 実装 → green（600 passed・ruff/mypy クリーン。実ネットワークで `_download` の動作も確認）
- [ ] verify-gate
- [ ] PR

## リリース・検証（タスク完了後の続き）

マージ後に v0.6.3 をリリースし、手元の v0.6.2 から **実 GUI の自己更新**（新版検出 → 更新して再起動 → 差し替え → 再起動）で #262 修正の実地検証を行う（0.6.0/0.6.1 は自己更新不能のため、この検証は 0.6.2 起点が初）。
