# #134 coverage omit から app.py / settings_dialog.py を解除

- Issue: #134
- 親: #132 / PR #133（モーダル駆動テスト追加）
- 方針: [docs/testing/policy.md](../testing/policy.md) §1 段階導入・§5 カバレッジ運用

## 目的

#132 で `app.py` / `settings_dialog.py` のモーダル経路を手段B（offscreen + `QTimer`/静的メソッド固定）でテスト化したが、`pyproject.toml` の `[tool.coverage.run] omit` に両モジュールが残り計測へ反映されない。本タスクで `omit` から解除し計測対象へ含める。

## 変更内容

- `pyproject.toml`: `omit` から `yt_gui/app.py` / `yt_gui/settings_dialog.py` を削除
- `docs/testing/policy.md` §1 段階導入ノート・§5 を実態に合わせて更新

## 計測結果

| | 解除前 | 解除後 |
|---|---|---|
| TOTAL | 92%（1256 stmts） | 85%（2559 stmts） |
| `app.py` | omit | 66%（742 stmts / 252 miss） |
| `settings_dialog.py` | omit | 96%（561 stmts / 23 miss） |

低下要因はほぼ `app.py`（UI 構築・各種スロット等の配線部が未到達）。policy §5 の運用に沿って数値変動を許容し計測対象化する判断。`app.py` のカバレッジ引き上げはテスト追加で段階的に対応する。
