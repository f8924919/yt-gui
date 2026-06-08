# yt-dlp CLI 機能ギャップ調査メモ

[← 目次](index.md)

## 1. 目的

コマンドライン版 yt-dlp に存在するが、**yt-gui の UI からは到達できない機能**を洗い出し、今後の機能追加の優先度付けの土台とする。

---

## 2. 前提

yt-gui は yt-dlp を **Python ライブラリ**として利用している。実際に効くのは [`yt_gui/downloader.py`](../arch/downloader.md) の `_base_ydl_opts` / `_build_ydl_opts` が `YoutubeDL` に渡すオプションだけで、設定ダイアログ・オリジナル形式パネルに露出していない機能は「API 的には実装可能だが UI から到達できない」状態になる。

> したがって本メモの「使えない」は、原則として **API の根本的制約ではなく UI 露出の欠落**を指す。例外（現行 UX と相性が悪いもの）は §6 に分けて記載する。

調査時点の対応状況は [アプリ概要](../spec/overview.md) / [ダウンロード動作](../spec/features/download-behavior.md) / [ダウンロード形式](../spec/features/download-formats.md) / [設定管理](../spec/settings.md) を裏取りし、`downloader.py` のコードで確認した。

---

## 3. 現状サポートしている主な yt-dlp 機能（参考）

| 機能 | 対応箇所 |
|---|---|
| フォーマット選択（最高画質 / 解像度上限 / 音声のみ / オリジナル形式の個別トラック） | `formats.py` / オリジナル形式パネル |
| コンテナ結合（mp4 / mkv / webm）・remux | `merge_output_format` |
| 音声抽出（mp3 / flac、MP3 ビットレート指定） | `FFmpegExtractAudio` |
| サムネイル埋め込み | `EmbedThumbnail` |
| メタデータ・チャプター埋め込み | `FFmpegMetadata` |
| 字幕 DL・埋め込み（手動 / 自動、言語・形式指定） | オリジナル形式パネル限定 |
| Cookies（ファイル / ブラウザ） | `cookies` / `cookiesfrombrowser` |
| プロキシ（http/https/socks4/5/5h） | `proxy` |
| 出力テンプレート（単独 / プレイリスト） | `outtmpl` |
| プレイリスト自動展開 | `extract_flat` + キュー |
| ニコニコ動画コメント（ASS 変換・MKV ソフトサブ） | `danmaku2ass` + ffmpeg |

---

## 4. 利用者要望が出やすい主要な欠落

| yt-dlp 機能 | CLI オプション | 現状・備考 |
|---|---|---|
| ~~**SponsorBlock**（スポンサー区間のスキップ / 除去）~~ | `--sponsorblock-mark` / `--sponsorblock-remove` | ✅ 対応済み（設定の「SponsorBlock」タブ、#57）。[設定ダイアログ](../spec/screens/settings-dialog.md#sponsorblock-タブ)参照 |
| ~~**区間ダウンロード**（時間範囲の切り出し）~~ | `--download-sections` | ✅ 対応済み（メインウィンドウの区間指定、#81）。安定性優先で**フル取得→ローカル ffmpeg 切り出し**方式（ネイティブ `download_ranges` は不使用）。[区間ダウンロード](../spec/features/download-behavior.md#区間ダウンロード)参照。チャプター指定は将来対応 |
| ~~**ダウンロードアーカイブ**（既 DL 動画を記録してスキップ）~~ | `--download-archive` | ✅ 対応済み（設定の「ダウンロード」タブ、#75）。[ダウンロードアーカイブ](../spec/features/download-behavior.md#ダウンロードアーカイブ)参照 |
| ~~**速度制限**~~ | `--limit-rate` | ✅ 対応済み（設定の「ダウンロード」タブ、#64）。[設定ダイアログ](../spec/screens/settings-dialog.md#ダウンロードタブ)参照 |
| ~~**並列フラグメント DL（高速化）**~~ | `--concurrent-fragments` (`-N`) | ✅ 対応済み（設定の「ダウンロード」タブ、#53）。[設定ダイアログ](../spec/screens/settings-dialog.md#ダウンロードタブ)参照 |
| **ライブ配信を最初から / 配信待ち** | `--live-from-start` / `--wait-for-video` | 未対応。仕様案・課題は[ライブ配信を最初から / 配信待ち 調査メモ](live-stream-download.md)参照 |
| **再エンコード**（remux ではなく実変換） | `--recode-video` | 未対応。app は merge / remux のみ |
| **プレイリストの部分選択** | `--playlist-items` / `--max-downloads` | 未対応。`noplaylist:True` で全件展開し、キューから手動削除するしかない |

