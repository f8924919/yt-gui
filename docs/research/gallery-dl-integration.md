# gallery-dl 統合機能 設計書

## 1. 概要

gallery-dl は Pixiv・Twitter/X・Nijie・FC2 など 500 以上のサイトから画像・漫画・アーカイブを一括ダウンロードするための CLI ツール。  
現在の yt-gui は動画ダウンロード（yt-dlp）に特化しているが、同アプリ内に gallery-dl を統合することで「動画も画像もまとめてダウンロードできるデスクトップアプリ」として完成度を高める。

---

## 2. gallery-dl の特性（yt-dlp との比較）

| 観点 | yt-dlp | gallery-dl |
|------|--------|------------|
| 主な対象 | 動画（YouTube, ニコニコ等） | 画像・ギャラリー（Pixiv, Twitter等） |
| 対応サイト数 | 1,000+（動画中心） | 500+（画像中心） |
| 出力物 | 1 URL → 1 動画ファイル | 1 URL → N 枚の画像ファイル群 |
| フォーマット選択 | 必要（解像度・コーデック） | 不要（サイトが提供する原寸） |
| 事前ファイル数把握 | 可能（playlist） | 不可（スクレイプしながら逐次） |
| Python API | 公式・安定 | 未公式（CLI 前提） |
| 認証方式 | Cookies / ブラウザ共通 | サイト別（OAuth, cookies, username/password） |
| 進捗通知 | パーセント既知 | ファイル数カウントのみ |

---

## 3. 対応予定サイト（優先度順）

| サイト | 認証方式 | 備考 |
|--------|----------|------|
| Pixiv | OAuth token | `gallery-dl oauth:pixiv` でブラウザ認証フロー |
| Twitter / X | Cookies | yt-dlp 共通の cookies.txt が再利用可能 |
| Nijie | ユーザー名 / パスワード | |
| FC2 | Cookies | |
| その他 | — | Cookies があれば大半のサイトに対応 |

---

## 4. UI 設計案

### 案 A：タブ切り替え（推薦）

メイン UI 全体を `QTabWidget` で囲み「**動画**（yt-dlp）」と「**画像**（gallery-dl）」の 2 タブに分ける。

```
┌──────────────────────────────────────┐
│ yt-gui                    [ファイル]  │
├──────────────────────────────────────┤
│ [ 動画 (yt-dlp) ]  [ 画像 (gallery-dl) ] │ ← QTabWidget
├──────────────────────────────────────┤
│ URL:  [____________________________] │
│ (動画タブ時)                          │
│ 形式: [720p MP4              ▾]      │
│                                      │
│ (画像タブ時)                          │
│ (形式コンボなし)                      │
│ ファイル名: [デフォルト ▾]            │
├──────────────────────────────────────┤
│ ダウンロードキュー ─────────────────  │
│ # │ タイトル      │ 種別   │ 状態   │
│ 1 │ 作品名 (Pixiv)│ 画像   │ 待機中 │
│ 2 │ 動画タイトル  │ 720p   │ 待機中 │
└──────────────────────────────────────┘
```

**長所**
- yt-dlp / gallery-dl の概念の違いが UI で明示される
- 既存コードへの侵食が少ない（新タブとして追加）
- キューは同一ウィジェットを共有できる

**短所**
- ウィンドウ全体のレイアウト変更が必要（現在は `QGridLayout` で中央ウィジェットを直接構築）

---

### 案 B：モードボタン（ラジオ切り替え）

URL 入力欄の上部に「**動画**｜**画像**」ラジオボタンを置き、切り替えで形式コンボの表示/非表示を制御する。

```
┌──────────────────────────────────────┐
│ モード: ○ 動画  ● 画像               │
│ URL:  [____________________________] │
│                                      │
│ （画像モード時は形式コンボ非表示）      │
│ ファイル名: [デフォルト ▾]            │
│                          [追加]      │
├──────────────────────────────────────┤
│ キュー...                            │
└──────────────────────────────────────┘
```

**長所**
- UI の変化が小さい
- タブを使わないのでウィンドウ高さの圧迫がない

**短所**
- 「形式」の概念が画像には存在しないのに同一エリアに共存するため直感性が下がる

---

### 案 C：別ウィンドウ

メニュー「ファイル → 画像ダウンロード (gallery-dl)」で独立ウィンドウを開く。

**長所** — 既存コードへの影響ほぼゼロ  
**短所** — キューを共有しにくい、UX が分断される

---

### 推薦：案 A（タブ）

画像ダウンロードは「フォーマット選択」「字幕」「MP3変換」など動画固有の設定を一切必要とせず、UI の性格が根本的に異なる。タブで明確に分離することで、ユーザーの混乱を防ぎつつキューを共有できる。

---

## 5. 画像タブのUI詳細（案 A の場合）

