import asyncio
import json

import websockets
from websockets.exceptions import ConnectionClosed

from social_info.extension_hub import ExtensionHub


def test_extension_hub_roundtrip(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    hub = ExtensionHub(port=9876)
    hub.start()

    async def check():
        async with websockets.connect(f"ws://127.0.0.1:9876/?token={hub.token}") as socket:
            async def respond():
                request = json.loads(await socket.recv())
                assert request["command"] == "read"
                await socket.send(json.dumps({"id": request["id"], "ok": True,
                                              "data": {"title": "真实浏览器页面"}}))
            task = asyncio.create_task(respond())
            result = await hub.call("read")
            await task
            assert result["title"] == "真实浏览器页面"

    async def reject_wrong_token():
        try:
            async with websockets.connect("ws://127.0.0.1:9876/?token=wrong") as socket:
                await socket.recv()
        except ConnectionClosed:
            return
        raise AssertionError("错误令牌不应保持连接")

    try:
        asyncio.run(check())
        asyncio.run(reject_wrong_token())
    finally:
        hub.stop()
