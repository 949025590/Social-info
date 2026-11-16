import asyncio

from social_info.platforms.xhs import XhsAdapter

PIXEL = "data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///ywAAAAAAQABAAACAUwAOw=="


async def exercise():
    adapter = XhsAdapter()
    try:
        page = await adapter._page()
        await page.set_content(f"""
          <input placeholder="搜索"><button onclick="document.body.dataset.clicked='yes'">下一篇</button>
          <script>window.testScript=true</script><img src="{PIXEL}">
          <div class="comment-item"><span class="author"><span class="name">测试用户</span></span>
          <div class="note-text">测试评论</div><span class="like"><span class="count">3</span></span></div>
        """)
        snapshot = await adapter.snapshot()
        target = next(item for item in snapshot["elements"] if item["text"] == "下一篇")
        await adapter.interact("click", target["target_id"], snapshot["snapshot_id"])
        assert await page.locator("body").get_attribute("data-clicked") == "yes"
        raw = await adapter.view("html", "raw")
        clean = await adapter.view("html", "sanitized")
        assert "testScript" in raw["html"] and "testScript" not in clean["html"]
        assert len((await adapter.media())["images"]) == 1
        comments = await adapter.comments()
        assert comments["items"][0]["author"] == "测试用户"
        assert comments["items"][0]["text"] == "测试评论"
        assert (await adapter.screenshot()).startswith(b"\x89PNG")
    finally:
        await adapter.close()


def test_real_chromium_local_integration():
    asyncio.run(exercise())
