# ruff ルールセット・mypy 厳格化（A-3）

対応 Issue: [#212](https://github.com/f8924919/yt-gui/issues/212) / 親調査: [workflow-improvement-survey.md](workflow-improvement-survey.md) A-3

## 目的

静的解析の検査「強度」を引き上げ、バグ検出力を高める。検査「範囲」の対称化は A-2（#211）で完了済みが前提。

## 実測データ（2026-07-10・main = A-2 マージ後）

### ruff 候補ルールセット別の違反数

| ルールセット | 違反数 | 内訳・備考 |
|---|---|---|
| `B`（bugbear） | 2 | B009（自動修正可）・B017 |
| `SIM`（simplify） | 12 | SIM102×7・SIM105×2・SIM300×2・SIM115×1 |
| `C4`（comprehensions） | 0 | — |
| `RUF` | 878 | うち **840 件は RUF001/002/003**（全角文字の「曖昧な Unicode」誤検知。日本語コメント・docstring が原因）。残り 38 件 = RUF100（不要 noqa）×31・RUF059×4・RUF012×2・RUF043×1 |

- RUF100 の 31 件は大半が `# noqa: E402`。現行 ruff は `pytest.importorskip()` 後の import を E402 違反としないため不要化しており、削除して安全（`ruff check --select E402 tests/test_app.py` は pass を実測確認）。

### mypy 厳格化オプション別のエラー数

| オプション | エラー数 | 備考 |
|---|---|---|
| `check_untyped_defs` | 52 | 型注釈のない関数本体も検査。内訳: has-type×18・union-attr×12・func-returns-value×7・var-annotated×7 ほか。ファイル別: app.py×19・test_settings_dialog.py×15・test_app.py×11 ほか |
| 上記 + `strict_equality` + `warn_unused_ignores` | 52 | 追加検出 0（現状コストなしで将来のリグレッションを防げる） |
| `disallow_untyped_defs` | 451 | テスト関数を含む全関数に型注釈を強制。工数大 |

## 設計（採用案）

### ruff（pyproject.toml `[tool.ruff.lint]`）

- `select = ["E", "F", "I", "UP", "B", "SIM", "C4", "RUF"]`
- `ignore = ["RUF001", "RUF002", "RUF003"]` — 全角の句読点・括弧等を「曖昧な Unicode」と誤検知するため除外。本リポジトリはコメント・docstring・UI 文字列が日本語であり、指摘のほぼ全量（840/878 件）が誤検知
- 既存違反 52 件（B2 + SIM12 + RUF38）を修正して green にする

### mypy（pyproject.toml `[tool.mypy]`）

- `check_untyped_defs = true` — 型注釈のない関数本体も検査（+52 件を修正）
- `warn_unreachable = true` — 到達不能コード（バグの典型的兆候）を検出（+5 件を修正。design-review の提案を採用）
- `strict_equality = true` / `warn_unused_ignores = true` — 現状追加コスト 0 で有効化

### 見送り（理由の記録）

- **`disallow_untyped_defs`（451 件）**: テスト関数を含む全関数への型注釈強制は修正量が大きく、テスト関数の戻り値 `-> None` 注釈などの機械的追記が大半で検出力向上への寄与が薄い。`check_untyped_defs` で関数本体の検査は既に効くため、費用対効果から今回は見送り。将来導入する場合は `yt_gui/` 限定の override から段階導入する
- **RUF001/002/003**: 上記のとおり日本語プロジェクトでは誤検知が支配的。恒久 ignore とする

## 代替案との比較

| 案 | 内容 | 不採用理由 |
|---|---|---|
| 最小案 | B・SIM・C4 のみ追加（RUF 見送り） | RUF100/RUF012 等の残り 38 件は有用で修正コストも小さい。ignore 3 つで導入可能 |
| 最大案 | `disallow_untyped_defs` まで一括導入 | 451 件の修正は 1 PR の粒度を超え、大半が機械的注釈でレビュー負荷に見合わない |
| ALL 導入案 | `select = ["ALL"]` から ignore で絞る | 導入時の判断コストと誤検知の精査が大きく、Issue の意図（バグ検出に効く既知セットの追加）を超える |

## 進捗

- [x] 実測・設計案の作成（2026-07-10）
- [x] design-review（2026-07-10。設計妥当。warn_unreachable の追加提案を採用、pyproject へのインライン注記を推奨→採用。app.py 19 件の Qt 挙動変更リスクは低いと確認）
- [x] ユーザー承認（2026-07-10。RUF001-003 ignore・warn_unreachable 追加・1 PR コミット 3 分割を承認）
- [ ] 実装・違反修正・CI green
