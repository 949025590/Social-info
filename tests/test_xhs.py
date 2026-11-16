import asyncio
import pytest

from social_info.core import SocialError, guard_click
from social_info.platforms.xhs import XhsAdapter


class Body:
    async def inner_text(self):
        return "当前笔记暂时无法浏览\n请打开小红书App扫码查看"


class TextQuery:
    async def wait_for(self, timeout):
        return None


class Page:
    url = "https://www.xiaohongshu.com/verify/note"

    def locator(self, selector):
        assert selector == "body"
        return Body()

    def get_by_text(self, text, exact=True):
        return TextQuery()


def test_mobile_only_note_is_not_login_error():
    with pytest.raises(SocialError) as error:
        asyncio.run(XhsAdapter()._check(Page()))
    assert error.value.code == "APP_SCAN_REQUIRED"


def test_external_click_is_blocked():
    with pytest.raises(SocialError) as error:
        guard_click("站外链接", "https://example.com", {"www.xiaohongshu.com"})
    assert error.value.code == "URL_NOT_ALLOWED"
