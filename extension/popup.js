const tokenInput = document.querySelector("#token");
const status = document.querySelector("#status");

chrome.storage.local.get("token", ({token}) => {
  if (token) tokenInput.value = token;
});
chrome.runtime.sendMessage({type: "status"}, (connected) => {
  chrome.storage.local.get("lastError", ({lastError}) => {
    status.textContent = connected ? "已连接本机服务" : (lastError || "尚未连接");
  });
});
document.querySelector("#connect").addEventListener("click", () => {
  chrome.runtime.sendMessage({type: "connect", token: tokenInput.value.trim()}, (connected) => {
    if (connected) {
      status.textContent = "连接成功";
    } else {
      chrome.storage.local.get("lastError", ({lastError}) => {
        status.textContent = lastError || "连接失败，请确认本机服务正在运行且令牌正确";
      });
    }
  });
});
