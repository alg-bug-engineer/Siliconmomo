# 视频 URL 提取方案分析与实施建议

**完成时间**: 2026-02-06
**参考项目**: MediaCrawler
**问题**: 当前 DOM 提取方式只能获取 blob URL，无法获取真实 CDN 视频链接

---

## 📊 问题分析

### 当前实现 (DOM-based)

```python
# actions/interaction.py - _extract_video()
async def _extract_video(self):
    return await self.page.evaluate("""
        () => {
            const videoEl = document.querySelector('.note-detail-mask video');
            return videoEl ? videoEl.src : '';  // ❌ 返回 blob:https://...
        }
    """)
```

**问题**:
- ✅ 能检测到视频元素
- ❌ `video.src` 是 blob URL (临时内存地址)
- ❌ blob URL 无法下载/保存
- ❌ 播放器内部使用 CDN URL，但不暴露给 DOM

**为什么 DOM 方法不行？**

小红书视频播放流程：
```
1. 前端从 API 获取 origin_video_key
2. 构造 CDN URL: http://sns-video-bd.xhscdn.com/{key}
3. 视频流通过 Media Source Extensions (MSE) 加载
4. 浏览器创建 blob URL 供 <video> 标签使用
5. ❌ 原始 CDN URL 不会出现在 DOM 中
```

---

## 🔍 MediaCrawler 的解决方案

### 核心流程

MediaCrawler 使用 **API 方式** 获取视频 URL：

```python
# 1. 调用 API 获取笔记详情
note_detail = await xhs_client.get_note_by_id(
    note_id=note_id,
    xsec_source=xsec_source,
    xsec_token=xsec_token
)

# 2. 从 API 响应中提取视频 URL
def get_video_url_arr(note_item: Dict) -> List:
    if note_item.get('type') != 'video':
        return []

    # 方法1: 从 origin_video_key 构造 CDN URL (推荐)
    originVideoKey = note_item.get('video').get('consumer').get('origin_video_key')
    if originVideoKey:
        return [f"http://sns-video-bd.xhscdn.com/{originVideoKey}"]

    # 方法2: 从 h264 流获取 master_url (备选)
    videos = note_item.get('video').get('media').get('stream').get('h264')
    if isinstance(videos, list):
        return [v.get('master_url') for v in videos]

    return []
```

### API 请求详情

**端点**: `/api/sns/web/v1/feed`

**请求参数**:
```json
{
  "source_note_id": "6788786b000000001203e6b0",
  "image_formats": ["jpg", "webp", "avif"],
  "extra": {"need_body_topic": 1},
  "xsec_source": "pc_feed",
  "xsec_token": "..."
}
```

**响应结构** (视频笔记):
```json
{
  "items": [{
    "note_card": {
      "note_id": "6788786b000000001203e6b0",
      "type": "video",
      "video": {
        "consumer": {
          "origin_video_key": "spectrum/1040g0k03kqi67uhg7g5g5os4ugnb89hgl6lhpfg"
        },
        "media": {
          "stream": {
            "h264": [{
              "master_url": "http://sns-video-bd.xhscdn.com/stream/110/258/...",
              "backup_urls": ["..."]
            }]
          }
        }
      }
    }
  }]
}
```

**最终 CDN URL**:
```
http://sns-video-bd.xhscdn.com/spectrum/1040g0k03kqi67uhg7g5g5os4ugnb89hgl6lhpfg
```

---

## 🚀 SiliconMomo 集成方案

### 方案对比

| 方案 | 优点 | 缺点 | 推荐度 |
|------|------|------|--------|
| **方案A: API Only** | CDN URL 可靠 | 需要 xsec_token | ⭐⭐⭐⭐⭐ |
| **方案B: DOM Only** | 无需 API 请求 | blob URL 不可用 | ❌ |
| **方案C: Hybrid** | 逐步迁移 | 复杂度高 | ⭐⭐⭐ |

### 推荐方案: API-based 视频提取

**优势**:
1. ✅ 获取真实 CDN URL，可下载/保存
2. ✅ MediaCrawler 已验证可行
3. ✅ `temp.py` 已有完整 XiaoHongShuClient 实现
4. ✅ 支持备用 URL (h264 stream)

