import asyncio
import base64
import json
import os
import sys
from pathlib import Path
from urllib.parse import quote, urlparse

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


async def run():
    async with httpx.AsyncClient(timeout=30) as http:
        async with streamable_http_client("http://127.0.0.1:8765/mcp", http_client=http) as (read, write, _):
            async with ClientSession(read, write) as client:
                await client.initialize()

                async def call(name, args=None):
                    result = await client.call_tool(name, args or {})
                    data = result.structuredContent
                    if data is None and result.content and result.content[0].type == "text":
                        try:
                            data = json.loads(result.content[0].text)
                        except json.JSONDecodeError:
                            data = {"ok": False, "raw": result.content[0].text}
                    return data if data is not None else result.content

                async def read_page():
                    data = await call("social_extension_read")
                    if not data.get("ok"):
                        raise RuntimeError(data.get("error"))
                    return data

                keyword = sys.argv[1] if len(sys.argv) > 1 else "美食视频"
                await call("social_extension_open", {"url": f"https://www.xiaohongshu.com/search_result?keyword={quote(keyword)}"})
                await asyncio.sleep(3)
                candidates = []
                for _ in range(15):
                    search = await read_page()
                    candidates = [link for link in search["links"]
                                  if link["text"] and urlparse(link["url"]).path.startswith(("/search_result/", "/explore/"))]
                    if candidates:
                        break
                    await asyncio.sleep(1)
                print("SEARCH", search["title"], "LINKS", len(search["links"]), flush=True)
                opened = False
                for link in candidates[:3]:
                    await call("social_extension_click", {"url": link["url"]})
                    await asyncio.sleep(3)
                    note = await read_page()
                    if "当前笔记暂时无法浏览" in note["text"] or "请打开小红书App扫码查看" in note["text"]:
                        print("SKIP_SCAN", link["text"], flush=True)
                        await call("social_extension_interact", {"action": "back"})
                        await asyncio.sleep(2)
                        continue
                    opened = True
                    print("OPEN_OK", note["title"], link["text"], "TEXT", len(note["text"]),
                          "IMAGES", len(note["images"]), "VIDEOS", len(note["videos"]), flush=True)
                    html = await call("social_extension_read", {"include_html": True})
                    assert html["html"] and "html_truncated" in html
                    comments = await call("social_extension_comments")
                    print("COMMENTS", comments["returned"], flush=True)
                    if note["videos"]:
                        for action in ("video_play", "video_seek", "video_pause"):
                            result = await call("social_extension_interact", {"action": action, "seconds": 1})
                            print(action, result, flush=True)
                    for action in ("image_next", "image_previous"):
                        result = await call("social_extension_interact", {"action": action})
                        print(action, result, flush=True)
                    screenshot = await call("social_extension_screenshot")
                    if isinstance(screenshot, dict):
                        print("SCREENSHOT_RESULT", screenshot, flush=True)
                        screenshot = []
                    for item in screenshot:
                        if getattr(item, "type", None) == "image":
                            path = Path(os.environ["LOCALAPPDATA"]) / "SocialInfo" / "logs" / "edge-note.png"
                            path.write_bytes(base64.b64decode(item.data))
                            print("SCREENSHOT", path, flush=True)
                        elif getattr(item, "type", None) == "text":
                            print("SCREENSHOT_RESULT", item.text, flush=True)
                    await call("social_extension_interact", {"action": "back"})
                    await asyncio.sleep(2)
                    returned = await read_page()
                    print("BACK", returned["url"], flush=True)
                    break
                if not opened:
                    print("NO_ACCESSIBLE_NOTE_IN_SAMPLE", flush=True)


if __name__ == "__main__":
    asyncio.run(run())
