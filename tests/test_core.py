import pytest

from social_info.core import (
    SocialError, guard_click, html_chunk, redact_html, redact_url, sanitize_html, validate_url,
)

HOSTS = {"www.xiaohongshu.com"}


def test_url_allowlist():
    assert validate_url("https://www.xiaohongshu.com/explore/1", HOSTS)
    for url in ("http://www.xiaohongshu.com/1", "https://www.xiaohongshu.com.evil.test/1"):
        with pytest.raises(SocialError):
            validate_url(url, HOSTS)


def test_click_guard():
    for label in ("点赞", ""):
        with pytest.raises(SocialError) as error:
            guard_click(label, "", HOSTS)
        assert error.value.code == "ACTION_NOT_ALLOWED"
    guard_click("下一篇", "/explore/1", HOSTS)


def test_url_redaction():
    assert "access_token=%3Credacted%3E" in redact_url(
        "https://www.xiaohongshu.com/?access_token=secret&id=1"
    )


def test_html_cleanup_and_chunks():
    html = "<style>x</style><main>正文</main><script>alert(1)</script>"
    assert sanitize_html(html) == "<main>正文</main>"
    assert redact_html('<a href="?access_token=secret&id=1">') == '<a href="?access_token=<redacted>&id=1">'
    first = html_chunk("x" * 2500, 0, 1000)
    second = html_chunk("x" * 2500, first["next_cursor"], 1000)
    assert first["next_cursor"] == 1000
    assert second["next_cursor"] == 2000
