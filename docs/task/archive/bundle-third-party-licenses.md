# GPL/MIT 同梱バイナリのライセンス同梱（#12）

対応 Issue: #12

## 背景

GPL（ffmpeg / ffprobe、danmaku2ass）と MIT（deno）の外部バイナリを同梱してリリースしているが、
リリース成果物にライセンス全文・著作権表示・対応ソース入手先が含まれていない。GPL/MIT の再配布義務を満たすため同梱する。

## 方針

1. `scripts/download_binaries.py`
   - 同梱コンポーネントのメタデータを `COMPONENTS` に定義（名称・ライセンス・著作権者・上流 URL・対応ソース・配布元）。
   - 配布アーカイブに含まれるライセンス本文を `bin/licenses/<component>/` へベストエフォートで抽出（BtbN zip / johnvansickle tarball / danmaku2ass clone）。失敗してもビルドは継続。
   - `write_third_party_notices()` で `bin/licenses/THIRD-PARTY-NOTICES.md` を生成（オフライン・単体テスト可能）。属性表示＋対応ソースの書面オファーを兼ねる。
2. `yt-gui.spec`
   - 本体 `LICENSE`（GPLv3）と `bin/licenses/` 一式を `licenses/` 配下へ `datas` 同梱。
3. `README.md` / `docs/build.md` にライセンス同梱仕様を追記。
4. `tests/test_download_binaries.py` に notices 生成内容の検証を追加。

## 補足

- evermeet（macOS ffmpeg）と deno のアーカイブはライセンス本文を同梱しないため、対応ソース入手先を
  `THIRD-PARTY-NOTICES.md` に明記して書面のオファーとする。GPL 本文自体は本体 `LICENSE`（GPLv3）が
  バンドルに含まれるため参照可能。
- これは法的助言ではなく、GPL/MIT の一般的な再配布義務に基づく対応。

## 進捗

- 完了（2026-05-29）。PR #13 をマージし v0.1.1 を公開。リリース成果物（macOS zip）を展開して
  `licenses/LICENSE`（GPLv3）・`licenses/THIRD-PARTY-NOTICES.md`・`licenses/danmaku2ass/COPYING` の
  同梱を実検証済み。
- 既出の v0.1.0 はリリースノートにライセンス・対応ソースを追記して是正（ファイル添付はサンドボックスの
  `uploads.github.com` 制約で不可のため、ホスト側／Web UI からの添付が残作業）。
