# yt-dlp 本体の更新機能: 実装方式の決定

- 関連 Issue: [#119](https://github.com/f8924919/yt-gui/issues/119)
- ステータス: 完了（方式決定＋docs 作成）
- ブランチ: `feature/119-yt-dlp-update-design`

## ゴール（本タスク）

実装着手前の **方式判断（設計決定）**。受け入れ条件は「方式を決定し、採用方式の
spec/arch を起こす」まで。実体の実装は方式確定後に別 Issue で進める。

## 決定事項

- **採用方式: A→B 段階導入**
  - **Phase A（短期）**: yt-dlp / アプリのバージョン表示＋更新チェック＋通知。
    実体更新はせず既存の週次 Dependabot → 再リリースで配信。
  - **Phase B（本格）**: 最新 yt-dlp wheel をユーザー領域へ取得し、起動時に
    `sys.path` 先頭へ差し込んで freeze 同梱版を上書きする side-load。Python API は
    維持（`downloader.py` の import 経路は不変）。
- **C（バイナリ＋subprocess 再設計）は不採用**: `downloader.py` の進捗・
  キャンセル・PostProcessor を全面再実装することになりコストに見合わない。
- **Phase A の照会先: PyPI JSON API**（`pypi.org/pypi/yt-dlp/json` の
  `info.version`）。同梱が PyPI/uv パッケージでバージョン体系が一致し、Phase B の
  wheel 取得とも整合する。
- **実装フェーズの落とし込み: Phase A / Phase B を別 Issue 起票**。#119 は
  方式決定ハブとしてクローズする。
  - Phase A: [#178](https://github.com/f8924919/yt-gui/issues/178)
  - Phase B: [#179](https://github.com/f8924919/yt-gui/issues/179)

## 成果物

- spec: [docs/spec/features/yt-dlp-update.md](../../spec/features/yt-dlp-update.md)
- arch: [docs/arch/yt_dlp_update.md](../../arch/yt_dlp_update.md)
- index 追記: spec/index.md・arch/index.md
- #119 へ決定をコメント記録、Phase A / Phase B の実装 Issue を起票

## 備考

- 本タスクはコード変更を伴わない（docs ＋ 決定記録 ＋ 後続 Issue 起票）。
  そのためテスト追加は対象外。実装は Phase A / Phase B の各 Issue で
  テストファースト運用に従う。
