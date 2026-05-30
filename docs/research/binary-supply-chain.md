# 同梱バイナリのサプライチェーン対策と更新運用 設計メモ

[← 研究メモ目次](.)

> 本メモは `scripts/download_binaries.py` が取得する外部バイナリ（deno / ffmpeg / ffprobe / danmaku2ass）の
> 完全性検証とバージョン更新運用の方針を定める。**(b) ピン留め + sha256 検証は実装済み**（`bin/pins.json` +
> `download_binaries.py` の `_verify_sha256`、運用は [docs/build.md](../build.md) の「ピン留めと sha256 検証」に転記）。
> 残りは (c) 週次自動更新 Workflow（[6. 実装分解](#6-実装分解)）。本メモは設計経緯の記録として残す。

---

## 1. 背景

`download_binaries.py` は同梱バイナリを **無検証** かつ **可変参照** で取得しており、ビルド時の上流侵害が
そのまま配布物に混入するサプライチェーンリスクを抱えている。構成上、以下の点でリスクが増幅される。

- `bin/` は `.gitignore` 済み（`.gitignore:11`）→ バイナリはリポジトリに固定されず、**リリースのたびにネットから取り直す**。
- `release.yml` が `--yes`（GPL 同意プロンプト省略）で取得 → そのまま PyInstaller でバンドルし、**ユーザー配布物に同梱**される。

HTTPS は通信経路（中間者攻撃）は守るが、**上流アカウント・CDN・ビルドパイプラインが侵害された場合は無力**である。

---

## 2. 現状の確認

| コンポーネント | 取得元 | 参照の固定性 | 完全性検証 |
|---|---|---|---|
| deno | github.com/denoland（公式） | `latest`（**可変**） | なし |
| ffmpeg (Win) | BtbN/FFmpeg-Builds | `master-latest` autobuild（**可変**） | なし |
| ffmpeg (mac) | evermeet.cx（第三者・個人） | `getrelease`（**可変**） | なし |
| ffmpeg (Linux) | johnvansickle.com（第三者・個人） | `ffmpeg-git-*-static`（**可変**） | なし |
| danmaku2ass | github.com/m13253 | **コミット SHA 固定**（`DANMAKU2ASS_REF`） | git の内容アドレス性 |

danmaku2ass のみ SHA 固定で実質的な完全性がある（理論上 SHA-1 衝突の懸念は残るが現実的脅威は低い）。
**残り 4 つは可変参照かつ無検証**で、特に evermeet.cx / johnvansickle.com は個人運営の第三者ビルドである。

---

## 3. 方針: ピン留め + ハッシュ検証

### 3.1 ハッシュ検証だけでは不十分

`latest` / `master-latest` のような **可変参照のままハッシュだけ足しても意味がない**（取得物が変わるたびに
ハッシュも変わり事前固定できない）。対策は必ず次の 2 点をセットで行う。

1. **バージョン（タグ／リリース）をピン留め**して取得物を不変にする。
2. その不変物の **既知ハッシュ（理想は署名）を検証**する。

### 3.2 単一の台帳を真実の源にする

コンポーネントごとに **バージョン・URL・sha256** をまとめた台帳（`bin/pins.json` 想定）を真実の源とする。
`download_binaries.py` はこの台帳だけを見て取得・検証する。**更新＝台帳の差分を含む PR** となり、レビュー対象が
「バージョン番号とハッシュの変化」という監査しやすい形に収束する。

```jsonc
// bin/pins.json（想定スキーマ）
{
  "deno":          { "version": "v2.1.4",      "assets": { "<platform>": { "url": "...", "sha256": "..." } } },
  "ffmpeg-win":    { "version": "n7.1",         "url": "...", "sha256": "..." },
  "ffmpeg-mac":    { "version": "7.1",          "url": "...", "sha256": "..." },
  "ffmpeg-linux":  { "version": "7.1-static",   "url": "...", "sha256": "..." },
  "danmaku2ass":   { "ref": "ced8817..." }      // 既存どおり SHA 固定（git の内容アドレス性で担保）
}
```

ピン留めの理念は更新を止めることではなく、**更新を「暗黙（毎ビルド勝手に変わる）」から「明示（レビュー可能な PR 差分）」へ移す**ことにある。

---

## 4. 更新運用フロー

ピン留めの代償として ffmpeg / deno のセキュリティパッチへの追従が鈍るのを防ぐため、更新を 1 つの
レビュー可能なイベントとして回す。

| フェーズ | 内容 | 担い手 |
|---|---|---|
| 平常時 | 台帳どおりに取得・検証してビルド。台帳が固定なので取得物は不変 | CI（`release.yml`） |
| 定期 | 週次の定期ジョブが上流最新を取得し、**上流チェックサム／署名で検証**してから台帳を書き換え、更新 PR を自動起票 | 定期 Workflow |
| レビュー | 人は「旧→新バージョン」「ハッシュ変化」「上流チェックサム照合結果」を確認して承認 | 人 |
| 緊急時 | 重大 CVE 検知時は定期ジョブを待たず、手動で台帳更新 PR を切る | 人 |

GitHub package ではないため Dependabot は直接使えない。現実解は **「週次 cron の Actions で更新検知→検証→PR 自動起票」**
（Dependabot 相当を自前実装）であり、`release.yml` の取得ロジックを再利用する。

更新の検知対象には GitHub Security Advisories や各上流のリリースノートも含め、最低でも週次で確認する。

---

## 5. 更新時の信頼の確立

更新運用の肝は **「新ハッシュを取得物からそのまま計算して採用してはいけない」** 点にある
（攻撃済みの物のハッシュを記録するだけになる）。更新の瞬間こそ上流の真正性を確認する。優先順位は以下。

1. **署名検証**（あれば最優先）— Deno はリリースにチェックサム／署名がある。可能なら cosign / minisign で検証。
2. **上流公開のチェックサムと照合** — BtbN は各 zip の隣に `.sha256`、Deno は `*.sha256sum` を同梱。
3. **チェックサムが無い場合**（evermeet.cx / johnvansickle.com）— TOFU（Trust On First Use）を運用で補完する。
   別ネットワーク／別時刻での再取得一致確認、`ffmpeg -version` のビルド情報突き合わせなど複数経路で確認する。

つまり **「更新時だけは人＋上流チェックサムで真正性を担保し、以後は台帳のピンで固定」** という二段構えとする。

---

## 6. 実装分解

本メモを正本に、以下の単位で後続 Issue を切る。

| # | Issue | 内容 | 対象 |
|---|---|---|---|
| (b) | [#32](https://github.com/f8924919/yt-gui/issues/32) | 台帳 `bin/pins.json` 導入 + `download_binaries.py` に sha256 検証ヘルパー追加（不一致は `raise` で中断）。各バイナリをバージョン固定 | `scripts/download_binaries.py`, `bin/pins.json`, [docs/build.md](../build.md) |
| (c) | [#33](https://github.com/f8924919/yt-gui/issues/33) | 週次 cron の Workflow で上流更新を検知・検証し、台帳更新 PR を自動起票（(b) を前提） | `.github/workflows/`（新規） |
| 補強 | — | GitHub Actions の artifact attestation / SLSA provenance（`actions/attest-build-provenance`）でビルド由来を署名 | `release.yml` |

danmaku2ass は SHA 固定済みで現状良好。厳密化するならビルド後バイナリのハッシュも台帳化する。

実装着手時（(b)）には、本メモの「更新運用フロー」「信頼の確立」を [docs/build.md](../build.md) のバイナリ取得
セクションへ正式版として転記し、本メモは設計経緯の記録として残す。
