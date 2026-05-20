# 複数音声トラックのダウンロード機能 踏査メモ

[← 研究メモ目次](.)

## 1. 背景

現状の yt-gui は 1 ダウンロードあたり 1 音声トラックしか指定できない。
多言語動画（日本語＋英語の元音声）や、複数言語の dub 版が同一動画内で配信されているソース（YouTube の Multi-Audio Track、ニコニコ動画の多重音声、Twitch の VOD 等）では、現状以下のいずれかしか選べない。

- 自動 (`bestaudio`): yt-dlp の優先順位により 1 言語だけがダウンロードされる
- 特定 ID: 1 トラックを明示指定するが、他言語は捨てられる

「JP + EN の両方が欲しい」「言語別 MP3 を一括取得したい」というニーズに応える方法を yt-dlp 側で確認し、本アプリへの実装案を検討する。

---

## 2. 現状実装の確認

### 2.1 音声選択が単数になっている箇所

| ファイル | 箇所 | 内容 |
|---|---|---|
| `yt_gui/original_format_panel.py` | `_audio_combo: QComboBox` | 単一選択コンボ |
| `yt_gui/original_format_panel.py` | `get_format_spec()` | `{video_id}+{audio_id}` の 1:1 連結 |
| `yt_gui/original_format_panel.py` | `get_raw_settings()` | `audio_id: str \| None` を返す |
| `yt_gui/original_format_panel.py` | `_apply_pending_restore()` | `audio_id` を 1 つだけ復元 |
| `yt_gui/formats.py` | `fmt_mp3` の spec | `bestaudio/best` 固定（複数指定不可） |
| `yt_gui/downloader.py` | `download_video()` | `audio_only=True` 時に `FFmpegExtractAudio` を 1 回だけ適用 |

### 2.2 既に複数選択になっている類似機能

字幕は `_subtitle_list: _ToggleListWidget` で `ExtendedSelection` 設定されており、複数言語を同時に書き出せる仕組みが揃っている（言語コードを `subtitleslangs` に配列で渡す）。
**音声トラックの multi-select UI もこの字幕リストの実装パターンを流用できる**。

### 2.3 fetch 時点で言語情報は既に取得済み

`Downloader.fetch_formats()` で各 audio format について `f.get("language")` を読み、ラベルに `[ja]` のように埋め込んでいる（`original_format_panel.py` の `_run_fetch` → `_on_fetch_done`）。
複数音声選択時に「言語別にどのトラックを選ぶか」を提示する UI 要素は、データ的には追加コストなしで作れる。

---

## 3. yt-dlp 側の実現手段

### 3.1 複数音声を 1 つのコンテナに格納する（multi-stream merge）

#### 構文

```
-f "bv*+ID1+ID2" --audio-multistreams
```

または「映像 + 利用可能な全音声」：

```
-f "bv*+mergeall[vcodec=none]" --audio-multistreams
```

#### 仕組み

- 通常 `format1+format2` の `+` は **「動画 1 + 音声 1」までしか許容しない**。
- `--audio-multistreams`（Python API では `'allow_multiple_audio_streams': True`）を渡すと `+` 連結で **音声を複数指定可能になる**。
- 出力ファイルは内部に複数の音声ストリームを持つ単一メディアファイルになる。

#### 推奨コンテナ

- **MKV** が最も互換性が高い（任意の codec 組み合わせ・複数言語タグ・チャプターを許容）。
- MP4 でも複数音声は技術的に格納可能だが、AAC 以外の codec を含むと remux に失敗するケースがある。
- WebM は仕様上 Vorbis/Opus のみ。
- 結論: **複数音声マージ時は `merge_output_format='mkv'` 固定が安全**。設定の動画コンテナが MP4 / WebM でも、複数音声選択時はアプリ側で MKV に強制する判断が必要。

#### 言語タグ

