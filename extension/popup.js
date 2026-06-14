// ツールバーのポップアップ: 形式を選んで送信する。
// 選択は chrome.storage に記憶し、次回以降の既定（および右クリック即送信）に使う。
// 表示文言は chrome.i18n（_locales/）でブラウザの UI 言語に追従する。
//
// 仕様: ../docs/spec/features/browser-extension.md#ポップアップ形式選択

const F = self.ytGuiFormat;

function localize() {
  document.documentElement.lang = chrome.i18n.getUILanguage();
  for (const el of document.querySelectorAll("[data-i18n]")) {
    const msg = chrome.i18n.getMessage(el.dataset.i18n);
    if (msg) el.textContent = msg;
  }
}

// select に option 群を流し込み、value を選択する。
function fillSelect(id, values, selected) {
  const el = document.getElementById(id);
  el.innerHTML = "";
  for (const v of values) {
    const opt = document.createElement("option");
    opt.value = v;
    opt.textContent = v;
    el.appendChild(opt);
  }
  el.value = selected;
}

// 選択中の kind に応じてサブ選択行の表示/非表示を切り替える。
function updateRows() {
  const kind = document.getElementById("kind").value;
  const audioFormat = document.getElementById("audio_format").value;
  document
    .getElementById("row-resolution")
    .classList.toggle("hidden", kind !== "resolution");
  document
    .getElementById("row-audio-format")
    .classList.toggle("hidden", kind !== "audio");
  document
    .getElementById("row-bitrate")
    .classList.toggle("hidden", kind !== "audio" || audioFormat !== "mp3");
}

// 現在の UI 状態を choice オブジェクトとして読む。
function readChoice() {
  return {
    kind: document.getElementById("kind").value,
    resolution: document.getElementById("resolution").value,
    audio_format: document.getElementById("audio_format").value,
    mp3_bitrate: document.getElementById("mp3_bitrate").value,
  };
}

async function init() {
  localize();
  const choice = await F.loadFormatChoice();
  document.getElementById("kind").value = choice.kind;
  fillSelect("resolution", F.RESOLUTIONS, choice.resolution);
  fillSelect("audio_format", F.AUDIO_FORMATS, choice.audio_format);
  fillSelect("mp3_bitrate", F.MP3_BITRATES, choice.mp3_bitrate);
  updateRows();

  for (const id of ["kind", "resolution", "audio_format", "mp3_bitrate"]) {
    document.getElementById(id).addEventListener("change", async () => {
      updateRows();
      await F.saveFormatChoice(readChoice());
    });
  }
}

async function send() {
  const choice = readChoice();
  await F.saveFormatChoice(choice);
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  const url = tab && tab.url;
  if (url) {
    chrome.runtime.sendMessage({
      type: "send",
      url,
      format: F.buildFormatPayload(choice),
    });
  }
  window.close();
}

document.addEventListener("DOMContentLoaded", init);
document.getElementById("send").addEventListener("click", send);
