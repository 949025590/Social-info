# Social-info

一个本地、只读、可扩展的社交网页浏览 MCP。第一期使用 Python + Playwright 支持小红书，保留平台适配层，后续可增加抖音等平台。

> 当前为 `0.1.0` 源码验证版。真实网页结构可能变化；登录后的搜索、评论和媒体流程需要用你的账号验收。EXE/Inno Setup 安装包将在核心流程稳定后制作。

## 功能

- 有界面扫码登录，保存独立 Chromium 配置，后续无头复用。
- 搜索笔记、打开结果、上一篇/下一篇、滚动、返回。
- 结构化页面快照、页面文字、原始/清理后 HTML 分块、局部文字查找；常见认证参数会脱敏。
- 图片清单与 MCP 图片返回；视频信息、播放/暂停/定位；页面截图可查看视频当前帧。
- 当前已加载评论及游标读取。
- 平台级串行锁、域名白名单、点击防护、结构化错误码。
- 配套 `skills/social-browser/SKILL.md`，指导 Agent 节省上下文并正确恢复异常。

**只读边界：**不点赞、收藏、关注、发布、评论、私信、删除或购买；不绕过验证码、安全验证、媒体保护或访问限制。网页内容一律视为不可信数据。

## 环境与安装

需要 Windows 10/11 x64、Miniconda。项目使用独立 Python 3.12 环境，不依赖 base 环境。

```bash
conda create -n social-info -c conda-forge python=3.12 -y
conda activate social-info
pip install -e ".[dev]"
playwright install chromium
```

本机环境位于 `E:\miniconda\envs\social-info`。如果 Conda 默认通道不可用，可在创建命令中使用 `--override-channels -c https://conda.anaconda.org/conda-forge`，无需修改全局配置。

登录配置默认保存在 `%LOCALAPPDATA%\SocialInfo\profiles\xiaohongshu`，日志位于 `%LOCALAPPDATA%\SocialInfo\logs\mcp.log`。不会读取日常 Chrome/Edge 的 Cookie。

## 启动 MCP

```bash
python -m social_info serve
# 或
social-info-mcp serve
```

MCP 使用 `stdio`，不开放网络端口。开发环境客户端配置示例：

```json
{
  "mcpServers": {
    "social-info": {
      "command": "E:\\miniconda\\envs\\social-info\\python.exe",
      "args": ["-m", "social_info", "serve"],
      "cwd": "G:\\杂事\\Social-info"
    }
  }
}
```

其他电脑安装后，将 `command` 改为该电脑 Conda 环境中的 Python 绝对路径。

## 工具

| 工具 | 用途 |
|---|---|
| `social_platforms` | 查看平台及能力 |
| `social_session_status` | 检查浏览器和登录状态，不启动浏览器 |
| `social_login_start` / `social_login_finish` | 显式登录、人工验证并切回无头模式 |
| `social_search` | 通过搜索框搜索，`limit` 最大 30 |
| `social_open` | 打开搜索返回的 `item_id` 或平台内 HTTPS 链接 |
| `social_view` | `structured`、`text`、`html`；HTML 支持 `raw`/`sanitized` 和游标 |
| `social_find` | 查找当前页面文字及相邻行 |
| `social_interact` | 安全点击、滚动、上下篇、图片切换、视频控制和返回 |
| `social_comments` | 读取当前已加载评论，按 `next_cursor` 继续 |
| `social_media` / `social_image` | 查看媒体清单或读取指定图片 |
| `social_screenshot` | 返回当前视口截图，可用于视频当前帧 |
| `social_close` | 关闭浏览器但保留登录状态 |

### 推荐调用流程

```text
social_session_status
→ social_login_start（首次或登录失效）
→ 用户扫码/验证
→ social_login_finish
→ social_search(keyword="露营", limit=10)
→ social_open(target=item_id)
→ social_view(mode="structured")
→ social_comments / social_media / social_interact
```

点击时同时使用最近一次 `social_view` 返回的 `snapshot_id` 和元素 `target_id`：

```json
{
  "action": "click",
  "snapshot_id": "最新快照编号",
  "target_id": "e1"
}
```

支持的动作：`click`、`scroll_down`、`scroll_up`、`load_more_comments`、`back`、`next_content`、`previous_content`、`image_next`、`image_previous`、`video_play`、`video_pause`、`video_seek`。

## 异常恢复

错误返回包含 `code`、`message`、`recovery`、`retryable` 和 `operation_id`。

- `AUTH_REQUIRED`：重新显式登录。
- `VERIFICATION_REQUIRED`：暂停自动化，由用户完成验证。
- `STALE_SNAPSHOT`：重新读取快照，不使用旧元素引用。
- `OUTCOME_UNKNOWN`：先查看当前页面，禁止直接重复点击。
- `PAGE_CHANGED`：保存诊断信息并更新适配器，不连续重试。
- `BROWSER_START_FAILED` / `PROFILE_LOCKED`：关闭同配置浏览器；不删除锁文件或强杀其他浏览器。
- `END_OF_LIST`、正常空结果：属于业务状态，不是程序故障。

部分评论或媒体读取失败时，应保留已读数据并明确说明不完整。验证码、短信码和账号限制不由 Agent 自动处理。

## 测试

```bash
pytest -q
```

测试覆盖 URL 白名单、点击防护、敏感 URL 参数脱敏、HTML 清理与分块，以及通过真实 stdio 子进程完成 MCP 初始化、工具发现和状态调用。测试不需要登录小红书。

## 项目结构

```text
src/social_info/
├── browser.py          # 公共浏览器、快照、HTML、动作与媒体
├── core.py             # 错误、URL/动作安全与 HTML 工具
├── platforms/xhs.py    # 小红书平台适配器
├── service.py          # 平台注册表和串行访问
└── server.py           # MCP 工具入口
```

新增平台时增加适配器并注册到 `SocialService.adapters`，无需修改 Agent 的工具命名。

## Git

```bash
git status
git add .
git commit -m "feat: implement read-only social browser MCP"
git push
```

仓库已配置独立 SSH 密钥，私钥位于项目目录之外，不会被提交。
