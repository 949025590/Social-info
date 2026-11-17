import asyncio
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def check_server():
    params = StdioServerParameters(
        command=sys.executable, args=["-m", "social_info", "serve"],
        cwd=str(Path(__file__).parents[1]),
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as client:
            await client.initialize()
            tools = await client.list_tools()
            names = {tool.name for tool in tools.tools}
            assert {"social_search", "social_view", "social_interact", "social_media"} <= names
            result = await client.call_tool("social_session_status", {})
            assert result.structuredContent["ok"] is True
            assert result.structuredContent["browser"] == "stopped"
            extension = await client.call_tool("social_extension_status", {})
            assert extension.structuredContent["connected"] is False
            assert extension.structuredContent["port"] == 8766


def test_mcp_stdio():
    asyncio.run(check_server())
