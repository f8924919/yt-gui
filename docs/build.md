# ビルドとバンドルバイナリ

PyInstaller でスタンドアロンバイナリをビルドする際の構成と、同梱する外部バイナリの取り扱いを記載。

## ビルドコマンド

```bash
uv run pyinstaller yt-gui.spec
```

ビルド成果物は `dist/yt-gui/` に出力される（macOS は `dist/yt-gui.app/`、Linux は加えて `dist/yt-gui-{version}-{arch}.AppImage`）。

## 同梱するバイナリ

| バイナリ | パス | 用途 |
|---|---|---|
| deno | `bin/deno[.exe]` | yt-dlp の JavaScript ランタイム（`js_runtimes` オプションで指定） |
| ffmpeg | `bin/ffmpeg/ffmpeg[.exe]` | 動画結合・音声変換（`ffmpeg_location` で指定） |
| ffprobe | `bin/ffmpeg/ffprobe[.exe]` | 動画メタデータ取得（`ffmpeg_location` から自動検索される） |
| danmaku2ass | `bin/danmaku2ass[.exe]` | ニコニコ動画コメント JSON → ASS 字幕変換（オリジナル形式パネルから subprocess 呼び出し） |

`yt-gui.spec` の `binaries` 設定でこれらをバイナリに同梱する。

## 同梱バイナリのライセンス（GPL/MIT 対応）

ffmpeg / ffprobe・danmaku2ass は GPL、deno は MIT ライセンスである。再配布義務（ライセンス全文・著作権表示の保持、GPL の対応ソース提供）を満たすため、リリース成果物にライセンス類を同梱する。

| 同梱物 | バンドル内パス | 生成元 |
|---|---|---|
| 本体 GPLv3 全文 | `licenses/LICENSE` | リポジトリの `LICENSE` |
| 各バイナリのライセンス本文 | `licenses/<component>/...` | `download_binaries.py` が配布アーカイブから抽出（BtbN zip / johnvansickle tarball / danmaku2ass clone） |
| サードパーティ告知 | `licenses/THIRD-PARTY-NOTICES.md` | `download_binaries.py` の `write_third_party_notices()` が生成 |

`THIRD-PARTY-NOTICES.md` は各コンポーネントの名称・ライセンス・著作権者・対応ソース入手先を列挙し、GPL が要求する**対応ソース提供の書面によるオファー**を兼ねる。アーカイブにライセンス本文を同梱しない配布元（macOS ffmpeg＝evermeet / osxexperts、deno）については、対応ソース入手先を同告知に明記してこれを担保する（GPL 本文自体はバンドル同梱の `licenses/LICENSE` で参照可能）。

`yt-gui.spec` は `bin/licenses/` 配下を再帰的に `licenses/` へ同梱する。これらは `bin/` 配下のためリポジトリにはコミットせず、ビルド時に毎回生成する。

## バイナリの自動取得

`scripts/download_binaries.py` で deno / ffmpeg / ffprobe / danmaku2ass を自動取得し `bin/` 配下に配置する。あわせて上記のライセンス本文を `bin/licenses/` に抽出し、`THIRD-PARTY-NOTICES.md` を生成する（ライセンス本文の抽出は失敗してもビルドは継続する）。`yt-gui.spec` のビルド時に自動呼び出しされる。

danmaku2ass は GitHub から `git clone` でソースを取得し、`sys.executable -m PyInstaller --onefile` で単独実行ファイルにビルドする。再現性のため master 追従ではなくコミットハッシュ（`DANMAKU2ASS_REF`）で固定する。ライセンスが GPL-3.0 なので ffmpeg と同様に同意プロンプトを通る（CI では `--yes` で省略）。

クロスビルド非対応のため、ターゲット OS と同じ OS 上でビルドする必要がある（GitHub Actions の OS マトリックスに準拠）。

```bash
# 既存ファイルがあればスキップ
python scripts/download_binaries.py

# 既存ファイルを強制的に再ダウンロード
python scripts/download_binaries.py --update
```

## ピン留めと sha256 検証

サプライチェーン対策として、deno / ffmpeg / ffprobe はバージョンを固定し、取得物を sha256 で検証する。設計の背景・経緯は [docs/research/binary-supply-chain.md](research/binary-supply-chain.md) を参照。

### 台帳 `bin/pins.json`

