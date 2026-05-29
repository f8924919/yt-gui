# ニコニコ動画コメント取得 ― フェーズ 3: ffmpeg ソフトサブ MKV 統合

[← タスク一覧](index.md)

> 前提: [niconico-comments-phase2.md](niconico-comments-phase2.md) 完了

## 背景

フェーズ 2 で生成した `*.comments.ass` を、動画ファイルへ **MKV ソフトサブ字幕トラック**として埋め込む。再エンコード不要のため低リスクかつ高速で、ユーザーは再生時に字幕オフで通常動画として視聴することもできる。

ハード焼付け（動画フレームへの直接描き込み）は本タスクのスコープ外。将来のフェーズ 4 として別タスク化する。

## 仕様

### UI 追加（`OriginalFormatPanel`）

フェーズ 2 で追加した「ニコニコ動画コメント」グループ内に、ASS 変換チェックの直下に以下を追加:

| ウィジェット | キー | 説明 |
|---|---|---|
| `QCheckBox`（MKV にコメントを統合） | `chk_nico_embed_mkv` | 既定 OFF。ON 時は `chk_nico_convert_ass` を強制 ON にする |

**前提条件・排他**:

- `chk_nico_embed_mkv` ON → `chk_nico_convert_ass` を強制 ON（再帰的依存）。UI 上は ASS チェックをグレーアウトせず、自動同期する
- 出力モードが「音声のみ」「remux のみ」の場合は本チェックを無効化（音声のみ・remux は本機能の対象外）
- 出力コンテナが MP4/WebM の場合でも本チェック ON にした時点で **MKV 自動昇格**を行う（multi-audio と同じパターン）

### 解像度の自動追従

ASS のコメント描画には解像度指定が必須（フェーズ 2 では 1920x1080 固定）。フェーズ 3 では:

- フォーマット取得結果（`fetch_formats` の `info.formats`）から選択中の映像 ID の `width` / `height` を抽出し、ASS 変換時の `-s {w}x{h}` に渡す
- `OriginalFormatPanel.get_raw_settings()` の `nico_comments` dict に `auto_resolution: bool`（既定 True）を追加。OFF 時は手動入力値を使う
- 取得不能な場合は手動値にフォールバック

### `Downloader.download_video()` の拡張

`nico_comments_opts` に `embed_to_mkv: bool` を追加。`True` の場合の処理フロー:

1. yt-dlp で動画 + `*.comments.json` をダウンロード
2. danmaku2ass で `*.comments.ass` を生成（フェーズ 2 既存処理）
3. ffmpeg で動画 + ASS を **新規 MKV** に結合（`-c copy -c:s ass`）
4. 中間ファイル（元動画・ass・json）は **既定で残す**（OUTPUT TEMPLATE の挙動と整合）

```python
def _embed_ass_to_mkv(video_path: str, ass_path: str, out_path: str) -> None:
    cmd = [
        _ffmpeg_path(),
        "-y",
        "-i", video_path,
        "-i", ass_path,
        "-map", "0",
        "-map", "1",
        "-c", "copy",
        "-c:s", "ass",
        "-metadata:s:s:0", "title=ニコニコ動画コメント",
        "-metadata:s:s:0", "language=jpn",
        out_path,
    ]
    subprocess.run(cmd, check=True, capture_output=True, text=True)
```

#### MKV 出力名

`{title}.with-comments.mkv` で保存。`OUTPUT TEMPLATE` の解決後ファイル名に `.with-comments` サフィックスを挿入する。`{title}.mkv` をそのまま上書きする選択肢はファイル名衝突回避ポリシー違反になるため採用しない。

#### 同名ファイルの衝突回避

既存の `(n)` サフィックス機構を再利用。

### MKV 自動昇格との衝突

multi-audio タスクで既に `+` を 2 個以上含む場合の MKV 強制ロジックが存在する。本機能は **MKV 出力**そのものではなく、**追加で MKV 化された統合ファイルを生成**するため、yt-dlp 自体の `merge_output_format` には触らない。

- 動画本体: ユーザー設定どおりに MP4/WebM/MKV のいずれかで出力
- 統合ファイル: 別途 `{title}.with-comments.mkv` を生成

例外: ユーザーが「remux のみ」を選択している場合は元コンテナ尊重のため、コメント統合チェックを無効化（前述）。

### 動画解像度の取得経路

`fetch_formats()` の戻り値構造に `width` / `height` をフィールド追加する案と、`OriginalFormatPanel` が選択中映像 ID の元 dict を保持する案がある。後者の方が変更が小さいため推奨:

```python
# 映像コンボの itemData に {"fid": str, "width": int|None, "height": int|None} を入れる
```

### 翻訳キー追加

| キー | ja | en |
|---|---|---|
| `nico_embed_mkv` | `コメントを MKV に統合` | `Embed comments into MKV` |
| `nico_auto_resolution` | `動画の解像度を自動使用` | `Auto-detect video resolution` |
| `status_nico_mkv_created` | `コメント統合 MKV を生成しました: {filename}` | `Created MKV with comments: {filename}` |

### キュー / 編集モード

`nico_comments` dict に `embed_to_mkv` / `auto_resolution` キーを追加。既存の get/restore に乗る。

### ドキュメント更新

- `docs/spec/screens/original-format-panel.md`
  - ニコニコ動画コメント節に MKV 統合チェック・解像度自動追従の項を追記
- `docs/spec/features/download-behavior.md`
  - 「コメント統合 MKV」節を追加
- `docs/spec/overview.md`
  - 主な機能リストに「ニコニコ動画コメント統合」を追加
- `docs/arch/downloader.md`
  - `_embed_ass_to_mkv` の実装メモを追記
- `docs/arch/original_format_panel.md`
  - `nico_comments` dict のフィールド一覧を更新

## 範囲外

- ハード焼付け（再エンコード式）。将来のフェーズ 4
- コメント色・フィルタ（NG ワード等）のカスタマイズ
- 既に MKV になっている動画への in-place 字幕追加（常に別ファイルを生成）

## テスト

`downloader.py` 内のサブプロセス呼び出しはテスト対象外（既存方針通り）。

実機確認項目:

- ニコニコ動画 URL + `chk_nico_embed_mkv` ON で MP4 出力選択 → 元 MP4 + `*.comments.json` + `*.comments.ass` + `*.with-comments.mkv` の 4 ファイル
- 統合 MKV を VLC/MPV/mpv で開き、字幕トラックがオン/オフでコメントが表示・非表示されることを確認
- `auto_resolution=ON` で 1080p 選択 → ASS が 1920x1080 で生成される
- `auto_resolution=ON` で 720p 選択 → ASS が 1280x720 で生成される
- 「remux のみ」「音声のみ」選択時は MKV 統合チェックが disable
- `chk_nico_embed_mkv` ON + ASS 変換 OFF の遷移で ASS 変換チェックが自動 ON になる
- 同名 MKV が既に存在する状況で実行 → `(1)` サフィックス付きで保存される

## 想定リスク

- **ffmpeg の subtitle codec サポート**: ASS は ffmpeg 標準対応。問題なし
- **MKV 再生互換**: 主要プレイヤー全対応。QuickTime のみ非対応だが Windows/macOS のメインユース VLC/mpv では問題ない
- **ファイル数増加**: 中間ファイル 3 種類 + MKV で計 4 ファイル。将来「中間ファイルを削除」オプションを追加検討（本タスクでは扱わない）
- **解像度ミスマッチ**: ASS の解像度と実動画解像度がズレるとコメント位置がずれる。`auto_resolution=ON` を既定にしてリスク軽減

## ステータス

完了 (2026-05-24)