- yt-dlp は `info["formats"]` の `language` を ffmpeg の `-metadata:s:a:N language=xxx` に渡してくれる（FFmpegMergerPP の挙動）ため、**プレイヤー側で言語を切り替えられる MKV が生成される**。

### 3.2 複数音声をそれぞれ別ファイルとして出力する（comma syntax）

#### 構文

```
-f "ID1,ID2"
```

複数 ID をカンマで区切ると、それぞれが**独立した outtmpl 適用で別ファイルとして保存**される。

#### Python API での挙動

- `'format': 'ID1,ID2'` を渡すと `download_video` 内の `with YoutubeDL(ydl_opts) as ydl:` のループで複数回ダウンロードが走る。
- `outtmpl` が衝突しやすいので、テンプレートに `%(format_id)s` または `%(language)s` を含める必要がある。
  - 例: `%(title)s.%(language)s.%(ext)s` → `動画名.ja.m4a` / `動画名.en.m4a`
- `FFmpegExtractAudio` ポストプロセッサは**各ファイルに対して個別に適用**される（言語別 MP3 を 2 つ得る、というユースケースに直結）。

#### 注意

- `progress_hooks` は各ファイルごとに発火する。アプリ側のプログレスバーは、複数ファイル分を「1 ジョブ」として進捗を表現する必要がある（例: 「2/2 ファイル目」を併記）。
- ファイル数の見積もり方法: `format` 文字列に含まれるカンマ数 + 1 でわかる。

### 3.3 そのほかの組み合わせ例

| 用途 | format 文字列 |
|------|----------------|
| 映像 1 + 音声 N をマージ | `bv*+ID1+ID2` (+ `--audio-multistreams`) |
| 映像 1 + 全音声をマージ | `bv*+mergeall[vcodec=none]` (+ `--audio-multistreams`) |
| 音声 N を別ファイル | `ID1,ID2` |
| 映像 + 音声 1 + 別途音声 1 | `bv*+ID1,ID2` (+ `--audio-multistreams`) — **片方は merge、片方は別ファイル**（コンマ後の `ID2` のみ独立ファイル） |

詳細は yt-dlp の README "FORMAT SELECTION" セクション、および `--audio-multistreams` のヘルプを参照。

---

## 4. ユースケース整理

| # | シナリオ | 想定操作 | 出力 |
|---|----------|----------|------|
| A | 多言語動画を 1 ファイルで保持し、プレイヤーで言語切替したい | オリジナル形式 → 映像 1 + 音声を JP/EN 両方選択 | 単一 MKV、複数音声トラック |
| B | 同じ動画から JP / EN の MP3 を両方欲しい | オリジナル形式 → 「音声のみ」モード → JP/EN 両方選択 | MP3 × 2 ファイル（言語別） |
| C | 高ビットレート版と低ビットレート版を両方保存 | オリジナル形式 → 同言語の 2 トラックを選択 | 別ファイル or 同ファイル内のマルチストリーム |
| D | 全音声トラックを自動取得 | 「全部入り」チェック相当のショートカット | 単一 MKV に全音声マージ |

A・B の優先度が高く、D は「便利オプション」として候補に入る。C は実需が薄いが副作用的に対応できる。

---

## 5. UI / 仕様案

検討対象は **オリジナル形式パネルのみ**（既存の `fmt_mp3` は「気軽に 1 トラック取得する」用途として残し、複数音声サポートは入れない）。

### 5.1 案 A: 音声コンボを multi-select リストに置き換え（推奨）

字幕リストと同じパターンで `_ToggleListWidget` を採用。