各バイナリの **バージョン・取得 URL・sha256** をまとめた台帳。`bin/` は `.gitignore` 対象だが、`pins.json` のみ追跡する（`.gitignore` で `bin/*` 除外 + `!bin/pins.json`）。`download_binaries.py` はこの台帳だけを見て取得し、ダウンロード後に sha256 を照合する。**不一致または sha256 未設定のときは取得物を削除して例外送出しビルドを中断する**（`_verify_sha256`、サイレント続行はしない）。

| コンポーネント | 台帳キー | 固定対象 | 備考 |
|---|---|---|---|
| deno | `deno` | バージョン付きリリースタグ + プラットフォーム別アセット | 上流 `<asset>.zip.sha256sum`（authoritative）と照合 |
| ffmpeg (Win) | `ffmpeg-win` | BtbN の **n リリースビルド**を**日付固定の不変 `autobuild-*` タグ**にピン（master ローリング・`latest` タグは不可） | zip を取得して sha256 算出 |
| ffmpeg (mac x86_64) | `ffmpeg-mac.x86_64` | evermeet の versioned zip（ffmpeg / ffprobe 個別） | `verify: zip`（zip の sha256 を照合）。GPG `.sig` 検証が望ましい |
| ffmpeg (mac arm64) | `ffmpeg-mac.arm64` | osxexperts.net の Apple Silicon 静的ビルド（evermeet と同一作者） | `verify: binary`（公開値が**展開後バイナリ**の sha256 のため展開後に照合） |
| ffmpeg (Linux) | `ffmpeg-linux` | johnvansickle の static ビルド（arch 別） | 公開 `.md5` と照合のうえ sha256 算出 |
| danmaku2ass | `danmaku2ass` | git コミット SHA（`ref`） | 内容アドレス性で担保するため **sha256 検証対象外** |

`danmaku2ass` の `repo` / `ref` は台帳を単一ソースとし、`download_binaries.py` の定数はここから読む。

### 更新運用

ピン留めの目的は更新の停止ではなく、**更新を「毎ビルド可変取得」から「レビュー可能な PR 差分」へ移す**ことにある。更新は `bin/pins.json` の差分を含む PR として行い、レビュアはバージョンと sha256 の変化を確認して承認する。

- **更新時の信頼の確立**: 新しい sha256 は取得物から計算してそのまま採用しない。上流の署名（Deno）・公開チェックサム（Deno `.sha256sum`、johnvansickle `.md5`）と照合する。チェックサム非公開の項目（evermeet）は GPG `.sig` 検証や別経路での再取得一致で TOFU を補完する。macOS arm64（osxexperts.net）はページが**展開後バイナリ**の sha256 を公開するため、展開後バイナリと公開値の一致を確認して登録する（`verify: binary`）。osxexperts は API・署名サイドカーが無いため週次自動追従の対象外とし、更新時はページの公開値を人手で確認する。
- **自動追従（週次）**: `.github/workflows/update-binaries.yml` が毎週 `scripts/refresh_pins.py` を実行し、上流最新を解決・検証して `bin/pins.json` を更新する PR を自動起票する（差分が無ければ PR は作らない）。検証根拠（旧→新・上流チェックサム照合結果）は PR 本文に出力されるため、レビュアは差分の確認だけで承認できる。
- **手動での差し替え手順**: ①`scripts/refresh_pins.py` を実行（または手動で上流バージョン URL を確認）→ ②上流チェックサム／署名で真正性を確認 → ③`bin/pins.json` の `version` / `url` / `sha256` を更新 → ④PR でレビュー。重大 CVE 時は週次を待たず手動で実施する。
- **ffmpeg-win の不変ピン（ドリフト対策）**: BtbN の `latest` はローリングタグで、同一バージョン（例 `n8.1`）でも上流が再ビルドするたびに同名アセットの中身＝ sha256 が変わる。これを `pins.json` に固定するとリリース CI が sha256 不一致で失敗するため、**日付固定の不変 `autobuild-YYYY-MM-DD-HH-MM` タグ配下のアセット URL にピンする**。`refresh_pins.py` は `releases/latest` ではなく最新の `autobuild-*` リリースを解決し（`_select_latest_autobuild`）、その中の最新ブランチ `win64-gpl` アセット（`ffmpeg-nX.Y.Z-<N>-g<hash>-win64-gpl-X.Y.zip`）を選んで不変 URL を書き込む。新バージョン追従時もこの仕組みで自動的に新しい不変タグへ再ピンされる。

## バージョン管理（単一ソース）

アプリのバージョンは **`pyproject.toml` の `[project] version` を唯一のソース** とする。更新時はこの 1 箇所だけを書き換える。

