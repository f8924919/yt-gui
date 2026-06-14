// yt-gui Connector — 形式選択の共有ロジック
//
// popup.js（ツールバーのポップアップ）と background.js（右クリック即送信）の
// 両方から使う。chrome.storage に保持する選択状態（choice）と、受信サーバーへ
// 送る形式指定オブジェクト（payload）の変換を 1 箇所に集約する。
//
// 仕様: ../docs/spec/features/browser-extension.md#形式指定オブジェクトformat

const FORMAT_CHOICE_KEY = "formatChoice";

const RESOLUTIONS = ["480", "720", "1080", "1440", "2160"];
const AUDIO_FORMATS = ["mp3", "flac"];
const MP3_BITRATES = ["128", "192", "256", "320"];

// 初回既定は「アプリの既定を使う」。サブ選択の初期値もここで持つ。
const DEFAULT_CHOICE = {
  kind: "app_default",
  resolution: "720",
  audio_format: "mp3",
  mp3_bitrate: "192",
};

// chrome.storage から選択状態を読む（未保存なら既定）。
async function loadFormatChoice() {
  const data = await chrome.storage.local.get(FORMAT_CHOICE_KEY);
  return { ...DEFAULT_CHOICE, ...(data[FORMAT_CHOICE_KEY] || {}) };
}

// 選択状態を保存する。
async function saveFormatChoice(choice) {
  await chrome.storage.local.set({ [FORMAT_CHOICE_KEY]: choice });
}

// 選択状態 → POST /enqueue の format（yt-dlp 文字列は組み立てず意味のみ）。
// app_default / 未知は null を返し、呼び出し側は format を省略する。
// container は送らない（アプリ設定に従う）。
function buildFormatPayload(choice) {
  if (!choice || !choice.kind || choice.kind === "app_default") return null;
  if (choice.kind === "best") return { kind: "best" };
  if (choice.kind === "resolution") {
    return { kind: "resolution", resolution: choice.resolution };
  }
  if (choice.kind === "audio") {
    const payload = { kind: "audio", audio_format: choice.audio_format };
    if (choice.audio_format === "mp3") payload.mp3_bitrate = choice.mp3_bitrate;
    return payload;
  }
  return null;
}

// service worker（importScripts）と popup（module 風 script）の双方から参照できるよう
// グローバルへぶら下げる。
self.ytGuiFormat = {
  FORMAT_CHOICE_KEY,
  RESOLUTIONS,
  AUDIO_FORMATS,
  MP3_BITRATES,
  DEFAULT_CHOICE,
  loadFormatChoice,
  saveFormatChoice,
  buildFormatPayload,
};
