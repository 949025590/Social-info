import asyncio
import json
import secrets
import threading
import uuid
from pathlib import Path
import os
from urllib.parse import parse_qs, urlparse

import websockets

from .core import SocialError


class ExtensionHub:
    def __init__(self, port=8766):
        self.port = port
        self.base = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "SocialInfo"
        self.base.mkdir(parents=True, exist_ok=True)
        self.token_path = self.base / "extension-token.txt"
        if self.token_path.exists():
            self.token = self.token_path.read_text(encoding="utf-8").strip()
        else:
            self.token = secrets.token_urlsafe(32)
            self.token_path.write_text(self.token, encoding="utf-8")
        self.loop = None
        self.thread = None
        self.connection = None
        self.server = None
        self.pending = {}
        self.ready = threading.Event()
        self.start_error = None

    def start(self):
        if self.thread:
            return
        self.thread = threading.Thread(target=self._run, name="extension-hub", daemon=True)
        self.thread.start()
        self.ready.wait(timeout=5)
        if self.start_error:
            raise self.start_error

    def _run(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        try:
            async def listen():
                return await websockets.serve(
                    self._handler, "127.0.0.1", self.port, max_size=16 * 1024 * 1024
                )
            self.server = self.loop.run_until_complete(listen())
        except Exception as exc:
            self.start_error = exc
            self.ready.set()
            return
        self.ready.set()
        self.loop.run_forever()

    async def _handler(self, websocket):
        supplied = parse_qs(urlparse(websocket.request.path).query).get("token", [""])[0]
        if not secrets.compare_digest(supplied, self.token):
            await websocket.close(code=4001, reason="unauthorized")
            return
        if self.connection:
            await self.connection.close(code=1000, reason="replaced")
        self.connection = websocket
        try:
            async for message in websocket:
                data = json.loads(message)
                future = self.pending.pop(data.get("id"), None)
                if future and not future.done():
                    if data.get("ok"):
                        future.set_result(data.get("data"))
                    else:
                        future.set_exception(SocialError("EXTENSION_ACTION_FAILED", data.get("error", "扩展操作失败")))
        finally:
            if self.connection is websocket:
                self.connection = None

    async def _call(self, command, args):
        if not self.connection:
            raise SocialError("EXTENSION_NOT_CONNECTED", "请先安装扩展并填写本地连接令牌", "social_extension_status")
        operation_id = uuid.uuid4().hex
        future = self.loop.create_future()
        self.pending[operation_id] = future
        await self.connection.send(json.dumps({"id": operation_id, "command": command, "args": args}))
        try:
            return await asyncio.wait_for(future, timeout=20)
        finally:
            self.pending.pop(operation_id, None)

    async def call(self, command, args=None):
        if not self.loop:
            raise SocialError("EXTENSION_UNAVAILABLE", "扩展连接服务尚未启动")
        future = asyncio.run_coroutine_threadsafe(self._call(command, args or {}), self.loop)
        return await asyncio.wrap_future(future)

    def stop(self):
        if not self.loop:
            return
        async def shutdown():
            if self.connection:
                await self.connection.close()
            if self.server:
                self.server.close()
                await self.server.wait_closed()
        try:
            asyncio.run_coroutine_threadsafe(shutdown(), self.loop).result(timeout=3)
        except Exception:
            pass
        self.loop.call_soon_threadsafe(self.loop.stop)
        self.thread.join(timeout=3)
        self.loop = None
        self.thread = None
