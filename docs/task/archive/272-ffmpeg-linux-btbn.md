# #272 ffmpeg-linux の取得元を johnvansickle から BtbN（不変 autobuild タグ）へ切り替える

- Issue: [#272](https://github.com/f8924919/yt-gui/issues/272)
- ブランチ: `feature/272-ffmpeg-linux-btbn`
- ステータス: 完了（2026-07-20）

## 背景（要約）

johnvansickle.com は GitHub ランナーからの取得がブロックされリリース CI が不安定（#265 で特定）。上流更新も 2024-06 で停止。ffmpeg-win が採用済みの BtbN/FFmpeg-Builds（日付固定の不変 `autobuild-*` タグ・GitHub リリースアセット）へ切り替える。詳細は Issue 本文を正とする。

## 受け入れ条件の改訂（criteria-review 反映・2026-07-20）

ユーザー確認のうえ以下を確定し、Issue 本文へ反映済み。

1. CI 検証は `release.yml` に `workflow_dispatch` を**恒久追加**して実施する。
2. win/linux の autobuild タグ・バージョン統一を受け入れ条件の**必須要件に昇格**（amd64/arm64 の同一リリース保証も含む）。
3. BtbN Linux ビルドが完全静的リンクでなかった場合は**作業を中断してユーザーに方針を相談**する。

## 事前確認の結果（2026-07-20・Windows ローカルで実施）

`autobuild-2026-07-19-13-12`（ffmpeg-win の現ピンと同一タグ）の実アセットを取得して裏取り。

- アセット存在: `ffmpeg-n8.1.2-22-g94138f6973-linux64-gpl-8.1.tar.xz` / 同 `linuxarm64-gpl` を確認。
- sha256（ローカル算出。pins.json に採用）:
  - linux64: `166375e7f8b1f6963949a61a83ffffe858eba742f6326180b8ff3bc58b205c72`（125,618,132 bytes）
  - linuxarm64: `371203e43ab3aaa703c9904b40f6a6065dcc08fd3260f441f3bbe040e1afe8bf`（107,323,040 bytes）
- アーカイブ構成（linux64 実物）: `ffmpeg-<version>-linux64-gpl-8.1/` 直下に `LICENSE.txt`・`bin/{ffmpeg,ffprobe,ffplay}`・`doc/`・`man/`・`presets/`。win zip と同じ `/bin/` ネスト形式。
- ライセンス抽出: `LICENSE.txt`（basename）は `_is_license_name` の `_LICENSE_BASENAMES` に含まれ、既存ロジックのまま抽出可能。
- サイズ変化: ダウンロードは amd64 で約 42MB → 約 126MB。展開後の ffmpeg / ffprobe は各約 145MB（johnvansickle 比で大幅増）。AppImage は squashfs 圧縮のため配布物サイズへの実影響は CI 実行時に実測して本メモへ記録する。
- 静的リンク確認（`ldd`）と実変換は Linux 環境が必要のため CI スモークで実施（下記）。

## 設計

### bin/pins.json

`ffmpeg-linux` を BtbN へ差し替え。スキーマ（`version` / `comment` / `assets.{amd64,arm64}.{url,sha256}`）は維持し、値のみ変更。ffmpeg-win と同一の不変 autobuild タグ・同一バージョンにピンする。

### scripts/download_binaries.py

- `_download_ffmpeg_linux`: メンバー選択を johnvansickle 用の basename 一致から、win と同じ `endswith("/bin/<name>")` 一致へ変更（`ffplay` 等の誤爆余地がない厳密な形）。**見つからない場合は silent skip せず `RuntimeError` で明示的に中断**する（受け入れ条件の異常系。`next(gen, None)` → `None` 判定で握り替え、`StopIteration` を漏らさない）。win 側（現状 `next()` で `StopIteration` が漏れる）も同じ形に揃える。ライセンス抽出は既存の全 member 走査＋`_is_license_name` のまま（BtbN の `LICENSE.txt` で機能確認済み）。
- `COMPONENTS` の FFmpeg `distribution`（Linux 行）を BtbN に更新（`write_third_party_notices()` 経由で THIRD-PARTY-NOTICES.md に反映）。

### scripts/refresh_pins.py

- `_select_btbn_versioned_asset(assets, variant, ext)` へ一般化（現状 `win64-gpl`・`.zip` ハードコード）。win は `("win64-gpl", "zip")`、linux は `("linux64-gpl", "tar.xz")` / `("linuxarm64-gpl", "tar.xz")` で呼ぶ。
- **win/linux のタグ解決を共通化（引数注入方式・design-review 反映）**: `refresh_pins()` が BtbN releases 一覧の取得＋`_select_latest_autobuild` を 1 回だけ行い、解決済みリリース dict を `refresh_ffmpeg_win(old, release)` / `refresh_ffmpeg_linux(old, release)` へ**引数で渡す**。module-global キャッシュは使わない（テストのキャッシュ汚染・refresher 実行順への暗黙依存を排除し、「同一実行内で同一リリース」を構造的に保証する）。
- `refresh_ffmpeg_linux`: `.md5` 照合方式を廃し、共有リリースから amd64/arm64 のアセットを選び `_hashes_of_url` で sha256 確定。amd64/arm64 のバージョントークン不一致は例外で中断。共有リリースに必要アセットが欠けている場合も fail-closed（例外で停止し PR 不作成。その週の週次 refresh は止まる運用として許容）。
- `_parse_jvs_version` と johnvansickle 関連の記述（docstring・`_build_summary` の TOFU 注記「evermeet / johnvansickle は TOFU」）を削除・更新。`_hashes_of_url` の md5 算出は johnvansickle 照合専用だったため戻り値から削除（デッドコード除去。呼び出し 3 箇所を追随）。

### .github/workflows/release.yml

- `workflow_dispatch` トリガーを恒久追加。**dispatch 実行はビルド検証専用のドライラン**。design-review の指摘（`release` ジョブが `if` 無条件／`should_release` がイベント種別を見ない／`build` の `always()` 化による main push 冪等性破壊）を受け、各ジョブの条件式を以下に確定する:
  - `tag`: `if: github.event_name == 'push' && needs.version-gate.outputs.should_release == 'true'`
  - `build`: `if: always() && needs.version-gate.result == 'success' && (needs.tag.result == 'success' || (github.event_name == 'workflow_dispatch' && needs.tag.result == 'skipped'))`
  - `release`: `if: github.event_name == 'push' && needs.version-gate.outputs.should_release == 'true'`（`needs` の build 成功要件は維持）
  - `build` の checkout ref: `${{ github.event_name == 'workflow_dispatch' && github.sha || format('v{0}', needs.version-gate.outputs.version) }}`
  - `concurrency.group` は `release-${{ github.event_name }}` に分離（ドライランが本番リリースをブロックしない。dispatch はタグ・リリースを作らないため並走しても競合しない）
- Linux ビルドに **ffmpeg スモークステップを恒久追加**（`download_binaries.py` 直後）: `ldd` の動的依存が **glibc コアの whitelist**（libc / libm / libdl / librt / libpthread / libmvec / libgcc_s / ld-linux / linux-vdso）に収まることを判定し（範囲外の `.so` 依存は fail、完全静的なら "not a dynamic executable" で即 pass）、`ffmpeg -version` / `ffprobe -version`・lavfi 入力での実変換 1 本を実行する。AppImage に入るのは同一バイトのため、これで「AppImage 内の ffmpeg が動作する」ことを担保する（AppImage 生成自体は build の既存ステップで検証される）。
  - **判定基準の経緯**: 当初は「純静的のみ合格」で実装したが、初回 CI 実行（run 29745460999）で BtbN linux64-gpl が **glibc コアのみ動的リンク**（コーデック等は静的同梱）と判明し、承認済み方針どおり中断してユーザーに相談。アプリ本体（PyInstaller ビルド）が既に同等の glibc 依存を持ち動作要件が追加されないこと（BtbN の要求 glibc 2.28+ は本体要件より緩い）を根拠に、**glibc コア限定の whitelist 許容**へ緩和することをユーザーが承認（2026-07-20）。

### docs / THIRD-PARTY-NOTICES

- `docs/build.md`: 台帳表の ffmpeg (Linux) 行、リトライ節の背景記述への解決経緯追記、更新運用（johnvansickle `.md5` 記述の除去）、「ffmpeg-win の不変ピン」節の win/linux 一般化、「同梱バイナリのピン自動更新」表の検証列、release.yml 節（workflow_dispatch・スモーク）。
- `docs/research/binary-supply-chain.md`: 設計経緯の記録という位置づけを崩さず、§2 表・§5 の johnvansickle 言及へ「#272 で BtbN へ切替済み」の追記を行う（履歴の書き換えはしない）。

## テスト計画（テストファースト）

- `tests/test_download_binaries.py`
  - pins 検証テストに「ffmpeg-win / ffmpeg-linux の URL が不変 `autobuild-*` タグ配下」のアサーション追加。
  - `_download_ffmpeg_linux` の展開テストを新設: BtbN 実物構成（`ffmpeg-*/bin/{ffmpeg,ffprobe,ffplay}`・`LICENSE.txt`）を再現した tar.xz フィクスチャを `tmp_path` に生成し、`_download_verified` を monkeypatch。正常系（両バイナリ配置・実行権限・ライセンス抽出・ffplay 非抽出）と異常系（`bin/ffmpeg` 欠落レイアウトで `RuntimeError`）。
- `tests/test_refresh_pins.py`
  - `_select_btbn_versioned_asset` の一般化テスト（linux64-gpl / linuxarm64-gpl / tar.xz 拡張子。既存 win テストは新シグネチャへ追随）。
  - `refresh_ffmpeg_linux` のテスト: amd64/arm64 が同一リリース・同一バージョンから解決されること、バージョン不一致で例外。
  - win/linux の共有解決テスト: 同一実行内で `refresh_ffmpeg_win` / `refresh_ffmpeg_linux` が同一タグ・同一バージョンを返すこと（releases API モックの呼び出しが 1 回に共有されること）。
  - `_parse_jvs_version` のテストを削除。

## 検証記録

### refresh_pins.py 実走（2026-07-20・Windows ローカル）

- `uv run python scripts/refresh_pins.py` を実走。ffmpeg-linux が autobuild 再ピン方式で解決され、win と同一タグ・同一バージョン（`n8.1.2-22-g94138f6973`）で「変更なし」を報告。
- 再ダウンロードで算出した sha256 がピン値と一致＝別時刻・別経路の再取得一致確認（TOFU 補完）を兼ねる。
- サマリ定型文から johnvansickle が除去されていることも確認。

### CI 1 回目（release.yml workflow_dispatch・run 29745460999・2026-07-20）

- [x] ドライラン設計の動作確認: `version-gate` 成功・`tag` / `release` スキップ・`build` 4 OS 実行
- [x] windows / macos arm64 / macos x86_64 の build 成功（変更の影響なしを確認）
- [x] `build (ubuntu-22.04)` は **ffmpeg スモークの静的判定で設計どおり fail-closed**: `ldd` の結果、BtbN linux64-gpl は glibc コア（libc / libm / libdl / librt / libpthread / libmvec / libgcc_s / ld-linux / linux-vdso）のみ動的リンク、範囲外の `.so` 依存なし。ユーザー相談のうえ whitelist 許容へ緩和（上記「判定基準の経緯」）。

### CI 2 回目（whitelist 緩和後の再実行・run 29746529269・2026-07-20）

- [x] 全ジョブ success（build 4 OS。`tag` / `release` はスキップ＝ドライラン設計どおり）
- [x] ffmpeg スモーク pass: glibc コア whitelist 判定 OK（範囲外依存なし）・`ffmpeg -version` / `ffprobe -version` = `n8.1.2-22-g94138f6973-20260719`・lavfi → mp3 実変換 1 本成功
- [x] AppImage 生成成功（`yt-gui-0.7.0-x86_64.AppImage`）。配布物サイズ: ubuntu artifact 約 235.5MB（AppImage＋拡張 zip）。v0.7.0 実リリースの AppImage（johnvansickle 同梱）は約 186.7MB で、**約 +49MB（+26%）の増**（BtbN の ffmpeg/ffprobe が展開後 各約 145MB と大きいため。squashfs 圧縮後の増分としては想定内と判断）

## 進捗

- [x] Issue 受け入れ条件の改訂（criteria-review → ユーザー確認 → Issue 反映）
- [x] 事前確認（アセット存在・sha256・レイアウト・ライセンス名）
- [x] docs 先行反映
- [x] design-review 実施・指摘反映（release.yml 条件式の確定・引数注入方式・ldd 判定式・md5 デッドコード除去）
- [x] テスト先行（red 15 件を確認してから実装）
- [x] 実装 → green（ruff / mypy / 全 515 テスト pass）
- [x] CI 検証（workflow_dispatch 2 回。1 回目は静的判定で設計どおり fail → 方針確認 → 2 回目 all green）
- [x] verify-gate（verify green・docs-check 指摘なし・evaluator 全 6 条件 PASS）→ PR
