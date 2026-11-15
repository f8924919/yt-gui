# Windows の配布用ビルドで外部プログラムの起動時にコンソールウィンドウを出さない

> Issue: [#395](https://github.com/f8924919/yt-gui/issues/395)
> ステータス: 進行中
> ブランチ: `bugfix/395-hide-subprocess-console`
> 基点: `3922cdd`

受け入れ条件の正本は Issue。設計は [arch/downloader.md](../../arch/downloader.md) の「外部プログラムの起動（コンソールを出さない）」。1 PR で終わる小さなタスクなので archive に直接作った（docs-guide §4.2 の特例）。

## 原因（3 点）

- コード位置: `yt_gui/downloader.py` の `subprocess.run` 5 か所（danmaku2ass・区間の切り出し・チャプターごとの切り出し・MKV 統合・焼きこみ）。どれも `creationflags` を渡していない。
- 判定の構造: 配布用のビルドは `yt-gui.spec:178` の `console=False` でコンソールを持たない。Windows はコンソールを持たない親から起動したコンソールプログラムに新しいコンソール（ウィンドウ付き）を割り当てる。
- 実値: 下の「プローブ」。コンソールを持たない親（`pythonw.exe`）から起動した子の `GetConsoleWindow()` が、フラグ無しで `3671352`、`creationflags=0x08000000` で `0`。

## 進捗

- [ ] C1 起動を `_run_external` にまとめ、win32 では `creationflags=0x08000000` を単独で、他の OS では渡さない — 証跡: 未
- [ ] C2 `yt_gui/` で起動関数を直接呼ぶのが `_run_external` の中だけ（ast で読むテスト） — 証跡: 未
- [ ] C3 コンソールを持たない親から `_run_external` で起動した子がウィンドウを持たない（Windows でだけ走るテスト。対照が 0 なら skip） — 証跡: 未
- [ ] C4 配布用のビルドの焼きこみでウィンドウが開かない（ユーザーの目視） — 証跡: 未
- [ ] C5 arch に起動のしかたを書く — 証跡: 未

## プローブ（2026-11-15、探索の段）

ツールのセッションの親（`uv run python`）は `GetConsoleWindow()` が 0 で、子はフラグの有無にかかわらず 0 だった（対照にならない）。そこで親を `pythonw.exe` にした。

```
noflag 3671352
flag 0
```

## 訂正ログ

| 日付 | 誤って書いたこと | 正しくは | 原因と再発防止 |
|---|---|---|---|

## 次にやること

テスト先行（C1〜C3）→ 実装 → 変異 → red → `/verify-gate` → 配布用のビルドをユーザーに確かめてもらう（C4）。

訂正ログ: 0 件