**挑战**:
1. ⚠️ 需要 `xsec_token` 和 `xsec_source` 参数
2. ⚠️ 需要请求签名 (X-S, X-T headers)
3. ⚠️ 需要管理 API 请求频率

---

## 💻 实施方案

### Step 1: 集成 temp.py 的 XiaoHongShuClient

**目标**: 复用 temp.py 的 API 客户端，无需重写

**实施**:

1. **修改 `actions/interaction.py`** - 初始化 API 客户端:

```python
from temp import XiaoHongShuClient  # 导入现有客户端

class ActionExecutor:
    def __init__(self, page, human, recorder):
        self.page = page
        self.human = human
        self.recorder = recorder
        self.kb = KnowledgeBase(recorder)

        # 新增: 初始化 API 客户端
        self.xhs_client = None

    async def _init_api_client(self):
        """懒加载 API 客户端 (仅在需要时初始化)"""
        if self.xhs_client is not None:
            return

        try:
            # 从浏览器上下文获取 cookies
            cookies = await self.page.context.cookies()
            cookie_dict = {c['name']: c['value'] for c in cookies}
            cookie_str = '; '.join([f"{k}={v}" for k, v in cookie_dict.items()])

            headers = {
                "User-Agent": await self.page.evaluate("() => navigator.userAgent"),
                "Cookie": cookie_str,
                "Referer": "https://www.xiaohongshu.com",
            }

            self.xhs_client = XiaoHongShuClient(
                timeout=30,
                headers=headers,
                playwright_page=self.page,
                cookie_dict=cookie_dict
            )
            self.recorder.log("info", "✅ [API客户端] 初始化成功")
        except Exception as e:
            self.recorder.log("warning", f"⚠️ [API客户端] 初始化失败: {e}")
            self.xhs_client = None
```

2. **增强 `_extract_video()`** - API-based 提取:

```python
async def _extract_video(self):
    """
    提取视频 URL (API-based 方法)
    返回: CDN URL 或空字符串
    """
    # 步骤1: 从 URL 提取 note_id
    url_match = re.search(r'/explore/([a-f0-9]+)', self.page.url)
    if not url_match:
        return ""

    note_id = url_match.group(1)

    # 步骤2: 检查是否为视频笔记 (DOM 快速判断)
    is_video = await self.page.evaluate("""
        () => {
            const noteContainer = document.querySelector('[data-type="video"]');
            return noteContainer && noteContainer.getAttribute('data-type') === 'video';
        }
    """)

    if not is_video:
        return ""

    # 步骤3: 初始化 API 客户端
    await self._init_api_client()
    if not self.xhs_client:
        self.recorder.log("warning", "⚠️ [视频提取] API客户端不可用，无法获取视频URL")
        return ""

    # 步骤4: 从 URL 参数获取 xsec_token (如果有)
    try:
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(self.page.url)
        query_params = parse_qs(parsed.query)
        xsec_token = query_params.get('xsec_token', [''])[0]
        xsec_source = query_params.get('xsec_source', ['pc_feed'])[0]

        # 步骤5: 调用 API 获取笔记详情
        note_detail = await self.xhs_client.get_note_by_id(
            note_id=note_id,
            xsec_source=xsec_source,
            xsec_token=xsec_token
        )

        if not note_detail:
            self.recorder.log("warning", f"⚠️ [视频提取] 未获取到笔记详情: {note_id}")
            return ""

        # 步骤6: 提取 video URL
        video_url = self._extract_video_url_from_note(note_detail)

        if video_url:
            self.recorder.log("info", f"✅ [视频提取] 成功获取CDN URL: {video_url[:60]}...")
        else:
            self.recorder.log("warning", f"⚠️ [视频提取] 笔记 {note_id} 无视频数据")

        return video_url

    except Exception as e:
        self.recorder.log("error", f"❌ [视频提取] API调用失败: {e}")
        return ""

def _extract_video_url_from_note(self, note_detail: dict) -> str:
    """
    从 API 响应中提取视频 CDN URL
    参考 MediaCrawler 的 get_video_url_arr() 逻辑
    """
    if note_detail.get('type') != 'video':
        return ""

    video_info = note_detail.get('video', {})

    # 方法1: 从 origin_video_key 构造 CDN URL (首选)
    origin_key = video_info.get('consumer', {}).get('origin_video_key', '')
    if not origin_key:
        origin_key = video_info.get('consumer', {}).get('originVideoKey', '')  # 备选字段名

    if origin_key:
        return f"http://sns-video-bd.xhscdn.com/{origin_key}"

    # 方法2: 从 h264 stream 获取 master_url (备选)
    try:
        h264_videos = video_info.get('media', {}).get('stream', {}).get('h264', [])
        if isinstance(h264_videos, list) and len(h264_videos) > 0:
            master_url = h264_videos[0].get('master_url', '')
            if master_url:
                return master_url
    except Exception as e:
        self.recorder.log("warning", f"⚠️ [视频提取] 解析h264流失败: {e}")

    return ""
```

