let socket = null;

function isXhs(url) {
  const host = new URL(url).hostname;
  return host === "xiaohongshu.com" || host.endsWith(".xiaohongshu.com");
}

async function targetTab() {
  const [active] = await chrome.tabs.query({active: true, currentWindow: true});
  if (active?.url && isXhs(active.url)) return active;
  const tabs = await chrome.tabs.query({url: "https://*.xiaohongshu.com/*"});
  if (!tabs.length) throw new Error("请先在小红书标签页中打开目标页面");
  return tabs[0];
}

async function execute(tab, func, args=[]) {
  const [result] = await chrome.scripting.executeScript({target: {tabId: tab.id}, func, args});
  if (result?.error) throw new Error(result.error.description || String(result.error));
  if (!result || result.result === null || result.result === undefined) {
    throw new Error("页面操作失败或未返回结果");
  }
  return result.result;
}

async function handle(command, args) {
  if (command === "open") {
    if (!isXhs(args.url)) throw new Error("只允许打开小红书页面");
    const tabs = await chrome.tabs.query({url: "https://*.xiaohongshu.com/*"});
    if (tabs.length) await chrome.tabs.update(tabs[0].id, {url: args.url, active: true});
    else await chrome.tabs.create({url: args.url, active: true});
    return {url: args.url};
  }
  const tab = await targetTab();
  if (command === "scroll") {
    return execute(tab, (delta) => {
      window.scrollBy({top: delta, behavior: "instant"});
      return {scroll_y: window.scrollY};
    }, [args.delta]);
  }
  if (command === "back") {
    return execute(tab, () => {
      history.back();
      return {back: true};
    }, []);
  }
  if (command === "video") {
    return execute(tab, async (action, seconds) => {
      const video = document.querySelector("video");
      if (!video) throw new Error("当前页面没有视频");
      if (action === "video_play") await video.play();
      if (action === "video_pause") video.pause();
      if (action === "video_seek") video.currentTime = Math.min(seconds, video.duration || seconds);
      return {paused: video.paused, current_time: video.currentTime, duration: video.duration || null};
    }, [args.action, args.seconds || 0]);
  }
  if (command === "image") {
    return execute(tab, (action) => {
      const selector = action === "image_next" ? ".arrow-controller.right,[aria-label*='下一张']" : ".arrow-controller.left,[aria-label*='上一张']";
      const button = document.querySelector(selector);
      if (!button) throw new Error("当前页面没有对应的图片切换按钮");
      button.click();
      return {action};
    }, [args.action]);
  }
  if (command === "comments") {
    return execute(tab, () => [...document.querySelectorAll(".comment-item")].map((el, index) => ({
      id: el.getAttribute("data-comment-id"), position: index,
      author: (el.querySelector(".author .name,.name")?.innerText || "").trim(),
      text: (el.querySelector(".note-text,.content")?.innerText || el.innerText || "").trim(),
      likes: (el.querySelector(".like .count")?.innerText || "").trim() || null
    })), []);
  }
  if (command === "screenshot") {
    const target = {tabId: tab.id};
    await chrome.debugger.attach(target, "1.3");
    try {
      const result = await chrome.debugger.sendCommand(target, "Page.captureScreenshot", {format: "png"});
      return {base64: result.data};
    } finally {
      await chrome.debugger.detach(target);
    }
  }
  if (command === "click") {
    return execute(tab, (url) => {
      const path = new URL(url).pathname;
      const link = [...document.querySelectorAll("a[href]")].find(a => a.pathname === path);
      if (!link) throw new Error("当前页面没有对应笔记链接");
      link.scrollIntoView({block: "center"});
      link.click();
      return {clicked: true, path};
    }, [args.url]);
  }
  if (command === "read") {
    return execute(tab, (includeHtml) => ({
      url: location.href, title: document.title,
      text: document.body?.innerText || "",
      html: includeHtml ? document.documentElement.outerHTML : null,
      images: [...document.images].map((img, index) => ({index,
        src: img.currentSrc || img.src, width: img.naturalWidth, height: img.naturalHeight, alt: img.alt})),
      videos: [...document.querySelectorAll("video")].map((video, index) => ({index,
        src: video.currentSrc || video.src || null, poster: video.poster || null,
        duration: video.duration || null, current_time: video.currentTime, paused: video.paused})),
      links: [...document.querySelectorAll("a[href]")].slice(0,100).map((a, index) => ({index,
        url: a.href, text: (a.innerText || "").trim().slice(0,200)}))
    }), [args.includeHtml === true]);
  }
  throw new Error("不支持的扩展命令");
}

function connect(token) {
  if (socket) {
    socket.onclose = null;
    socket.close();
  }
  socket = new WebSocket(`ws://127.0.0.1:8766/?token=${encodeURIComponent(token)}`);
  socket.onopen = () => chrome.storage.local.set({token, lastError: ""});
  socket.onerror = () => chrome.storage.local.set({lastError: "无法连接本机服务"});
  socket.onclose = (event) => {
    chrome.storage.local.set({lastError: `连接已断开：${event.reason || event.code}`});
    setTimeout(() => chrome.storage.local.get("token", ({token: saved}) => {
      if (saved) connect(saved);
    }), 2000);
  };
  socket.onmessage = async (event) => {
    const request = JSON.parse(event.data);
    try {
      const data = await handle(request.command, request.args);
      socket.send(JSON.stringify({id: request.id, ok: true, data}));
    } catch (error) {
      socket.send(JSON.stringify({id: request.id, ok: false, error: String(error)}));
    }
  };
}

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.type === "status") {
    sendResponse(socket?.readyState === WebSocket.OPEN);
    return;
  }
  if (request.type === "connect") {
    connect(request.token);
    const timer = setInterval(() => {
      if (socket?.readyState === WebSocket.OPEN) {
        clearInterval(timer);
        sendResponse(true);
      }
    }, 100);
    setTimeout(() => { clearInterval(timer); sendResponse(false); }, 3000);
    return true;
  }
});

chrome.storage.local.get("token", ({token}) => {
  if (token) connect(token);
});

chrome.alarms.create("social-info-keepalive", {periodInMinutes: 0.25});
chrome.alarms.onAlarm.addListener(() => {
  if (socket?.readyState !== WebSocket.OPEN) {
    chrome.storage.local.get("token", ({token}) => { if (token) connect(token); });
  }
});
