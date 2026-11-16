import hashlib

from playwright.async_api import Error as PlaywrightError

from ..browser import BrowserAdapter
from ..core import SocialError, redact_url


class XhsAdapter(BrowserAdapter):
    name = "xiaohongshu"
    home = "https://www.xiaohongshu.com"
    hosts = {"xiaohongshu.com", "www.xiaohongshu.com"}
    capabilities = BrowserAdapter.capabilities + ["search", "comments", "next_content", "video"]

    def __init__(self):
        super().__init__()
        self._items = {}
        self._search_order = []
        self._current_item = None

    async def auth_state(self, page):
        url = page.url.lower()
        if any(word in url for word in ("verify", "captcha", "security-check")):
            return "verification_required"
        if "login" in url:
            return "logged_out"
        try:
            if await page.locator(".login-container").first.is_visible():
                return "logged_out"
            search = page.locator("input").first
            placeholder = await search.get_attribute("placeholder") if await search.count() else ""
            if "登录" in (placeholder or ""):
                return "logged_out"
            if await page.locator('input[placeholder*="搜索"]').first.is_visible():
                return "logged_in"
        except PlaywrightError:
            return "unknown"
        return "unknown"

    async def _check(self, page):
        state = await self.auth_state(page)
        if state == "verification_required":
            raise SocialError("VERIFICATION_REQUIRED", "页面要求安全验证", "social_login_start")
        if state == "logged_out":
            raise SocialError("AUTH_REQUIRED", "未登录或登录状态已失效", "social_login_start")

    async def search(self, keyword, limit=10):
        keyword = keyword.strip()
        if not keyword:
            raise SocialError("INVALID_ARGUMENT", "搜索关键词不能为空")
        limit = min(max(1, limit), 30)
        page = await self._page()
        if page.url == "about:blank":
            await page.goto(self.home, wait_until="domcontentloaded")
        if await self.auth_state(page) != "logged_in":
            raise SocialError("AUTH_REQUIRED", "请先显式登录小红书", "social_login_start")
        box = page.locator('input[placeholder*="搜索"]').first
        try:
            await box.fill(keyword)
            await box.press("Enter")
            await page.locator("section.note-item").first.wait_for(timeout=12000)
        except PlaywrightError as exc:
            await self._check(page)
            body = await page.locator("body").inner_text()
            if "暂无" in body and "结果" in body:
                return {"items": [], "count": 0}
            raise SocialError("PAGE_CHANGED", "未识别到搜索结果，请查看页面快照", "social_view") from exc
        cards = await page.locator("section.note-item").evaluate_all("""cards => cards.map(card => {
          const a=card.querySelector('a[href]'), title=card.querySelector('.title');
          const author=card.querySelector('.author .name,.name'), img=card.querySelector('img');
          return {url:a?.href||'', title:(title?.innerText||a?.innerText||'').trim(),
            author:(author?.innerText||'').trim(), text:(card.innerText||'').trim(),
            image:img?.currentSrc||img?.src||null};
        })""")
        items = []
        self._search_order = []
        for card in cards:
            if not card["url"]:
                continue
            item_id = hashlib.sha256(card["url"].encode()).hexdigest()[:16]
            self._items[item_id] = card["url"]
            self._search_order.append(item_id)
            card.update(item_id=item_id, url=redact_url(card["url"]))
            items.append(card)
            if len(items) >= limit:
                break
        return {"items": items, "count": len(items), "snapshot": await self.snapshot()}

    async def open_content(self, target):
        url = self._items.get(target, target)
        if target in self._items:
            self._current_item = target
        return await self.open_url(url)

    async def _custom_action(self, page, action, **kwargs):
        selectors = {
            "image_next": ['.arrow-controller.right', '[aria-label*="下一张"]'],
            "image_previous": ['.arrow-controller.left', '[aria-label*="上一张"]'],
        }
        if action in selectors:
            for selector in selectors[action]:
                button = page.locator(selector).first
                if await button.count() and await button.is_visible():
                    await button.click()
                    return True
            await page.keyboard.press("ArrowRight" if action == "image_next" else "ArrowLeft")
            return True
        if action in {"next_content", "previous_content"}:
            if self._current_item not in self._search_order:
                raise SocialError("NAVIGATION_UNAVAILABLE", "当前没有关联的搜索结果")
            index = self._search_order.index(self._current_item)
            index += 1 if action == "next_content" else -1
            if index < 0 or index >= len(self._search_order):
                raise SocialError("END_OF_LIST", "已经到达列表边界")
            await self.open_content(self._search_order[index])
            return True
        return False

    async def comments(self, limit=20, cursor=0):
        limit = min(max(1, limit), 50)
        if cursor < 0:
            raise SocialError("INVALID_CURSOR", "评论游标无效")
        page = await self._page()
        await self._check(page)
        if cursor:
            await page.mouse.wheel(0, 650)
            await page.wait_for_timeout(500)
        body = await page.locator("body").inner_text()
        if "评论已关闭" in body or "暂无评论权限" in body:
            raise SocialError("COMMENTS_UNAVAILABLE", "评论区不可用")
        data = await page.locator(".comment-item").evaluate_all("""items => items.map((el,index) => ({
          id:el.getAttribute('data-comment-id')||null, position:index,
          author:(el.querySelector('.author .name,.name')?.innerText||'').trim(),
          text:(el.querySelector('.note-text,.content')?.innerText||el.innerText||'').trim(),
          likes:(el.querySelector('.like .count')?.innerText||'').trim()||null
        }))""")
        end = min(cursor + limit, len(data))
        return {
            "items": data[cursor:end], "count": len(data), "returned": end - cursor,
            "next_cursor": end if end < len(data) else None,
            "partial": end < len(data), "url": redact_url(page.url),
            "warning": None if data else "当前未识别到评论；可查看页面或加载更多后重试",
        }
