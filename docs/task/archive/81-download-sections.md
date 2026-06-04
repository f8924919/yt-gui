# 区間ダウンロード（--download-sections 相当）

対応 Issue: [#81](https://github.com/f8924919/yt-gui/issues/81)

## 概要

動画の一部分（時間範囲）だけを切り出してダウンロードする機能。yt-dlp の
`--download-sections` 相当（Python API では `download_ranges` +
`force_keyframes_at_cuts`）。初期スコープは**時間範囲指定のみ**（チャプター名の
正規表現指定は将来の別 Issue）。

## 設計方針（確定）

- **データ保持**: 区間は「動画固有・形式非依存」なので、全 DL 共通の設定ではなく
  キューアイテム単位 = `JobSpec` に持たせる。
  - `JobSpec` に `section_start: str | None` / `section_end: str | None` /
    `section_force_keyframes: bool` を追加（デフォルト None / None / False）。
  - 生の入力文字列（`HH:MM:SS` 等）を保持し、秒への変換は downloader 側で
    `yt_dlp.utils.parse_duration` を使って行う。
  - `build_job_spec()` に kwarg を追加し、`dataclasses.replace` で全 format_id に
    一律付与（4 つの `_build_*` ヘルパは変更不要）。
- **downloader**: `_build_ydl_opts` で `job.section_start`/`section_end` があれば
  `download_ranges = download_range_func([], [(start, end)])` を設定。
  `section_force_keyframes` のとき `force_keyframes_at_cuts = True`。
- **UI（メインウィンドウ）**: 形式選択の下に開閉式の区間入力を追加。
  - 有効化チェック `_section_check`（常時表示・形式非依存）。
  - チェック時のみ表示する入力群: 開始 / 終了 QLineEdit、再エンコードトグル
    `_section_keyframe_check`。
- **検証**: チェック時、開始・終了が `parse_duration` で解釈でき、かつ
  `開始 < 終了`、空欄不可。不正なら追加/変更をブロックして警告。
- **プレイリスト（後追いバリデーション）**: 入力時点では単一/プレイリストを判定
  できないため、取得後 `_on_fetch_for_add_done` でプレイリストかつ区間指定ありの
  場合に `warn_playlist_section` を表示して中断（`fmt_original × playlist` と同パターン）。
- **複数アイテム編集**: 1 つの時間範囲を異なる複数動画へ適用するのは無意味なため、
  複数選択編集中は区間 UI を無効化（グレーアウト）。
- **編集モード（単一）**: `JobSpec` から区間を UI へ復元し再編集可能にする。
- **ツールチップ**: キューアイテムに区間（`開始〜終了`）を表示。

## 変更対象

- `yt_gui/job_spec.py` — `JobSpec` フィールド・`build_job_spec` kwarg
- `yt_gui/downloader.py` — `_build_ydl_opts` に `download_ranges` /
  `force_keyframes_at_cuts`、`download_range_func` / `parse_duration` インポート
- `yt_gui/app.py` — 区間 UI・検証・後追いバリデーション・編集復元・複数編集の無効化・
  ツールチップ
- `yt_gui/locales/ja.py` / `en.py` — i18n 文字列
- tests/ — `test_job_spec.py` / `test_downloader.py`（+ 必要なら `test_app.py`）
- docs/ — spec / arch / feature-gap

## 実装方式の変更（2026-06-04）

当初は yt-dlp ネイティブの `download_ranges`（`--download-sections` 相当）で実装したが、
YouTube の `https` / DASH フォーマットでは部分取得が `FFmpegFD`（ffmpeg にネットワーク
取得を委ねる経路）になり、バンドル ffmpeg が**サンドボックスでクラッシュ（SIGSEGV）・
ユーザー環境（Windows）でハング**することが判明。ユーザー判断のもと、方針を
**フル取得 → ローカル ffmpeg 切り出し** に変更（通信量節約は犠牲、安定性を優先）。

- `_build_ydl_opts` は区間 opt を渡さない。`download_video` が DL 成功後に
  `_cut_section` でローカル切り出し（`_build_cut_cmd` で copy / 再エンコードを分岐）。
- 当初入れた contextvar 修正（`FFmpegPostProcessor._ffmpeg_location`）は不要になり撤去。
- サンドボックスでエンドツーエンド検証済み（mp3 5 秒区間 = 122KB を確認）。

## 進捗

- [x] Issue #81 起票
- [x] ブランチ `feature/81-download-sections` 作成
- [x] 調査（investigate 委譲）
- [x] docs 反映
- [x] テスト追加（red）
- [x] 実装（green）
- [x] 検証ゲート（lint / format / mypy / 185 tests green、docs-check 整合済み）
- [ ] PR
