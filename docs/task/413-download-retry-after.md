# 同梱バイナリの取得で HTTP 429 / 503 に Retry-After で待ってリトライする

> Issue: [#413](https://github.com/f8924919/yt-gui/issues/413)
> ステータス: 進行中
> ブランチ: `feature/413-download-retry-after`
> 基点: `3da4cbe`

受け入れ条件の正本は Issue（2026-11-28 に criteria-review とユーザー確認を経て書き直した版）。設計は [build.md](../build.md) の「ピン留めと sha256 検証」のリトライの段落。前のタスクは [#265](archive/265-download-retry.md)（取得リトライの導入）と [#412](archive/412-arm64-pin-staleness.md)（`refresh_pins.py` のページ取得のリトライ）。

## 進捗

- [ ] C1 共通のリトライ（`_download_verified` と arm64 が同じ関数・429/503 とそれ以外の分類） — 証跡: 未
- [ ] C2 Retry-After の秒数（本物の HTTPError・429 と 503） — 証跡: 未
- [ ] C3 Retry-After の HTTP 日付（現在時刻の注入・過去・0 以下・不正値） — 証跡: 未
- [ ] C4 Retry-After が無いときの待ちの列（30・60・120・120） — 証跡: 未
- [ ] C5 上限（1 回 120 秒・120 と 121 の境界・最大 5 回・最悪 480 秒） — 証跡: 未
- [ ] C6 対象外の失敗は今のまま（502 + Retry-After・408・404・混在・既存 6 本） — 証跡: 未
- [ ] C7 取り尽くしたとき（最後の例外・状態・待った合計） — 証跡: 未
- [ ] C8 macOS arm64（取得は取り直す・展開後の不一致と展開失敗と未設定は取り直さない） — 証跡: 未
- [ ] C9 sha256 の扱いは不変 — 証跡: 未
- [ ] C10 実物との突き合わせ（ローカルの http.server） — 証跡: 未
- [ ] C11 変異 → red — 証跡: 未
- [ ] C12 docs — 証跡: 未

## 設計（2026-11-28）

ユーザー確認で決めたこと: 429 / 503 は最大 5 回・待ちは 30・60・120・120 秒（`Retry-After` は 1 回 120 秒で切る）、404 / 410 は今のまま（即時中断を入れない）。

- `scripts/download_binaries.py`
  - 定数（正本）: `_THROTTLE_STATUSES = frozenset({429, 503})`、`_THROTTLE_WAITS_SEC = (30.0, 60.0, 120.0, 120.0)`、`_THROTTLE_MAX_WAIT_SEC = 120.0`、`_THROTTLE_ATTEMPTS = 5`。
  - `_retry_after_sec(exc, now) -> float | None`: `HTTPError` の `headers` の `Retry-After` を読む。整数の秒数なら そのまま、HTTP 日付なら `email.utils.parsedate_to_datetime` で（日付 − `now()`）秒を切り上げる。無い・解釈できない・0 以下は `None`。
  - `_download_retrying(url, dest, label, *, check=None, retries=3, backoff_initial_sec=2.0, sleep=time.sleep, now=time.time) -> None`: 試行のたびに前の部分ファイルを消して `_download`、続けて `check()`（与えられていれば）。失敗したら診断を出し、
    - 429 / 503 なら、429 / 503 の失敗が通算 `_THROTTLE_ATTEMPTS` 回に達していれば送出、そうでなければ `min(Retry-After または _THROTTLE_WAITS_SEC[429/503 の失敗の回数 − 1], _THROTTLE_MAX_WAIT_SEC)` だけ待つ。
    - それ以外なら、それ以外の失敗が通算 `retries` 回に達していれば送出、そうでなければ `backoff_initial_sec * 2 ** (それ以外の失敗の回数 − 1)` だけ待つ（今と同じ列）。
    - 送出の前に、最後の状態と待った秒の合計を出す。
  - `_download_verified(url, dest, expected, label, *, retries=3, backoff_initial_sec=2.0, sleep=time.sleep)`: 公開のシグネチャは変えない。sha256 未設定なら取得 1 回のあと即時中断（今と同じ）。それ以外は `_download_retrying(..., check=lambda: _verify_sha256(dest, expected, label))`。
  - `_download_ffmpeg_macos`: `verify: binary` の経路を `_download_retrying(url, tmp, label)`（`check` なし）に替える。展開と展開後の `_verify_sha256` は今のまま（取り直さない）。
- 共通化: `refresh_pins.py` の `_is_transient` / `_fetch_page`（#412）とは分類が違う（refresh_pins は 5xx 全般・429 を一時的とみなす）ので、今回は共通化しない。
- テスト: `tests/test_download_binaries.py`。既存の `_FakeDownload` に本物の `urllib.error.HTTPError`（`headers` は `email.message.Message`）を渡す。`now` は引数で注入する。C10 はローカルの `http.server` を別スレッドで立てて `_download` をそのまま通す。

## 訂正ログ

| 日付 | 誤って書いたこと | 正しくは | 原因と再発防止 |
|---|---|---|---|

## 次にやること

- design-review（investigate の推奨が yes）
- テスト先行（`tests/test_download_binaries.py`）

訂正ログ: 0 件
