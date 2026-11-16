import argparse
import asyncio
import functools
import logging
import os
import sys
import uuid
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP, Image

from .core import SocialError
from .service import SocialService

log_dir = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "SocialInfo" / "logs"
log_dir.mkdir(parents=True, exist_ok=True)
logging.basicConfig(filename=log_dir / "mcp.log", level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("social-info")
mcp = FastMCP("social-info")
service = SocialService()


def safe_tool(func):
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        operation_id = uuid.uuid4().hex[:12]
        try:
            result = await func(*args, **kwargs)
            if isinstance(result, dict):
                result.update(ok=True, operation_id=operation_id)
            return result
        except SocialError as exc:
            result = exc.as_dict()
            result["operation_id"] = operation_id
            return result
        except Exception as exc:
            log.exception("operation=%s", operation_id)
            return {"ok": False, "operation_id": operation_id,
                    "error": {"code": "INTERNAL_ERROR", "message": str(exc),
                              "recovery": "social_view", "retryable": False}}
    return wrapper


@mcp.tool()
@safe_tool
async def social_platforms() -> dict[str, Any]:
    """列出支持的平台和各自能力。"""
    return {"platforms": service.platforms()}


@mcp.tool()
@safe_tool
async def social_session_status(platform: str = "xiaohongshu") -> dict[str, Any]:
    """检查浏览器与登录状态，不启动浏览器。"""
    async with service.use(platform) as adapter:
        return await adapter.status()


@mcp.tool()
@safe_tool
async def social_login_start(platform: str = "xiaohongshu") -> dict[str, Any]:
    """打开有界面浏览器，由用户扫码、登录或完成安全验证。"""
    async with service.use(platform) as adapter:
        return await adapter.login_start()


@mcp.tool()
@safe_tool
async def social_login_finish(platform: str = "xiaohongshu") -> dict[str, Any]:
    """确认显式登录完成，保存会话并切回无头模式。"""
    async with service.use(platform) as adapter:
        return await adapter.login_finish()


@mcp.tool()
@safe_tool
async def social_search(keyword: str, limit: int = 10, platform: str = "xiaohongshu") -> dict[str, Any]:
    """通过平台搜索框搜索内容，最多返回 30 条。"""
    async with service.use(platform) as adapter:
        return await adapter.search(keyword, limit)


@mcp.tool()
@safe_tool
async def social_open(target: str, platform: str = "xiaohongshu") -> dict[str, Any]:
    """打开搜索结果 item_id 或同平台 HTTPS 内容链接。"""
    async with service.use(platform) as adapter:
        return await adapter.open_content(target)


@mcp.tool()
@safe_tool
async def social_view(mode: str = "structured", html_mode: str = "sanitized",
                      cursor: int = 0, max_chars: int = 20000,
                      platform: str = "xiaohongshu") -> dict[str, Any]:
    """查看 structured/text/html；HTML 使用 next_cursor 分块读取。"""
    async with service.use(platform) as adapter:
        return await adapter.view(mode, html_mode, cursor, max_chars)


@mcp.tool()
@safe_tool
async def social_find(text: str, platform: str = "xiaohongshu") -> dict[str, Any]:
    """在当前页面文字中查找关键词及相邻行，避免读取完整 HTML。"""
    async with service.use(platform) as adapter:
        return await adapter.find(text)


@mcp.tool()
@safe_tool
async def social_interact(action: str, target_id: str | None = None,
                          snapshot_id: str | None = None, delta: int = 650,
                          seconds: float | None = None,
                          platform: str = "xiaohongshu") -> dict[str, Any]:
    """执行只读浏览：click、滚动、上下篇、图片切换、视频控制或 back。"""
    async with service.use(platform) as adapter:
        return await adapter.interact(action, target_id, snapshot_id, delta, seconds)


@mcp.tool()
@safe_tool
async def social_comments(limit: int = 20, cursor: int = 0,
                          platform: str = "xiaohongshu") -> dict[str, Any]:
    """读取当前内容已加载的评论；next_cursor 用于继续读取。"""
    async with service.use(platform) as adapter:
        return await adapter.comments(limit, cursor)


@mcp.tool()
@safe_tool
async def social_media(platform: str = "xiaohongshu") -> dict[str, Any]:
    """列出当前页面图片、视频地址和播放状态。"""
    async with service.use(platform) as adapter:
        return await adapter.media()


@mcp.tool()
@safe_tool
async def social_image(index: int, platform: str = "xiaohongshu") -> Image:
    """按 social_media 返回的图片序号读取图片内容。"""
    async with service.use(platform) as adapter:
        data, image_format = await adapter.image(index)
        return Image(data=data, format=image_format)


@mcp.tool()
@safe_tool
async def social_screenshot(platform: str = "xiaohongshu") -> Image:
    """截取当前页面视口，用于查看图片或视频当前帧。"""
    async with service.use(platform) as adapter:
        return Image(data=await adapter.screenshot(), format="png")


@mcp.tool()
@safe_tool
async def social_server_stop() -> dict[str, Any]:
    """关闭受管浏览器并停止本地 MCP 服务，供托盘程序使用。"""
    await service.close()
    asyncio.get_running_loop().call_later(0.5, os._exit, 0)
    return {"state": "stopped"}


@mcp.tool()
@safe_tool
async def social_close(platform: str = "xiaohongshu") -> dict[str, Any]:
    """关闭该平台浏览器；保留磁盘上的登录状态。"""
    async with service.use(platform) as adapter:
        await adapter._close_context()
        return {"state": "stopped"}


def main():
    parser = argparse.ArgumentParser(description="Social Info MCP")
    parser.add_argument("command", nargs="?", default="serve", choices=["serve"])
    parser.add_argument("--transport", choices=["stdio", "http"], default="stdio")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    try:
        if args.transport == "http":
            mcp.settings.host = "127.0.0.1"
            mcp.settings.port = args.port
            mcp.run(transport="streamable-http")
        else:
            mcp.run()
    finally:
        asyncio.run(service.close())


if __name__ == "__main__":
    main()
