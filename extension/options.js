// オプション画面: トークン・ポートを chrome.storage.local に保存する。

const DEFAULT_PORT = 8718;

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
  status.textContent = "保存しました。";
  setTimeout(() => (status.textContent = ""), 2000);
}

document.addEventListener("DOMContentLoaded", restore);
document.getElementById("save").addEventListener("click", save);
