# macOS arm64 の ffmpeg ピンの古さを週次で検知する

> Issue: [#412](https://github.com/f8924919/yt-gui/issues/412)
> ステータス: 完了（PR #PRNUM）
> ブランチ: `feature/412-arm64-pin-staleness`
> 基点: `dd66c0d`

受け入れ条件の正本は Issue（2026-11-28 に criteria-review とユーザー確認を経て書き直した版）。設計は [build.md](../../build.md) の「更新運用」「同梱バイナリのピン自動更新（GitHub Actions）」。

## 進捗

- [x] C1 版の読み取り（リンクと文言の両方・末尾 `.0` の省略・Intel と ffplay を拾わない） — 証跡: `test_parse_osxexperts_reads_apple_silicon_91`、`…_accepts_dropped_trailing_zero_in_link`（9.0 の実物断片）、`…_rejects_broken_structure`（link_only・text_only・link_text_mismatch・duplicate_link）、`test_check_arm64_ffmpeg_ffprobe_version_split_is_reported`（a2ee01b）。下の「変異 → red」の M2・M8・M9
- [x] C2 古さの判定（x86_64 との差だけでは警告しない） — 証跡: `test_check_arm64_current_pin_has_no_alerts`、`…_old_pin_is_stale`、`…_url_differs_from_page_is_stale`、`…_pin_90_written_as_9_matches_90_page`、`test_same_version_ignores_trailing_zero`、`test_refresh_ffmpeg_mac_notes_arch_version_difference`（a2ee01b）、`test_run_does_not_alert_on_x86_arm_version_difference_alone`（e7c3cc7）、`test_check_arm64_version_mismatch_alone_is_stale`（b8dc053）。M1・M3・M21・M24
- [x] C3 URL の生存（HEAD / Range、404・410 と 5xx の区別、リダイレクト・非 zip） — 証跡: `test_url_ok_*`（a2ee01b の 6 関数・10 ケースに、e7c3cc7 の `test_url_ok_redirect_to_other_zip_is_gone`・`test_url_ok_error_on_raw_oserror`（2 ケース）を足した）、`test_check_arm64_gone_url_is_stale_per_tool`（ffmpeg・ffprobe）、`…_url_check_error_is_unchecked`（a2ee01b）。実物で、ピンの 2 本は ok、取り下げ済みの `ffmpeg9arm.zip` は gone（下の「C9」）。M4・M20・M23
- [x] C4 検査不能の区別（取得失敗・リンクだけ・文言だけ・食い違い） — 証跡: `test_check_arm64_fetch_failure_is_unchecked`、`…_fetch_http_error_reports_status_code`（4cbde5f）、`…_structure_change_is_unchecked_and_does_not_leak_html`、`…_unexpected_exception_becomes_unchecked`、C1 の構造のテスト（a2ee01b）、ページ取得のリトライの `test_check_arm64_retries_page_fetch_on_503_then_succeeds`・`…_gives_up_after_retries_and_reports`・`…_does_not_retry_permanent_failure`（2176eb9）。M5・M6・M7・M19・M25・M26
- [x] C5 他の再ピンを止めない・検査を先に行い先に書く — 証跡: `test_run_checks_and_writes_alerts_before_refresh`、`test_run_passes_refresh_result_through_and_keeps_arm64`（a2ee01b）。M11
- [x] C6 警告の出力（サマリの先頭・警告ファイル） — 証跡: `test_build_summary_puts_alerts_first`、`…_without_alerts_has_no_caution`、`test_write_alerts_uses_lf_and_creates_empty_file`（a2ee01b）、`test_main_exits_zero_with_alerts_and_wires_outputs`（4cbde5f）、`test_run_writes_empty_alerts_file_when_no_alerts`（e7c3cc7）。M16〜M18・M22
- [x] C7 ジョブの失敗（PR 作成の後・PR 作成失敗でも走る・ファイル欠落は不備） — 証跡: `tests/test_update_binaries_workflow.py` の `test_refresh_step_writes_alerts_file`・`test_fail_step_*`（構造 5 本）と、スクリプトを bash で実行する `test_fail_step_script_behaviour`（4 ケース。f1e4d75）。M12〜M15
- [x] C8 sha256 を書き換えない — 証跡: `test_run_passes_refresh_result_through_and_keeps_arm64`、`test_run_with_real_check_does_not_touch_arm64_pin`、`test_refresh_ffmpeg_mac_notes_arch_version_difference`（arm64 不変）（a2ee01b）
- [x] C9 実物との突き合わせ — 証跡: 下の「C9」と、実物の `bin/pins.json` を読む `test_real_pins_json_arm64_matches_fixture_page`
- [x] C10 変異 → red — 証跡: 下の「変異 → red」（28 変異すべて、狙ったテストが落ちた）
- [x] C12 sha256 がページに載っているか — 証跡: `test_check_arm64_sha_missing_from_page_is_stale`、`…_sha_comparison_is_case_insensitive`（a2ee01b）、`…_malformed_pin_sha_is_stale`（empty・truncated・non_hex）・`…_page_sha_in_uppercase_still_matches`（a177b99）。M10・M27・M28
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
- ページの取得は、一時的な失敗（5xx・429・接続失敗・タイムアウト）のときだけ 10 秒・30 秒と待って計 3 回まで取得し直す（`_fetch_page`・`_PAGE_RETRY_WAITS`。2176eb9）。当初は「リトライしない」としていたが、手元で HTTP 503 を観測したので変えた（状態コードで確かめたのは 1 回。下の「C9」）。2026-11-28 にユーザーの確認を得て、Issue の方針も改訂した。取得し尽くしても失敗した警告文に HTTP の状態コードを入れ、`workflow_dispatch` による再実行を促す。
- フィクスチャ: 現行ページ（9.1）と、Wayback の 2026-10-18 版（9.0、`ffmpeg9arm.zip`）から Apple Silicon と Intel の部分を切り出す。出所（URL・取得日時・sha256）をフィクスチャの先頭に書く。
- C9 は手元からの取得で確かめる。ランナーからの実行は、ワークフローを手動で回すとピン更新 PR が実際に作られうるため、マージ後の週次実行で確かめる。

## テスト先行の red（2026-11-28）

実装前のコード（HEAD `4a8d434` の `scripts/refresh_pins.py`・`.github/workflows/update-binaries.yml`）に、`a177b99` のテストとフィクスチャを当てて走らせた（scratchpad に一時的な作業ツリーを作り、本体の `.venv` の Python で `pytest -q -rfE`。終わった後に作業ツリーは消した）。要約行は `57 failed, 26 passed, 9 errors in 0.79s`。落ちたのは新しく足したテストだけで、既存の 26 本はすべて pass。テストを書いた直後（4a8d434 の時点のテスト）の要約行は `40 failed, 26 passed, 5 errors` で、その後に足したテストの分だけ増えている。

<details><summary>FAILED / ERROR の行（66 件）</summary>

  - `FAILED tests/test_refresh_pins.py::test_parse_osxexperts_reads_apple_silicon_91`
  - `FAILED tests/test_refresh_pins.py::test_parse_osxexperts_accepts_dropped_trailing_zero_in_link`
  - `FAILED tests/test_refresh_pins.py::test_parse_osxexperts_rejects_broken_structure[link_only]`
  - `FAILED tests/test_refresh_pins.py::test_parse_osxexperts_rejects_broken_structure[text_only]`
  - `FAILED tests/test_refresh_pins.py::test_parse_osxexperts_rejects_broken_structure[link_text_mismatch]`
  - `FAILED tests/test_refresh_pins.py::test_parse_osxexperts_rejects_broken_structure[duplicate_link]`
  - `FAILED tests/test_refresh_pins.py::test_same_version_ignores_trailing_zero`
  - `FAILED tests/test_refresh_pins.py::test_check_arm64_current_pin_has_no_alerts`
  - `FAILED tests/test_refresh_pins.py::test_check_arm64_pin_90_written_as_9_matches_90_page`
  - `FAILED tests/test_refresh_pins.py::test_check_arm64_old_pin_is_stale`
  - `FAILED tests/test_refresh_pins.py::test_check_arm64_url_differs_from_page_is_stale`
  - `FAILED tests/test_refresh_pins.py::test_check_arm64_sha_missing_from_page_is_stale`
  - `FAILED tests/test_refresh_pins.py::test_check_arm64_sha_comparison_is_case_insensitive`
  - `FAILED tests/test_refresh_pins.py::test_check_arm64_ffmpeg_ffprobe_version_split_is_reported`
  - `FAILED tests/test_refresh_pins.py::test_refresh_ffmpeg_mac_notes_arch_version_difference`
  - `FAILED tests/test_refresh_pins.py::test_url_ok_head_200_zip`
  - `FAILED tests/test_refresh_pins.py::test_url_ok_gone_on_404_410[404]`
  - `FAILED tests/test_refresh_pins.py::test_url_ok_gone_on_404_410[410]`
  - `FAILED tests/test_refresh_pins.py::test_url_ok_error_on_server_or_network_failure[500]`
  - `FAILED tests/test_refresh_pins.py::test_url_ok_error_on_server_or_network_failure[503]`
  - `FAILED tests/test_refresh_pins.py::test_url_ok_error_on_server_or_network_failure[timeout]`
  - `FAILED tests/test_refresh_pins.py::test_url_ok_error_on_server_or_network_failure[oserror]`
  - `FAILED tests/test_refresh_pins.py::test_url_ok_redirect_to_other_url_is_gone`
  - `FAILED tests/test_refresh_pins.py::test_url_ok_non_zip_response_is_gone`
  - `FAILED tests/test_refresh_pins.py::test_url_ok_falls_back_to_range_get_when_head_not_allowed`
  - `FAILED tests/test_refresh_pins.py::test_check_arm64_gone_url_is_stale_per_tool[ffmpeg]`
  - `FAILED tests/test_refresh_pins.py::test_check_arm64_gone_url_is_stale_per_tool[ffprobe]`
  - `FAILED tests/test_refresh_pins.py::test_check_arm64_url_check_error_is_unchecked`
  - `FAILED tests/test_refresh_pins.py::test_check_arm64_fetch_failure_is_unchecked`
  - `FAILED tests/test_refresh_pins.py::test_check_arm64_structure_change_is_unchecked_and_does_not_leak_html`
  - `FAILED tests/test_refresh_pins.py::test_check_arm64_unexpected_exception_becomes_unchecked`
  - `FAILED tests/test_refresh_pins.py::test_alerts_are_single_line`
  - `FAILED tests/test_refresh_pins.py::test_write_alerts_uses_lf_and_creates_empty_file`
  - `FAILED tests/test_refresh_pins.py::test_build_summary_puts_alerts_first`
  - `FAILED tests/test_refresh_pins.py::test_build_summary_without_alerts_has_no_caution`
  - `FAILED tests/test_refresh_pins.py::test_run_checks_and_writes_alerts_before_refresh`
  - `FAILED tests/test_refresh_pins.py::test_run_passes_refresh_result_through_and_keeps_arm64`
  - `FAILED tests/test_refresh_pins.py::test_run_with_real_check_does_not_touch_arm64_pin`
  - `FAILED tests/test_refresh_pins.py::test_real_pins_json_arm64_matches_fixture_page`
  - `FAILED tests/test_refresh_pins.py::test_check_arm64_fetch_http_error_reports_status_code`
  - `FAILED tests/test_refresh_pins.py::test_main_exits_zero_with_alerts_and_wires_outputs`
  - `FAILED tests/test_refresh_pins.py::test_url_ok_redirect_to_other_zip_is_gone`
  - `FAILED tests/test_refresh_pins.py::test_url_ok_error_on_raw_oserror[timed out]`
  - `FAILED tests/test_refresh_pins.py::test_url_ok_error_on_raw_oserror[reset]`
  - `FAILED tests/test_refresh_pins.py::test_run_does_not_alert_on_x86_arm_version_difference_alone`
  - `FAILED tests/test_refresh_pins.py::test_run_writes_empty_alerts_file_when_no_alerts`
  - `FAILED tests/test_refresh_pins.py::test_check_arm64_version_mismatch_alone_is_stale`
  - `FAILED tests/test_refresh_pins.py::test_check_arm64_retries_page_fetch_on_503_then_succeeds`
  - `FAILED tests/test_refresh_pins.py::test_check_arm64_gives_up_after_retries_and_reports[503]`
  - `FAILED tests/test_refresh_pins.py::test_check_arm64_gives_up_after_retries_and_reports[429]`
  - `FAILED tests/test_refresh_pins.py::test_check_arm64_gives_up_after_retries_and_reports[timeout]`
  - `FAILED tests/test_refresh_pins.py::test_check_arm64_does_not_retry_permanent_failure`
  - `FAILED tests/test_refresh_pins.py::test_check_arm64_malformed_pin_sha_is_stale[empty]`
  - `FAILED tests/test_refresh_pins.py::test_check_arm64_malformed_pin_sha_is_stale[truncated]`
  - `FAILED tests/test_refresh_pins.py::test_check_arm64_malformed_pin_sha_is_stale[non_hex]`
  - `FAILED tests/test_refresh_pins.py::test_check_arm64_page_sha_in_uppercase_still_matches`
  - `FAILED tests/test_update_binaries_workflow.py::test_refresh_step_writes_alerts_file`
  - `ERROR tests/test_update_binaries_workflow.py::test_fail_step_reads_same_alerts_file`
  - `ERROR tests/test_update_binaries_workflow.py::test_fail_step_comes_after_pr_creation`
  - `ERROR tests/test_update_binaries_workflow.py::test_fail_step_runs_even_if_pr_creation_failed`
  - `ERROR tests/test_update_binaries_workflow.py::test_fail_step_fails_on_alerts_with_error_annotation`
  - `ERROR tests/test_update_binaries_workflow.py::test_fail_step_treats_missing_file_after_success_as_failure`
  - `ERROR tests/test_update_binaries_workflow.py::test_fail_step_script_behaviour[missing_after_success]`
  - `ERROR tests/test_update_binaries_workflow.py::test_fail_step_script_behaviour[missing_after_failure]`
  - `ERROR tests/test_update_binaries_workflow.py::test_fail_step_script_behaviour[empty]`
  - `ERROR tests/test_update_binaries_workflow.py::test_fail_step_script_behaviour[two_alerts]`

</details>

## C9 実物との突き合わせ（2026-11-28、HEAD `4a8d434`、`scripts/refresh_pins.py` は a2ee01b と同じ作業ツリー）

- 取得: `https://www.osxexperts.net/` を 2026-11-28T03:52:04Z に取得（UA `yt-gui-pin-refresh`、Windows の手元から）。36,168 バイト、sha256 `cadec69ed157ec5ac29e9c623a382f86121a5b428103940c1eab25f0009fa60c`（フィクスチャ `tests/data/osxexperts_arm64_9.1.html` の切り出し元と同じハッシュ）
- 生の行:
  - `<a href="https://www.osxexperts.net/ffmpeg91arm.zip" class="btn btn-c-5861" target="_blank">Download ffmpeg 9.1 (Apple Silicon)</a>`
  - `</h3><a href="https://www.osxexperts.net/ffprobe91arm.zip" class="btn btn-c-5861" target="_blank">Download ffprobe 9.1 (Apple Silicon)</a>`
- 抽出: ffmpeg `('9.1', 'https://www.osxexperts.net/ffmpeg91arm.zip')`、ffprobe `('9.1', 'https://www.osxexperts.net/ffprobe91arm.zip')`
- ピン（`bin/pins.json` の `ffmpeg-mac.arm64`）: version `9.1`、ffmpeg `https://www.osxexperts.net/ffmpeg91arm.zip`、ffprobe `https://www.osxexperts.net/ffprobe91arm.zip`
- `_url_ok`: ffmpeg `ok`、ffprobe `ok`、取り下げ済みの `https://www.osxexperts.net/ffmpeg9arm.zip` は `gone`
- `check_ffmpeg_mac_arm64(ピン)`: 1 回目は `arm64 のピンを検査できなかった: … を取得できない（HTTPError）` になった。直後に 3 回続けて取得するとすべて成功し、もう一度検査すると警告 0 件（`[]`）。1 回目は、数十秒のうちにページの取得と HEAD を繰り返した後だったので、一時的な制限とみられる（状態コードは控えていない）と書いたが、誤り（訂正ログ 2 件目。下の取り直しで HTTP 503 を確かめた）。
- 再現の確認（2026-11-28T03:59:06Z〜、HEAD `bdfe5da`）: 検査と同じ順（ページ GET → ffmpeg HEAD → ffprobe HEAD）を 6 回、続けて既定の取得関数での検査を 3 回、間を空けずに行った。ページ GET 9 回・HEAD 18 回の計 27 回はすべて 200 で、警告は毎回 0 件。原因は特定できなかった。次に起きたときに切り分けられるよう、警告に HTTP の状態コードを入れた（4cbde5f）。
- 取り直し（2026-11-28T04:16:29Z、HEAD `b8dc053`）: ページ 36,168 バイト・sha256 `cadec69e…`（上と同じ）、生の行・抽出・ピン・`_url_ok` の結果は上と同じ。ただし検査そのもの（2 回目のページ取得）が `arm64 のピンを検査できなかった: … を取得できない（HTTP 503）` になった。直後（04:17:25Z）に 1 秒おきに 12 回取得すると、すべて 200 で、応答はキャッシュ（Varnish。`Age` が 33 から 55 へ増え、`X-Varnish` に 2 つの ID）から返っていた。キャッシュが切れて配布元へ取りに行ったときに 503 が返るとみられる。週次の実行はランナーからの初回アクセスでこの条件に当たりやすいので、ページ取得の一時的な失敗だけ取得し直すようにした（2176eb9。`test_check_arm64_retries_page_fetch_on_503_then_succeeds` ほか）
- 取り直し（2026-11-28T04:20:45Z、HEAD `2176eb9`、コードの作業ツリーは clean）: ページ 36,168 バイト・sha256 `cadec69ed157ec5ac29e9c623a382f86121a5b428103940c1eab25f0009fa60c`、生の行・抽出（ffmpeg / ffprobe とも 9.1・`…91arm.zip`）・ピン（9.1）は上と同じ。`_url_ok` はピンの 2 本が ok、`ffmpeg9arm.zip` が gone。`check_ffmpeg_mac_arm64(ピン)` は警告 0 件（`[]`）。その後の HEAD までに `scripts/refresh_pins.py` が変わったのは a177b99 の `_fetch_page` の docstring 5 行だけで（`git diff 2176eb9 HEAD -- scripts bin tests/data .github`）、挙動は変わっていない
- ランナーからの実行はしていない（手動でワークフローを回すとピン更新 PR が作られうるため）。マージ後の週次実行で確かめる

## 変異 → red（2026-11-28、基点 `a177b99`）

作業用のハーネス（scratchpad の `mutate.py`。追跡しない）が、1 変異ずつ置換を 1 か所だけ当て（当たり 0 件・2 件以上はハーネスの失敗として止める）、`tests/test_refresh_pins.py`・`tests/test_update_binaries_workflow.py` を走らせて落ちたテストを集め、`git checkout` で戻して `git diff --quiet` を確かめた。無変異は `passed=92`、戻した後も `passed=92`。同じ HEAD で全体は `1015 passed`（`uv run pytest -q`）。

| 変異 | 書き換え | 落ちたテスト |
|---|---|---|
| M1 | 版の比較を常に一致扱い（`if not _same_version(page_version, pin_version):` → `if False:`） | `test_check_arm64_version_mismatch_alone_is_stale` |
| M2 | リンクの末尾 `.0` の正規化を外す | `test_parse_osxexperts_accepts_dropped_trailing_zero_in_link`、`test_check_arm64_pin_90_written_as_9_matches_90_page` |
| M3 | 版の比較の末尾 `.0` の正規化を外す（`return a == b`） | `test_same_version_ignores_trailing_zero`、`test_check_arm64_pin_90_written_as_9_matches_90_page` |
| M4 | URL の生存確認を無効にする（`status = "ok"`） | `test_check_arm64_gone_url_is_stale_per_tool[ffmpeg]`、`test_check_arm64_gone_url_is_stale_per_tool[ffprobe]`、`test_check_arm64_url_check_error_is_unchecked` |
| M5 | 構造の変化を握りつぶす（`return [] and [`） | `test_check_arm64_structure_change_is_unchecked_and_does_not_leak_html` |
| M6 | 取得失敗を握りつぶす | `test_check_arm64_fetch_failure_is_unchecked`、`test_check_arm64_fetch_http_error_reports_status_code`、`test_check_arm64_gives_up_after_retries_and_reports[503]`、`test_check_arm64_gives_up_after_retries_and_reports[429]`、`test_check_arm64_gives_up_after_retries_and_reports[timeout]`、`test_check_arm64_does_not_retry_permanent_failure` |
| M7 | 想定外の例外を握りつぶす | `test_check_arm64_unexpected_exception_becomes_unchecked` |
| M8 | Intel 版も拾う（`arm\.zip` → `(?:arm\|intel)\.zip`） | `test_parse_osxexperts_reads_apple_silicon_91`、`test_parse_osxexperts_accepts_dropped_trailing_zero_in_link`、`test_check_arm64_current_pin_has_no_alerts`、`test_check_arm64_pin_90_written_as_9_matches_90_page`、`test_check_arm64_old_pin_is_stale`、`test_check_arm64_url_differs_from_page_is_stale`、`test_check_arm64_sha_missing_from_page_is_stale`、`test_check_arm64_sha_comparison_is_case_insensitive`、`test_check_arm64_ffmpeg_ffprobe_version_split_is_reported`、`test_check_arm64_gone_url_is_stale_per_tool[ffmpeg]`、`test_check_arm64_gone_url_is_stale_per_tool[ffprobe]`、`test_check_arm64_unexpected_exception_becomes_unchecked`、`test_run_with_real_check_does_not_touch_arm64_pin`、`test_real_pins_json_arm64_matches_fixture_page`、`test_run_does_not_alert_on_x86_arm_version_difference_alone`、`test_run_writes_empty_alerts_file_when_no_alerts`、`test_check_arm64_version_mismatch_alone_is_stale`、`test_check_arm64_retries_page_fetch_on_503_then_succeeds`、`test_check_arm64_malformed_pin_sha_is_stale[empty]`、`test_check_arm64_malformed_pin_sha_is_stale[truncated]`、`test_check_arm64_malformed_pin_sha_is_stale[non_hex]`、`test_check_arm64_page_sha_in_uppercase_still_matches` |
| M9 | リンクと文言の照合を外す | `test_parse_osxexperts_rejects_broken_structure[link_text_mismatch]` |
| M10 | sha256 の確認を外す | `test_check_arm64_sha_missing_from_page_is_stale`、`test_run_with_real_check_does_not_touch_arm64_pin` |
| M11 | 検査を再ピンの後に回す | `test_run_checks_and_writes_alerts_before_refresh` |
| M12 | 失敗ステップを消す | `test_fail_step_reads_same_alerts_file`、`test_fail_step_comes_after_pr_creation`、`test_fail_step_runs_even_if_pr_creation_failed`、`test_fail_step_fails_on_alerts_with_error_annotation`、`test_fail_step_treats_missing_file_after_success_as_failure`、`test_fail_step_script_behaviour[missing_after_success]`、`test_fail_step_script_behaviour[missing_after_failure]`、`test_fail_step_script_behaviour[empty]`、`test_fail_step_script_behaviour[two_alerts]` |
| M13 | 失敗ステップの条件を `success()` にする | `test_fail_step_runs_even_if_pr_creation_failed` |
| M14 | ファイル欠落の判定を消す（`if [ "$REFRESH_OUTCOME" = "success" ]` → `if false`） | `test_fail_step_script_behaviour[missing_after_success]` |
| M15 | `--alerts-out` を外す | `test_refresh_step_writes_alerts_file`、`test_fail_step_reads_same_alerts_file` |
| M16 | 警告があれば `main()` を非 0 で終える（`return 1 if alerts else 0`） | `test_main_exits_zero_with_alerts_and_wires_outputs` |
| M17 | PR 本文に警告を渡さない（`_build_summary(changes, statuses)`） | `test_main_exits_zero_with_alerts_and_wires_outputs` |
| M18 | `--alerts-out` を `run()` に渡さない | `test_main_exits_zero_with_alerts_and_wires_outputs` |
| M19 | 取得失敗の警告に状態コードを入れない | `test_check_arm64_fetch_http_error_reports_status_code`、`test_check_arm64_does_not_retry_permanent_failure` |
| M20 | リダイレクトの判定を外す（Content-Type だけを見る） | `test_url_ok_redirect_to_other_zip_is_gone` |
| M21 | x86_64 との版の差を警告に足す | `test_run_does_not_alert_on_x86_arm_version_difference_alone` |
| M22 | 警告が無いときは警告ファイルを作らない（`if alerts_out and alerts:`） | `test_run_writes_empty_alerts_file_when_no_alerts` |
| M23 | 生の `OSError` を捕まえない（`except urllib.error.URLError:`） | `test_url_ok_error_on_raw_oserror[timed out]`、`test_url_ok_error_on_raw_oserror[reset]` |
| M24 | URL だけ違う警告から版を外す | `test_check_arm64_url_differs_from_page_is_stale` |
| M25 | ページ取得を取得し直さない（`for wait in (None,):`） | `test_check_arm64_retries_page_fetch_on_503_then_succeeds`、`test_check_arm64_gives_up_after_retries_and_reports[503]`、`test_check_arm64_gives_up_after_retries_and_reports[429]`、`test_check_arm64_gives_up_after_retries_and_reports[timeout]` |
| M26 | 恒久的な失敗も取得し直す（`if wait is None:`） | `test_check_arm64_does_not_retry_permanent_failure` |
| M27 | ピンの sha256 の形（64 桁の 16 進）の確認を外す | `test_check_arm64_malformed_pin_sha_is_stale[empty]`、`test_check_arm64_malformed_pin_sha_is_stale[truncated]` |
| M28 | ページの sha256 を小文字にしない（`lowered = html`） | `test_check_arm64_page_sha_in_uppercase_still_matches` |

経緯: 最初の実行（基点 `a2ee01b`、M1〜M15）では M14 が生き残った（構造のテストが文字列の有無しか見ていなかった）ので、失敗ステップのスクリプトを bash で実際に走らせる `test_fail_step_script_behaviour` を足した（f1e4d75）。M16〜M18 は `main()` を走らせるテストが無く生き残る形だったので、`test_main_exits_zero_with_alerts_and_wires_outputs` を足した（4cbde5f）。M20〜M24 は evaluator（1 巡目）が scratchpad のコピーで生き残らせたもので、テストを足した（e7c3cc7）。その修正で URL が違うときの警告にも版を入れたため M1 が生き残り、版だけが違うピンのテストを足した（b8dc053）。M25・M26 はページ取得のリトライ（2176eb9）に合わせて足した。M27・M28 は evaluator（2 巡目）が生き残らせたもので、テストを足した（a177b99）。M27 で `non_hex` のケースが落ちないのは、16 進でない値はページに含まれず、sha256 がページに無いという同じ警告が別の条件で出るため（狙いの `empty`・`truncated` は落ちる）。

## 訂正ログ

| 日付 | 誤って書いたこと | 正しくは | 原因と再発防止 |
|---|---|---|---|
| 2026-11-28 | 設計に「リンクの数字が版から `.` を除いたものと一致すれば採用」と書いた | osxexperts は 9.0 を `ffmpeg9arm.zip`（`.0` を省く）、9.1 を `ffmpeg91arm.zip` と名付けており、当初の規則では 9.0 の期間に毎週「検査できない」になる。末尾 `.0` の省略も一致とする | 現行ページ 1 枚（9.1）だけを見て規則を決めた。#411 の直前のピン（`ffmpeg9arm.zip` が 9.0）を見れば分かった。外部の命名規則は、手元にある過去の値（git 履歴のピン・アーカイブ）と突き合わせてから書く。伝播先は「除いた」で洗い、このメモの設計節だけだった |
| 2026-11-28 | C9 に、1 回目の検査の HTTPError を「数十秒のうちに取得を繰り返した後だったので、一時的な制限とみられる」と書いた | 状態コードを入れて取り直すと HTTP 503 で、続けて取得するとキャッシュから 200 が返った。回数制限ではなく、キャッシュが切れたときに配布元が 503 を返すとみられる | 状態コードを控えずに原因を推測で書いた。外部の失敗は、状態コードと応答ヘッダーを控えてから原因を書く。伝播先は「制限」で洗い、このメモの C9 だけだった（設計の「リトライしない」は、この観測を受けた設計の変更として直した） |

## 検証ゲート

| 巡 | HEAD | verify | docs-check | evaluator |
|---|---|---|---|---|
| 1 | `76f24c7` | green（1000 passed、skip 0） | 1 件を修正（`refresh_ffmpeg_mac` の冒頭コメントに古さの検知を追記。76f24c7） | FAIL（[欠陥] 4 / [証跡・文言] 5） |
| 2 | `3d1ec87` | 主エージェントが確認（1011 passed） | — | FAIL（[欠陥] 2 / [証跡・文言] 3。1 巡目の 9 件はすべて閉じていると確認） |
| 3 | `35c5296` | evaluator が確認（1015 passed、ruff・mypy green） | — | PASS（follow-up あり。[欠陥] 0 / [証跡・文言] 5。2 巡目の 5 件はすべて閉じていると確認。5 件はすべてこの PR で直した: 変異の数の書き違い・`html.lower()` の記述の矛盾・C9 の鮮度の注記・build.md の更新運用の行の限定句・止め規則の読み直しの 1 行） |

1 巡目の指摘と閉じ方:

| # | 区分 | 指摘 | 閉じ方 | 証跡・コミット |
|---|---|---|---|---|
| 1 | 欠陥 | C2「x86_64 との差だけなら警告しない」にテストの錨が無い | テストを足した | `test_run_does_not_alert_on_x86_arm_version_difference_alone`（e7c3cc7）、変異 M21 |
| 2 | 欠陥 | C3 のリダイレクトの判定を単独で確かめるテストが無い | テストを足した | `test_url_ok_redirect_to_other_zip_is_gone`（e7c3cc7）、変異 M20 |
| 3 | 欠陥 | 警告 0 件で空の警告ファイルを作る約束にテストが無い | テストを足した | `test_run_writes_empty_alerts_file_when_no_alerts`（e7c3cc7）、変異 M22 |
| 4 | 欠陥（要判断） | URL だけ違うときの警告にページとピンの版が無い | 条件の文言どおり版を入れる側に直した（コードとテスト） | `scripts/refresh_pins.py` の URL 不一致の警告、`test_check_arm64_url_differs_from_page_is_stale`（e7c3cc7）、変異 M24。これで M1 が生き残ったので `test_check_arm64_version_mismatch_alone_is_stale`（b8dc053） |
| 5 | 証跡・文言 | テスト先行の red が要約行だけ | 実装前のコードに今のテストを当てて取り直し、FAILED / ERROR の行を貼った | 上の「テスト先行の red」 |
| 6 | 証跡・文言 | C9 の実物での確認が古い | HEAD `2176eb9` で取り直した（途中の `b8dc053` で 503 を観測し、ページ取得のリトライを入れた） | 上の「C9」、2176eb9 |
| 7 | 証跡・文言 | 変異の表の基点の後に対象のファイルが動いた | HEAD `2176eb9` で全 26 変異を取り直した | 上の「変異 → red」 |
| 8 | 証跡・文言 | 「戻した状態で全テストが green」が対象 2 ファイルだけ | 全体の結果（1011 passed）を HEAD つきで追記した | 上の「変異 → red」 |
| 9 | 証跡・文言 | 限定句の伝播漏れ（build.md の表の行、`docs/task/index.md`） | 限定句を足した | `docs/build.md` の「arm64 の古さの検知」の行、`docs/task/index.md` の #412 の行 |


2 巡目の指摘と閉じ方:

| # | 区分 | 指摘 | 閉じ方 | 証跡・コミット |
|---|---|---|---|---|
| D1 | 欠陥（要判断） | ページ取得のリトライが Issue 本文の方針（リトライしない）と食い違う | ユーザーの確認（「このまま続ける」。リトライを含める）を得て、Issue 本文の方針を改訂し、経緯をコメントに残した | Issue #412 の本文と 2026-11-28 のコメント、このメモの末尾の「止まった」 |
| D2 | 欠陥 | sha256 の確認の `re.fullmatch` の守りと `html.lower()` を外す変異が生き残る | テストを足した | `test_check_arm64_malformed_pin_sha_is_stale`・`test_check_arm64_page_sha_in_uppercase_still_matches`（a177b99）、変異 M27・M28 |
| 3 | 証跡・文言 | 「503 を 2 回観測」が実測（状態コードで確かめたのは 1 回）を上回る。原因を事実の形で書いている | build.md・`_fetch_page` の docstring・このメモを「確かめたのは 1 回」「とみられる」に直した | a177b99、このコミット |
| 4 | 証跡・文言 | build.md の「対象外」の行に限定句が無い | 限定句と次の行への参照を足した | a177b99 |
| 5 | 証跡・文言 | M23 のテスト ID が `[timed` で切れている | `[timed out]` に直した | 上の「変異 → red」 |

evaluator が独立の変異で生き残らせた `OSError` の捕捉の除去は、テストを足して塞いだ（`test_url_ok_error_on_raw_oserror`、e7c3cc7、変異 M23）。`html.lower()` の除去は、2 巡目の指摘（D2）で M28 として塞いだ。
## 次にやること

- なし（完了）。マージ後に main で `update-binaries.yml` を 1 回手動実行し、ランナーから検査が通る（警告 0 件）ことを確かめる（下の archive/index.md の申し送り）

訂正ログ: 2 件（止まった: 2026-11-28。ユーザーの判断は「このまま続ける」（ページ取得のリトライを含める））
読み直した結果: 2 件とも外部の事実（配布元の命名・失敗の原因）を確かめないまま書いた誤りで、設計の柱（知らせ方・版の照合・x86_64 との差を判定に使わない）には響かない。2 件目の観測からリトライを足したことだけが設計の変更で、Issue の方針も改訂した。