# yt-gui Connector（ブラウザ拡張）

開いている動画ページの URL と Cookie を、ワンクリックで yt-gui のダウンロードキューへ送る Chromium 系（Chrome / Edge / Brave など）向け拡張機能です。

仕様: [docs/spec/features/browser-extension.md](../docs/spec/features/browser-extension.md)

## 構成

| ファイル | 役割 |
|---|---|
| `manifest.json` | Manifest V3 定義（権限・background・options・popup・icons・default_locale） |
| `background.js` | service worker。URL/Cookie 取得 → 受信サーバーへ POST。右クリックメニュー（記憶済み形式で即送信）も担う |
| `popup.html` / `popup.js` | ツールバーボタンのポップアップ。形式（最高画質/解像度指定/音声のみ/アプリ既定）を選んで送信。選択は `chrome.storage` に記憶 |
| `options.html` / `options.js` | トークン・ポートの設定画面（表示はブラウザ言語に追従） |
| `_locales/{en,ja}/messages.json` | オプション画面の多言語メッセージ |
| `icons/icon-{16,32,48,128}.png` | 拡張アイコン（アプリ本体と同一。`assets/icon.png` 由来） |

## 多言語・アイコン・バージョン

- **多言語**: オプション画面の文言は Chrome 標準の `_locales/` + `chrome.i18n` でブラウザの UI 言語（日本語 / 英語）に自動追従します。未対応言語は英語（`default_locale`）にフォールバックします。`manifest.json` の `name` / `description` は英語固定です。
- **アイコン**: アプリ本体と同一アイコンを使用します。生成は `scripts/build_extension_icons.py`（`assets/icon.png` から 16/32/48/128 px を生成）。
- **バージョン**: `manifest.json` の `version` はアプリ本体（`pyproject.toml`）と同期します。リリース時に CI が `scripts/sync_extension_version.py` で揃えます。

## 配布物（リリース zip）

リリースでは拡張一式を `yt-gui-extension-{version}.zip` として GitHub Release に添付します。手元では `extension/` フォルダをそのまま unpacked 読み込みできます。

## インストール（unpacked）

1. yt-gui を起動し、「設定 → ブラウザ連携」でサーバーを有効化してトークンをコピーする。
2. Chrome で `chrome://extensions` を開き、右上の「デベロッパーモード」を ON にする。
3. 「パッケージ化されていない拡張機能を読み込む」で本 `extension/` フォルダを選ぶ。
4. 拡張の「詳細 → 拡張機能のオプション」を開き、コピーしたトークンとポート（既定 8718）を保存する。

## 使い方

- **形式を選んで送る**: 動画ページでツールバーのアイコンをクリックするとポップアップが開きます。形式（`最高画質` / `解像度指定` / `音声のみ` / `アプリの既定を使う`）を選び、「yt-gui に送る」を押します。選んだ形式は次回以降の既定として記憶されます。
  - コンテナ（mp4/mkv/webm）は拡張では選べません。実際の出力コンテナは yt-gui アプリ側の設定に従います。
  - オリジナル形式（トラック個別選択）は拡張では選べません。
- **記憶済み形式でワンクリック送信**: ページを右クリックして「yt-gui に送る」を選ぶと、ポップアップを開かずに前回選択した形式で即送信します。
- 結果はアイコンのバッジで通知されます。

| バッジ | 意味 |
|---|---|
| `OK`（緑） | キューに追加成功 |
| `403`（赤） | トークン不一致（オプションを確認） |
| `OFF`（赤） | 接続不可（yt-gui 未起動 / 連携無効） |
| `KEY`（赤） | トークン未設定 |
| `ERR`（赤） | その他のエラー |

## トラブルシューティング

### ニコニコ等で「ログインが必要」エラーが出る

yt-gui に有効な Cookie が届いていない可能性があります。まず yt-gui の**動作ログ**で受信 Cookie 件数を確認してください。

- `🍪 Cookie を受信: N 件` と出る → Cookie は届いています。N が十分なら、ログイン済みアカウントに視聴権限があるか確認してください。
- `🍪 Cookie なしで受信...` または件数が 0 → 認証 Cookie が取得できていません。次を確認:
  1. **同じ Chrome プロファイルでログインしているか**。拡張を読み込んだプロファイルと、サイトにログインしているプロファイルが異なると Cookie は取得できません（最頻出の原因）。
  2. 対象サイトに実際にログインしているか（セッション切れに注意）。
  3. 拡張の権限（`<all_urls>` / `cookies`）が有効か。
  4. シークレットウィンドウの Cookie は対象外です。

## 権限について

- `cookies` + `<all_urls>`: 任意の動画サイトの Cookie を読み取り、認証付き動画の取得に使うため。
- `http://127.0.0.1/*`: ローカルの yt-gui 受信サーバーへ送信するため（外部送信はありません）。

Cookie とトークンはローカルの yt-gui（127.0.0.1）へのみ送信され、外部サーバーには送りません。