```
┌── オリジナル形式の詳細設定 ─────────────────────────────┐
│ 映像: [▼ 自動 (最良を選択)              ] [形式を取得]  │
│ 音声: ┌──────────────────────────────────┐              │
│       │ ☐ 自動 (最良を選択)              │              │
│       │ ☐ ダウンロードしない             │              │
│       │ ☑ opus (webm) [251] – 129kbps [ja]│              │
│       │ ☑ aac (m4a) [140] – 128kbps [en] │              │
│       │ ☐ aac (m4a) [139] – 48kbps [ja]  │              │
│       └──────────────────────────────────┘              │
│ 字幕: [...] (既存)                                       │
│ 出力: ● MKV に結合 (複数音声推奨)                        │
│       ○ MP4 に結合 (1 音声のみ)                          │
│       ○ remux のみ                                       │
│       ○ 音声のみ (MP3 192kbps)                           │
│       ☐ サムネイル ☑ メタデータ ☑ チャプター            │
└─────────────────────────────────────────────────────────┘
```

#### 動作ルール

| 選択状態 | 出力モード | 振る舞い |
|---|---|---|
| 1 トラックのみ | MP4/MKV/WebM 結合 | 従来どおり `{video_id}+{audio_id}` |
| 複数トラック | MP4 結合 | コンテナを **自動的に MKV へ昇格**（ステータスバーに通知） |
| 複数トラック | MKV 結合 | `{video_id}+{aid1}+{aid2}` + `audio-multistreams` |
| 複数トラック | 音声のみ (MP3/FLAC) | カンマ構文で `aid1,aid2` → 言語別の別ファイル出力 |
| 「自動」と他トラックを同時選択 | — | `自動` チェック時は他チェックを自動解除（排他） |
| 「ダウンロードしない」と他トラックを同時選択 | — | 同様に排他 |
| 複合フォーマット（★）映像選択時 | — | 音声リスト全体を無効化（現行と同じ挙動） |

#### 長所
- 字幕リストと UI が揃い、操作感が一貫する
- 複数選択 / 単一選択を同じウィジェットで扱える
- 「自動」「ダウンロードしない」が独立行として残るため後方互換が高い

#### 短所
- 音声トラックが 1 行で済む現状より縦方向のスペースを取る（リスト高さで 4 行程度は必要）。パネルの最小高さを調整する必要がある
- 「自動」「ダウンロードしない」を「単一の特殊行」として排他処理する分、`get_format_spec()` のロジックが複雑化する

### 5.2 案 B: 「複数音声を含める」チェック + 言語フィルタ

```
音声: [▼ 自動 (最良を選択)              ]
      ☑ すべての言語を含める  [▼ 言語: ja, en]
```

- チェックすると `bv*+mergeall[vcodec=none]` を選択し、必要に応じて `[language=ja]/[language=en]` の追加フィルタを噛ませる
- 単一・複数の切り替えがチェック 1 つで完結

#### 長所
- UI 追加要素が少なく、既存レイアウトをほぼ維持できる

#### 短所
- 「ビットレート違いの 2 トラック」など言語以外の選別ができない
- `language` が無い動画 / 音声に対するふるまいが不明瞭になる
- 言語フィルタコンボの操作系（multi-select ドロップダウン）が PySide6 にビルトインで存在しないため、自作する手間がある

### 5.3 案 C: 単一コンボ + 「追加音声トラック」リスト併設

```
音声: [▼ aac (m4a) [140] – 128kbps [en] ]     (主音声)
追加: ┌────────────────────────────────┐
      │ ☐ opus (webm) [251] – ja        │
      │ ☐ ...                           │
      └────────────────────────────────┘
```

#### 長所
- 「主音声」「副音声」の役割が UI に表れる
- 単一選択を期待する既存ユーザーへの破壊が小さい

#### 短所
- 主/副の概念は yt-dlp のフォーマット文字列には反映されない（順序差のみ）
- 排他ロジックが二重になる（主側の選択を追加側で再表示しない等）

### 5.4 推奨

**案 A（multi-select リスト）を採用**する。

理由：
- 既存の字幕リスト実装と同じパターンで保守コストが低い
- 複数音声・単一音声の切り替えが「リスト内の選択数」で表現でき、専用フラグが不要
- ユースケース A〜D いずれにも対応可能

---

## 6. フォーマット文字列の生成ロジック改定

