# #168 ビリビリ動画のコメント（弾幕）ダウンロード対応

- 対応 Issue: [#168](https://github.com/f8924919/yt-gui/issues/168)
- ブランチ: `feature/168-bilibili-danmaku-comments`

## 目的

ニコニコ動画コメント機能を一般化し、ビリビリ動画の弾幕（yt-dlp の `danmaku` 字幕トラック、Bilibili XML 形式）も同じパイプライン（ASS 変換 / MKV ソフトサブ統合 / ハードサブ焼き込み）で扱えるようにする。

## 設計方針

- `comments`（ニコニコ・JSON）と `danmaku`（ビリビリ・XML）を「コンテナ埋め込み不可・サイドカー保存・danmaku2ass で ASS 化可能」な**コメント/弾幕字幕**として共通化する。
- `_JSON_ONLY_SUB_LANGS`（実体は XML も含むため誤称）→ `_SIDECAR_ONLY_SUB_LANGS = {"live_chat", "comments", "danmaku"}` に改称。PP クラス `_StripJsonOnlySubsBeforeEmbedPP` → `_StripSidecarOnlySubsBeforeEmbedPP` に追従。
- ASS 変換は lang → (拡張子, danmaku2ass フォーマット) のマップで分岐する。
  - `comments` → `.comments.json` / `-f NiconicoYtdlpJson2`
  - `danmaku` → `.danmaku.xml` / `-f Bilibili`
- 変換・統合・焼き込みの各メソッドは処理対象 lang を引数で受け取り、入力 `{stem}.{lang}.{ext}` / 出力 `{stem}.{lang}.ass` を組み立てる。MKV / ハードサブの出力名（`.with-comments.mkv` / `.hardsub.mp4`）は両形式で共通。
- 字幕リスト生成（`fetch_formats`）に `danmaku` の専用分岐を追加し、`danmaku – ビリビリ弾幕 (埋め込み不可・サイドカー保存) [xml]` として 1 行表示。自動字幕ループでは `_SIDECAR_ONLY_SUB_LANGS` でスキップ。
- UI（オリジナル形式パネルのコメントグループ）は表示条件を `comments` または `danmaku` のいずれか出現時に拡張し、グループタイトル等の文言を「コメント・弾幕」へ汎用化する。内部の `nico_comments` opts キー・グループ制御系ロケールキー（形式非依存）は維持し、表示文言と弾幕ラベル（`orig_sub_bilibili_danmaku_name`）を追加/汎用化する。
- 中断時クリーンアップ（`_is_cleanup_target`）に `.danmaku.xml` を追加。

## 受け入れ条件

Issue #168 を参照。

## 検証メモ

- `-f Bilibili` を採用。yt-dlp が `comment.bilibili.com/{cid}.xml` から取得するのはクラシック形式の弾幕 XML（`<i><d p="…">…</d></i>`）であり、danmaku2ass の `Bilibili`（オリジナル形式）に対応する。`Bilibili2` は 2.0 エンコーディング用のため不採用（Issue 本文も `Bilibili` に修正済み）。
- verify ゲート: ruff check / ruff format / mypy / pytest すべて green。
- evaluator: 受け入れ条件 9 項目すべて PASS。