```
┌── 画像 (gallery-dl) タブ ───────────┐
│ URL:  [____________________________] │
│                                      │
│ ファイル名: [デフォルト              ▾] │
│   └ デフォルト / サイト別テンプレート  │
│                                      │
│ サブフォルダ: ○ 自動（サイト別）       │
│              ○ フラット（サブフォルダなし）│
│                                      │
│                [追加]               │
└──────────────────────────────────────┘
```

キュー行（ツールチップ）では以下を表示：
- サイト名（Pixiv / Twitter / ...）
- ギャラリー名 or ユーザー名
- 取得済みファイル数 / 合計未確定

---

## 6. アーキテクチャ設計

### 6.1 呼び出し方式の選択

gallery-dl の Python API は**未公式・未ドキュメント**（`gallery_dl.job.DownloadJob` は内部クラス扱い）。  
バージョンアップで予告なく変更される可能性があるため、**subprocess 呼び出し**を採用する。

```
App
 └── GalleryDownloader          # 新規クラス
      ├── check_available()     # gallery-dl の存在確認
      ├── fetch_gallery_info()  # URL のギャラリー名取得（--dump-json --no-download）
      └── download_gallery()    # subprocess で gallery-dl を実行
```

### 6.2 GalleryDownloader の概略

```python
class GalleryDownloader:
    def __init__(self, output_dir, log_callback=None, status_callback=None):
        ...

    def check_available(self) -> bool:
        # shutil.which('gallery-dl') or importlib.util.find_spec('gallery_dl')

    def fetch_gallery_info(self, url, cookies_path=None) -> dict:
        # gallery-dl --dump-json --no-download --num-to-filename 0 <url>
        # → {"title": ..., "extractor": "pixiv", ...}

    def download_gallery(self, url, cookies_path=None, output_dir_override=None,
                         filename_template=None, on_file_done=None):
        # subprocess: gallery-dl --verbose --cookies <path> -d <dir> <url>
        # 標準出力をリアルタイムパースしてファイル数をカウント
```

### 6.3 _QueueItem の拡張

既存の `_QueueItem` に `item_type` フィールドを追加して動画/画像を区別する。  
（または `GalleryQueueItem` を新設して共通キューに同居させる）

```python
@dataclass
class _QueueItem:
    ...
    item_type: str = "video"        # "video" | "gallery"
    gallery_file_count: int = 0     # ダウンロード済みファイル数（画像時のみ）
```

### 6.4 設定の拡張

`Settings` dataclass に gallery-dl 用フィールドを追加：

```python
@dataclass
class Settings:
    ...
    # gallery-dl 認証
    pixiv_refresh_token: str = ""   # Pixiv OAuth refresh token
    gallery_cookies_path: str = ""  # gallery-dl 専用 cookies（空なら yt-dlp 設定を共有）
```

設定ダイアログに「gallery-dl」タブを追加し、Pixiv トークン・cookies パスを設定する。

---

## 7. 技術的課題

### 課題1: gallery-dl のインストール確認と不在時の案内

gallery-dl は yt-dlp と異なり**バンドルバイナリが配布されていない**。  
起動時に `shutil.which('gallery-dl')` または `importlib.util.find_spec('gallery_dl')` で存在確認し、見つからない場合は画像タブをグレーアウトして案内メッセージを表示する。

**対応方針**：
- `pip install gallery-dl` を案内する
- `uv add gallery-dl` で依存に追加（ビルド成果物に含める）
- PyInstaller スペックに gallery-dl のデータ/ファイルを追加する

---

### 課題2: プログレス表示（総ファイル数が事前に不明）

yt-dlp は 1 ファイルのパーセント進捗が分かるが、gallery-dl は**スクレイプしながら逐次ダウンロード**するため総数が不明。

**対応方針**：
- プログレスバーを「不確定モード（indeterminate）」で回転させる
  - `QProgressBar.setRange(0, 0)` → アニメーション表示