`OriginalFormatPanel.get_format_spec()` を以下のように拡張する想定。

```python
audio_ids = [...]  # 選択された format_id のリスト（空 / 1件 / 複数）
# 「自動」「ダウンロードしない」は特殊状態として別フラグで保持
audio_auto = ...
audio_skip = ...

if audio_only:                       # 音声のみモード
    if not audio_ids:
        return "bestaudio/best"
    return ",".join(audio_ids)       # カンマ構文で別ファイル化

if is_combined:                      # ★ 複合フォーマット選択
    return video_id

if video_skip:                       # 映像ダウンロードしない
    if not audio_ids:
        return "bestaudio/best"
    return ",".join(audio_ids) if len(audio_ids) > 1 else audio_ids[0]

if audio_skip:                       # 音声ダウンロードしない
    return video_id or "bestvideo/best"

# 通常: 映像 1 + 音声 1..N
video_part = video_id or "bestvideo"
if not audio_ids:                    # 自動
    return f"{video_part}+bestaudio"
if len(audio_ids) == 1:
    return f"{video_part}+{audio_ids[0]}"
return f"{video_part}+" + "+".join(audio_ids)   # multi-stream
```

加えて `Downloader.download_video()` 側で次のフラグを切り替える：

| 条件 | yt-dlp 側設定 |
|---|---|
| 音声 ID が 2 個以上 + `+` 連結 | `allow_multiple_audio_streams: True`、`merge_output_format: "mkv"` を強制 |
| 音声 ID が 2 個以上 + カンマ連結 (音声のみ) | 何もしない（comma syntax は自動で複数 DL になる）。outtmpl に言語サフィックス挿入 |
| 音声 ID が 1 個以下 | 従来どおり |

---

## 7. データモデル変更

### 7.1 `_QueueItem`（`yt_gui/app.py`）

| 既存フィールド | 変更 |
|---|---|
| 暗黙: format_spec は単一文字列 | 変更不要（生成後の spec 文字列が複雑化するだけ） |
| `orig_settings: dict` | キー `audio_id` を `audio_ids: list[str]` に置換 |

### 7.2 `OriginalFormatPanel.get_raw_settings()` / `restore_from_settings()`

- `audio_id: str | None` → `audio_ids: list[str]`
- `is_combined`, `audio_skip` は維持
- 復元ロジック: `_apply_pending_restore` で list を順次 setSelected する

### 7.3 ツールチップ（`features/queue.md` 参照）

キューアイテムのツールチップに表示される「形式仕様」フィールドは、複数音声選択時に以下のように整形する。

```
形式: bestvideo+251+140 (+ audio-multistreams)
言語: ja, en
出力: MKV
```

---

## 8. 出力ファイル名テンプレート

### 8.1 音声のみ・複数選択時

カンマ構文では同一テンプレートから複数ファイルが生成されるため、**重複時の自動連番ロジック（`タイトル (1).mp3`）が衝突する**。代わりに言語コードをファイル名に組み込む。

| ケース | 出力 |
|---|---|
| 単一音声 (既存) | `動画タイトル.mp3` |
| 複数音声 (今回) | `動画タイトル [ja].mp3`、`動画タイトル [en].mp3` |

実装の方向性：
- アプリ側で `outtmpl` に `[%(language|und)s]` を後付け
- もしくは `%(format_id)s` を末尾に追加して衝突を回避（言語不明な場合のフォールバック）
- 既存のテンプレート（設定の「ファイル名タブ」で編集可能）との整合性を取るため、**「複数音声時のみ自動でサフィックスを挿入する」モードフラグ**を新設する

### 8.2 動画 + 複数音声マージ時

単一 MKV ファイルなのでテンプレートは現行のまま流用できる。コンテナ拡張子だけ `.mkv` に統一される。

### 8.3 既存テンプレート編集ユーザーへの影響

