# yt_gui/original_format_dialog.py

> 関連仕様: [オリジナル形式ダイアログ](../spec/screens/original-format-dialog.md)
> 内包パネル: [original_format_panel.md](original_format_panel.md)

## クラス: `OriginalFormatDialog(QDialog)`

「オリジナルの形式」の詳細設定を行うモーダルダイアログ。[`OriginalFormatPanel`](original_format_panel.md) を**コンポジションで内包**し、ダイアログ自身は起動・ボタン・シグナル中継のみを担う薄いシェルとする。ロジック資産（フォーマット文字列生成・排他制御・スナップショット）はパネル側に残し、テスト単位もパネルを維持する。

## ライフサイクル

開くたびに `App` が新規生成し、閉じたら破棄する（使い捨て）。`App` は生存インスタンスを保持しない。生成時点の言語・コンテナ設定で `panel.retranslate(video_container, audio_label)` を 1 回呼ぶため、表示中の言語変更を生存インスタンスへ配送する仕組み（旧 `size_hint_changed` / `on_size_hint_changed` のような再配線）は持たない。

## コンストラクタ引数

パネルの DI をそのまま受け渡し、加えてモードと初期設定を受ける。

| 引数 | 型 | 用途 |
|---|---|---|
| `downloader` | `Downloader` | パネルへ委譲 |
| `get_url` | `Callable[[], str]` | パネルの形式取得・上部 URL 表示 |
| `get_cookies` | `Callable[[], tuple[str \| None, str \| None]]` | パネルへ委譲 |
| `update_status` | `Callable[[str, float], None]` | パネルへ委譲 |
| `video_container` | `str` | 生成時 `retranslate` 用 |
| `audio_label` | `str \| None` | 生成時 `retranslate` 用 |
| `mode` | `"add" \| "edit"` | 主ボタンのラベルと emit するシグナルを切り替える |
| `restore_settings` | `dict \| None` | 編集モード時に `panel.restore_from_settings()` へ渡す |

## シグナル（内部クラス `_DialogSignals(QObject)` ないし `QDialog` 直接定義）

| シグナル | 引数 | タイミング |
|---|---|---|
| `add_requested` | — | 追加モードで検証通過し主ボタンが押されたとき |
| `edit_applied` | — | 編集モードで検証通過し主ボタンが押されたとき |
| `edit_cancelled` | — | 編集モードでキャンセル / クローズされたとき |

引数は持たせず、`App` 側のハンドラが内包パネルの公開 API（`get_snapshot` 等）を直接読み取って `JobSpec` を組み立てる。`App` はダイアログ参照をハンドラ内で受け取れるよう、`open_*` ヘルパでローカル変数として保持する。

## 公開メソッド

| メソッド | 説明 |
|---|---|
| `panel` (プロパティ) | 内包する `OriginalFormatPanel`。`App` が `get_snapshot` / `has_formats_loaded` / `get_audio_only` / `is_audio_skipped` / `is_both_skipped` / `get_fetched_title` などを読むための入口 |
| `open_for_add()` | 追加モードで `exec()`（必要に応じて `show()` ベースの非ブロッキングも可。検証は accept 前に行う） |

## レイアウト追従

内包パネルの `size_hint_changed` シグナル（コメント・弾幕グループの出現等で発火）を受けて `adjustSize()` を呼び、ダイアログをパネルの新しい sizeHint に再フィットさせる。旧インライン埋め込み時の `App._resync_splitter_to_top_hint` による `QSplitter` 高さ再計算・ウィンドウ `resize` は不要になった。

## 起動時の処理

- 追加モード: 何もせず表示（ユーザーが「形式を取得」を押す）。
- 編集モード: `panel.restore_from_settings(restore_settings)` → `panel.trigger_fetch()` を順に実行。トラック選択は取得完了後にパネル内部の `_apply_pending_restore()` で復元される。

## 主ボタン押下時の流れ

1. パネルの状態で検証（`get_audio_only` / `is_audio_skipped` / `is_both_skipped`）。NG ならダイアログ内で警告し、開いたまま戻る。
2. OK なら `mode` に応じて `add_requested` / `edit_applied` を emit。
3. `accept()` で閉じる。

検証ロジックは `App` 側からダイアログへ移設する（旧 `_add_url` / `_apply_edit` の該当ブロック）。

## `App` 側の配線

| 旧 | 新 |
|---|---|
| 上段に `OriginalFormatPanel` を埋め込み（`layout.addWidget`） | 埋め込み撤去。代わりに「詳細設定...」ボタンを配置 |
| `_on_format_changed` で `setVisible` + `resize` | パネル可視制御を「詳細設定...」ボタンの表示切替に変更。`resize` 分岐は撤去 |
| `on_size_hint_changed(self._resync_splitter_to_top_hint)` | 撤去 |
| `_add_url` のオリジナル分岐 | `add_requested` ハンドラへ移動（enqueue / 取得済み・未取得分岐は `App` に残す） |
| `_apply_edit` のオリジナル分岐 | `edit_applied` ハンドラへ移動 |
| `_on_edit_mode_entered` のパネル復元 + `trigger_fetch` | 編集モードのダイアログ生成（`restore_settings` 渡し）に移動 |

## 拡張起点の起動（`kind: "original"`）

ブラウザ拡張から `kind: "original"` を受けたときも、本ダイアログを**追加モード**で起動する（仕様: [browser-extension.md — オリジナル形式（アプリ側ダイアログ起動）](../spec/features/browser-extension.md#オリジナル形式アプリ側ダイアログ起動)）。GUI からの「詳細設定...」起動との違いは DI の差し替えのみで、ダイアログ実装自体は変更しない。

- `get_url`: メイン画面 URL 欄の参照ではなく、拡張由来 URL を返す `lambda: url` を注入する。
- `get_cookies`: 拡張の一時 cookies（アイテム単位）を返す callable を注入し、トラックプローブ・確定後ダウンロード双方へ適用する。
- 起動・直列化（複数 URL 連続送信時の多重モーダル防止）・ウィンドウ前面化は `App` 側（[`_dispatch_next_original_dialog`](app.md#オリジナル形式ダイアログ起動kind-original)）が担う。
- `add_requested` で従来どおりキューへ追加。キャンセル（`reject`）時はキューに追加しない。

## テスト方針

モーダル `QDialog.exec` はヘッドレス検証しにくいため、検証ロジックはダイアログの純粋ヘルパ（または引き続きパネル側の公開 API）に寄せ、`exec` を回さずに「ボタン押下相当 → シグナル emit / 警告判定」を検証できる構造にする。既存のパネル単体テストは再ペアレント後も流用する。
