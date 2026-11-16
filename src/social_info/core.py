import re
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

BLOCKED_ACTIONS = re.compile(
    r"点赞|收藏|关注|发布|发表评论|写评论|回复|私信|分享|删除|退出登录|购买|充值"
)
SENSITIVE_PARAMS = {"access_token", "code", "token", "session", "sessionid"}


class SocialError(Exception):
    def __init__(self, code, message, recovery=None, retryable=False, partial=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.recovery = recovery
        self.retryable = retryable
        self.partial = partial

    def as_dict(self):
        return {
            "ok": False,
            "error": {
                "code": self.code,
                "message": self.message,
                "recovery": self.recovery,
                "retryable": self.retryable,
            },
            "partial_data": self.partial,
        }


def redact_url(url):
    parsed = urlparse(url)
    query = urlencode([
        (key, "<redacted>" if key.lower() in SENSITIVE_PARAMS else value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
    ])
    return urlunparse(parsed._replace(query=query))


def validate_url(url, hosts):
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in hosts:
        raise SocialError("URL_NOT_ALLOWED", "只允许访问平台 HTTPS 页面")
    return url


def guard_click(label, href, hosts):
    if not (label or "").strip() and not href:
        raise SocialError("ACTION_NOT_ALLOWED", "无法确认用途的图标按钮不允许通用点击")
    if BLOCKED_ACTIONS.search(label or ""):
        raise SocialError("ACTION_NOT_ALLOWED", "只读模式禁止账户或互动操作")
    if href:
        if href.startswith("/"):
            return
        if href.startswith("http"):
            validate_url(href, hosts)
        else:
            raise SocialError("ACTION_NOT_ALLOWED", "禁止非网页或站外点击")


def sanitize_html(html):
    return re.sub(r"<(script|style)\b[^>]*>.*?</\1>", "", html, flags=re.I | re.S)


def redact_html(html):
    return re.sub(r"(?i)\b(access_token|sessionid|code)=([^&\s\"'<>]+)", r"\1=<redacted>", html)


def html_chunk(html, cursor=0, max_chars=20000):
    max_chars = min(max(1000, max_chars), 30000)
    if cursor < 0 or cursor > len(html):
        raise SocialError("INVALID_CURSOR", "HTML 游标无效")
    end = min(cursor + max_chars, len(html))
    return {
        "html": html[cursor:end],
        "cursor": cursor,
        "next_cursor": end if end < len(html) else None,
        "total_chars": len(html),
    }
