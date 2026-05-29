# オリジナル形式パネルへの「音声のみ」出力選択肢の追加

[← タスク一覧](index.md)

## 背景

オリジナル形式パネルの「出力形式」ラジオには現在 `{container} に結合` / `remux のみ` の 2 択しかなく、映像トラックを明示的に除外して音声のみを書き出す（`fmt_mp3` 相当）使い方ができない。`fmt_mp3` を選択すれば音声のみは取れるが、その場合は `bestaudio/best` 固定でトラック選択ができない。オリジナル形式の柔軟なトラック選択UIをそのまま使いつつ、音声抽出パスにも乗せられるようにする。

## 仕様

### UI 変更

- 出力形式ラジオに 3 つ目の選択肢「音声のみ ({label})」を追加する。
  - `{label}` は `fmt_mp3` の表示と揃え、音声形式が `mp3` なら `MP3 192kbps`、`flac` なら `FLAC` を埋め込む。
- 「音声のみ」を選択したときの挙動:
  - **映像コンボ** を `setEnabled(False)`。選択値はそのまま残すがフォーマット文字列生成では無視。
  - **字幕リスト / 字幕フォーマット / 字幕埋め込み** を `setEnabled(False)` し、選択もクリアする。
  - サムネイル埋め込み / メタデータ埋め込み / チャプター埋め込みは現状のまま有効（FLAC の場合のサムネイルはダウンローダ側で無視される既存挙動を流用）。
- 他のラジオに切り替えるとそれぞれの無効化を解除する。

### フォーマット文字列生成

「音声のみ」選択時は音声コンボの選択値のみを使用する。

| 音声 | 生成される文字列 |
|---|---|
| 自動 | `bestaudio/best` |
| 特定 ID | `{audio_id}` |
| ダウンロードしない | 警告（音声のみモードでは音声をスキップ不可） |

「音声のみ」モードで音声コンボがスキップの場合は `warn_skip_both` ではなく専用警告で弾く。

### ダウンローダ

- `_QueueItem` に `audio_only: bool` を追加。
- `Downloader.download_video` に `audio_only: bool = False` 引数を追加。`format_id == "fmt_original"` かつ `audio_only` のとき `is_audio = True` として扱い、`audio_codec`（`mp3` / `flac`）と `mp3_bitrate` を `FFmpegExtractAudio` に渡す。
- これにより既存の `fmt_mp3` 経路と同じ後段処理（拡張子置換・サムネイル埋め込みなど）が走る。

### 設定保存 / 復元

- `get_raw_settings()` / `restore_from_settings()` に `audio_only` を含めて、編集モードでの復元に対応する。

### i18n

- 新キー `orig_output_audio_only`（プレースホルダ `{label}`）を `ja.py` / `en.py` に追加。

### ドキュメント

- `docs/spec/screens/original-format-panel.md` のレイアウト・出力形式表・フォーマット文字列表を更新。
- `docs/arch/original_format_panel.md` の公開 API に `get_audio_only()` を追加。
- `docs/spec/features/download-formats.md` の「オリジナル形式」節に音声のみ経路を追記。

## ステータス

完了
