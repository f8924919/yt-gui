# yt_gui/formats.py

> 関連仕様: [ダウンロード形式](../spec/features/download-formats.md) / [ブラウザ拡張連携](../spec/features/browser-extension.md)

フォーマット仕様の定数と、yt-dlp フォーマット文字列を生成するユーティリティ。

## 定数

| 定数 | 型 | 内容 |
|------|----|------|
| `FORMAT_SPECS` | `dict[str, tuple[str, bool]]` | 内部キー → `(yt-dlp フォーマット文字列, 音声のみフラグ)` |
| `FORMAT_KEYS` | `list[str]` | UI 表示順のキーリスト |
| `VIDEO_RESOLUTIONS` | `tuple[str, ...]` | `"480"` 〜 `"2160"` |
| `MP3_BITRATES` | `tuple[str, ...]` | `"128"` 〜 `"320"` |
| `AUDIO_FORMATS` | `tuple[str, ...]` | `("mp3", "flac")` |
| `VIDEO_CONTAINERS` | `tuple[str, ...]` | `("mp4", "mkv", "webm")` |

## 関数

### `build_best_spec(container: str) -> str`

コンテナ別の「最高画質」yt-dlp フォーマット文字列を返す。

### `build_720p_spec(resolution: str, container: str) -> str`

解像度上限つきのフォーマット文字列を返す。

### `resolve_extension_format(fmt, *, default_resolution, default_audio_format, default_mp3_bitrate) -> ResolvedExtensionFormat | OriginalIntent | None`

ブラウザ拡張から受け取った[形式指定オブジェクト](../spec/features/browser-extension.md#形式指定オブジェクトformat)（`dict | None`）を、許可値へクランプ済みの形式情報に正規化する **Qt 非依存の pure function**。`app.py` の `_on_extension_enqueue` から呼ぶ。返り値は **3 状態**:

- `ResolvedExtensionFormat`（`@dataclass(frozen=True)`）: `format_id`（`fmt_best_mp4` / `fmt_720p` / `fmt_mp3`）と実効 `resolution` / `audio_format` / `mp3_bitrate`。呼び出し側はこれを `dataclasses.replace(settings, ...)` に流して `build_job_spec` に渡す（`best` / `resolution` / `audio`）。
- `OriginalIntent`（センチネル singleton）: `kind == "original"` のとき返す。「アプリ側でオリジナル形式ダイアログを開く必要がある」ことだけを表し、パラメータは持たない。呼び出し側は [`_dispatch_next_original_dialog`](app.md#オリジナル形式ダイアログ起動kind-original) でダイアログを起動する。
- **`None` = アプリ既定形式を使う**（`kind == "app_default"` / `fmt` が `None` / dict でない / `kind` が未知）。

その他:

- クランプ: `resolution` は `VIDEO_RESOLUTIONS`、`audio_format` は `AUDIO_FORMATS`、`mp3_bitrate` は `MP3_BITRATES` に含まれない・欠落なら対応する `default_*` へフォールバック。
- container は受け取らない（拡張はコンテナを指定しない。実コンテナはアプリ設定に従う）。
- `kind: "original"` に追加パラメータはなく、トラック選択はアプリ側ダイアログが担う。未知 `kind` は `original` と区別され、従来どおり `None`（既定フォールバック）。

## コンテナ別フォーマット文字列の方針

| コンテナ | フォーマット制約 |
|----------|----------------|
| MP4 | `[ext=mp4]+[ext=m4a]` を指定 |
| MKV | コーデック無制限 |
| WebM | `[ext=webm]` 制約 |
