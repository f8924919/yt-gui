// オプション画面: トークン・ポートを chrome.storage.local に保存する。
// 表示文言は chrome.i18n（_locales/）でブラウザの UI 言語に追従する。

const DEFAULT_PORT = 8718;

// data-i18n / data-i18n-placeholder を持つ要素を _locales のメッセージで差し替える。
function localize() {
  document.documentElement.lang = chrome.i18n.getUILanguage();
  for (const el of document.querySelectorAll("[data-i18n]")) {
    const msg = chrome.i18n.getMessage(el.dataset.i18n);
    if (msg) el.textContent = msg;
  }
  for (const el of document.querySelectorAll("[data-i18n-placeholder]")) {
    const msg = chrome.i18n.getMessage(el.dataset.i18nPlaceholder);
    if (msg) el.placeholder = msg;
  }
}

async function restore() {
  const { token = "", port = DEFAULT_PORT } = await chrome.storage.local.get([
    "token",
    "port",
  ]);
  document.getElementById("token").value = token;
  document.getElementById("port").value = port;
}

async function save() {
  const token = document.getElementById("token").value.trim();
  const port = Number(document.getElementById("port").value) || DEFAULT_PORT;
  await chrome.storage.local.set({ token, port });
  const status = document.getElementById("status");
  status.textContent = chrome.i18n.getMessage("savedStatus");
  setTimeout(() => (status.textContent = ""), 2000);
}

document.addEventListener("DOMContentLoaded", () => {
  localize();
  restore();
});
document.getElementById("save").addEventListener("click", save);