### Step 2: 获取 xsec_token 的方法

**问题**: API 需要 `xsec_token` 参数，从哪里获取？

**解决方案** (优先级排序):

#### 方案 2.1: 从当前页面 URL 获取 (最简单)

如果用户是通过搜索进入详情页，URL 中已包含 token:
```
https://www.xiaohongshu.com/explore/6788786b?xsec_token=ABC&xsec_source=pc_search
```

```python
# 直接从 URL 提取
from urllib.parse import urlparse, parse_qs
parsed = urlparse(self.page.url)
query_params = parse_qs(parsed.query)
xsec_token = query_params.get('xsec_token', [''])[0]
```

#### 方案 2.2: 从页面 __INITIAL_STATE__ 提取

```python
xsec_token = await self.page.evaluate("""
    () => {
        if (window.__INITIAL_STATE__ && window.__INITIAL_STATE__.note) {
            return window.__INITIAL_STATE__.note.xsec_token || '';
        }
        return '';
    }
""")
```

#### 方案 2.3: 使用空 token (有风险，可能被拦截)

```python
xsec_token = ""
xsec_source = "pc_feed"
```

**建议**: 按 2.1 → 2.2 → 2.3 的顺序尝试。

### Step 3: 处理 API 签名问题

**问题**: 小红书 API 需要请求头签名 (X-S, X-T)

**好消息**: `temp.py` 的 `XiaoHongShuClient` 已实现！

```python
# temp.py 已有实现
async def _pre_headers(self, url: str, data=None) -> Dict:
    """请求头参数签名"""
    encrypt_params = await self.playwright_page.evaluate(
        "([url, data]) => window._webmsxyw(url,data)", [url, data]
    )
    # 自动生成 X-S, X-T 签名
    signs = sign(...)
    return headers
```

**实施**: 直接使用 `temp.py` 的客户端，无需额外工作。

---

## 📋 完整实施清单

### Phase 1: 基础集成 (1-2小时)

- [x] ✅ 分析 MediaCrawler 源码
- [ ] 📝 修改 `actions/interaction.py`:
  - [ ] 导入 `temp.py` 的 `XiaoHongShuClient`
  - [ ] 添加 `_init_api_client()` 方法
  - [ ] 重写 `_extract_video()` 方法
  - [ ] 添加 `_extract_video_url_from_note()` 辅助方法
- [ ] 🧪 测试视频 URL 提取:
  - [ ] 找一个视频笔记测试
  - [ ] 验证能获取到 CDN URL
  - [ ] 验证 URL 可访问 (curl 测试)

### Phase 2: 鲁棒性优化 (1小时)

- [ ] 🛡️ 添加错误处理:
  - [ ] API 调用失败降级策略
  - [ ] token 缺失时的处理
  - [ ] 网络超时重试
- [ ] 📊 增强日志:
  - [ ] 记录 API 调用次数
  - [ ] 区分成功/失败案例
  - [ ] 显示 CDN URL 预览

### Phase 3: 性能优化 (可选)

- [ ] ⚡ 缓存优化:
  - [ ] 同一 note_id 只调用一次 API
  - [ ] API 客户端单例复用
- [ ] 🔄 异步优化:
  - [ ] 视频 URL 提取与评论抓取并行

---

## 🧪 测试方法

### 1. 找到测试视频

```python
# 在小红书搜索 "AI工具推荐"，找到视频笔记
# 示例 URL:
# https://www.xiaohongshu.com/explore/6788786b?xsec_token=...&xsec_source=pc_search
```

