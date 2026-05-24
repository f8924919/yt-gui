# タスク一覧

`docs/task/` 配下のタスクの進捗を管理します。タスク追加・完了時にはこのファイルを更新してください。

## ステータス凡例

- **未着手** : 着手前
- **進行中** : 作業中（中断含む）
- **完了** : 対応済み

## タスク

| タスク | ステータス | 概要 | 更新日 |
|---|---|---|---|
| [refine-docs.md](refine-docs.md) | 完了 | CLAUDE.md と docs 構成の改善（言語ルール追加・arch/build ハブ新設・双方向リンク） | 2026-05-16 |
| [yt-dlp-output-template.md](yt-dlp-output-template.md) | 完了 | 設定画面へのOUTPUT TEMPLATE設定UIの追加 | 2026-05-16 |
| [fix-original-format-no-codec.md](fix-original-format-no-codec.md) | 完了 | codec 情報を返さない抽出器（xvideos 等）でオリジナル形式が「プレイリスト」誤判定される不具合の修正 | 2026-05-17 |
| [linux-appimage-build.md](linux-appimage-build.md) | 完了 | Linux 向け PyInstaller ビルド時の AppImage 自動生成 | 2026-05-17 |
| [original-audio-only.md](original-audio-only.md) | 完了 | オリジナル形式パネルの出力形式に「音声のみ」選択肢を追加 | 2026-05-17 |
| [multi-audio-download.md](multi-audio-download.md) | 完了 | オリジナル形式パネルの音声を multi-select 化し、複数音声トラックを MKV にマージできるようにする（フェーズ 1） | 2026-05-20 |
| [proxy-settings.md](proxy-settings.md) | 完了 | 設定ダイアログにプロキシタブを追加し、yt-dlp の `proxy` オプションを GUI から設定可能にする | 2026-05-22 |
| [niconico-comments-verify.md](niconico-comments-verify.md) | 完了 | ニコニコ動画コメント取得（フェーズ 0）: yt-dlp の `comments` JSON が danmaku2ass で変換可能かを事前検証する Go/NoGo ゲート | 2026-05-24 |
| [niconico-comments-phase1.md](niconico-comments-phase1.md) | 完了 | ニコニコ動画コメント取得（フェーズ 1）: `comments` lang を字幕リストに追加し JSON ファイルとして保存可能にする | 2026-05-24 |
| [niconico-comments-phase2.md](niconico-comments-phase2.md) | 未着手 | ニコニコ動画コメント取得（フェーズ 2）: danmaku2ass を PyInstaller でビルドして `bin/` に同梱し、コメント JSON を ASS に変換する | 2026-05-24 |
| [niconico-comments-phase3.md](niconico-comments-phase3.md) | 未着手 | ニコニコ動画コメント取得（フェーズ 3）: ffmpeg で動画 + ASS を MKV ソフトサブとして統合する | 2026-05-24 |
