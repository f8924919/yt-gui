# macOS arm64 の ffmpeg ピンの古さを週次で検知する

> Issue: [#412](https://github.com/f8924919/yt-gui/issues/412)
> ステータス: 進行中
> ブランチ: `feature/412-arm64-pin-staleness`
> 基点: `dd66c0d`

受け入れ条件の正本は Issue（2026-11-28 に criteria-review とユーザー確認を経て書き直した版）。設計は [build.md](../build.md) の「更新運用」「同梱バイナリのピン自動更新（GitHub Actions）」。

## 進捗

- [ ] C1 版の読み取り（リンクと文言の両方・末尾 `.0` の省略・Intel と ffplay を拾わない） — 証跡: 未
- [ ] C2 古さの判定（x86_64 との差だけでは警告しない） — 証跡: 未
- [ ] C3 URL の生存（HEAD / Range、404・410 と 5xx の区別、リダイレクト・非 zip） — 証跡: 未
- [ ] C4 検査不能の区別（取得失敗・リンクだけ・文言だけ・食い違い） — 証跡: 未
- [ ] C5 他の再ピンを止めない・検査を先に行い先に書く — 証跡: 未
- [ ] C6 警告の出力（サマリの先頭・警告ファイル） — 証跡: 未
- [ ] C7 ジョブの失敗（PR 作成の後・PR 作成失敗でも走る・ファイル欠落は不備） — 証跡: 未
- [ ] C8 sha256 を書き換えない — 証跡: 未
- [ ] C9 実物との突き合わせ — 証跡: 未
- [ ] C10 変異 → red — 証跡: 未
- [ ] C12 sha256 がページに載っているか — 証跡: 未
- [ ] C13 警告文に入れるもの（絞った値と固定文・LF） — 証跡: 未
- [ ] C11 docs — 証跡: 未

## 設計（2026-11-28。design-review の指摘を反映）

ユーザー確認で決めたこと: 知らせ方は「PR は作り最後に失敗」、x86_64 との版の一致は注記に格下げ、版はリンクと文言の両方から読んで照合、直すまで毎週失敗、ピンの sha256 がページに載っているかも見る（design-review の提案）。

- `scripts/refresh_pins.py`
  - `_parse_osxexperts_arm64(html) -> dict[str, tuple[str, str]]`（純関数）: ツール（`ffmpeg` / `ffprobe`）ごとに、`href` の `https://www.osxexperts.net/<tool><数字>arm.zip` と、文言 `Download <tool> <版> (Apple Silicon)` をそれぞれちょうど 1 件探す。版は文言を正とし、リンクの数字は照合にだけ使う。一致の判定は `_arm_link_token(版)`（版から `.` を除いたもの、または末尾の `.0` を省いてから `.` を除いたもの、のどちらか）。見つからない・複数ある・食い違うときは `ArmPageError` を送出する。
  - `_same_version(a, b)`: 末尾の `.0` を省いて比べる（ページとピンの版の比較に使う）。
  - `_url_ok(url) -> str`: HEAD（使えなければ `Range: bytes=0-0` の GET）で確かめ、`"ok"` / `"gone"`（404・410、別 URL へのリダイレクト、zip でない応答）/ `"error"`（タイムアウト・5xx・接続失敗）を返す。
  - `check_ffmpeg_mac_arm64(arm_pin, fetch_text=_http_text, url_ok=_url_ok) -> list[str]`: ページを取得し（失敗は「検査できなかった」）、読み（`ArmPageError` は「検査できなかった（構造の変化またはブロック）」）、ツールごとにページの版・URL とピンを比べ（違えば「古い」）、ピンの URL を確かめ、ピンの sha256 がページにあるかを見る（無ければ「古い（差し替えの可能性）」）。ffmpeg と ffprobe でページの版が違えばその旨を出す。警告の文字列のリストを返す。全体を `except Exception` で受け、型名だけを入れた「検査できなかった」警告に変える（黙らない）。警告文には絞った値と固定文だけを入れる。
  - `refresh_ffmpeg_mac()` は変えない（arm64 を書き換えない）。x86_64 と arm64 の版が違うときは、状況欄の文言に注記を足す。
  - `refresh_pins()` は変えない。`main()` が `check_ffmpeg_mac_arm64` → 警告ファイルの書き出し → `refresh_pins()` の順に呼ぶ。テストしやすいよう、IO の無い `run(pins, alerts_out=None)` のような形に分けるかは実装時に決める。
  - `_build_summary(changes, statuses, alerts=())`: 警告があれば先頭に `> [!CAUTION]` の欄（警告の箇条書きと手で更新する手順）を出す。
  - `main()`: `--alerts-out` を足す。警告が無くても空ファイルを必ず作る。1 警告 1 行、`newline="\n"` で書く。終了コードは 0 のまま（PR 作成を止めない）。
- `.github/workflows/update-binaries.yml`: Refresh pins に `id: refresh` と `--alerts-out "${RUNNER_TEMP}/pin-alerts.txt"` を足す。PR 作成の後に「Fail if arm64 pin needs attention」ステップを置き、`if: ${{ !cancelled() }}`。Refresh pins が成功（`steps.refresh.outcome == 'success'`）なのにファイルが無ければ不備として失敗。ファイルが空でなければ `while IFS= read -r line || [ -n "$line" ]` で 1 行ずつ `printf '::error::%s\n'` を出して `exit 1`。
- ページの取得は 1 回だけ（リトライしない）。取得失敗の警告文で `workflow_dispatch` による再実行を促す。
- フィクスチャ: 現行ページ（9.1）と、Wayback の 2026-10-18 版（9.0、`ffmpeg9arm.zip`）から Apple Silicon と Intel の部分を切り出す。出所（URL・取得日時・sha256）をフィクスチャの先頭に書く。
- C9 は手元からの取得で確かめる。ランナーからの実行は、ワークフローを手動で回すとピン更新 PR が実際に作られうるため、マージ後の週次実行で確かめる。

## 訂正ログ

| 日付 | 誤って書いたこと | 正しくは | 原因と再発防止 |
|---|---|---|---|
| 2026-11-28 | 設計に「リンクの数字が版から `.` を除いたものと一致すれば採用」と書いた | osxexperts は 9.0 を `ffmpeg9arm.zip`（`.0` を省く）、9.1 を `ffmpeg91arm.zip` と名付けており、当初の規則では 9.0 の期間に毎週「検査できない」になる。末尾 `.0` の省略も一致とする | 現行ページ 1 枚（9.1）だけを見て規則を決めた。#411 の直前のピン（`ffmpeg9arm.zip` が 9.0）を見れば分かった。外部の命名規則は、手元にある過去の値（git 履歴のピン・アーカイブ）と突き合わせてから書く。伝播先は「除いた」で洗い、このメモの設計節だけだった |

## 次にやること

- テスト先行（`tests/test_refresh_pins.py`・`tests/test_update_binaries_workflow.py`）。フィクスチャの切り出しから

訂正ログ: 1 件