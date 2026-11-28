# 同梱バイナリの取得で HTTP 429 / 503 に Retry-After で待ってリトライする

> Issue: [#413](https://github.com/f8924919/yt-gui/issues/413)
> ステータス: 進行中
> ブランチ: `feature/413-download-retry-after`
> 基点: `3da4cbe`

受け入れ条件の正本は Issue（2026-11-28 に criteria-review とユーザー確認を経て書き直した版）。設計は [build.md](../build.md) の「ピン留めと sha256 検証」のリトライの段落。前のタスクは [#265](archive/265-download-retry.md)（取得リトライの導入）と [#412](archive/412-arm64-pin-staleness.md)（`refresh_pins.py` のページ取得のリトライ）。

## 進捗

- [ ] C1 共通のリトライ（`_download_verified` と arm64 が同じ関数・429/503 とそれ以外の分類） — 証跡: 未
- [ ] C2 Retry-After の秒数（本物の HTTPError・429 と 503・既定の待ちが下限・数字以外は不正） — 証跡: 未
- [ ] C3 Retry-After の HTTP 日付（現在時刻の注入・過去・0 以下・不正値） — 証跡: 未
- [ ] C4 Retry-After が無いときの待ちの列（30・60・120・120） — 証跡: 未
- [ ] C5 上限（1 回 120 秒・120 と 121 の境界・最大 5 回・最悪 480 秒 / 混在で 7 回・486 秒） — 証跡: 未
- [ ] C6 対象外の失敗は今のまま（502 + Retry-After・408・404・混在・既存 6 本） — 証跡: 未
- [ ] C7 取り尽くしたとき（最後の例外・状態・待った合計） — 証跡: 未
- [ ] C8 macOS arm64（取得と壊れた zip は取り直す・展開後の不一致と未設定は取り直さない） — 証跡: 未
- [ ] C9 sha256 の扱いは不変 — 証跡: 未
- [ ] C10 実物との突き合わせ（ローカルの http.server） — 証跡: 未
- [ ] C11 変異 → red — 証跡: 未
- [ ] C12 docs — 証跡: 未

## 設計（2026-11-28。design-review の指摘を反映）

ユーザー確認で決めたこと: 429 / 503 は最大 5 回・既定の待ち 30・60・120・120 秒・1 回 120 秒で切る、404 / 410 は今のまま、`Retry-After` は既定の待ちを下限にする（長いほうだけ待つ）、arm64 は転送中に壊れた zip を取り直す。

- `scripts/download_binaries.py`
  - 定数（正本）: `_THROTTLE_STATUSES = frozenset({429, 503})`、`_THROTTLE_WAITS_SEC = (30.0, 60.0, 120.0, 120.0)`、`_THROTTLE_MAX_WAIT_SEC = 120.0`、`_THROTTLE_ATTEMPTS = len(_THROTTLE_WAITS_SEC) + 1`（同じ事実を 2 か所に書かない）。
  - `class PinConfigError(RuntimeError)`: `_verify_sha256` が sha256 未設定のときに送出する。`_download_retrying` はこれを種類を問わず即座に送出する（取り直さない）。`RuntimeError` の子なので、既存テストの `pytest.raises(RuntimeError, match=r"pins\.json")` は通る。今の `isinstance(exc, RuntimeError) and not expected` の 2 か所の結び付きをなくす。
  - `_retry_after_sec(exc, now) -> float | None`: どんな入力でも例外を出さない（例外処理の中で呼ぶため）。`HTTPError` でない・`headers` が `None`・ヘッダが無いなら `None`。値が `\d+`（前後の空白は除く）なら整数の秒、そうでなければ `email.utils.parsedate_to_datetime` で日付として読み、タイムゾーンが無ければ UTC とみなして（日付 − `now()`）秒を切り上げる。`ValueError` / `TypeError` / `OverflowError` と 0 以下は `None`。
  - `_retry_after_raw(exc) -> str`: 診断用のヘッダの生の値（印字できる ASCII だけ・40 文字まで。無ければ「なし」）。
  - `_download_retrying(url, dest, label, *, check=None, retries=3, backoff_initial_sec=2.0, sleep=time.sleep, now=time.time) -> None`: 試行のたびに前の部分ファイルを消して `_download`、診断用にサイズ・先頭 16 バイトを読み（照合の前。`_verify_sha256` は不一致のとき取得物を消すため）、続けて `check()`（与えられていれば）。失敗したら、`HTTPError` なら `close()` し、
    - `PinConfigError` は即座に送出。
    - 429 / 503（`isinstance(exc, HTTPError) and exc.code in _THROTTLE_STATUSES` だけ）なら、429 / 503 の失敗が通算 `_THROTTLE_ATTEMPTS` 回に達していれば送出、そうでなければ `min(max(Retry-After or 0, _THROTTLE_WAITS_SEC[t − 1]), _THROTTLE_MAX_WAIT_SEC)` だけ待つ（t は 429 / 503 の失敗の回数）。
    - それ以外なら、それ以外の失敗が通算 `retries` 回に達していれば送出、そうでなければ `backoff_initial_sec * 2 ** (o − 1)` だけ待つ（o はそれ以外の失敗の回数。今と同じ列）。
    - 毎試行の診断: 試行の番号・429 / 503 と他の失敗の回数とそれぞれの上限・サイズ・Content-Length・先頭 16 バイト・HTTP の状態（無ければ「なし」）・`Retry-After` の生の値・次に待つ秒数。送出の前に、最後の状態と待った秒の合計を出す。
    - 最悪の値: 1 ファイルあたり取得 `(_THROTTLE_ATTEMPTS − 1) + (retries − 1) + 1` = 7 回、待ち `4 × 120 + (2 + 4)` = 486 秒（429 / 503 だけなら 480 秒）。macOS は ffmpeg と ffprobe を順に取るのでジョブではその倍。
  - `_download_verified(url, dest, expected, label, *, retries=3, backoff_initial_sec=2.0, sleep=time.sleep)`: 公開のシグネチャは変えない。`_download_retrying(..., check=lambda: _verify_sha256(dest, expected, label))`。sha256 未設定は取得 1 回の後に `PinConfigError` で即時中断（今と同じ。取得の失敗は取り直す）。
  - `_check_zip(path, member_basename)`: `zipfile.ZipFile(path).testzip()` が `None`（CRC が合う）で、対象のファイル（`__MACOSX/` を除く）があることを確かめる。壊れていれば `zipfile.BadZipFile` などを送出する（それ以外の失敗として短いリトライに入る）。
  - `_download_ffmpeg_macos`: `verify: binary` の経路を `_download_retrying(url, tmp, label, check=lambda: _check_zip(tmp, tool))` に替える。展開と展開後の `_verify_sha256` は今のまま（取り直さない）。
- 共通化: `refresh_pins.py` の `_is_transient` / `_fetch_page`（#412）とは分類が違う（refresh_pins は 5xx 全般・429 を一時的とみなす）ので、今回は共通化しない。
- テスト: `tests/test_download_binaries.py`。既存の `_FakeDownload` に本物の `urllib.error.HTTPError`（`headers` は `email.message.Message`）を渡す。C3 は `_download_retrying` か `_retry_after_sec` を直接呼んで `now` を注入する。C8 は `_download_ffmpeg_macos` を `BIN_DIR`・`_load_pins`・`_download` を差し替えて呼び、本物の zip（`zipfile` で作る）と壊した zip を使う。C10 はローカルの `http.server` を `127.0.0.1`・ポート 0・daemon スレッドで立て、`NO_PROXY` を設定し、`_DOWNLOAD_TIMEOUT_SEC` を数秒に縮め、`sleep` は偽物を注入して `_download` をそのまま通す。
## 訂正ログ

| 日付 | 誤って書いたこと | 正しくは | 原因と再発防止 |
|---|---|---|---|

## 次にやること

- テスト先行（`tests/test_download_binaries.py`）

訂正ログ: 0 件
