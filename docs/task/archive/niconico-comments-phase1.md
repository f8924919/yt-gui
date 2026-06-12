# ニコニコ動画コメント取得 ― フェーズ 1: JSON ダウンロード対応

[← タスク一覧](index.md)

> 前提: [niconico-comments-verify.md](niconico-comments-verify.md) で `comments` JSON が取得可能であることを確認済みであること。

## 背景

ニコニコ動画 URL を入力した際、yt-dlp の `NiconicoIE._get_subtitles` が出力する **コメント JSON**（`lang='comments'`, `ext='json'`）を、`live_chat` と同様の経路で字幕トラックとしてダウンロードできるようにする。

フェーズ 1 のスコープは **JSON ファイルの保存まで**。ASS 変換 (フェーズ 2)・動画への統合 (フェーズ 3) は本タスクでは扱わない。

## 仕様

### `comments` lang の特別扱い（`yt_gui/downloader.py`）

既存の `_LIVE_CHAT_LANG = "live_chat"` パターンを汎用化し、`json` 専用・埋め込み不可なメタ字幕を 1 グループとして扱う。

```python
_LIVE_CHAT_LANG = "live_chat"
_COMMENTS_LANG = "comments"
_JSON_ONLY_SUB_LANGS = frozenset({_LIVE_CHAT_LANG, _COMMENTS_LANG})
```

#### `_StripLiveChatBeforeEmbedPP` の改名・拡張

- クラス名を `_StripJsonOnlySubsBeforeEmbedPP` に改名
- `requested_subtitles` から `_JSON_ONLY_SUB_LANGS` に含まれる lang を一括除外する
- 呼び出し側の `needs_strip_live_chat` 判定も「いずれかの json 専用 lang が選択されているか」に拡張する（変数名は `needs_strip_json_only_subs` に変更）

```python
sub_langs = (subtitle_opts or {}).get("subtitleslangs") or []
needs_strip_json_only_subs = (
    (subtitle_opts or {}).get("embed", False)
    and any(lang in _JSON_ONLY_SUB_LANGS for lang in sub_langs)
)
```

#### `fetch_formats()` の字幕ラベル生成

`live_chat` の専用ラベル（`orig_sub_live_chat_name`）と並列に `comments` 用ラベルを追加する。

```python
if lang == _LIVE_CHAT_LANG:
    subtitle_list.append(
        (f"{lang} – {t('orig_sub_live_chat_name')} [json]", lang, False)
    )
    continue
if lang == _COMMENTS_LANG:
    subtitle_list.append(
        (f"{lang} – {t('orig_sub_nico_comments_name')} [json]", lang, False)
    )
    continue
```

`automatic_captions_raw` ループ側でも `_LIVE_CHAT_LANG` と並べて `_COMMENTS_LANG` をスキップ対象に追加（自動キャプション側に紛れることは通常無いが防御的に揃える）。

### 字幕埋め込み時の自動除外

ユーザーが MP4 出力 + 字幕埋め込み ON で `comments` を選択したケースでも、ffmpeg に渡らないことが既存の strip 機構で保証される。JSON ファイル自体はディスクに保存される（既存の `live_chat` と同じ挙動）。

### `original_format_panel.py` の影響

特になし。字幕リストは `fetch_formats()` が返した `subtitles` 配列をそのまま表示するため、ラベルさえ追加すれば自動的にリストに現れる。`get_subtitle_opts()` の生成ロジックも変更不要。

### 翻訳キー

`yt_gui/locales/ja.py` / `en.py` に以下を追加:

| キー | ja | en |
|---|---|---|
| `orig_sub_nico_comments_name` | `ニコニコ動画コメント` | `Niconico comments` |

### キュー / 編集モード

字幕選択は既存の `subtitle_opts["subtitleslangs"]` 配列に `"comments"` が入るだけなので、`_QueueItem` の構造変更は不要。編集モード復元 (`_apply_pending_restore`) も既存ロジックで動作する。

### 出力ファイル名

yt-dlp の標準テンプレートに従い `{title}.comments.json` 形式で保存される（プレイリスト時は `output_template_playlist` のサブフォルダ配下）。OUTPUT TEMPLATE 設定とは独立。

## ドキュメント更新

- `docs/arch/downloader.md`
  - `_JSON_ONLY_SUB_LANGS` 定数の説明を追加
  - 「ポストプロセッサの順序」節の `_StripLiveChatBeforeEmbedPP` を `_StripJsonOnlySubsBeforeEmbedPP` に書き換え、対象が `live_chat` と `comments` の両方であることを明記
- `docs/spec/screens/original-format-panel.md`
  - 字幕リストの表示例にニコニココメント行を追加
- `docs/spec/features/download-behavior.md`（字幕節）
  - `comments` lang が JSON のみで埋め込み不可・MP4 でも自動で除外される旨を追記
- `docs/arch/locales.md` / `docs/spec/i18n.md`
  - 新キー `orig_sub_nico_comments_name` を追加

## 範囲外

- danmaku2ass による ASS 変換（フェーズ 2）
- 動画への統合 / 焼付け（フェーズ 3）
- ニコニコ生放送（live chat）の取得
- 既存の `live_chat` 取り扱いに対する挙動変更（rename のみで挙動は維持）

## テスト

[docs/testing/policy.md](../../testing/policy.md) で `downloader.py` (外部 I/O) は単体テスト対象外のため、追加テストは行わない。実機での動作確認で担保する。

実機確認項目:

- ニコニコ動画 URL 入力 → オリジナル形式パネルの字幕リストに「comments – ニコニコ動画コメント [json]」行が表示される
- 同行のみチェックして MP4 ダウンロード実行 → 動画 MP4 と `*.comments.json` の両方が出力される
- 字幕埋め込み ON + `comments` 選択 + MP4 → ffmpeg のエラーが出ず、MP4 には埋め込まれないが `.comments.json` は保存される
- YouTube 動画では字幕リストに `comments` 行が出ない（NiconicoIE 限定であることの確認）

## 想定リスク

- **yt-dlp の API 変更**: `_get_subtitles` が返す lang 名 `"comments"` は仕様化されていない。将来 yt-dlp 側で名前が変わる可能性は低いがゼロではない。検出失敗時の影響は「字幕リストに該当行が出ない」だけで、致命的ではない。
- **`live_chat` リネームの波及**: クラス名・変数名変更は内部 API。外部公開していないため後方互換は不要。

## ステータス

完了 (2026-05-24)