---

## 5. カテゴリ別の欠落一覧

### 5.1 形式・後処理

- **任意フォーマット文字列の直接指定 / 並べ替え** — `-f`（生記述）・`-S` / `--format-sort`。オリジナル形式パネルでトラック個別選択はできるが、`bestvideo[...]` のような自由記述や format-sort は不可。
- **音声形式が mp3 / flac の 2 種のみ** — yt-dlp は `aac / opus / vorbis / m4a / wav / alac` も抽出可能（`AUDIO_FORMATS = ("mp3", "flac")` に限定）。
- **ffmpeg への引数渡し** — `--postprocessor-args` / `--ppa`。未対応。
- **チャプター分割 / 除去** — `--split-chapters` / `--remove-chapters`。未対応。
- **サムネイルのファイル保存** — `--write-thumbnail`。`writethumbnail` は埋め込み目的でしか立てておらず単体画像保存は不可。
- **サムネイル形式変換** — `--convert-thumbnails`。未対応。

### 5.2 メタデータ / サイドカー出力

- `--write-info-json`（メタデータ JSON 保存）
- `--write-description`（説明文保存）
- `--write-comments`（動画コメント取得。※ニコニコの `comments` 字幕とは別物）
- `--embed-info-json` / `--xattrs`

### 5.3 字幕

- 字幕の選択・埋め込みは **「オリジナル形式」パネル限定**。最高画質 / 解像度指定 / MP3 形式では字幕を選べない（`subtitle_opts` を渡す経路が無い）。
- `--sub-format` の細かな指定（app は srt / vtt / best のみ）。

### 5.4 認証

- **サイトログイン** — `--username` / `--password`、`--netrc`、`--video-password`、`--ap-mso`（TV プロバイダ）、`--client-certificate`。未対応。認証は **Cookies のみ**（設定の `username` / `password` はプロキシ認証用で別物）。

### 5.5 ネットワーク / 地域 / 抽出器

- **地域制限回避** — `--geo-bypass` / `--xff`。未対応。
- **リトライ調整** — `--retries` / `--fragment-retries` / `--retry-sleep` / `--socket-timeout`。未対応（既定値固定）。
- **IP 指定** — `--source-address` / `--force-ipv4` / `--force-ipv6`。未対応。
- **抽出器引数** — `--extractor-args`（例: YouTube の player client 切替）。未対応。

---

## 5.6 アプリ機能レベルの欠落（CLI オプション由来ではない UX）

§4・§5 は「CLI の yt-dlp オプションに対応するが UI 露出が無い」ものを扱う。一方で、yt-dlp の単一オプションでは表現できない **アプリ（キュー / UI）レベルの欠落** も利用者要望が大きい。これらは `_build_ydl_opts` への追加では解決せず、キュー実行モデルや UI の設計変更を伴う。

