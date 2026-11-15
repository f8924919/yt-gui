# 区間ダウンロード: ネイティブ `download_ranges` 経路の再検討（通信量節約版は採用しない）

> Issue: [#84](https://github.com/f8924919/yt-gui/issues/84)
> ステータス: 完了（Issue の方向性のうち「現行の方式を正式採用として確定し、本 Issue をクローズする」を選んだ）
> ブランチ: `docs/84-section-native-ranges-decision`
> 基点: `63138b9`

区間ダウンロードは今の「フル取得 → ローカル ffmpeg で切り出し」（[#81](81-download-sections.md)）を正式な方式として確定し、yt-dlp のネイティブ `download_ranges` は使わない（ユーザー判断 2026-11-15）。設計の正本は [arch/downloader.md](../../arch/downloader.md#区間ダウンロード) の「区間ダウンロード」。コードは変えていない。1 PR で終わる docs だけのタスクなので archive に直接作った（docs-guide §4.2 の特例）。

証跡の段へ移った日と主張（policy §8.0）: 2026-11-15、arch の「ネイティブ区間 DL を使わない理由」のうち、yt-dlp のソースで確かめた 3 点（区間指定で `FFmpegFD` が選ばれること、`FFmpegFD` が ffmpeg の終了まで進捗フックを呼ばないこと、API から使うと ffmpeg の場所をスレッドごとに設定する必要があること）。下の「試しの run」の速度・成否は探索の段のまま（仮説・観察）で、arch には事実として書いていない。

## ソースで確かめたこと（yt-dlp 2026.10.26、`.venv/Lib/site-packages/yt_dlp/`）

- 区間指定があると、`FFmpegFD.can_download` が真なら無条件で `FFmpegFD` を選ぶ（`downloader/__init__.py:89-90`）。プロトコルは見ない。`FFmpegFD` 以外が選ばれたまま区間指定だと `This format cannot be partially downloaded` で中止する（`YoutubeDL.py:3478-3485`）。
- `FFmpegFD` は ffmpeg を起動して `proc.wait()` で終了を待つだけで（`downloader/external.py:560-564`）、進捗フックは終了後の `finished` の 1 回だけ（同 `:62-75`）。アプリの一時停止・中止は `_progress_hook` で `DownloadCancelled` を投げる仕組み（`yt_gui/downloader.py:257-259`）なので、区間の取得中は効かない。ffmpeg が止まった場合も中止できない。
- `FFmpegFD.available()` は downloader を渡さない `FFmpegPostProcessor()` で判定するので（`downloader/external.py:382-385`）、params の `ffmpeg_location` を見ず contextvar（`postprocessor/ffmpeg.py:87`、CLI だけが `__init__.py:975` で設定）だけを見る。API から使うと、ffmpeg が PATH に無ければ `ffmpeg is not installed` で中止する（下の試しの run で観察）。

## 試しの run（2026-11-15、Windows 11、探索の段）

対象は公開動画 `aqz-KE-bpKQ`（10:34）。Cookie・アカウント情報は使っていない。プローブは scratchpad に置いたまま（`probe_ytdlp.py` = `git hash-object` `d34e13ec0af791f5079742cf77318b87f18a307f`、`probe_api.py` = `1a2227ce90d8b1a944b5a262693bfaec57c7bb5a`）。どれも試しの run であり、回数の規則は掛けていない。

ffmpeg は 2 つを比べた。

- 旧: 開発環境の `bin/ffmpeg` に残っていた `N-124633-gc79dfd29e6-20260525`（2026-05-25 の master ビルド。#81 当時の同梱物と同じ系統と推測）
- ピン: `bin/pins.json` の `n9.0.2-48-gd4070a14ce`（zip の sha256 がピンと一致）。TLS は両方 schannel。`-h protocol=tls` の `-tls_verify` は旧が `default false`、ピンが `default true`

| run | ffmpeg | 区間 | 形式（itag） | 結果 |
|---|---|---|---|---|
| old1 | 旧 | 60-70 | 398+140 | `Destination:` の直後で止まった。150 秒で 0 バイト、プロセスツリーを kill。ログは 51 行で、1 本目の入力を開いた所で止まっている |
| pin1 | ピン | 60-70 | 398+140 | 成功。1.25MiB、226.70KiB/s。出力 10.008 秒 |
| pin2・pin3 | ピン | 300-330 | 398+140 | 成功。どちらも 5.00MiB、21 秒、235〜238KiB/s |
| pin_def | ピン | 120-140 | 401+251（既定の形式。webm に結合） | 成功。27.67MiB、2.10MiB/s。出力は 30.0 秒 |
| pin_aud | ピン | 120-140 | 251 → mp3 | 成功。489.47KiB。出力は 29.99 秒 |
| api | ピン | 400-460 | 398+140 | pythonw（`GetConsoleWindow()` = 0）のワーカースレッドから API で。contextvar を設定しないと `ffmpeg is not installed` で中止、設定すると成功。10.07MiB、43 秒、236.17KiB/s。進捗フックは 45.4 秒時点の `finished` 1 回だけ |

比較の観察:

- 通信量: 720p（398+140）は全体が 81,782,983 バイトで、10 秒の区間は約 1.3MB。4K の映像（401）は全体が 712,445,280 バイトで、20 秒の区間（映像＋音声）は約 29MB。
- 速度: 720p の全体取得（yt-dlp 既定のダウンローダ）は 6 秒。ffmpeg の区間取得は、720p で 60 秒の区間に 43 秒かかった。取得速度は形式のビットレートに沿っており（720p で約 230KiB/s、4K で約 2.1MiB/s）、区間の再生時間の半分〜7 割ほどの時間がかかった。区間が長いと全体取得より遅くなりうる（仮説）。
- 精度: 入力側シーク＋stream copy なので、どちらの方式もキーフレームに揃う。webm 音声（251）で 120-140 を指定すると、ネイティブでも、全体取得したファイルを今の `_build_cut_cmd` と同じ `-ss 120 -to 140 -i … -c copy` で切っても 30.0 秒になった。mp4（401）を同じく切ると 20.0 秒。
- ハング: 旧では再現し、ピンでは 6 本とも成功した。どの修正で直ったのかは特定していない。macOS（ビルド元が別）と Linux は試していない。

## 判断（2026-11-15、ユーザー）

ネイティブ経路を任意の設定として足す案（中止のための ffmpeg の自前停止・失敗時の今の方式への戻し・止まりの検出が要る。macOS / Linux は試せない）と比べ、今の方式を正式に採用して Issue を閉じることにした。取得中に一時停止・中止・進捗が効かないことはアプリ側の工夫では避けにくく、速度もビットレート並みに落ちるため。

## 進捗

- [x] C1 試しの run で現状を確かめ、方向性をユーザーに諮る — 証跡: 上の「試しの run」と「判断」
- [x] C2 arch・spec・feature-gap の「使わない理由」を今の事実に合わせる — 証跡: [arch/downloader.md](../../arch/downloader.md#区間ダウンロード)・[spec の区間ダウンロード](../../spec/features/download-behavior.md#区間ダウンロード)

## 訂正ログ

| 日付 | 誤って書いたこと | 正しくは | 原因と再発防止 |
|---|---|---|---|

## 次にやること

完了。

訂正ログ: 0 件