| 参照先 | 取得方法 |
|---|---|
| ウィンドウタイトル（実行時） | `yt_gui.get_version()` → `importlib.metadata.version("yt-gui")` |
| macOS `.app` の `CFBundleShortVersionString` | `yt-gui.spec` が `tomllib` で `pyproject.toml` を読み取り注入 |
| Windows `.exe` のバージョンリソース | `yt-gui.spec` が `VSVersionInfo` を組み立て `EXE(version=...)` に渡す（`FileVersion` / `ProductVersion`） |
| Linux AppImage のファイル名 | `scripts/build_appimage.py` が `get_version()` を用い `yt-gui-{version}-{arch}.AppImage` とし、`VERSION` 環境変数も設定 |

`importlib.metadata` で実行時にバージョンを解決するため、以下が前提となる。

- `pyproject.toml` に `[build-system]`（hatchling）を定義し、`uv sync` で yt-gui 自身をパッケージとしてインストールしてメタデータ（`*.dist-info`）を生成する。
- PyInstaller バンドルでもメタデータを解決できるよう、`yt-gui.spec` の `datas` に `copy_metadata('yt-gui')` を追加して `*.dist-info` を同梱する。

> メタデータが見つからない場合 `get_version()` は `"unknown"` を返す（クラッシュさせない）。Windows のバージョンリソースは `pyproject.toml` の値を直接読むため `"unknown"` にはならないが、AppImage のファイル名は `get_version()` 経由のため `uv sync` 未実施時は `unknown` を含みうる。

## CI / リリース自動化（GitHub Actions）

`.github/workflows/release.yml` が、`main` への push を契機にタグ作成からリリース公開までを自動化する。詳細な設計は [docs/task/archive/release-workflow.md](task/archive/release-workflow.md) を参照。

### トリガーと冪等性

`pyproject.toml` の `[project] version` を読み取り、`v{version}` タグが**未存在のときだけ**リリース処理を実行する（コミット差分ではなくタグ有無で判定するため冪等）。バージョンを上げて `main` にマージするだけで一連の処理が走り、バージョン無関係の push やワークフロー再実行では何もしない。

### ジョブ構成

| ジョブ | 役割 |
|---|---|
| `version-gate` | version を読み、`v{version}` タグの有無で `should_release` を決定 |
| `tag` | `should_release` のとき `v{version}` タグを作成・push |
| `build` | OS マトリックスでビルドし成果物を artifact 化 |
| `release` | artifact を集約し `gh release create v{version}` に添付 |

`GITHUB_TOKEN` で作成したタグは別ワークフローを再トリガーしない仕様のため、`tag` → `build` → `release` を `needs` で同一実行内に連結している（PAT 不要）。

`build` がアップロードする `dist-*` artifact は、同一実行内の `release` ジョブが `download-artifact` で集約するためだけの中間成果物である。配布物は GitHub Release のアセットとして恒久的に残り（Actions ストレージ枠とは別カウント）、実行完了後に artifact 自体は不要になる。private リポジトリは Actions ストレージの無料枠が小さく、リリースごとに数百 MB の artifact が蓄積すると容量警告に達するため、`upload-artifact` に `retention-days: 1` を設定して翌日に自動失効させている。

### OS マトリックスと成果物

クロスビルド非対応のため各 OS ランナーでビルドする。

| ランナー | アーキ | 成果物 |
|---|---|---|
| `windows-latest` | x64 | `yt-gui-{version}-windows-x64.zip`（`dist/yt-gui/` を圧縮） |
| `macos-latest` | arm64 | `yt-gui-{version}-macos-arm64.zip`（`dist/yt-gui.app` を `ditto` で圧縮） |
| `macos-15-intel` | x86_64 | `yt-gui-{version}-macos-x86_64.zip`（`dist/yt-gui.app` を `ditto` で圧縮） |
| `ubuntu-22.04` | x64 | `yt-gui-{version}-x86_64.AppImage`（spec が生成） |

OS 非依存の成果物として、ブラウザ拡張の zip を Linux ランナーで併せて生成する。

| 成果物 | 内容 |
|---|---|
| `yt-gui-extension-{version}.zip` | `extension/` 一式（`manifest.json` / `background.js` / `popup.*` / `format_choice.js` / `options.*` / `_locales/` / `icons/`）。zip 化の直前に `scripts/sync_extension_version.py` で `manifest.json` の version を `pyproject.toml` に同期する |

