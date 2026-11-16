from contextlib import asynccontextmanager

from .core import SocialError
from .platforms.xhs import XhsAdapter


class SocialService:
    def __init__(self):
        self.adapters = {"xiaohongshu": XhsAdapter()}

    def platforms(self):
        return {name: {"capabilities": adapter.capabilities} for name, adapter in self.adapters.items()}

    @asynccontextmanager
    async def use(self, platform):
        if platform not in self.adapters:
            raise SocialError("PLATFORM_NOT_SUPPORTED", f"暂不支持平台：{platform}")
        adapter = self.adapters[platform]
        async with adapter.lock:
            yield adapter

    async def close(self):
        for adapter in self.adapters.values():
            await adapter.close()
