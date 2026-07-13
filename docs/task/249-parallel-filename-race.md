# #249 並列ダウンロード時のファイル名衝突（TOCTOU レース）修正

対応 Issue: [#249](https://github.com/f8924919/yt-gui/issues/249)

## 問題

`_resolve_unique_path`（[yt_gui/downloader.py](../../yt_gui/downloader.py)）の `(n)` サフィックス決定が「実行直前の `os.path.exists()` チェック」のみで、ワーカー間の排他が無い。並列ダウンロード（#108）で同一出力パスに解決される 2 項目が同時に走ると、双方がサフィックス無しの同一パスへ書き込み、上書き・`PermissionError`・破損が起こり得る。

## 設計（パス予約方式）

- `Downloader` のクラス属性として、プロセス内共有の予約集合 `_reserved_paths: set[str]` とロック `_reservation_lock: threading.Lock` を持つ（全 `Downloader` インスタンス＝全ワーカーで共有）。
- `_resolve_unique_path` のサフィックス決定を「ファイルが存在する **or** 予約中」判定に変更し、判定〜予約登録をロック内で原子的に行う。`extract_info`（ネットワーク処理）はロック外のまま。
- **中間ファイルも予約対象**: 最終パス（`effective_stem + final_ext`）に加え、変換前の取得ファイルパス（`effective_stem + raw_ext`）も予約・衝突判定する。同一 URL を MP3 と FLAC で並列 DL した場合など、最終拡張子が異なっても中間ファイル（例: `.webm`）が衝突するため。
- 予約解除は `download_video()` 内の try/finally で保証する（後処理〔区間切り出し・コメント変換・埋め込み〕の失敗、`DownloadCancelled` を含む全経路）。**`queue_controller.py` の変更は不要**。
- `DownloadSkipped` は `_resolve_unique_path` 内の予約前に送出されるため解除対象外。
- 予約はインメモリ・プロセス内限定。多重起動・外部プロセスとの競合はスコープ外。

## 設計判断メモ

- 予約状態の置き場所: DI（QueueController から注入）ではなくクラス属性を採用。並列時はワーカーごとに `Downloader` インスタンスが生成されるため共有が必須で、注入は配線が増えるだけで利点が薄い。予約キーは絶対パスなので複数出力先でも破綻しない。テストは autouse フィクスチャで `Downloader._reserved_paths.clear()` を毎テスト実行して分離する。
- 解除の接続機構: `_resolve_unique_path` の返り値に予約トークンを加えた 4-tuple 化を採用（design-review 指摘。#83 の 3-tuple 化と同型の契約変更で、既存テストの 3-tuple スタブ更新を伴う）。インスタンス属性への隠し置きは不採用（明示性優先）。
- チャプター名モードの分割クリップ（`タイトル - チャプター名.ext`）同士の衝突は従来からの挙動でありスコープ外。

## design-review の指摘と反映（2026-07-13）

- 返り値契約変更（4-tuple）とテストスタブ波及を docs/Issue に明記 → 反映済み。
- 最終・中間パスは**単一の n** で両方の空きを確認しまとめて予約、衝突なし（n=0）でも基底パスを必ず登録 → arch/Issue に明記。
- 分離の本質的保証は `outtmpl` 上書きが全派生名（`.part`・`.fNNN.`）へ伝播すること。派生ファイルの個別予約は不要 → arch に明記。
- **掃除 glob 干渉（隣接バグ）**: `_cleanup_partial_files` の `stem + "*"` 前方一致が並列中の `(n)` 付き兄弟の `.part` を削除しうる → ユーザー確認のうえ #249 スコープに追加。`stem + ".*"` に厳密化。
- 解除順序: `except` の掃除 → `finally` の解除の順を維持（逆だと解除直後に予約した別ワーカーの `.part` を巻き込む）。
- 既知の限界として明記: プロセス内限定・ケース非依存 FS の異ケース同名・ドット区切り前方一致タイトルの掃除干渉。

## テスト方針

タイミング依存の統計的テストは書かない。`threading.Barrier` / フックで競合区間を決定的に再現する（Issue AC7）。掃除 glob 干渉は実ファイルの削除有無まで観測する。

## 進捗

- [x] Issue 起票・criteria-review 反映（2026-07-13）
- [x] docs 先行（spec/arch 更新）
- [x] design-review（§5.5 発火: investigate 推奨 yes）→ 指摘反映（2026-07-13）
- [x] テスト先行（予約・並列競合・掃除 glob の決定的テストを追加、2026-07-13）
- [x] 実装 → green（全 497 テスト・ruff・mypy クリーン、2026-07-13）
- [ ] verify-gate → PR
