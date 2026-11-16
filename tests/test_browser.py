import asyncio

from playwright.async_api import Error as PlaywrightError

from social_info.platforms.xhs import XhsAdapter


class Context:
    def __init__(self, pages):
        self.pages = pages

    async def new_page(self):
        raise AssertionError("不应新建页面")


class Page:
    pass


def test_headed_snapshot_reuses_page():
    adapter = XhsAdapter()
    page = Page()
    adapter._context = Context([page])
    adapter._headless = False

    async def check():
        assert await adapter._page(allow_headed=True) is page

    asyncio.run(check())


def test_close_is_idempotent_after_browser_disconnect():
    adapter = XhsAdapter()

    class ClosedContext(Context):
        async def close(self):
            raise PlaywrightError("closed")

    adapter._context = ClosedContext([])
    asyncio.run(adapter._close_context())
    assert adapter._context is None