- macOS は arm64 / x86_64 の 2 アーキを別ランナーでビルドする。`PyInstaller` は `target_arch=None`（ランナーのネイティブ arch）でビルドし、deno・ffmpeg・ffprobe はダウンロード時に `platform.machine()` で arch を解決するため、ランナーごとに対応 arch のバイナリが同梱される。zip 名は matrix の `macos_arch` で出し分ける。
  - Intel ランナーは `macos-13` 退役後の標準 Intel イメージ `macos-15-intel` を使用する。
  - ffmpeg/ffprobe は arm64 = osxexperts.net（Apple Silicon ネイティブ）、x86_64 = evermeet.cx をそれぞれ取得する（`bin/pins.json` の `ffmpeg-mac.<arch>`）。両 arch ともネイティブで動作し、arm64 成果物の Rosetta 依存は解消済み。
- `ubuntu-22.04` を採用するのは glibc 互換性のため（新しい glibc でビルドした AppImage は古い環境で起動しない）。
- ビルド前に `scripts/download_binaries.py --yes` を実行して GPL 同意プロンプトを自動承認する（spec 内の再呼び出しは既存ファイルありでスキップ）。
- Linux ランナーでは `binutils`（objdump）・`file`（appimagetool）を apt で導入する。

### 成果物の来歴署名（SLSA provenance / artifact attestation）

`release` ジョブが GitHub Release を作成する直前に `actions/attest-build-provenance` で配布成果物（zip / AppImage）へ来歴署名を付与する。「この成果物が確かに本リポジトリの `release.yml` が当該 commit から生成した物である」ことを暗号的に検証可能にし、配布物の差し替え・偽造を検知できるようにする（同梱バイナリ＝入力のピン留めと合わせ、供給網の入力・出力の両端を固める）。

- Sigstore のキーレス署名（OIDC + Fulcio + Rekor 透明性ログ）を用いるため秘密鍵管理は不要。`release` ジョブに `id-token: write` / `attestations: write` を付与する。
- 公開する物と同一バイトを subject にするため、Release 作成の直前に `assets/**/*.{zip,AppImage}` を対象に署名する。
- **`actions/attest-build-provenance` は個人所有の private リポジトリでは利用できない**ため、`if: ${{ !github.event.repository.private }}` でガードし private のときはスキップする（スキップ時も Release 作成は続行する）。public 化すれば自動で署名が有効になる。

配布物の検証（任意・第三者が実行可能）:

```bash
gh attestation verify <ダウンロードしたファイル> --repo f8924919/yt-gui
```

### 留意点

