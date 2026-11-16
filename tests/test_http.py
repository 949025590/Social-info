import asyncio
import subprocess
import sys
import time

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


async def check_client():
    async with httpx.AsyncClient(timeout=3) as http:
        async with streamable_http_client("http://127.0.0.1:8768/mcp", http_client=http) as (read, write, _):
            async with ClientSession(read, write) as client:
                await client.initialize()
                result = await client.call_tool("social_platforms", {})
                assert result.structuredContent["ok"] is True
                await client.call_tool("social_server_stop", {})


def test_http_mcp():
    process = subprocess.Popen([
        sys.executable, "-m", "social_info", "serve", "--transport", "http", "--port", "8768"
    ])
    try:
        for _ in range(40):
            try:
                asyncio.run(check_client())
                return
            except Exception:
                if process.poll() is not None:
                    raise RuntimeError("HTTP MCP 启动失败")
                time.sleep(0.25)
        raise TimeoutError("HTTP MCP 启动超时")
    finally:
        if process.poll() is None:
            process.terminate()
        process.wait(timeout=10)
