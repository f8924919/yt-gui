# fix(ci): macOS arm64 リリースの ffmpeg を Apple Silicon ネイティブ化

対応 Issue: #42

## 背景

`macos-arm64` リリースは、本体（PySide6）・deno は arm64 ネイティブだが、**ffmpeg/ffprobe だけが Intel x86_64**（evermeet.cx 提供）で、Apple Silicon 機では Rosetta 2 経由で動作していた。evermeet は Apple Silicon ネイティブ版を提供しないと明言しているため、別ソースが必要。

## 入手元の選定

候補を実取得・検証して比較した。

| 候補 | 信頼モデル | 検証可否 | バージョン | 判定 |
|---|---|---|---|---|
| osxexperts.net | ページが展開後バイナリの sha256 を公開（同一作者の evermeet と同系・TOFU） | ✅ 取得・検証済 | 8.1（Intel 8.1.1 とほぼ揃う） | **採用** |
| eugeneware/ffmpeg-static | GitHub 公開 digest | ✅ | 6.1.1（版ずれ大）・再配布元 | 不採用 |
| 自前ビルド | 第三者依存なし | — | 任意 | 不採用（CI 複雑化） |

**採用: osxexperts.net**（Helmut Tessarek 氏の Apple Silicon 静的ビルド。evermeet の正規 arm64 対応物）。
取得物を展開し、`file` で Mach-O arm64 ネイティブ（静的）、sha256 がページ公開値と一致することを確認:

- ffmpeg  8.1 arm64: `9a08d61f9328e8164ba560ee7a79958e357307fcfeea6fe626b7d66cdc287028`
- ffprobe 8.1 arm64: `aab17ac7379c1178aaf400c3ef36cdb67db0b75b1a23eeef2cb9f658be8844e6`

## 実装

- `bin/pins.json`: `ffmpeg-mac` を arch 別構造へ再編（`x86_64`=evermeet / `arm64`=osxexperts）。各 arch に `verify`（`zip` / `binary`）を持たせる。
  - osxexperts の公開値は zip ではなく**展開後バイナリ**の sha256 のため `verify: binary`。
- `scripts/download_binaries.py` `_download_ffmpeg_macos`: `platform.machine()` で arch を解決し該当サブ設定を取得。`verify` モードに応じて zip（DL 時）／binary（展開後）で sha256 照合。`__MACOSX/._*`（AppleDouble）を除外。`COMPONENTS` の配布元記載に arm64 を追記。
- `scripts/refresh_pins.py` `refresh_ffmpeg_mac`: 新構造に対応。x86_64 は evermeet info API で自動追従、arm64 は API/署名が無いため自動追従せず現状維持（手動更新）。
- `tests/test_download_binaries.py`: arch 別構造の sha256 存在チェックへ更新。
- docs: `docs/build.md`（pin 表・OS マトリクス注記・信頼確立・週次対象外）、`docs/research/binary-supply-chain.md`（§5 に arm64 追記）。

`release.yml` の変更は不要（arm64 は既に `macos-latest` でビルドされ、ffmpeg 取得は `download_binaries.py` が arch 解決するため）。

## 検証

- `bin/pins.json` は valid JSON。
- `uv run pytest tests/test_download_binaries.py tests/test_refresh_pins.py` 通過。
- `uv run ruff check`（変更ファイル）通過。`scripts/` は `yt_gui/` 外のため `ruff format` 非対象（既存どおりシングルクォート方針）。
- 実機 arm64 での `ffmpeg -version` / ネイティブ動作確認は次回 macOS arm64 リリース時に実施。

## 関連

- #41（Intel Mac ビルド追加）— 本 Issue はその過程で判明した課題。

## 対象ファイル

- `bin/pins.json` / `scripts/download_binaries.py` / `scripts/refresh_pins.py`
- `tests/test_download_binaries.py`
- `docs/build.md` / `docs/research/binary-supply-chain.md`
- `docs/task/macos-arm64-ffmpeg.md`（本ファイル） / `docs/task/index.md`
