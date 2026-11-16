import asyncio
import base64
import json
import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def run():
    params = StdioServerParameters(command=sys.executable, args=["-m", "social_info", "serve"])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as client:
            await client.initialize()

            async def call(name, args=None):
                result = await client.call_tool(name, args or {})
                data = result.structuredContent
                if data is None and result.content and getattr(result.content[0], "type", None) == "text":
                    data = json.loads(result.content[0].text)
                if isinstance(data, dict):
                    if not data.get("ok", True):
                        raise RuntimeError(data["error"])
                    return data
                return result.content

            async def save_screenshot(name):
                shot = await call("social_screenshot")
                for item in shot:
                    if getattr(item, "type", None) == "image":
                        path = Path(os.environ["LOCALAPPDATA"]) / "SocialInfo" / "logs" / name
                        path.write_bytes(base64.b64decode(item.data))
                        print("SCREENSHOT", path, flush=True)
                        break

            async def wait_for_user():
                await call("social_login_start")
                print("请在浏览器中完成登录或安全验证，程序会自动继续。", flush=True)
                for _ in range(120):
                    status = await call("social_session_status")
                    if status["auth"] == "logged_in":
                        break
                    await asyncio.sleep(5)
                else:
                    raise TimeoutError("等待登录或验证超时")
                if "--headed" not in sys.argv:
                    await call("social_login_finish")
                print("LOGIN_OK", flush=True)

            async def wait_for_app_scan():
                await call("social_login_start")
                print("请使用小红书 App 扫描当前二维码；检测到正文后会自动继续。", flush=True)
                for _ in range(60):
                    try:
                        return await call("social_view")
                    except RuntimeError as exc:
                        if not exc.args or exc.args[0].get("code") != "APP_SCAN_REQUIRED":
                            raise
                        await asyncio.sleep(5)
                raise TimeoutError("等待 App 扫码超时")

            if "--search-only" in sys.argv:
                await call("social_open", {"target": "https://www.xiaohongshu.com"})
            else:
                await wait_for_user()
            try:
                result = await call("social_search", {"keyword": "露营", "limit": 3})
            except Exception:
                await save_screenshot("search-error.png")
                page = await call("social_view", {"mode": "text"})
                print("SEARCH_ERROR_PAGE", page["url"], page["text"][-3000:], flush=True)
                raise
            print("SEARCH_COUNT", result["count"], flush=True)
            if not result["items"]:
                return
            note = None
            for item in result["items"]:
                target = item["item_id"]
                try:
                    note = await call("social_open", {"target": target})
                    break
                except RuntimeError as exc:
                    code = exc.args[0].get("code") if exc.args else None
                    if code == "CONTENT_UNAVAILABLE":
                        print("SKIP_UNAVAILABLE", item["title"], flush=True)
                        continue
                    if code == "APP_SCAN_REQUIRED":
                        note = await wait_for_app_scan()
                        break
                    if code != "VERIFICATION_REQUIRED":
                        raise
                    await save_screenshot("verification-required.png")
                    await wait_for_user()
                    note = await call("social_open", {"target": target})
                    break
            if note is None:
                raise RuntimeError("本次搜索结果均不可在网页端读取")
            print("NOTE_TITLE", note["title"], flush=True)
            text = await call("social_view", {"mode": "text"})
            html = await call("social_view", {"mode": "html", "html_mode": "sanitized", "max_chars": 5000})
            assert text["text"] and html["html"]
            comments = await call("social_comments", {"limit": 5})
            if comments["warning"]:
                raise RuntimeError(comments["warning"])
            media = await call("social_media")
            print("COMMENTS", comments["returned"], "IMAGES", len(media["images"]),
                  "VIDEOS", len(media["videos"]), flush=True)
            candidates = [img for img in media["images"] if img["width"] >= 200 and img["height"] >= 200]
            if candidates:
                picture = await call("social_image", {"index": candidates[0]["index"]})
                for item in picture:
                    if getattr(item, "type", None) == "image":
                        suffix = item.mimeType.split("/")[-1].replace("jpeg", "jpg")
                        path = Path(os.environ["LOCALAPPDATA"]) / "SocialInfo" / "logs" / f"live-image.{suffix}"
                        path.write_bytes(base64.b64decode(item.data))
                        print("IMAGE_OK", path, flush=True)
                        break
            if media["videos"]:
                await call("social_interact", {"action": "video_play"})
                await call("social_interact", {"action": "video_seek", "seconds": 1})
                await call("social_interact", {"action": "video_pause"})
                state = await call("social_media")
                assert state["videos"][0]["paused"] and state["videos"][0]["current_time"] >= 1
                print("VIDEO_CONTROLS_OK", flush=True)
            await call("social_interact", {"action": "scroll_down"})
            await call("social_interact", {"action": "scroll_up"})
            next_note = await call("social_interact", {"action": "next_content"})
            await call("social_interact", {"action": "previous_content"})
            print("NAVIGATION_OK", next_note["title"], flush=True)
            await save_screenshot("live-note.png")
            await call("social_close")


if __name__ == "__main__":
    asyncio.run(run())
