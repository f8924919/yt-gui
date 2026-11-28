# macOS arm64 の ffmpeg ピンの古さを週次で検知する

> Issue: [#412](https://github.com/f8924919/yt-gui/issues/412)
> ステータス: 進行中
> ブランチ: `feature/412-arm64-pin-staleness`
> 基点: `dd66c0d`

受け入れ条件の正本は Issue（2026-11-28 に criteria-review とユーザー確認を経て書き直した版）。設計は [build.md](../build.md) の「更新運用」「同梱バイナリのピン自動更新（GitHub Actions）」。

## 進捗

- [ ] C1 版の読み取り（リンクと文言の両方・Intel を拾わない） — 証跡: 未
- [ ] C2 古さの判定（x86_64 との差だけでは警告しない） — 証跡: 未
- [ ] C3 URL の生存（ffmpeg だけ・ffprobe だけ） — 証跡: 未
- [ ] C4 検査不能の区別（取得失敗・リンクだけ・文言だけ・食い違い） — 証跡: 未
- [ ] C5 他の再ピンを止めない — 証跡: 未
- [ ] C6 警告の出力（サマリの先頭・警告ファイル） — 証跡: 未
- [ ] C7 ジョブの失敗（PR 作成の後のステップ） — 証跡: 未
- [ ] C8 sha256 を書き換えない — 証跡: 未
- [ ] C9 実物との突き合わせ — 証跡: 未
- [ ] C10 変異 → red — 証跡: 未
- [ ] C11 docs — 証跡: 未

## 設計（2026-11-28）

ユーザー確認で決めたこと: 知らせ方は「PR は作り最後に失敗」、x86_64 との版の一致は注記に格下げ、版はリンクと文言の両方から読んで照合、直すまで毎週失敗。

- `scripts/refresh_pins.py`
  - `_parse_osxexperts_arm64(html) -> dict[str, tuple[str, str]]`（純関数）: ツール（`ffmpeg` / `ffprobe`）ごとに、`href` の `https://www.osxexperts.net/<tool><数字>arm.zip` と、文言 `Download <tool> <版> (Apple Silicon)` をそれぞれちょうど 1 件探す。リンクの数字が版から `.` を除いたものと一致すれば `(版, URL)` を返す。見つからない・複数ある・食い違うときは `ArmPageError` を送出する。
  - `check_ffmpeg_mac_arm64(arm_pin) -> list[str]`: ページを `_http_text` で取得し（失敗は「検査できなかった（取得失敗）」）、`_parse_osxexperts_arm64` で読み（`ArmPageError` は「検査できなかった（構造）」）、ツールごとにページの版・URL とピンを比べる（違えば「古い」）。ピンの URL は `_url_ok`（GET してステータスだけ見る）で確かめる（取得できなければ「古い」）。警告の文字列のリストを返し、例外は外へ出さない。
  - `refresh_ffmpeg_mac()` は変えない（arm64 を書き換えない）。x86_64 と arm64 の版が違うときは、状況欄の文言に注記を足す。
  - `refresh_pins()` は `(new_pins, changes, statuses, alerts)` を返す。`alerts` は `check_ffmpeg_mac_arm64(pins["ffmpeg-mac"]["arm64"])`。
  - `_build_summary(changes, statuses, alerts)`: 警告があれば先頭に `> [!CAUTION]` の欄（警告の箇条書きと手で更新する手順）を出す。
  - `main()`: `--alerts-out` を足し、警告を 1 行ずつ書き出す（警告が無ければ空ファイル）。終了コードは 0 のまま（PR 作成を止めない）。
- `.github/workflows/update-binaries.yml`: Refresh pins に `--alerts-out "${RUNNER_TEMP}/pin-alerts.txt"` を足す。PR 作成の後に「Fail if arm64 pin needs attention」ステップを置き、ファイルが空でなければ 1 行ずつ `::error::` を出して `exit 1`。前のステップが成功していれば PR の有無に関係なく走る。
- ページの取得は 1 回だけ（リトライしない）。一時的な失敗でもその週は失敗として知らせ、翌週に再検査する。

## 訂正ログ

| 日付 | 誤って書いたこと | 正しくは | 原因と再発防止 |
|---|---|---|---|

## 次にやること

- design-review（investigate の推奨が yes）
- テスト先行（`tests/test_refresh_pins.py`・`tests/test_update_binaries_workflow.py`）

訂正ログ: 0 件
