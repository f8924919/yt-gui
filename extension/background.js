// yt-gui Connector — service worker
//
// 動作:
//   1. ツールバーボタンはポップアップ（popup.html）で形式を選んで送信
//   2. 右クリックメニューは記憶済み形式でワンクリック送信
//   3. chrome.cookies で当該ドメインの Cookie を取得し Netscape 形式へ整形
//   4. ローカル受信サーバー (127.0.0.1) の /enqueue へ POST（トークン認証）
//
// 仕様: ../docs/spec/features/browser-extension.md

importScripts("format_choice.js");

const DEFAULT_PORT = 8718;
const MENU_ID = "yt-gui-send";

chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: MENU_ID,
    title: chrome.i18n.getMessage("menuTitle"),
    contexts: ["page", "link", "video"],
  });
});

// ツールバーボタンは default_popup を持つため onClicked は発火しない。
// 送信トリガはポップアップ（popup.js）からのメッセージで受ける。
chrome.runtime.onMessage.addListener((msg) => {
  if (msg && msg.type === "send" && msg.url) {
    sendToYtGui(msg.url, msg.format || null);
  }
});

// 右クリックメニューは記憶済みの形式で即送信する。
chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  if (info.menuItemId !== MENU_ID) return;
  const url = info.linkUrl || (tab && tab.url);
  if (!url) return;
  const choice = await self.ytGuiFormat.loadFormatChoice();
  sendToYtGui(url, self.ytGuiFormat.buildFormatPayload(choice));
});

// chrome.storage から設定（トークン・ポート）を読む。
async function getConfig() {
  const { token = "", port = DEFAULT_PORT } = await chrome.storage.local.get([
    "token",
    "port",
  ]);
  return { token, port: Number(port) || DEFAULT_PORT };
}

// chrome.cookies の Cookie 配列を Netscape cookies.txt 文字列へ整形する。
function toNetscape(cookies) {
  const lines = ["# Netscape HTTP Cookie File"];
  for (const c of cookies) {
    const includeSub = c.hostOnly ? "FALSE" : "TRUE";
    let domain = c.domain || "";
    if (!c.hostOnly && domain && !domain.startsWith(".")) domain = "." + domain;
    const secure = c.secure ? "TRUE" : "FALSE";
    const expiry = c.session ? 0 : Math.floor(c.expirationDate || 0);
    lines.push(
      [domain, includeSub, c.path || "/", secure, expiry, c.name, c.value].join(
        "\t",
      ),
    );
  }
  return lines.join("\n") + "\n";
}

async function sendToYtGui(url, format = null) {
  const { token, port } = await getConfig();
  if (!token) {
    flashBadge("KEY", "#c62828"); // トークン未設定
    return;
  }

  let cookieStr = null;
  try {
    const cookies = await chrome.cookies.getAll({ url });
    if (cookies && cookies.length) cookieStr = toNetscape(cookies);
  } catch (e) {
    // Cookie 取得失敗は致命ではない（Cookie なしで送る）。
    console.warn("cookie 取得失敗", e);
  }

  // format は app_default / 未指定なら省略（アプリ既定形式を使う）。
  const payload = { url, cookies: cookieStr };
  if (format) payload.format = format;
  const body = JSON.stringify(payload);
  // 設定ポート → +1 → +2 の順に試す（アプリ側のフォールバックに追従）。
  // 接続失敗のときだけ次のポートへ。HTTP 応答（403 等）が返ったら止める。
  for (const p of [port, port + 1, port + 2]) {
    try {
      const resp = await fetch(`http://127.0.0.1:${p}/enqueue`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-YtGui-Token": token,
        },
        body,
      });
      if (resp.ok) {
        flashBadge("OK", "#2e7d32");
      } else if (resp.status === 403) {
        flashBadge("403", "#c62828");
      } else {
        flashBadge("ERR", "#c62828");
      }
      return; // HTTP 応答が返ったら終了
    } catch (e) {
      // 接続失敗 → 次のポートを試す
      continue;
    }
  }
  flashBadge("OFF", "#c62828"); // 接続不可（アプリ未起動 / 連携無効）
}

// ツールバーアイコンにバッジで結果を表示し、数秒後に消す。
function flashBadge(text, color) {
  chrome.action.setBadgeBackgroundColor({ color });
  chrome.action.setBadgeText({ text });
  setTimeout(() => chrome.action.setBadgeText({ text: "" }), 4000);
}