- 設定の OUTPUT TEMPLATE は「単独動画用」「プレイリスト用」の 2 種。複数音声・別ファイル化のために 3 種目（「複数音声時」）を増やすか、サフィックスを自動付加するかは要判断。
- まずは「自動サフィックス方式」で実装し、テンプレートそのものは触らせない方針が無難。

---

## 9. プログレス表示と進捗統合

`Downloader._progress_hook` は yt-dlp が format ごとに発火させる。複数音声・別ファイル時には:

- 1 アイテムにつき N ファイルダウンロードが連続して走る
- パーセンテージは N 分割で表示する（`(current_file - 1 + percent_of_current) / N`）
- ステータスラベルに `(2/2)` のような副カウンタを併記

実装上は `download_video()` 内で「カンマ含む format 文字列」を検出し `self._total_files = N` を立て、`_progress_hook` 内で `finished` イベントを使ってインデックスを進める方式が現実的。

---

## 10. 実装上の課題

### 10.1 コンテナ自動昇格（MP4 → MKV）の UX

**リスク度: 中**

複数音声を選んで「MP4 に結合」を選んでもアプリが勝手に MKV に切り替える挙動はユーザーを驚かせる。

対応案：
- 「複数音声選択時は MP4 出力に対応していません」というインライン警告ラベルを音声リスト直下に表示し、`MKV に結合` ラジオを自動選択する
- もしくは MP4 ラジオを動的に無効化（複数音声時のみ）
- 既存設定の動画コンテナ自体は変更しない（アイテム単位での昇格扱い）

### 10.2 言語情報がない音声トラックの扱い

**リスク度: 中**

YouTube 以外のサイト（xvideos、niconico の一部）では `language` が空のことがある。
複数音声を別ファイル出力する際、`%(language)s` が `NA` になるとファイル名衝突 → 上書きが発生する。

対応案：
- フォールバックとして `%(format_id)s` を併用したテンプレート（`動画タイトル [%(language,format_id)s].mp3`）
- 既存の重複回避ロジック（`タイトル (1).mp3`）と組み合わせる

### 10.3 「自動」「ダウンロードしない」の排他ロジック

**リスク度: 低**

multi-select リストでは特殊行を含む 5 行ほどが並ぶ。`自動 / ダウンロードしない` のいずれかが選ばれたら**他の音声 ID 行を強制解除**しないと意味不明な状態になる。

対応案：
- `_audio_list.itemSelectionChanged` シグナルで「自動」「ダウンロードしない」行が含まれていれば他をクリア
- 通常音声 ID が選ばれたら逆に「自動」「ダウンロードしない」を解除
- 字幕リストと違って排他ロジックが必要なので、`_ToggleListWidget` を継承して `_AudioListWidget` を新設するのが落ち着く

### 10.4 編集モードでの復元

**リスク度: 低**

`_pending_restore` の構造を `audio_ids: list[str]` に変えるだけ。既存の単一値で保存されていた古いキューアイテム（保存はしないので発生しない）への配慮は不要。

### 10.5 fmt_mp3 への波及

**リスク度: 低（スコープ外）**

`fmt_mp3` のシンプルさは維持する。「複数言語の MP3 を欲しい」ニーズは **「オリジナルの形式 → 音声のみ」経由** に誘導する。
ドキュメントとリリースノートで明示する。

### 10.6 字幕埋め込みとの相互作用

**リスク度: 低**

複数音声 + 字幕埋め込み（MP4 結合時のみ有効）の組み合わせは、MKV 昇格で `mov_text` 埋め込みパスが ass/srt 経路に変わる。
現行の `FFmpegSubtitlesConvertor` + `FFmpegEmbedSubtitle` は MKV でも動作するため新規対応は不要。テストで確認する程度。

### 10.7 サイト依存の不確実性

**リスク度: 中**

`--audio-multistreams` は YouTube・ニコニコでは安定動作する一方、サイトごとの抽出器の質に依存する。
xvideos のように `language` も `acodec` も空のサイトでは「複数音声」概念がそもそも存在しないが、UI 上は単一トラックしか返らないので問題は起きない（multi-select でも候補が 1 つしかない）。