| 機能 | 現状 | 備考 |
|---|---|---|
| **並列ダウンロード（複数アイテム同時）＋行単位の進捗表示** | 未対応。`queue_controller` の `_worker` が単一スレッドで逐次実行（先頭の `waiting` を 1 件ずつ）。進捗はステータスバーの全体 1 本のみ（`app.py` `progress_bar`） | **Issue #108 で起票済み**。同時実行数の設定＋ワーカープール化＋キュー行単位の進捗。`concurrent-fragments`（§4・1 動画内のフラグメント並列）とは別物 |
| **yt-dlp 本体の更新機能** | 未対応。バンドル yt-dlp（Python 依存）が古いと YouTube 仕様変更で DL 失敗し、アプリの新リリースを待つしかない | 体験影響が最大。frozen（PyInstaller）環境での yt-dlp 差し替え方式の検討が要る。[binary-supply-chain.md](binary-supply-chain.md) と関連 |
| **キューの永続化＋ダウンロード履歴** | 未対応。`_queue_items` はメモリ上のみで再起動で消える。完了履歴も残らない（ログはセッション中のみ） | 再起動でのキュー復元、完了履歴＋「フォルダ/ファイルを開く」操作 |
| **完了通知・完了後アクション** | 未対応 | 全件完了時の OS 通知（トレイ/トースト）、保存先フォルダを開く |
| **クリップボード監視・ドラッグ&ドロップで URL 追加** | 未対応。URL は入力欄への手入力のみ | ブラウザからのコピー自動検出・D&D。ダウンローダの定番 UX |
| **失敗時の自動リトライ（アイテム単位）** | 未対応。`error` になったアイテムは手動で再追加するしかない | yt-dlp の `--retries`（§5.5、フラグメント/接続レベル）とは別に、キューアイテム失敗時の再試行 |

> 出典: 2026-06-08 の実装ギャップ調査。spec（[queue.md](../spec/features/queue.md) / [overview.md](../spec/overview.md) / [download-behavior.md](../spec/features/download-behavior.md)）と `app.py` / `queue_controller.py` / `downloader.py` のコードで裏取り。

---

## 6. 現行 UX と相性が悪い（露出には設計判断が要る）もの

- `--match-filter`（再生数・長さ等での絞り込み）
- 日付フィルタ `--date` / `--datebefore` / `--dateafter`
- `--min-filesize` / `--max-filesize`、`--min-views` / `--max-views`

これらは「全件展開してキュー編集」という現行 UX とぶつかる。導入するならキュー追加前のフィルタ UI など、別の設計が必要。

---

## 7. アプリの別機能で代替済み（参考）

| yt-dlp 機能 | 代替 |
|---|---|
| `--batch-file`（URL リスト一括） | キュー機能 |
| `-o` / `--output`（出力テンプレート） | 設定の OUTPUT TEMPLATE（単独 / プレイリスト） |
| `--cookies` / `--cookies-from-browser` | 対応済み |
| `--proxy` | 対応済み |

---

## 8. 所見・推奨

- §4・§5 の大半は **`_build_ydl_opts` にオプションを足すだけで実装可能**で、API の根本的制約ではない（SponsorBlock・download-sections・concurrent-fragments・recode・write-info-json など）。UI 露出と設定永続化の追加が主作業になる。
- 利用者メリットが大きい順の機能追加候補:
  1. ~~**SponsorBlock**~~ — ✅ 対応済み（#57、設定の「SponsorBlock」タブ）
  2. ~~**並列フラグメント DL（`concurrent_fragments`）**~~ — ✅ 対応済み（#53、設定の「ダウンロード」タブ）
  3. ~~**ダウンロードアーカイブ**~~ — ✅ 対応済み（#75、設定の「ダウンロード」タブ）。アイテム単位の再取得は #76
  4. ~~**区間ダウンロード（`download_sections`）**~~ — ✅ 対応済み（#81、メインウィンドウの区間指定。時間範囲のみ・チャプター指定は将来）
- §5.6 のアプリ機能レベルの欠落のうち、**並列ダウンロード＋行単位進捗は Issue #108 で起票済み**。yt-dlp 本体の更新機能は体験影響が大きく次点候補。

> Issue 化する場合は [git-workflow](../git-workflow.md) のテンプレに沿い、対応する [spec](../spec/index.md) / [arch](../arch/index.md) の更新方針もあわせて起票する。