- ステータスラベルに「N 枚完了」を逐次表示
- gallery-dl の stdout "`[#extractor] ..."` パターンをパースしてカウント

```
📥 12 枚ダウンロード中...  [回転するプログレスバー]
```

---

### 課題3: Pixiv OAuth 認証フロー

Pixiv はメールアドレス/パスワード認証を廃止しており、**OAuth refresh token** が必要。  
取得フローは `gallery-dl oauth:pixiv` コマンドでブラウザを開く手順が必要。

**対応方針**：
- 設定ダイアログの「gallery-dl」タブに「Pixiv 認証」ボタンを設置
- ボタン押下で `gallery-dl oauth:pixiv` をサブプロセス実行 → ブラウザが開く
- ユーザーが認証後に表示されるトークンをテキストフィールドに手動ペーストしてもらう
- あるいは、設定ファイル（`~/.gallery-dl.conf`）への直接書き込みを案内する

---

### 課題4: gallery-dl 設定ファイルとの競合

gallery-dl はデフォルトで `~/.gallery-dl.conf` や `%APPDATA%\gallery-dl\config.toml` を読み込む。  
ユーザーが既存の設定ファイルを持っている場合、アプリ側の設定と競合する可能性がある。

**対応方針**：
- `--config-ignore` フラグで既存設定ファイルを無視する
- アプリが一時設定ファイルを `tempfile.mkstemp()` で生成し `--config <path>` で渡す
- ダウンロード後に一時ファイルを削除する

---

### 課題5: ギャラリー情報の事前プレビュー

yt-dlp は URL 追加時に `fetch_title_or_entries()` でタイトルを取得してキューに表示するが、  
gallery-dl で同等のことをするには `--dump-json --no-download` が使える。

ただし、一部サイト（Pixiv 等）は認証なしでメタデータ取得できないケースがある。  
また、サイトによっては `--dump-json` が全ファイル情報を出力するため非常に遅い場合がある。

**対応方針**：
- `--num-to-filename 0` または `--range 1` など 1 件だけ取得してギャラリー名を抜き出す
- タイムアウト（例: 5 秒）を設けてフォールバックとして URL をそのままキュー表示
- 取得失敗時はキューに URL のみ表示（タイトルなし）でダウンロード自体は続行

---

### 課題6: PyInstaller バンドル時の対応

gallery-dl を `pip install` ではなく `uv add` で依存に追加してバンドルする場合、  
gallery-dl の extractor モジュール群が PyInstaller の自動解析から漏れる可能性がある。

**対応方針**：
- `yt-gui.spec` の `hiddenimports` に `gallery_dl.extractor.*` を追加する
- またはバンドルせず、起動時に `gallery-dl` コマンドのパス検索（subprocess 方式）に徹する
  - この場合ユーザーは別途 `pip install gallery-dl` が必要

**推薦**：初期実装は subprocess 方式 + インストール案内にとどめる。バンドルは後続 Issue で検討。

---

### 課題7: subprocess パース（出力フォーマットの安定性）

gallery-dl の stdout/stderr 出力フォーマットは公式仕様ではなく、バージョン間で変わりうる。

現行の出力例（`--verbose` 時）：
```
[pixiv][info] Downloading gallery "xxxx" (123 files)
[pixiv][info] Saving "12345678_p0.jpg"
...
```

**対応方針**：
- `[info] Saving` 行をパースしてカウントアップ
- パターンマッチが壊れても「ファイル数不明」として継続する（エラーにしない）
- `--write-info-json` を使ってメタデータを JSON で取得し、出力テキストへの依存を減らす

---

### 課題8: Cookies 設定の yt-dlp / gallery-dl 共有

現在の cookies 設定（ファイルパスまたはブラウザ）は yt-dlp 用だが、  
Twitter/X などは gallery-dl でも同一 cookies が使えるため共有したい。

**対応方針**：
- 設定ダイアログの「gallery-dl」タブで「yt-dlp と同じ cookies を使用」チェックボックスを設ける
- デフォルト ON にすることで設定の重複入力を避ける

---

## 8. 実装ロードマップ（フェーズ案）

### Phase 1: 基盤（最小動作）
1. `gallery-dl` の存在確認と不在時のグレーアウト
2. `GalleryDownloader` クラス（subprocess ラッパー）の実装
3. タブ UI の追加（画像タブ内の URL 入力・追加ボタン）
4. キューへの `item_type` 追加と画像アイテムの表示

### Phase 2: ダウンロード機能
5. subprocess 実行・stdout パース・ファイル数カウント
6. 不確定プログレスバーとステータス表示
7. Cookies 共有オプションの設定

### Phase 3: 認証・設定
8. 設定ダイアログへの「gallery-dl」タブ追加
9. Pixiv OAuth トークン入力 UI
10. gallery-dl 専用 cookies パス設定

### Phase 4: 品質向上
11. ギャラリー情報の事前プレビュー（タイトル取得）
12. エラー詳細表示の改善
13. PyInstaller バンドル対応（検討）

---

## 9. 未決定事項（要ユーザー確認）

1. **キュー統合** — 動画・画像を同一キューに混在させる？それとも画像タブ内に専用キューを設ける？
2. **ファイル名テンプレート** — 初期実装は「デフォルト（gallery-dl の既定）のみ」で十分か？
3. **サブフォルダ構成** — gallery-dl のデフォルト（サイト名 / ユーザー名 / ...）を尊重する？フラットにする選択肢を提供する？
4. **Pixiv 認証** — OAuth フロー（複雑）を Phase 1 で実装する必要があるか？cookies.txt で代替できるか？
5. **gallery-dl のインストール方法** — uv の依存として同梱する（バイナリサイズ増大）vs. ユーザーが別途インストール？