- **コード署名なし**: Windows は SmartScreen 警告、macOS は Gatekeeper でブロックされる（未署名アプリのため）。署名・公証は別途対応が必要（バックログ: [#39](https://github.com/f8924919/yt-gui/issues/39)）。
- **provenance はコード署名ではない**: 上記の来歴署名は `gh attestation verify` による帯域外検証であり、OS の SmartScreen / Gatekeeper 警告は**解消しない**。起動時警告の解消には Authenticode / Apple Developer ID 署名・公証が別途必要（[#39](https://github.com/f8924919/yt-gui/issues/39)）。
- **検証はオプトイン**: 主な受益者は監査者・再配布者・自動化・インシデント対応。`release.yml` 自体（write 権限）が侵害された場合は防げないが、Rekor に証跡が残る。

## 同梱バイナリのピン自動更新（GitHub Actions）

`.github/workflows/update-binaries.yml` が週次（毎週月曜 06:00 UTC）と手動実行で `scripts/refresh_pins.py` を走らせ、上流最新を解決・検証して `bin/pins.json` を更新する PR を自動起票する。「ピン留めと sha256 検証」の更新運用を担う。

| 項目 | 内容 |
|---|---|
| トリガー | `schedule`（週次）+ `workflow_dispatch`（手動） |
| 検証 | deno は上流 `.sha256sum`、johnvansickle は公開 `.md5` と照合。BtbN は最新の不変 `autobuild-*` タグのアセットを取得し sha256 算出（`latest` ローリングは使わない）、evermeet（mac x86_64）は info API のサイズ・GPG `.sig` 有無を確認（TOFU） |
| 冪等性 | `bin/pins.json` に差分があるときだけ PR を作成（`peter-evans/create-pull-request`）。検証失敗時は例外で停止し PR を作らない |
| 対象外 | danmaku2ass（git の SHA 固定のため）、macOS arm64 ffmpeg（osxexperts.net・API/署名無しのため手動更新） |
| 権限 | `contents: write` / `pull-requests: write` |

> **前提設定**: GITHUB_TOKEN で PR を作成するため、リポジトリの Settings > Actions > General > **「Allow GitHub Actions to create and approve pull requests」を有効化**しておくこと。

## ワークフロー権限とリポジトリのセキュリティ設定

public リポジトリでは GITHUB_TOKEN の既定権限が外部 PR にも及ぶため、各ワークフローに**最小権限**を明示する。

| ワークフロー | `permissions` | 理由 |
|---|---|---|
| `test.yml` | `contents: read` | checkout・依存取得・テストのみで書き込み不要 |
| `release.yml`（ジョブ単位） | `contents: write` / `release` のみ `id-token: write` `attestations: write` | タグ・リリース作成と来歴署名（provenance）に必要 |
| `update-binaries.yml` | `contents: write` `pull-requests: write` | `bin/pins.json` 更新 PR の作成に必要 |

### 依存の自動更新（Dependabot）

`.github/dependabot.yml` が週次で 2 つのエコシステムを追従し、更新 PR を起票する。

| エコシステム | 対象 | 目的 |
|---|---|---|
| `github-actions` | ワークフローが参照する action のバージョン | action のサプライチェーン追従（タグピンの更新） |
| `uv` | `pyproject.toml` / `uv.lock` | Python 依存（yt-dlp 等）の更新・脆弱性対応 |

> 同梱バイナリ（ffmpeg / deno 等）のピンは Dependabot の対象外で、前述の `update-binaries.yml` が別途追従する。

### public 化後に有効化するリポジトリ設定

public 化（`gh repo edit f8924919/yt-gui --visibility public`）後、public で無料解放される以下を有効化する。

- **Secret scanning + Push protection**: 認証情報の誤コミット検知・ブロック。
- **Dependabot alerts / security updates**: 脆弱性アラートと自動修正 PR（上記 version updates と併用）。
- **Private Vulnerability Reporting**: [SECURITY.md](../SECURITY.md) の報告導線。Settings > Code security で有効化。
- **`main` のブランチ保護**: PR 必須・ステータスチェック（`Test`）必須。GitHub Flow（[git-workflow.md](git-workflow.md)）と整合。
- **Auto-delete merged branches**: マージ済みブランチの自動削除。

## yt-gui.spec の構成

- PySide6 向けに設定済み。`pyinstaller-hooks-contrib` が PySide6 プラグイン・データを自動検出するため追加設定は最小限。
- macOS 向けビルドでは `BUNDLE` ブロックで `.app` バンドルを自動生成する。
- Linux 向けビルドでは `scripts/build_appimage.py` を後処理として自動呼び出しし、`.AppImage` を生成する。
- アイコンは `assets/icon.png` から PNG → ICO（Windows）/ ICNS（macOS）への自動変換に対応。ブラウザ拡張用アイコン（`extension/icons/`、16/32/48/128 px）も同じ `assets/icon.png` から `scripts/build_extension_icons.py` で生成する（生成物はコミット）。
- ビルド時に `pyproject.toml` からバージョンを読み取り（`tomllib`）、`CFBundleShortVersionString` に注入する。`copy_metadata('yt-gui')` でパッケージメタデータも同梱する（バージョン管理セクション参照）。

## Linux AppImage の生成

Linux 上で `uv run pyinstaller yt-gui.spec` を実行すると、`COLLECT` 完了後に `scripts/build_appimage.py` が自動実行され `dist/yt-gui-{version}-{arch}.AppImage` を生成する。

| 要素 | 内容 |
|---|---|
| AppDir 配置 | `dist/yt-gui.AppDir/`（`AppRun` / `yt-gui.desktop` / `yt-gui.png` / `usr/`） |
| 同梱内容 | `usr/` 配下に PyInstaller `COLLECT` 出力を一式コピー（実行ファイルと `_internal/` の相対関係を維持） |
| `appimagetool` | `bin/appimagetool-{arch}.AppImage` に自動取得（既存があれば再利用） |
| 起動方法 | AppRun が `usr/yt-gui` を `exec` する |
| 実行モード | `--appimage-extract-and-run` で起動するため FUSE 未導入環境（CI / コンテナ）でも動作 |

手動で再生成したい場合は `uv run python scripts/build_appimage.py --force` を実行する。

## Cookies ファイル

Cookies ファイルはビルド成果物には**含めない**。GUI の設定画面でユーザーが任意に指定する運用。

実行時に Cookies フィールドのパスが指すファイルが存在しない場合は警告ダイアログを表示し、Cookies なしでダウンロードを続行する。