### 2. 手动测试 API

```python
# 在项目根目录创建 test_video_api.py
import asyncio
from temp import XiaoHongShuClient
from playwright.async_api import async_playwright

async def test():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()
        await page.goto("https://www.xiaohongshu.com")

        # 手动登录...
        input("登录后按回车继续...")

        cookies = await context.cookies()
        cookie_dict = {c['name']: c['value'] for c in cookies}

        client = XiaoHongShuClient(
            timeout=30,
            headers={"Cookie": "...", "User-Agent": "..."},
            playwright_page=page,
            cookie_dict=cookie_dict
        )

        # 测试获取视频笔记
        note_detail = await client.get_note_by_id(
            note_id="6788786b000000001203e6b0",
            xsec_source="pc_search",
            xsec_token=""
        )

        print("Note Detail:", note_detail)

        # 提取视频 URL
        origin_key = note_detail.get('video', {}).get('consumer', {}).get('origin_video_key')
        video_url = f"http://sns-video-bd.xhscdn.com/{origin_key}" if origin_key else ""
        print("Video URL:", video_url)

        await browser.close()

asyncio.run(test())
```

### 3. 验证 CDN URL

```bash
# 测试 URL 是否可访问
curl -I "http://sns-video-bd.xhscdn.com/spectrum/1040g0k03kqi67uhg7g5g5os4ugnb89hgl6lhpfg"

# 应该返回 200 OK
HTTP/1.1 200 OK
Content-Type: video/mp4
Content-Length: 1234567
```

### 4. 集成测试

```bash
# 运行主程序，观察日志
python main.py

# 预期日志:
# [INFO] ✅ [API客户端] 初始化成功
# [INFO] 📸 [抓取] ID:6788786b... | videox1 | 评论x5
# [INFO] ✅ [视频提取] 成功获取CDN URL: http://sns-video-bd.xhscdn.com/spectrum/...
# [INFO] 💾 [知识库-缓存] +1 新素材: AI工具推荐... | 视频x1 | 评论x5 (缓冲区:1)
```

---

## ⚠️ 注意事项

### 1. API 频率限制

- 小红书可能限制 API 调用频率
- **建议**: 只在检测到视频类型时才调用 API
- **策略**: DOM 快速判断 → 命中再调 API

### 2. xsec_token 时效性

- token 可能有时效限制 (1小时?)
- **建议**: 优先使用 URL 中的 token (最新的)
- **降级**: token 失效时，记录但继续运行

### 3. 登录态依赖

- API 调用需要登录 cookies
- **建议**: 定期检查 `xhs_client.pong()`
- **处理**: 登录失效时暂停 API 调用

### 4. 数据结构变化

- API 响应结构可能更新
- **建议**: 添加 try-except 保护
- **日志**: 记录未知字段便于调试

---

## 📚 参考资料

### MediaCrawler 关键文件

- `media_platform/xhs/client.py:244-279` - `get_note_by_id()` API
- `media_platform/xhs/core.py:483-498` - `get_notice_video()` 调用流程
- `store/xhs/__init__.py:get_video_url_arr()` - 视频 URL 提取逻辑

### 小红书 API 端点

- **笔记详情**: `POST /api/sns/web/v1/feed`
- **评论列表**: `GET /api/sns/web/v2/comment/page`
- **视频 CDN**: `http://sns-video-bd.xhscdn.com/{origin_video_key}`

### 现有代码

- `temp.py` - 完整的 XiaoHongShuClient 实现
- `actions/interaction.py:_extract_video()` - 当前 DOM-based 实现
- `config/settings.py:ENABLE_CONTENT_SCRAPING` - 配置开关

---

## 🎯 预期效果

**改造前**:
```json
{
  "video_url": "blob:https://www.xiaohongshu.com/abc-123",
  "media_type": "video"
}
```
❌ blob URL 无法下载或保存

**改造后**:
```json
{
  "video_url": "http://sns-video-bd.xhscdn.com/spectrum/1040g0k03kqi67uhg7g5g5os4ugnb89hgl6lhpfg",
  "media_type": "video"
}
```
✅ 真实 CDN URL，可直接下载

---

**下一步**: 开始实施 Phase 1 - 基础集成