---

## 11. 実装スコープ案

### フェーズ 1: 動画 + 複数音声を 1 MKV にマージ

- `OriginalFormatPanel` の音声コンボを multi-select リストに置換
- 複数選択時の `+` 連結フォーマット文字列生成
- `Downloader` 側で `allow_multiple_audio_streams: True` と `merge_output_format='mkv'` を渡す
- MP4 ラジオの自動 MKV 昇格 UX
- 編集モードでの `audio_ids` 復元
- `ja.py` / `en.py` への文字列追加
- `docs/spec/screens/original-format-panel.md` 更新
- テスト: `_AudioListWidget` の排他ロジック / format 文字列生成

### フェーズ 2: 音声のみモードで複数音声を別ファイル出力

- カンマ構文での `format` 文字列生成
- outtmpl への言語サフィックス自動挿入
- 進捗表示の N 分割
- `download_video()` の `audio_only` 経路で複数ファイル分の重複回避処理

### フェーズ 3: 便利オプション（任意）

- 「すべての音声を含める（MKV）」ショートカットチェック（`mergeall[vcodec=none]`）
- キュー追加時のプリセット保存

### 対応しないもの

- `fmt_mp3`（簡易モード）への複数音声対応
- 異なる動画間（プレイリスト跨ぎ）の音声を合成する機能
- 音声トラックのオフセット / ミキシング

---

## 12. 影響ファイル一覧（実装時）

| ファイル | 変更内容 |
|---|---|
| `yt_gui/original_format_panel.py` | 音声 multi-select リスト・排他ロジック・`audio_ids` 化 |
| `yt_gui/downloader.py` | `allow_multiple_audio_streams` 切替・MKV 昇格・複数ファイル時の outtmpl 拡張・進捗 N 分割 |
| `yt_gui/app.py` | キューペイロード（`audio_ids`）・ツールチップ表示・MKV 昇格時のステータス通知 |
| `yt_gui/formats.py` | `fmt_original` 経路で渡される spec が複雑化するが定義側に変更なし |
| `yt_gui/locales/ja.py` / `en.py` | 「複数音声選択時はMKVへ自動昇格」「N 言語選択中」等のメッセージ |
| `docs/spec/screens/original-format-panel.md` | UI レイアウト・フォーマット文字列生成ロジック表の更新 |
| `docs/spec/features/download-formats.md` | 複数音声時の format 文字列例を追記 |
| `docs/spec/features/download-behavior.md` | 複数音声 / 言語別ファイルの命名規則を記載 |
| `tests/` | `OriginalFormatPanel.get_format_spec()` の単体テスト追加（複数音声パターン） |

---

## 13. 未検証事項（実装前に確認したい点）

1. PyInstaller バンドル版の ffmpeg で `--audio-multistreams` 相当の動作（複数 audio stream のマージ）が問題なくこなせるか
2. YouTube の Multi-Audio 動画で `language` フィールドが正しく付くか（一部のリージョン制限動画で空になる報告あり）
3. ニコニコ動画・Twitch VOD など主要対応サイトでの実機検証
4. 複数音声を選んだ際、字幕埋め込み + メタデータ埋め込みのポストプロセッサ順序が壊れないか（`_StripLiveChatBeforeEmbedPP` との競合）
5. カンマ構文で複数 MP3 抽出した際、`progress_hooks` がどう連続発火するか（1 ファイル完了で `finished` が来た後に次が `downloading` から再開する想定）

---

## 14. 参考

- yt-dlp README "FORMAT SELECTION": https://github.com/yt-dlp/yt-dlp#format-selection
- yt-dlp Wiki — multi-audio tracks: README 内 `--audio-multistreams` / `--video-multistreams` 節
- 既存研究: [plugin-manager-research.md](plugin-manager-research.md), [gallery-dl-integration.md](gallery-dl-integration.md)
