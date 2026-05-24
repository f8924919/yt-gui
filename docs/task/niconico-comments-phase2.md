# ニコニコ動画コメント取得 ― フェーズ 2: danmaku2ass バンドル + ASS 変換

[← タスク一覧](index.md)

> 前提: [niconico-comments-phase1.md](niconico-comments-phase1.md) 完了、および [niconico-comments-verify.md](niconico-comments-verify.md) で互換性結果が確定していること。

## 背景

フェーズ 1 で取得した `*.comments.json` を、ffmpeg がサブタイトルとして扱える **ASS ファイル**へ変換する。変換には [m13253/danmaku2ass](https://github.com/m13253/danmaku2ass) を利用し、**PyInstaller で単独実行ファイル化したバイナリ**を `bin/` に同梱して subprocess 経由で呼び出す（ffmpeg/deno と同じ扱い）。

ライセンス: danmaku2ass は GPL-3.0、yt-gui 本体も GPL-3.0 のため整合する。subprocess 呼び出しのため境界は明確。

## 仕様

### バイナリビルド（`scripts/download_binaries.py`）

ffmpeg / deno と並ぶ第 3 のセクションとして `build_danmaku2ass()` を追加する。

```python
DANMAKU2ASS_REPO = "https://github.com/m13253/danmaku2ass.git"
DANMAKU2ASS_REF = "<pin a specific commit hash>"  # 再現性確保のため master ではなく commit 固定

def build_danmaku2ass(force=False):
    out_path = os.path.join(BIN_DIR, f"danmaku2ass{_EXE_EXT}")
    if os.path.exists(out_path) and not force:
        print(f"[danmaku2ass] {out_path} already exists. Skipping.")
        return

    # 一時ディレクトリへ clone
    tmpdir = tempfile.mkdtemp(prefix="danmaku2ass-build-")
    try:
        subprocess.check_call(["git", "clone", DANMAKU2ASS_REPO, tmpdir])
        subprocess.check_call(["git", "-C", tmpdir, "checkout", DANMAKU2ASS_REF])

        # ビルド時のみ pyinstaller を一時環境にインストール
        # uv tool run pyinstaller を使うのがクリーン
        subprocess.check_call([
            "uv", "tool", "run", "--from", "pyinstaller", "pyinstaller",
            "--onefile", "--name", f"danmaku2ass",
            "--distpath", BIN_DIR,
            "--workpath", os.path.join(tmpdir, "_build"),
            "--specpath", os.path.join(tmpdir, "_build"),
            os.path.join(tmpdir, "danmaku2ass.py"),
        ])
        _make_executable(out_path)
        print(f"[danmaku2ass] Saved: {out_path}")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
```

`main()` の最後に `build_danmaku2ass()` 呼び出しを追加する。

#### ビルド環境の前提

- ホストに `git` が存在すること
- `uv` がパスにあること（既に開発環境前提）
- ターゲット OS と同じ OS 上でビルドする必要がある（クロスビルド非対応 ＝ ffmpeg/deno の方針と同じく、GitHub Actions の OS マトリックスで対応）

### バイナリパス解決（`yt_gui/utils.py` or 既存パターン）

`downloader.py` がバイナリパスを解決する既存ヘルパに以下を追加:

```python
def _danmaku2ass_path() -> str:
    base = get_resource_base()
    ext = ".exe" if sys.platform == "win32" else ""
    return os.path.join(base, "bin", f"danmaku2ass{ext}")
```

起動時の依存チェック（`app.py` で行っている ffmpeg/ffprobe/deno チェック）に **`danmaku2ass` を追加**する。**ただし無い場合は致命的とせず**、ステータスバーに警告を出して「ニコニコ動画コメント機能は無効」とする（ニコニコ動画 URL を扱わないユーザーには無関係なため）。

### `OriginalFormatPanel` の UI 追加

字幕リストの下に **「ニコニコ動画コメント」グループ**を新設する。フォーマット取得結果に `comments` lang が含まれる場合のみ可視化（`setVisible(True)`）。

| ウィジェット | キー | 説明 |
|---|---|---|
| `QCheckBox`（コメントを ASS に変換） | `chk_nico_convert_ass` | 既定 OFF |
| `QSpinBox`（画面解像度幅） | — | 既定 1920 |
| `QSpinBox`（画面解像度高さ） | — | 既定 1080 |
| `QDoubleSpinBox`（コメント表示秒数） | — | 既定 8.0 |
| `QDoubleSpinBox`（不透明度） | — | 既定 0.8、範囲 0.1〜1.0 |
| `QSpinBox`（フォントサイズ） | — | 既定 32 |

> 解像度の既定値は、後段のフェーズ 3 で動画の実解像度を自動取得して上書きする想定。フェーズ 2 単独では固定既定値で進める。

**前提条件**: `chk_nico_convert_ass` を ON にできるのは字幕リストで `comments` lang を選択している場合のみ。チェック ON 時には字幕リストの comments 行を自動選択する。

### `OriginalFormatPanel.get_raw_settings()` の拡張

戻り値 dict に以下を追加:

```python
"nico_comments": {
    "convert_to_ass": bool,
    "resolution_w": int,
    "resolution_h": int,
    "duration_sec": float,
    "opacity": float,
    "font_size": int,
}
```

`restore_from_settings` も同キーを読み戻すよう拡張。旧キー欠如時のデフォルト値は上記既定値。

### `Downloader.download_video()` の拡張

新規引数 `nico_comments_opts: dict | None = None` を追加。値が `convert_to_ass=True` を含む場合、`comments` JSON のダウンロード後に danmaku2ass を呼び出す。

#### 実装位置

yt-dlp の `postprocessor_hooks` または `progress_hooks` の最終フェーズで `*.comments.json` のパスを把握できる。シンプルには、ダウンロード完了後（`extract_info` の戻り値から `requested_subtitles['comments']['filepath']` を読む）に同期的に呼び出す。

```python
def _run_danmaku2ass(json_path: str, out_path: str, opts: dict) -> None:
    cmd = [
        _danmaku2ass_path(),
        "-o", out_path,
        "-s", f"{opts['resolution_w']}x{opts['resolution_h']}",
        "-f", "NiconicoYtdlpJson2",  # v1/threads JSON 用パーサ（フェーズ 0 検証済み）
        "-dm", str(opts["duration_sec"]),
        "-fs", str(opts["font_size"]),
        "-a", str(opts["opacity"]),
        json_path,
    ]
    subprocess.run(cmd, check=True, capture_output=True, text=True)
```

> フェーズ 0 検証（[niconico-comments-verify.md](niconico-comments-verify.md)）の結果、yt-dlp `v1/threads` JSON は danmaku2ass の `NiconicoYtdlpJson2` パーサと **フィールド完全一致**することを確認済み。アプリ側の変換層は不要。

#### エラー処理

- danmaku2ass のバイナリが無い → 警告ログ・スキップ（JSON は残る）
- 変換失敗（非 0 終了） → 警告ログ・スキップ・JSON は残す（致命的にしない）
- ログは `log_callback("[danmaku2ass] ...")` プレフィックス付き

### 出力ファイル

ASS は `*.comments.ass` で保存（JSON は併存させる）。

### 翻訳キー（追加）

| キー | ja | en |
|---|---|---|
| `nico_group_title` | `ニコニコ動画コメント` | `Niconico Comments` |
| `nico_convert_ass` | `コメントを ASS 字幕に変換` | `Convert comments to ASS subtitle` |
| `nico_resolution` | `画面解像度` | `Screen resolution` |
| `nico_duration` | `表示時間(秒)` | `Display duration (sec)` |
| `nico_opacity` | `不透明度` | `Opacity` |
| `nico_font_size` | `フォントサイズ` | `Font size` |
| `warn_danmaku2ass_missing` | `danmaku2ass が見つかりません。ニコニコ動画コメント機能は無効化されます。` | `danmaku2ass not found. Niconico comments feature disabled.` |
| `warn_danmaku2ass_failed` | `コメントの ASS 変換に失敗しました: {error}` | `Failed to convert comments to ASS: {error}` |

### キュー / 編集モード

`_QueueItem` の `orig_settings` に `nico_comments` dict が含まれるようになる。シリアライズ・復元は既存の get/restore パターンに乗る。

### ドキュメント更新

- `docs/arch/downloader.md`
  - `nico_comments_opts` 引数表に追加
  - 「ポストプロセッサの順序」節に danmaku2ass 呼び出しタイミング（yt-dlp 完了 → サブプロセス）を追記
  - 「バイナリパス解決」節に danmaku2ass を追加
- `docs/spec/screens/original-format-panel.md`
  - 「ニコニコ動画コメント」グループ節を新設
- `docs/spec/overview.md`
  - 「バンドルされるバイナリ」表に `danmaku2ass` を追加
- `docs/build.md`
  - `download_binaries.py` の `build_danmaku2ass()` ステップを追記
  - PyInstaller のビルド時に `uv tool` 経由で danmaku2ass を構築する旨を明記
- `docs/arch/original_format_panel.md`
  - `get_raw_settings()` の戻り値に `nico_comments` キーを追加
- `docs/spec/settings.md`
  - 該当する設定は無いが、後段のデフォルト値ポリシーは原則「OUTPUT TEMPLATE と同様にキュー側に従属」とする旨を一言だけ追記

## 範囲外

- ASS の動画統合（フェーズ 3）
- 解像度の動画自動追従（フェーズ 3 でまとめて実施）
- danmaku2ass の上流バージョン自動更新機構
- ニコニコ生放送コメント

## テスト

新規モジュール `yt_gui/niconico_comments.py`（互換性変換層）が必要になった場合は、テスト方針上「純粋ロジック」に該当するため pytest 対象。サブプロセス呼び出し本体（`downloader.py`）はテスト対象外。

実機確認項目:

- ニコニコ動画 URL + 字幕に `comments` 選択 + `chk_nico_convert_ass` ON で MP4 ダウンロード → MP4 + `*.comments.json` + `*.comments.ass` の 3 ファイルが出力される
- 出力された ASS を `ffplay -i sample.mp4 -vf "ass=sample.comments.ass"` で再生し、コメントが流れることを目視確認
- danmaku2ass バイナリを `bin/` から一時的にリネームしてアプリ起動 → 警告ダイアログ or ステータスバー通知が出る・他機能は通常動作する
- フェーズ 1 までの挙動（JSON のみ保存）は ASS 変換 OFF で再現する

## 想定リスク

- **PyInstaller クロスビルド非対応**: GitHub Actions の OS マトリックスで Windows/macOS/Linux 各々ビルドする必要がある。CI 既存パターンに合わせる
- **danmaku2ass のコミット pin**: master 追従だと再現性が崩れるためコミットハッシュで固定する。更新時は明示的に PR を切る
- **バイナリサイズ**: PyInstaller `--onefile` で 10〜30MB 程度の上乗せ。許容範囲だが overview.md の同梱バイナリ表に明記
- **JSON 形式変更**: yt-dlp 側の `_get_subtitles` 仕様変更で `v1/threads` の構造が変わる可能性。フェーズ 0 で対象 yt-dlp バージョンを記録しておく

## ステータス

未着手
