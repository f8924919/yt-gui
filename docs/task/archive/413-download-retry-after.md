# 同梱バイナリの取得で HTTP 429 / 503 に Retry-After で待ってリトライする

> Issue: [#413](https://github.com/f8924919/yt-gui/issues/413)
> ステータス: 完了（PR #417）
> ブランチ: `feature/413-download-retry-after`
> 基点: `3da4cbe`

受け入れ条件の正本は Issue（2026-11-28 に criteria-review とユーザー確認を経て書き直した版）。設計は [build.md](../../build.md) の「ピン留めと sha256 検証」のリトライの段落。前のタスクは [#265](265-download-retry.md)（取得リトライの導入）と [#412](412-arm64-pin-staleness.md)（`refresh_pins.py` のページ取得のリトライ）。

## 進捗

- [x] C1 共通のリトライ（`_download_verified` と arm64 が同じ関数・429/503 とそれ以外の分類） — 証跡: `_download_retrying` を `_download_verified` と `_download_ffmpeg_macos` の `verify: binary` 経路が呼ぶ（9dff740）。分類は C2・C6 のテスト。下の「変異 → red」の M7・M8
- [x] C2 Retry-After の秒数（本物の HTTPError・429 と 503・既定の待ちが下限・数字以外は不正） — 証跡: `test_retry_after_seconds_longer_than_default_is_used`（429・503）、`test_retry_after_shorter_than_default_uses_default`（429・503）、`test_retry_after_unparseable_uses_default`（11 値。下限 30 秒より大きい `+45`・`45.5`・`-45`・`1_045` を c69a477 で足した）、`test_retry_after_sec_parses_digits_with_surrounding_space`（9dff740）。M1・M2・M14・M15
- [x] C3 Retry-After の HTTP 日付（現在時刻の注入・過去・0 以下・不正値） — 証跡: `test_retry_after_sec_http_date`（6 ケース。タイムゾーン無しを含む）、`test_retry_after_sec_rounds_up_fraction`、`test_retry_after_sec_returns_none_without_header`（3 ケース）、`test_retry_after_http_date_goes_through_retry`（9dff740）、ホストのタイムゾーンによらない `test_retry_after_sec_naive_date_is_utc_regardless_of_host_tz`（c69a477）。M6・M16
- [x] C4 Retry-After が無いときの待ちの列（30・60・120・120） — 証跡: `test_throttle_default_waits`（429・503）、`test_throttle_constants`（リテラル）（9dff740）。M3
- [x] C5 上限（1 回 120 秒・120 と 121 の境界・最大 5 回・最悪 480 秒 / 混在で 7 回・486 秒） — 証跡: `test_throttle_wait_is_capped`（120・121）、`test_throttle_wait_cap_applies_to_http_date`（c69a477 で日付の 120・121 秒の境界を足した）、`test_throttle_gives_up_after_five_attempts`、`test_mixed_failures_worst_case_is_seven_attempts`（9dff740）。下の「最悪の値」。M4・M5
- [x] C6 対象外の失敗は今のまま（502 + Retry-After・408・404・混在・既存 6 本） — 証跡: `test_other_http_errors_keep_short_retry`（502 + Retry-After・408・404・410）、`test_mixed_failures_other_failures_still_stop_at_three`（9dff740）。既存のリトライのテスト 6 本は期待値を変えずに pass（下の「テスト先行の red」で実装前も pass）。M7
- [x] C7 取り尽くしたとき（最後の例外・状態・待った合計） — 証跡: `test_exhausted_throttle_reports_status_retry_after_and_total`、`test_exhausted_without_http_status_reports_none`（8bbc038 で毎試行の行を固有の書き方で確かめるよう直した）、`test_retry_after_raw_is_sanitized`、`test_throttle_gives_up_raising_the_last_error`・`test_mixed_failures_raise_the_last_error`（最後の例外のオブジェクトを送出。c69a477）、「次の待ち」の表示（c69a477）。M12・M13・M17・M18
- [x] C8 macOS arm64（取得と壊れた zip は取り直す・展開後の不一致と未設定は取り直さない） — 証跡: `test_mac_arm64_retries_throttled_download`、`…_retries_short_failure`、`…_retries_broken_zip`（bad_crc・missing_member・truncated）、`…_sha_mismatch_after_extract_is_not_retried`、`…_missing_sha_is_not_retried`（9dff740）。M8・M9・M10・M19
- [x] C9 sha256 の扱いは不変 — 証跡: 既存の `test_verify_sha256_*` 4 本と `test_download_verified_missing_expected_does_not_retry` が期待値を変えずに pass、`test_pin_config_error_is_runtime_error`、`test_missing_expected_after_throttle_still_aborts_without_retry`（9dff740）。M11
- [x] C10 実物との突き合わせ（ローカルの http.server） — 証跡: `test_download_verified_over_real_http_429`（9dff740）。下の「実物との突き合わせ」
- [x] C11 変異 → red — 証跡: 下の「変異 → red」（19 変異すべて、狙ったテストが落ちた）
- [x] C12 docs — 証跡: `docs/build.md`「ピン留めと sha256 検証」のリトライの段落（c1cc884、9439bfa、3db76ce）

## 設計（2026-11-28。design-review の指摘を反映）

ユーザー確認で決めたこと: 429 / 503 は最大 5 回・既定の待ち 30・60・120・120 秒・1 回 120 秒で切る、404 / 410 は今のまま、`Retry-After` は既定の待ちを下限にする（長いほうだけ待つ）、arm64 は転送中に壊れた zip を取り直す。

- `scripts/download_binaries.py`
  - 定数（正本）: `_THROTTLE_STATUSES = frozenset({429, 503})`、`_THROTTLE_WAITS_SEC = (30.0, 60.0, 120.0, 120.0)`、`_THROTTLE_MAX_WAIT_SEC = 120.0`、`_THROTTLE_ATTEMPTS = len(_THROTTLE_WAITS_SEC) + 1`（同じ事実を 2 か所に書かない）。
  - `class PinConfigError(RuntimeError)`: `_verify_sha256` が sha256 未設定のときに送出する。`_download_retrying` はこれを種類を問わず即座に送出する（取り直さない）。`RuntimeError` の子なので、既存テストの `pytest.raises(RuntimeError, match=r"pins\.json")` は通る。今の `isinstance(exc, RuntimeError) and not expected` の 2 か所の結び付きをなくす。
  - `_retry_after_sec(exc, now) -> float | None`: どんな入力でも例外を出さない（例外処理の中で呼ぶため）。`HTTPError` でない・`headers` が `None`・ヘッダが無いなら `None`。値が `[0-9]+`（ASCII の数字だけ。前後の空白は除く）なら整数の秒、そうでなければ `email.utils.parsedate_to_datetime` で日付として読み、タイムゾーンが無ければ UTC とみなして（日付 − `now()`）秒を切り上げる。`ValueError` / `TypeError` / `OverflowError` / `AttributeError` と 0 以下は `None`。
  - `_retry_after_raw(exc) -> str`: 診断用のヘッダの生の値（印字できる ASCII だけ・40 文字まで。無ければ「なし」）。
  - `_download_retrying(url, dest, label, *, check=None, retries=3, backoff_initial_sec=2.0, sleep=None, now=None) -> None`（`None` は呼ぶときに `time.sleep` / `time.time` に読み替える。テストが `time.sleep` を差し替えられるように）: 試行のたびに前の部分ファイルを消して `_download`、診断用にサイズ・先頭 16 バイトを読み（照合の前。`_verify_sha256` は不一致のとき取得物を消すため）、続けて `check()`（与えられていれば）。失敗したら、`HTTPError` なら `close()` し、
    - `PinConfigError` は即座に送出。
    - 429 / 503（`isinstance(exc, HTTPError) and exc.code in _THROTTLE_STATUSES` だけ）なら、429 / 503 の失敗が通算 `_THROTTLE_ATTEMPTS` 回に達していれば送出、そうでなければ `min(max(Retry-After or 0, _THROTTLE_WAITS_SEC[t − 1]), _THROTTLE_MAX_WAIT_SEC)` だけ待つ（t は 429 / 503 の失敗の回数）。
    - それ以外なら、それ以外の失敗が通算 `retries` 回に達していれば送出、そうでなければ `backoff_initial_sec * 2 ** (o − 1)` だけ待つ（o はそれ以外の失敗の回数。今と同じ列）。
    - 毎試行の診断: 試行の番号・429 / 503 と他の失敗の回数とそれぞれの上限・サイズ・Content-Length・先頭 16 バイト・HTTP の状態（無ければ「なし」）・`Retry-After` の生の値・次に待つ秒数。送出の前に、最後の状態と待った秒の合計を出す。
    - 最悪の値: 1 ファイルあたり取得 `(_THROTTLE_ATTEMPTS − 1) + (retries − 1) + 1` = 7 回、待ち `4 × 120 + (2 + 4)` = 486 秒（429 / 503 だけなら 480 秒）。macOS は ffmpeg と ffprobe を順に取るのでジョブではその倍。
  - `_download_verified(url, dest, expected, label, *, retries=3, backoff_initial_sec=2.0, sleep=None)`: 引数の名前と並びは変えない（`sleep` の既定だけ `time.sleep` から `None` に変えた。挙動は同じ）。`_download_retrying(..., check=lambda: _verify_sha256(dest, expected, label))`。sha256 未設定は取得 1 回の後に `PinConfigError` で即時中断（今と同じ。取得の失敗は取り直す）。
  - `_check_zip(path, tool)`: `zipfile.ZipFile(path).testzip()` が `None`（CRC が合う）で、対象のファイル（`__MACOSX/` を除く）があることを確かめる。壊れていれば `zipfile.BadZipFile` などを送出する（それ以外の失敗として短いリトライに入る）。
  - `_download_ffmpeg_macos`: `verify: binary` の経路を `_download_retrying(url, tmp, label, check=lambda t=tmp, n=tool: _check_zip(t, n))`（ループ変数を default 引数で束縛する） に替える。展開と展開後の `_verify_sha256` は今のまま（取り直さない）。
- 共通化: `refresh_pins.py` の `_is_transient` / `_fetch_page`（#412）とは分類が違う（refresh_pins は 5xx 全般・429 を一時的とみなす）ので、今回は共通化しない。
- テスト: `tests/test_download_binaries.py`。既存の `_FakeDownload` に本物の `urllib.error.HTTPError`（`headers` は `email.message.Message`）を渡す。C3 は `_download_retrying` か `_retry_after_sec` を直接呼んで `now` を注入する。C8 は `_download_ffmpeg_macos` を `BIN_DIR`・`_load_pins`・`_download` を差し替えて呼び、本物の zip（`zipfile` で作る）と壊した zip を使う。C10 はローカルの `http.server` を `127.0.0.1`・ポート 0・daemon スレッドで立て、`NO_PROXY` を設定し、`_DOWNLOAD_TIMEOUT_SEC` を数秒に縮め、`sleep` は偽物を注入して `_download` をそのまま通す。
## テスト先行の red（2026-11-28）

実装前のコード（HEAD `9439bfa`＝設計の docs だけを入れた時点の `scripts/download_binaries.py`）に、`c69a477` の `tests/test_download_binaries.py` を当てて走らせた（scratchpad に一時的な作業ツリーを作り、本体の `.venv` の Python で `pytest -q -rfE`。終わった後に作業ツリーは消した）。要約行は `56 failed, 20 passed in 1.40s`。pass の 20 件は、main にあった既存の 18 本（リトライの 6 本を含む。期待値は変えていない）と、実装前から通る新しい 2 本（`test_mac_arm64_sha_mismatch_after_extract_is_not_retried`・`test_mac_arm64_missing_sha_is_not_retried`。実装前の arm64 は取り直さないので、取り直さないことを確かめるこの 2 本は通る。取り直すようにする変異 M10・M19 で落ちることを下で確かめた）。

<details><summary>FAILED / ERROR の行（56 件）</summary>

  - `FAILED tests/test_download_binaries.py::test_throttle_constants`
  - `FAILED tests/test_download_binaries.py::test_retry_after_seconds_longer_than_default_is_used[429]`
  - `FAILED tests/test_download_binaries.py::test_retry_after_seconds_longer_than_default_is_used[503]`
  - `FAILED tests/test_download_binaries.py::test_retry_after_shorter_than_default_uses_default[429]`
  - `FAILED tests/test_download_binaries.py::test_retry_after_shorter_than_default_uses_default[503]`
  - `FAILED tests/test_download_binaries.py::test_retry_after_unparseable_uses_default[+7]`
  - `FAILED tests/test_download_binaries.py::test_retry_after_unparseable_uses_default[1_000]`
  - `FAILED tests/test_download_binaries.py::test_retry_after_unparseable_uses_default[7.5]`
  - `FAILED tests/test_download_binaries.py::test_retry_after_unparseable_uses_default[abc]`
  - `FAILED tests/test_download_binaries.py::test_retry_after_unparseable_uses_default[]`
  - `FAILED tests/test_download_binaries.py::test_retry_after_unparseable_uses_default[-5]`
  - `FAILED tests/test_download_binaries.py::test_retry_after_unparseable_uses_default[0]`
  - `FAILED tests/test_download_binaries.py::test_retry_after_unparseable_uses_default[+45]`
  - `FAILED tests/test_download_binaries.py::test_retry_after_unparseable_uses_default[45.5]`
  - `FAILED tests/test_download_binaries.py::test_retry_after_unparseable_uses_default[-45]`
  - `FAILED tests/test_download_binaries.py::test_retry_after_unparseable_uses_default[1_045]`
  - `FAILED tests/test_download_binaries.py::test_retry_after_sec_parses_digits_with_surrounding_space`
  - `FAILED tests/test_download_binaries.py::test_retry_after_sec_http_date[Sat, 28 Nov 2026 05:00:40 GMT-40.0]`
  - `FAILED tests/test_download_binaries.py::test_retry_after_sec_http_date[Sat, 28 Nov 2026 05:00:40 -0000-40.0]`
  - `FAILED tests/test_download_binaries.py::test_retry_after_sec_http_date[Sat, 28 Nov 2026 05:00:39 GMT-39.0]`
  - `FAILED tests/test_download_binaries.py::test_retry_after_sec_http_date[Sat, 28 Nov 2026 04:59:00 GMT-None]`
  - `FAILED tests/test_download_binaries.py::test_retry_after_sec_http_date[Sat, 28 Nov 2026 05:00:00 GMT-None]`
  - `FAILED tests/test_download_binaries.py::test_retry_after_sec_http_date[not a date-None]`
  - `FAILED tests/test_download_binaries.py::test_retry_after_sec_naive_date_is_utc_regardless_of_host_tz`
  - `FAILED tests/test_download_binaries.py::test_retry_after_sec_rounds_up_fraction`
  - `FAILED tests/test_download_binaries.py::test_retry_after_sec_returns_none_without_header[headers_none]`
  - `FAILED tests/test_download_binaries.py::test_retry_after_sec_returns_none_without_header[no_header]`
  - `FAILED tests/test_download_binaries.py::test_retry_after_sec_returns_none_without_header[not_http_error]`
  - `FAILED tests/test_download_binaries.py::test_retry_after_http_date_goes_through_retry`
  - `FAILED tests/test_download_binaries.py::test_throttle_default_waits[429]`
  - `FAILED tests/test_download_binaries.py::test_throttle_default_waits[503]`
  - `FAILED tests/test_download_binaries.py::test_throttle_wait_is_capped[120-120.0]`
  - `FAILED tests/test_download_binaries.py::test_throttle_wait_is_capped[121-120.0]`
  - `FAILED tests/test_download_binaries.py::test_throttle_wait_cap_applies_to_http_date[Sat, 28 Nov 2026 05:02:00 GMT]`
  - `FAILED tests/test_download_binaries.py::test_throttle_wait_cap_applies_to_http_date[Sat, 28 Nov 2026 05:02:01 GMT]`
  - `FAILED tests/test_download_binaries.py::test_throttle_wait_cap_applies_to_http_date[Sat, 28 Nov 2026 05:10:00 GMT]`
  - `FAILED tests/test_download_binaries.py::test_throttle_gives_up_raising_the_last_error`
  - `FAILED tests/test_download_binaries.py::test_mixed_failures_raise_the_last_error`
  - `FAILED tests/test_download_binaries.py::test_throttle_gives_up_after_five_attempts`
  - `FAILED tests/test_download_binaries.py::test_mixed_failures_worst_case_is_seven_attempts`
  - `FAILED tests/test_download_binaries.py::test_mixed_failures_other_failures_still_stop_at_three`
  - `FAILED tests/test_download_binaries.py::test_other_http_errors_keep_short_retry[502_with_retry_after]`
  - `FAILED tests/test_download_binaries.py::test_other_http_errors_keep_short_retry[408]`
  - `FAILED tests/test_download_binaries.py::test_other_http_errors_keep_short_retry[404]`
  - `FAILED tests/test_download_binaries.py::test_other_http_errors_keep_short_retry[410]`
  - `FAILED tests/test_download_binaries.py::test_exhausted_throttle_reports_status_retry_after_and_total`
  - `FAILED tests/test_download_binaries.py::test_exhausted_without_http_status_reports_none`
  - `FAILED tests/test_download_binaries.py::test_retry_after_raw_is_sanitized`
  - `FAILED tests/test_download_binaries.py::test_pin_config_error_is_runtime_error`
  - `FAILED tests/test_download_binaries.py::test_missing_expected_after_throttle_still_aborts_without_retry`
  - `FAILED tests/test_download_binaries.py::test_mac_arm64_retries_throttled_download`
  - `FAILED tests/test_download_binaries.py::test_mac_arm64_retries_short_failure`
  - `FAILED tests/test_download_binaries.py::test_mac_arm64_retries_broken_zip[bad_crc]`
  - `FAILED tests/test_download_binaries.py::test_mac_arm64_retries_broken_zip[missing_member]`
  - `FAILED tests/test_download_binaries.py::test_mac_arm64_retries_broken_zip[truncated]`
  - `FAILED tests/test_download_binaries.py::test_download_verified_over_real_http_429`

</details>

## 実物との突き合わせ（C10）

`test_download_verified_over_real_http_429` が、ローカルの `http.server`（`127.0.0.1`・ポート 0・daemon スレッド、`NO_PROXY=*`、`_DOWNLOAD_TIMEOUT_SEC=5`）に対して `_download_verified` をそのまま呼ぶ。サーバーは 1 回目に `429` と `Retry-After: 45`、2 回目に本体を返す。`_download` の `urlopen` が本物の `HTTPError`（`headers` は `http.client.HTTPMessage`）を送出し、応答の `Retry-After` を読んで 45 秒（既定の下限 30 秒より長い）が `sleep` に渡り、2 回目で取得・照合に成功することを確かめる（ヘッダを読まない変異 M1 で落ちる）。手元（Windows）で pass。evermeet.cx などの実際の配布元に 429 を出させることはできないので、配布元が実際に `Retry-After` を返すかは確かめていない（v0.8.2 の失敗のログからは、ヘッダの有無が読めなかった）。

## 最悪の値（C5）

定数（`scripts/download_binaries.py` の `_THROTTLE_WAITS_SEC = (30.0, 60.0, 120.0, 120.0)`・`_THROTTLE_MAX_WAIT_SEC = 120.0`・`_THROTTLE_ATTEMPTS = len(_THROTTLE_WAITS_SEC) + 1`）と `_download_verified` の既定（`retries=3`・`backoff_initial_sec=2.0`）から、1 ファイルあたり:

- 429 / 503 だけが続く: 取得 5 回、待ちの合計は既定の待ちなら 330 秒、Retry-After が上限を超えるなら 120 × 4 = 480 秒
- 他の失敗と混ざる: 取得は最大 (5 − 1) + (3 − 1) + 1 = 7 回（`test_mixed_failures_worst_case_is_seven_attempts` が 7 回目で成功する列を確かめる。待ちは既定の待ちで 336 秒）、待ちは Retry-After が上限を超える場合に最大 480 + 2 + 4 = 486 秒（定数からの計算。同じテストが計算式を確かめる）
- macOS は ffmpeg と ffprobe を順に取るので、ジョブではその倍。1 回の取得ごとに socket の timeout（`_DOWNLOAD_TIMEOUT_SEC = 300`）もある。`release.yml` にジョブの `timeout-minutes` は無い（既定 360 分）

## 変異 → red（2026-11-28、基点 `c69a477`）

作業用のハーネス（scratchpad の `mutate413.py`。追跡しない）が、1 変異ずつ置換を 1 か所だけ当て（当たり 0 件・2 件以上はハーネスの失敗として止める）、`tests/test_download_binaries.py` を走らせて落ちたテストを集め、`git checkout` で戻して `git diff --quiet` を確かめた。無変異は `passed=76`、戻した後も `passed=76`。同じ HEAD で全体は `1073 passed`（`uv run pytest -q`）。

| 変異 | 書き換え | 落ちたテスト |
|---|---|---|
| M1 | Retry-After を無視する（`hinted = 0.0`） | `test_retry_after_seconds_longer_than_default_is_used[429]`、`test_retry_after_seconds_longer_than_default_is_used[503]`、`test_retry_after_http_date_goes_through_retry`、`test_throttle_wait_is_capped[120-120.0]`、`test_throttle_wait_is_capped[121-120.0]`、`test_throttle_wait_cap_applies_to_http_date[Sat, 28 Nov 2026 05:02:00 GMT]`、`test_throttle_wait_cap_applies_to_http_date[Sat, 28 Nov 2026 05:02:01 GMT]`、`test_throttle_wait_cap_applies_to_http_date[Sat, 28 Nov 2026 05:10:00 GMT]`、`test_exhausted_throttle_reports_status_retry_after_and_total`、`test_download_verified_over_real_http_429` |
| M2 | 既定の待ちの下限を外す（`max(hinted, …)` → `(hinted or …)`） | `test_retry_after_shorter_than_default_uses_default[429]`、`test_retry_after_shorter_than_default_uses_default[503]`、`test_exhausted_throttle_reports_status_retry_after_and_total` |
| M3 | 既定の長い待ちを短い待ちに戻す（`(2.0, 4.0, 8.0, 16.0)`） | `test_throttle_constants`、`test_retry_after_shorter_than_default_uses_default[429]`、`test_retry_after_shorter_than_default_uses_default[503]`、`test_retry_after_unparseable_uses_default[+7]`、`test_retry_after_unparseable_uses_default[1_000]`、`test_retry_after_unparseable_uses_default[7.5]`、`test_retry_after_unparseable_uses_default[abc]`、`test_retry_after_unparseable_uses_default[]`、`test_retry_after_unparseable_uses_default[-5]`、`test_retry_after_unparseable_uses_default[0]`、`test_retry_after_unparseable_uses_default[+45]`、`test_retry_after_unparseable_uses_default[45.5]`、`test_retry_after_unparseable_uses_default[-45]`、`test_retry_after_unparseable_uses_default[1_045]`、`test_throttle_default_waits[429]`、`test_throttle_default_waits[503]`、`test_throttle_gives_up_after_five_attempts`、`test_mixed_failures_worst_case_is_seven_attempts`、`test_mixed_failures_other_failures_still_stop_at_three`、`test_exhausted_throttle_reports_status_retry_after_and_total`、`test_missing_expected_after_throttle_still_aborts_without_retry`、`test_mac_arm64_retries_throttled_download` |
| M4 | 1 回の上限を外す（`float('inf')`） | `test_throttle_wait_is_capped[121-120.0]`、`test_throttle_wait_cap_applies_to_http_date[Sat, 28 Nov 2026 05:02:01 GMT]`、`test_throttle_wait_cap_applies_to_http_date[Sat, 28 Nov 2026 05:10:00 GMT]` |
| M5 | 429・503 の最大回数を 3 に戻す | `test_throttle_constants`、`test_throttle_default_waits[429]`、`test_throttle_default_waits[503]`、`test_throttle_gives_up_raising_the_last_error`、`test_throttle_gives_up_after_five_attempts`、`test_mixed_failures_worst_case_is_seven_attempts` |
| M6 | HTTP 日付の引き算の向きを逆にする | `test_retry_after_sec_http_date[Sat, 28 Nov 2026 05:00:40 GMT-40.0]`、`test_retry_after_sec_http_date[Sat, 28 Nov 2026 05:00:40 -0000-40.0]`、`test_retry_after_sec_http_date[Sat, 28 Nov 2026 05:00:39 GMT-39.0]`、`test_retry_after_sec_http_date[Sat, 28 Nov 2026 04:59:00 GMT-None]`、`test_retry_after_sec_naive_date_is_utc_regardless_of_host_tz`、`test_retry_after_sec_rounds_up_fraction`、`test_retry_after_http_date_goes_through_retry`、`test_throttle_wait_cap_applies_to_http_date[Sat, 28 Nov 2026 05:02:00 GMT]`、`test_throttle_wait_cap_applies_to_http_date[Sat, 28 Nov 2026 05:02:01 GMT]`、`test_throttle_wait_cap_applies_to_http_date[Sat, 28 Nov 2026 05:10:00 GMT]` |
| M7 | 502 も 429 / 503 と同じ扱いにする（Retry-After を読む） | `test_throttle_constants`、`test_other_http_errors_keep_short_retry[502_with_retry_after]` |
| M8 | arm64 を直接の取得（`_download`）に戻す | `test_mac_arm64_retries_throttled_download`、`test_mac_arm64_retries_short_failure`、`test_mac_arm64_retries_broken_zip[bad_crc]`、`test_mac_arm64_retries_broken_zip[missing_member]`、`test_mac_arm64_retries_broken_zip[truncated]` |
| M9 | arm64 の zip の検査を外す（`check=None`） | `test_mac_arm64_retries_broken_zip[bad_crc]`、`test_mac_arm64_retries_broken_zip[missing_member]`、`test_mac_arm64_retries_broken_zip[truncated]` |
| M10 | arm64 で展開後の sha256 不一致も取り直す（展開と照合を `check` に入れる） | `test_mac_arm64_sha_mismatch_after_extract_is_not_retried` |
| M11 | sha256 未設定でも取り直す（`except PinConfigError: raise` を消す） | `test_download_verified_missing_expected_does_not_retry`、`test_missing_expected_after_throttle_still_aborts_without_retry` |
| M12 | 毎試行の診断から状態の表示を消す | `test_exhausted_throttle_reports_status_retry_after_and_total`、`test_exhausted_without_http_status_reports_none` |
| M13 | 待った合計を足さない（`waited += wait` → `pass`） | `test_exhausted_throttle_reports_status_retry_after_and_total`、`test_exhausted_without_http_status_reports_none` |
| M14 | Retry-After の + 付きの数を受け付ける（`\+?[0-9]+`） | `test_retry_after_unparseable_uses_default[+7]`、`test_retry_after_unparseable_uses_default[+45]` |
| M15 | Retry-After の小数を受け付ける | `test_retry_after_unparseable_uses_default[7.5]`、`test_retry_after_unparseable_uses_default[45.5]` |
| M16 | タイムゾーンの無い日付を UTC とみなさない（`replace(tzinfo=UTC)` を消す） | `test_retry_after_sec_http_date[Sat, 28 Nov 2026 05:00:40 -0000-40.0]`、`test_retry_after_sec_naive_date_is_utc_regardless_of_host_tz` |
| M17 | 最後ではなく最初の例外を送出する | `test_throttle_gives_up_raising_the_last_error`、`test_mixed_failures_raise_the_last_error` |
| M18 | 毎試行の「次の待ち」を固定値（`999 秒`）にする | `test_exhausted_throttle_reports_status_retry_after_and_total` |
| M19 | M10 と M11 を同時に（展開後の不一致も、sha256 未設定も取り直す） | `test_download_verified_missing_expected_does_not_retry`、`test_missing_expected_after_throttle_still_aborts_without_retry`、`test_mac_arm64_sha_mismatch_after_extract_is_not_retried`、`test_mac_arm64_missing_sha_is_not_retried` |

経緯: 最初の実行（基点 `9dff740`、M1〜M13）では M12 が生き残った。テストが見ていた「状態=429」が、取り尽くしたときの「最後の状態=429」の行にも含まれていたため。毎試行の行に固有の書き方（` 状態=429 Retry-After=45 `）で確かめるよう直した（8bbc038）。M14〜M18 は evaluator（1 巡目）が scratchpad のコピーで生き残らせたもので、テストを足した（c69a477）。M19 は、M10 単独では `test_mac_arm64_missing_sha_is_not_retried` が落ちないので、同時に掛けて落ちることを確かめた。1 巡目のハーネスは空白を含むテスト ID（日付のパラメータ）を取りこぼしていたので、解析を直した。

## 訂正ログ

| 日付 | 誤って書いたこと | 正しくは | 原因と再発防止 |
|---|---|---|---|

## 検証ゲート

| 巡 | HEAD | verify | docs-check | evaluator |
|---|---|---|---|---|
| 1 | `3bdbfaf` | green（1064 passed、skip 0） | 指摘なし | FAIL（[欠陥] 5 / [証跡・文言] 8） |
| 2 | `3db76ce` | evaluator が確認（1073 passed、ruff・mypy green） | — | PASS（follow-up あり。[欠陥] 0 / [証跡・文言] 3。1 巡目の 13 件のうち E6 の一部と E8 以外は閉じていると確認。3 件はこの PR で直した: 設計節の `[0-9]+`・`AttributeError`・`_check_zip` の引数名・lambda の書き方、C12 の証跡のコミット、最悪の値は PR 本文に書いた） |

1 巡目の指摘と閉じ方:

| # | 区分 | 指摘 | 閉じ方 | 証跡・コミット |
|---|---|---|---|---|
| D1 | 欠陥 | Retry-After の不正な値（`+7`・`7.5`・`-5`）が下限 30 秒に隠れて判別できない | 下限より大きい値を足し、`_retry_after_sec` が `None` を返すことを直接見る | `test_retry_after_unparseable_uses_default`（c69a477）、変異 M14・M15 |
| D2 | 欠陥 | タイムゾーン無しを UTC とみなす処理を外しても、UTC のホストでは落ちない | ホストのタイムゾーンによらない偽物の日付で確かめる | `test_retry_after_sec_naive_date_is_utc_regardless_of_host_tz`（c69a477）、変異 M16 |
| D3 | 欠陥 | 日付形式の 120 / 121 秒の境界が無い | 境界のケースを足した | `test_throttle_wait_cap_applies_to_http_date`（c69a477） |
| D4 | 欠陥 | 「最後の例外を送出する」を最初の例外と区別できない | 区別できる例外を並べ、オブジェクトで確かめる | `test_throttle_gives_up_raising_the_last_error`・`test_mixed_failures_raise_the_last_error`（c69a477）、変異 M17 |
| D5 | 欠陥 | 毎試行の「次の待ち」にテストが無い | 表示を確かめる assert を足した | `test_exhausted_throttle_reports_status_retry_after_and_total`（c69a477）、変異 M18 |
| E1 | 証跡・文言 | 「既存の 20 本はすべて pass」は誤り（main の既存は 18 本） | 20 件の内訳（既存 18 本＋実装前から通る新しい 2 本）を書いた | 上の「テスト先行の red」 |
| E2 | 証跡・文言 | `test_mac_arm64_missing_sha_is_not_retried` を落とす変異の行が無い | M10 と M11 を同時に掛ける M19 を足した | 上の「変異 → red」 |
| E3 | 証跡・文言 | M6 の行の落ちたテストが欠けている（空白を含む ID の取りこぼし） | ハーネスの解析を直して取り直した | 上の「変異 → red」 |
| E4 | 証跡・文言 | http.server のテストが Retry-After を読んだかを区別できない（`Retry-After: 1` は下限 30 秒と同じ） | `Retry-After: 45` にしてテストを強め、記述を直した | `test_download_verified_over_real_http_429`（c69a477）、変異 M1 |
| E5 | 証跡・文言 | 486 秒の根拠のテストが実際に測っているのは 336 秒 | 測った値と計算の値を分けて書いた | 上の「最悪の値」 |
| E6 | 証跡・文言 | 設計節の既定値（`sleep=time.sleep` など）がコードと違う | 設計節を直した | 上の「設計」 |
| E7 | 証跡・文言 | build.md の「既定 3 回」に名前が無い・診断の列挙が足りない | 直した | `docs/build.md` のリトライの段落 |
| E8 | 証跡・文言 | 最悪の値を PR に書く（PR がまだ無い） | PR 本文に書く | PR 本文 |
## 次にやること

- なし（完了）

訂正ログ: 0 件
