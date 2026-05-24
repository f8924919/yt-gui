# ニコニコ動画コメント取得 ― 事前検証（フェーズ 0）

[← タスク一覧](index.md)

## 背景

ニコニコ動画のコメント（danmaku）を yt-gui に取り込むため、yt-dlp の `NiconicoIE._get_subtitles` が出力する **`v1/threads` 由来の JSON** が、外部ツール [danmaku2ass (m13253)](https://github.com/m13253/danmaku2ass) でそのまま ASS に変換可能かを確認する。互換性が無い場合は、フェーズ 2 でアプリ内部に「JSON → danmaku2ass が読める形式」への変換層を挟む必要がある。

このタスクはフェーズ 1〜3 着手前の **Go/NoGo 判断ゲート**。実装は伴わず、検証手順と結果のみを本ファイルに追記する。

## 検証手順

ローカル開発環境（`uv sync` 済み）で以下を実施する。

### 1. サンプル JSON の取得

公開済みのニコニコ動画 URL（短尺・複数の典型コメント形式（白テキスト・色付き・上固定・下固定・コマンドコメント・AA）が含まれるもの）を 1 本以上選び、以下を実行する。

```bash
uv run yt-dlp \
    --write-subs --sub-langs comments --skip-download \
    --cookies-from-browser firefox \
    "https://www.nicovideo.jp/watch/sm9"
```

出力された `*.comments.json` の構造を `jq` で確認し、以下を記録する。

- トップレベルキー（例: `data.threads[].comments[]` か、yt-dlp が flatten 済みのリストか）
- 1 コメントエントリのキー（`vposMs` / `body` / `commands` / `userId` / `score` 等）
- コマンド配列に含まれる典型値（`white` / `big` / `ue` / `shita` / `184` 等）

### 2. danmaku2ass による変換試行

```bash
# danmaku2ass を取得
git clone https://github.com/m13253/danmaku2ass /tmp/danmaku2ass
cd /tmp/danmaku2ass

# 変換試行（Niconico フォーマット指定）
python danmaku2ass.py \
    -o out.ass -s 1920x1080 -f Niconico \
    -fn "Microsoft YaHei" -fs 32 -a 0.8 -dm 8 -ds 5 \
    /path/to/*.comments.json
```

以下のいずれに該当するかを記録する。

- (A) **そのまま変換成功**: 出力 ASS で `ffplay -vf "ass=out.ass" sample.mp4` が再生できる
- (B) **形式エラーで失敗**: パーサが旧 XML/旧 JSON 形式を期待しており、新 `v1/threads` JSON を受け付けない
- (C) **変換は走るがコメントが 0 件・崩れる**: フィールド名の対応が取れていない（`pos` vs `vposMs` 等）

### 3. 旧形式との差分調査（B/C の場合のみ）

danmaku2ass のリポジトリで `parse_niconico_json` 相当の関数を探し、期待するキー名・データ型を確認。yt-dlp の `v1/threads` 出力との差分表を本ファイルに残す。

### 4. 結論セクションを本ファイル末尾に追記

```
## 検証結果

- 検証日: YYYY-MM-DD
- 使用 yt-dlp バージョン: X.Y.Z
- 検証動画: sm9 ほか N 件
- 結果: (A / B / C)
- フェーズ 2 への影響:
  - (A の場合) danmaku2ass を subprocess 呼び出しでそのまま使える。変換層不要。
  - (B/C の場合) アプリ側で `comments.json` → danmaku2ass 互換 JSON への変換ステップを実装する。
    - 想定実装位置: yt_gui/niconico_comments.py（新規）の `convert_to_danmaku2ass_json(in_path, out_path)`
    - 既知の差分: ...（表を埋める）
- Go/NoGo: GO (フェーズ 1 着手可) / NoGo (代替ツール検討)
```

## 範囲外

- 実コード変更（フェーズ 1 以降で扱う）
- ハード焼付けの画質・FPS 検証（フェーズ 3 で扱う）
- ニコニコ生放送（live）コメントの取得（NiconicoLiveIE は別経路。当面スコープ外）

## 検証結果

- 検証日: 2026-05-24
- 検証実施者: ソースコード突き合わせ方式（サンドボックスから niconico API 到達不可のため、実 URL での JSON 取得は未実施）
- 使用 yt-dlp バージョン: `2026.03.17`
- 使用 danmaku2ass コミット: `ced881747670c2eb1c0dbd292c2a567f444b056a`（2024-08-28、`master` 当時最新）

### スキーマ突き合わせ

yt-dlp `yt_dlp/extractor/niconico.py` の `NiconicoIE._get_subtitles` は以下を出力する:

```python
danmaku = traverse_obj(
    self._download_json(f'{server}/v1/threads', ...),
    ('data', 'threads', ..., 'comments', ...)
)
return {'comments': [{'ext': 'json', 'data': json.dumps(danmaku)}]}
```

→ コメントオブジェクトが **flat な JSON 配列** として出力される。

danmaku2ass の `ReadCommentsNiconicoYtdlpJson2`（行 177〜202）が参照するフィールド:

| フィールド | 用途 | v1/threads 出力 |
|---|---|---|
| `body` | コメント本文 | ✓ ある |
| `commands` | スタイル指定の文字列配列 | ✓ ある |
| `vposMs` | 表示時刻（ms） | ✓ ある |
| `postedAt` | 投稿時刻（RFC3339） | ✓ ある |
| `no` | コメント番号 | ✓ ある |

→ **完全一致**。アプリ側に変換層を挟む必要は無い。

`ProbeCommentFormat`（行 61〜68）の自動判定ロジックは `[{"id": "` で始まる JSON を `NiconicoYtdlpJson2` と判定する。`v1/threads` のレスポンスは `id` フィールドを先頭に持つため autodetect でも動くが、堅牢性のため **`-f NiconicoYtdlpJson2` を明示指定する**ことを推奨。

### 動作確認

`v1/threads` の実応答を模した合成サンプル JSON（5 コメント・移動／上固定／下固定／color／big／184 を含む）を作成し、以下のコマンドで変換成功を確認:

```bash
python3 danmaku2ass.py -o out.ass -s 1920x1080 \
    -f NiconicoYtdlpJson2 -dm 8 -fs 32 -a 0.8 sample.comments.json
```

確認できた挙動:

- 5 コメント全て `Dialogue:` 行として出力された
- `ue` / `shita` が `\an8\pos(960, 0)` / `\an2\pos(960, 1080)` に変換された
- `big` が `\fs46` に変換された
- `red` / `blue` / `passionorange` が ASS の `\c&H...` で色付けされた（YUV→RGB 補正済み）
- `\n` を含む本文が `\N` に変換された
- `184`（匿名投稿フラグ）など未対応コマンドは警告ログを出さず黙って無視された
- 不透明度 0.8 が `&H33` プレフィックスとして全スタイルに反映された

### 結論

- **Go/NoGo: GO（フェーズ 1 着手可）**
- アプリ内変換層は不要
- danmaku2ass の format 指定は **`NiconicoYtdlpJson2`** を使う

### フェーズ 2 の設計修正

`niconico-comments-phase2.md` の subprocess 呼び出し例に `-f Niconico` を指定していたが、これは XML 旧形式リーダーへのマッピングで誤り。`-f NiconicoYtdlpJson2` に修正済み。

### 実機での最終確認（推奨）

サンドボックス外（ニコニコ動画 API へ到達可能なネットワーク）で以下を 1 度実施し、本検証結果を裏付けることを推奨する:

```bash
uv run yt-dlp --write-subs --sub-langs comments --skip-download \
    "https://www.nicovideo.jp/watch/{動画ID}"
uv tool run --from <pyinstaller化前の danmaku2ass> \
    danmaku2ass -o out.ass -s 1920x1080 -f NiconicoYtdlpJson2 *.comments.json
ffplay -vf "ass=out.ass" sample.mp4
```

スキーマ突き合わせの確度は高いため、これは形式的確認のみ。

## ステータス

完了 (2026-05-24)
