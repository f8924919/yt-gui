# Windows で拡張連携サーバーのポートフォールバックが発動しない不具合の修正

対応 Issue: [#201](https://github.com/f8924919/yt-gui/issues/201)

## 目的

Windows の `SO_REUSEADDR` 仕様差（LISTEN 中ポートへの bind が成功する）により、
`ExtensionServer` のポートフォールバック（8718→8719→8720）が Windows で発動しない
不具合を修正する。`tests/test_extension_server.py::test_server_falls_back_when_port_in_use`
が Windows で常に失敗する事象の根本原因。

## 設計判断（確定済み）

- **案 A を採用**: `ThreadingHTTPServer` サブクラスで `allow_reuse_address` を
  Windows のみ `0` にする（POSIX は `1` を維持＝TIME_WAIT 再バインド許容）。
- プラットフォーム分岐は `sys.platform` を引数に取る純関数に切り出し、
  Linux CI でも win32 分岐をテスト可能にする。
- Windows 実機確認はローカル開発機（Windows）の pytest で行い、結果を PR に記載。
- 設計: [docs/arch/extension_server.md](../arch/extension_server.md) の
  「bind の排他制御」節。

## 進捗

- [x] Issue 起票・受け入れ条件確定（criteria-review 反映済み・案 A 確定）
- [x] docs 先行: arch/extension_server.md に bind 方針を追記
- [x] 設計レビュー（design-review・§5.5 発火）: クラス属性で結線する技術的根拠
      （`bind_and_activate=True`）と Windows のポート「さまよい」許容仕様を docs に
      追記、テストに配線検証を追加
- [x] テスト先行（プラットフォーム分岐＋クラス配線の単体テスト追加）
- [x] 実装 → green（Windows ローカルで test_server_falls_back_when_port_in_use が
      pass するようになった。412 passed）
- [x] verify-gate（verify green / docs-check OK / evaluator 条件付き PASS＝PR 本文に
      Windows 実機結果を記載して確定）→ PR
