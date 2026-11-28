# macOS arm64 の ffmpeg ピンの古さを週次で検知する

> Issue: [#412](https://github.com/f8924919/yt-gui/issues/412)
> ステータス: 進行中
> ブランチ: `feature/412-arm64-pin-staleness`
> 基点: `dd66c0d`

受け入れ条件の正本は Issue（2026-11-28 に criteria-review とユーザー確認を経て書き直した版）。設計は [build.md](../build.md) の「更新運用」「同梱バイナリのピン自動更新（GitHub Actions）」。

## 進捗

- [x] C1 版の読み取り（リンクと文言の両方・末尾 `.0` の省略・Intel と ffplay を拾わない） — 証跡: `test_parse_osxexperts_reads_apple_silicon_91`、`…_accepts_dropped_trailing_zero_in_link`（9.0 の実物断片）、`…_rejects_broken_structure`（link_only・text_only・link_text_mismatch・duplicate_link）、`test_check_arm64_ffmpeg_ffprobe_version_split_is_reported`（a2ee01b）。下の「変異 → red」の M2・M8・M9
- [x] C2 古さの判定（x86_64 との差だけでは警告しない） — 証跡: `test_check_arm64_current_pin_has_no_alerts`、`…_old_pin_is_stale`、`…_url_differs_from_page_is_stale`、`…_pin_90_written_as_9_matches_90_page`、`test_same_version_ignores_trailing_zero`、`test_refresh_ffmpeg_mac_notes_arch_version_difference`（a2ee01b）。M1・M3
- [x] C3 URL の生存（HEAD / Range、404・410 と 5xx の区別、リダイレクト・非 zip） — 証跡: `test_url_ok_*`（6 関数・10 ケース）、`test_check_arm64_gone_url_is_stale_per_tool`（ffmpeg・ffprobe）、`…_url_check_error_is_unchecked`（a2ee01b）。実物で、ピンの 2 本は ok、取り下げ済みの `ffmpeg9arm.zip` は gone（下の「C9」）。M4
- [x] C4 検査不能の区別（取得失敗・リンクだけ・文言だけ・食い違い） — 証跡: `test_check_arm64_fetch_failure_is_unchecked`、`…_fetch_http_error_reports_status_code`（4cbde5f）、`…_structure_change_is_unchecked_and_does_not_leak_html`、`…_unexpected_exception_becomes_unchecked`、C1 の構造のテスト（a2ee01b）。M5・M6・M7・M19
- [x] C5 他の再ピンを止めない・検査を先に行い先に書く — 証跡: `test_run_checks_and_writes_alerts_before_refresh`、`test_run_passes_refresh_result_through_and_keeps_arm64`（a2ee01b）。M11
- [x] C6 警告の出力（サマリの先頭・警告ファイル） — 証跡: `test_build_summary_puts_alerts_first`、`…_without_alerts_has_no_caution`、`test_write_alerts_uses_lf_and_creates_empty_file`（a2ee01b）、`test_main_exits_zero_with_alerts_and_wires_outputs`（4cbde5f）。M16〜M18
- [x] C7 ジョブの失敗（PR 作成の後・PR 作成失敗でも走る・ファイル欠落は不備） — 証跡: `tests/test_update_binaries_workflow.py` の `test_refresh_step_writes_alerts_file`・`test_fail_step_*`（構造 5 本）と、スクリプトを bash で実行する `test_fail_step_script_behaviour`（4 ケース。f1e4d75）。M12〜M15
- [x] C8 sha256 を書き換えない — 証跡: `test_run_passes_refresh_result_through_and_keeps_arm64`、`test_run_with_real_check_does_not_touch_arm64_pin`、`test_refresh_ffmpeg_mac_notes_arch_version_difference`（arm64 不変）（a2ee01b）
- [x] C9 実物との突き合わせ — 証跡: 下の「C9」と、実物の `bin/pins.json` を読む `test_real_pins_json_arm64_matches_fixture_page`
- [x] C10 変異 → red — 証跡: 下の「変異 → red」（19 変異すべて、狙ったテストが落ちた）
- [x] C12 sha256 がページに載っているか — 証跡: `test_check_arm64_sha_missing_from_page_is_stale`、`…_sha_comparison_is_case_insensitive`（a2ee01b）。M10
- [x] C13 警告文に入れるもの（絞った値と固定文・LF） — 証跡: `test_check_arm64_fetch_failure_is_unchecked`・`…_structure_change_…`（HTML・`::error::` を流さない）、`test_alerts_are_single_line`、`test_write_alerts_uses_lf_and_creates_empty_file`（a2ee01b）
- [x] C11 docs — 証跡: `docs/build.md`「macOS arm64 のピンの古さの検知」と更新運用・ピン自動更新の表、`docs/research/binary-supply-chain.md` §5 の追記、`bin/pins.json` の arm64 の `comment`（7053e70、4a8d434、このコミット）

## 設計（2026-11-28。design-review の指摘を反映）

ユーザー確認で決めたこと: 知らせ方は「PR は作り最後に失敗」、x86_64 との版の一致は注記に格下げ、版はリンクと文言の両方から読んで照合、直すまで毎週失敗、ピンの sha256 がページに載っているかも見る（design-review の提案）。

- `scripts/refresh_pins.py`
  - `_parse_osxexperts_arm64(html) -> dict[str, tuple[str, str]]`（純関数）: ツール（`ffmpeg` / `ffprobe`）ごとに、`href` の `https://www.osxexperts.net/<tool><数字>arm.zip` と、文言 `Download <tool> <版> (Apple Silicon)` をそれぞれちょうど 1 件探す。版は文言を正とし、リンクの数字は照合にだけ使う。一致の判定は `_arm_link_tokens(版)`（版から `.` を除いたもの、または末尾の `.0` を省いてから `.` を除いたもの、のどちらか）。見つからない・複数ある・食い違うときは `ArmPageError` を送出する。
  - `_same_version(a, b)`: 末尾の `.0` を省いて比べる（ページとピンの版の比較に使う）。
  - `_url_ok(url) -> str`: HEAD（使えなければ `Range: bytes=0-0` の GET）で確かめ、`"ok"` / `"gone"`（404・410、別 URL へのリダイレクト、zip でない応答）/ `"error"`（タイムアウト・5xx・接続失敗）を返す。
  - `check_ffmpeg_mac_arm64(arm_pin, fetch_text=_http_text, url_ok=_url_ok) -> list[str]`: ページを取得し（失敗は「検査できなかった」。HTTPError は状態コードを入れる）、読み（`ArmPageError` は「検査できなかった（構造の変化またはブロック）」）、ツールごとにページの版・URL とピンを比べ（違えば「古い」）、ピンの URL を確かめ、ピンの sha256 がページにあるかを見る（無ければ「古い（差し替えの可能性）」）。ffmpeg と ffprobe でページの版が違えばその旨を出す。警告の文字列のリストを返す。全体を `except Exception` で受け、型名だけを入れた「検査できなかった」警告に変える（黙らない）。警告文には絞った値と固定文だけを入れる。
  - `refresh_ffmpeg_mac()` は変えない（arm64 を書き換えない）。x86_64 と arm64 の版が違うときは、状況欄の文言に注記を足す。
  - `refresh_pins()` は変えない。`run(pins, alerts_out=None)` が `check_ffmpeg_mac_arm64` → 警告ファイルの書き出し → `refresh_pins()` の順に呼び、`main()` は `run()` を呼ぶ。
  - `_build_summary(changes, statuses, alerts=())`: 警告があれば先頭に `> [!CAUTION]` の欄（警告の箇条書きと手で更新する手順）を出す。
  - `main()`: `--alerts-out` を足す。警告が無くても空ファイルを必ず作る。1 警告 1 行、`newline="\n"` で書く。終了コードは 0 のまま（PR 作成を止めない）。
- `.github/workflows/update-binaries.yml`: Refresh pins に `id: refresh` と `--alerts-out "${RUNNER_TEMP}/pin-alerts.txt"` を足す。PR 作成の後に「Fail if arm64 pin needs attention」ステップを置き、`if: ${{ !cancelled() }}`。Refresh pins が成功（`steps.refresh.outcome == 'success'`）なのにファイルが無ければ不備として失敗。ファイルが空でなければ `while IFS= read -r line || [ -n "$line" ]` で 1 行ずつ `printf '::error::%s\n'` を出して `exit 1`。
- ページの取得は 1 回だけ（リトライしない）。取得失敗の警告文で `workflow_dispatch` による再実行を促す。
- フィクスチャ: 現行ページ（9.1）と、Wayback の 2026-10-18 版（9.0、`ffmpeg9arm.zip`）から Apple Silicon と Intel の部分を切り出す。出所（URL・取得日時・sha256）をフィクスチャの先頭に書く。
- C9 は手元からの取得で確かめる。ランナーからの実行は、ワークフローを手動で回すとピン更新 PR が実際に作られうるため、マージ後の週次実行で確かめる。

## テスト先行の red（2026-11-28、HEAD `4a8d434`＝実装前）

`uv run pytest tests/test_refresh_pins.py tests/test_update_binaries_workflow.py -q` の要約行: `40 failed, 26 passed, 5 errors`。失敗はすべて新しいテスト（`AttributeError`: `_parse_osxexperts_arm64` などが未実装、ワークフローは `--alerts-out` が無い・失敗ステップが無い）。既存のテストは 26 本とも pass。

## C9 実物との突き合わせ（2026-11-28、HEAD `4a8d434`、`scripts/refresh_pins.py` は a2ee01b と同じ作業ツリー）

- 取得: `https://www.osxexperts.net/` を 2026-11-28T03:52:04Z に取得（UA `yt-gui-pin-refresh`、Windows の手元から）。36,168 バイト、sha256 `cadec69ed157ec5ac29e9c623a382f86121a5b428103940c1eab25f0009fa60c`（フィクスチャ `tests/data/osxexperts_arm64_9.1.html` の切り出し元と同じハッシュ）
- 生の行:
  - `<a href="https://www.osxexperts.net/ffmpeg91arm.zip" class="btn btn-c-5861" target="_blank">Download ffmpeg 9.1 (Apple Silicon)</a>`
  - `</h3><a href="https://www.osxexperts.net/ffprobe91arm.zip" class="btn btn-c-5861" target="_blank">Download ffprobe 9.1 (Apple Silicon)</a>`
- 抽出: ffmpeg `('9.1', 'https://www.osxexperts.net/ffmpeg91arm.zip')`、ffprobe `('9.1', 'https://www.osxexperts.net/ffprobe91arm.zip')`
- ピン（`bin/pins.json` の `ffmpeg-mac.arm64`）: version `9.1`、ffmpeg `https://www.osxexperts.net/ffmpeg91arm.zip`、ffprobe `https://www.osxexperts.net/ffprobe91arm.zip`
- `_url_ok`: ffmpeg `ok`、ffprobe `ok`、取り下げ済みの `https://www.osxexperts.net/ffmpeg9arm.zip` は `gone`
- `check_ffmpeg_mac_arm64(ピン)`: 1 回目は `arm64 のピンを検査できなかった: … を取得できない（HTTPError）` になった。直後に 3 回続けて取得するとすべて成功し、もう一度検査すると警告 0 件（`[]`）。1 回目は、数十秒のうちにページの取得と HEAD を繰り返した後だったので、一時的な制限とみられる（状態コードは控えていない）。
- 再現の確認（2026-11-28T03:59:06Z〜、HEAD `bdfe5da`）: 検査と同じ順（ページ GET → ffmpeg HEAD → ffprobe HEAD）を 6 回、続けて既定の取得関数での検査を 3 回、間を空けずに行った。ページ GET 9 回・HEAD 18 回の計 27 回はすべて 200 で、警告は毎回 0 件。原因は特定できなかった。次に起きたときに切り分けられるよう、警告に HTTP の状態コードを入れた（4cbde5f）。リトライは入れない（週次の実行は 1 回だけ取得し、一時的な失敗ならその週は「検査できなかった」で失敗する。警告文で再実行を促す）
- ランナーからの実行はしていない（手動でワークフローを回すとピン更新 PR が作られうるため）。マージ後の週次実行で確かめる

## 変異 → red（2026-11-28、基点 `4cbde5f`）

作業用のハーネス（scratchpad の `mutate.py`。追跡しない）が、1 変異ずつ置換を 1 か所だけ当て（当たり 0 件・2 件以上はハーネスの失敗として止める）、`tests/test_refresh_pins.py`・`tests/test_update_binaries_workflow.py` を走らせて落ちたテストを集め、`git checkout` で戻して `git diff --quiet` を確かめた。無変異は `passed=77`、戻した後も `passed=77`。

| 変異 | 書き換え | 落ちたテスト |
|---|---|---|
| M1 | 版の比較を常に一致扱い（`if not _same_version(page_version, pin_version):` → `if False:`） | `test_check_arm64_old_pin_is_stale` |
| M2 | リンクの末尾 `.0` の正規化を外す | `test_parse_osxexperts_accepts_dropped_trailing_zero_in_link`、`test_check_arm64_pin_90_written_as_9_matches_90_page` |
| M3 | 版の比較の末尾 `.0` の正規化を外す（`return a == b`） | `test_same_version_ignores_trailing_zero`、`test_check_arm64_pin_90_written_as_9_matches_90_page` |
| M4 | URL の生存確認を無効にする（`status = "ok"`） | `test_check_arm64_gone_url_is_stale_per_tool[ffmpeg]`・`[ffprobe]`、`test_check_arm64_url_check_error_is_unchecked` |
| M5 | 構造の変化を握りつぶす（`return [] and [`） | `test_check_arm64_structure_change_is_unchecked_and_does_not_leak_html` |
| M6 | 取得失敗を握りつぶす | `test_check_arm64_fetch_failure_is_unchecked`、`test_check_arm64_fetch_http_error_reports_status_code` |
| M7 | 想定外の例外を握りつぶす | `test_check_arm64_unexpected_exception_becomes_unchecked` |
| M8 | Intel 版も拾う（`arm\.zip` → `(?:arm\|intel)\.zip`） | 14 件（`test_parse_osxexperts_reads_apple_silicon_91`、`…_accepts_dropped_trailing_zero_in_link`、`test_real_pins_json_arm64_matches_fixture_page` ほか） |
| M9 | リンクと文言の照合を外す | `test_parse_osxexperts_rejects_broken_structure[link_text_mismatch]` |
| M10 | sha256 の確認を外す | `test_check_arm64_sha_missing_from_page_is_stale`、`test_run_with_real_check_does_not_touch_arm64_pin` |
| M11 | 検査を再ピンの後に回す | `test_run_checks_and_writes_alerts_before_refresh` |
| M12 | 失敗ステップを消す | 9 件（`test_fail_step_*` の構造 5 本と `test_fail_step_script_behaviour` 4 ケース） |
| M13 | 失敗ステップの条件を `success()` にする | `test_fail_step_runs_even_if_pr_creation_failed` |
| M14 | ファイル欠落の判定を消す（`if [ "$REFRESH_OUTCOME" = "success" ]` → `if false`） | `test_fail_step_script_behaviour[missing_after_success]` |
| M15 | `--alerts-out` を外す | `test_refresh_step_writes_alerts_file`、`test_fail_step_reads_same_alerts_file` |
| M16 | 警告があれば `main()` を非 0 で終える（`return 1 if alerts else 0`） | `test_main_exits_zero_with_alerts_and_wires_outputs` |
| M17 | PR 本文に警告を渡さない（`_build_summary(changes, statuses)`） | `test_main_exits_zero_with_alerts_and_wires_outputs` |
| M18 | `--alerts-out` を `run()` に渡さない | `test_main_exits_zero_with_alerts_and_wires_outputs` |
| M19 | 取得失敗の警告に状態コードを入れない | `test_check_arm64_fetch_http_error_reports_status_code` |

M14 は、最初のハーネス実行（基点 `a2ee01b`、M1〜M15）では**生き残った**（構造のテストが文字列の有無しか見ていなかった）。失敗ステップのスクリプトを bash で実際に走らせる `test_fail_step_script_behaviour` を足した（f1e4d75）。M16〜M18 は、`main()` を走らせるテストが無く生き残る形だったので、`test_main_exits_zero_with_alerts_and_wires_outputs` を足してから掛けた（4cbde5f）。M6 は 4cbde5f で置換の箇所が当たらなくなり、ハーネスが止まったので、置換を今のコードに合わせて直した。
## 訂正ログ

| 日付 | 誤って書いたこと | 正しくは | 原因と再発防止 |
|---|---|---|---|
| 2026-11-28 | 設計に「リンクの数字が版から `.` を除いたものと一致すれば採用」と書いた | osxexperts は 9.0 を `ffmpeg9arm.zip`（`.0` を省く）、9.1 を `ffmpeg91arm.zip` と名付けており、当初の規則では 9.0 の期間に毎週「検査できない」になる。末尾 `.0` の省略も一致とする | 現行ページ 1 枚（9.1）だけを見て規則を決めた。#411 の直前のピン（`ffmpeg9arm.zip` が 9.0）を見れば分かった。外部の命名規則は、手元にある過去の値（git 履歴のピン・アーカイブ）と突き合わせてから書く。伝播先は「除いた」で洗い、このメモの設計節だけだった |

## 次にやること

- `/verify-gate`（verify → docs-check → evaluator）→ PR

訂正ログ: 1 件