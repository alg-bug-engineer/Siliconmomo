# 视频 URL 提取功能 - 实施完成

**完成时间**: 2026-02-06
**实施内容**: API-based 视频 CDN URL 提取
**状态**: ✅ Phase 1 基础集成已完成

---

## 🎯 实施内容

### ⚠️ 重要修复

**问题**: 最初从 `temp.py` 直接导入 `XiaoHongShuClient` 时报错：
```
Can't instantiate abstract class XiaoHongShuClient with abstract method update_cookies
```

**原因**:
1. temp.py 中的 `XiaoHongShuClient` 继承自 `AbstractApiClient`
2. 抽象类要求实现 `update_cookies` 方法，但 temp.py 中未实现
3. temp.py 只是参考文件，不应直接导入到项目中

**解决方案**:
1. ✅ 创建 `core/xhs_api_client.py` - 项目内部的 API 客户端
2. ✅ 从 temp.py 和 MediaCrawler 中提取必要代码
3. ✅ 实现 `update_cookies` 方法（从 MediaCrawler 参考）
4. ✅ 移除抽象类继承，简化实现
5. ✅ 修改 `actions/interaction.py` 导入路径为 `core.xhs_api_client`

### 已完成的修改

#### 1. `core/xhs_api_client.py` - 新增 API 客户端文件 ⭐

**完整的小红书 API 客户端实现**（参考 temp.py 和 MediaCrawler）:

- **异常类**:
  - `DataFetchError` - 数据获取失败异常
  - `IPBlockError` - IP 被封禁异常

- **签名函数**:
  - `sign()` - 生成请求签名 (X-S, X-T, x-S-Common, X-B3-Traceid)
  - `get_b3_trace_id()` - 生成追踪 ID

- **XiaoHongShuClient 类**:
  - `__init__()` - 初始化客户端（headers, cookies, playwright_page）
  - `_pre_headers()` - 自动调用浏览器签名函数生成请求头
  - `request()` - 通用请求方法（支持重试，最多3次）
  - `get()` - GET 请求（自动签名）
  - `post()` - POST 请求（自动签名）
  - `get_note_by_id()` - 获取笔记详情 API
  - `update_cookies()` - 更新 cookies（登录后调用）

**关键技术**:
- ✅ 完全独立，不依赖 temp.py
- ✅ 实现了抽象方法 `update_cookies`（解决实例化错误）
- ✅ 使用 @retry 装饰器自动重试（最多3次）
- ✅ 调用浏览器中的 `window._webmsxyw` 生成签名
- ✅ 支持验证码检测和 IP 封禁检测

#### 2. `actions/interaction.py` - 核心文件

**新增导入**:
```python
import re
from urllib.parse import urlparse, parse_qs
from core.xhs_api_client import XiaoHongShuClient  # 从项目内部导入
```

**新增字段** (在 `__init__` 方法):
```python
# API 客户端（懒加载，仅在需要时初始化）
self.xhs_client = None
```

**新增方法**:

1. **`_init_api_client()`** - API 客户端初始化
   - 从浏览器上下文获取 cookies
   - 构造请求头 (User-Agent, Cookie, Referer)
   - 初始化 XiaoHongShuClient
   - 支持懒加载（仅在需要时初始化一次）

2. **`_extract_video()`** - 重写为 API-based 方法
   - 步骤1: 从 URL 提取 note_id
   - 步骤2: DOM 快速判断是否为视频笔记
   - 步骤3: 初始化 API 客户端（懒加载）
   - 步骤4: 从 URL 或 __INITIAL_STATE__ 获取 xsec_token
   - 步骤5: 调用 API 获取笔记详情
   - 步骤6: 提取视频 CDN URL

3. **`_extract_video_url_from_note()`** - 辅助方法
   - 方法1: 从 origin_video_key 构造 CDN URL (首选)
   - 方法2: 从 h264 stream 获取 master_url (备选)
   - 完整的错误处理和日志记录

#### 3. `test_video_extraction.py` - 测试脚本

独立的测试脚本，用于验证视频 URL 提取功能：
- ✅ 使用项目内部的 `core.xhs_api_client`
- ✅ 模拟真实浏览流程
- ✅ 测试 API 调用
- ✅ 验证 CDN URL 可访问性
- ✅ 详细的日志输出

---

## 🧪 测试方法

### 方法 1: 使用测试脚本（推荐）

```bash
# 运行独立测试脚本
python test_video_extraction.py
```

**测试步骤**:
1. 脚本会启动浏览器并打开小红书首页
2. 手动登录小红书账号
3. 搜索 "AI工具" 或其他关键词
4. **重要**: 点击一个**视频笔记**进入详情页
5. 回到终端按回车继续测试
6. 脚本会自动提取并验证视频 CDN URL

**预期输出**:
```
============================================================
视频 URL 提取功能测试
============================================================

1. 打开小红书首页...
⚠️  请在浏览器中登录小红书账号
⚠️  登录完成后，在小红书搜索 'AI工具' 并点击一个**视频笔记**
⚠️  进入视频详情页后，在终端按回车继续...

2. 当前页面: https://www.xiaohongshu.com/explore/6788786b...
   Note ID: 6788786b000000001203e6b0

3. 检查笔记类型...
✅ 确认为视频笔记

4. 初始化 API 客户端...
✅ API 客户端初始化成功

5. 获取 xsec_token...
✅ 从 URL 获取 token: ABC123...

6. 调用 API 获取笔记详情...
✅ API 调用成功
   笔记类型: video
   笔记标题: AI工具推荐...

7. 提取视频 CDN URL...
✅ 成功提取 CDN URL (origin_video_key):
   http://sns-video-bd.xhscdn.com/spectrum/1040g0k03kqi67uhg7g5g5os4ugnb89hgl6lhpfg

8. 验证 CDN URL 可访问性...
✅ CDN URL 可访问
   Content-Type: video/mp4
   Content-Length: 12.34 MB

============================================================
测试完成！
============================================================
```

### 方法 2: 运行主程序

```bash
# 运行主程序（集成测试）
python main.py
```

**观察日志**:

当程序遇到视频笔记时，会输出以下日志：

```
[INFO] ✅ [API客户端] 初始化成功
[INFO] 📸 [抓取] ID:6788786b... | videox1 | 评论x5
[INFO] 📹 [视频提取] 使用 origin_video_key: spectrum/1040g0k03kqi67...
[INFO] ✅ [视频提取] CDN URL: http://sns-video-bd.xhscdn.com/spectrum/...
[INFO] 💾 [知识库-缓存] +1 新素材: AI工具推荐... | 视频x1 | 评论x5 (缓冲区:1)
```

**验证数据**:

检查 `data/inspiration.json` 中保存的数据：

```bash
# 查看最新保存的视频素材
python3 -c "
import json
with open('data/inspiration.json', 'r') as f:
    data = json.load(f)
    videos = [item for item in data if item['media_type'] == 'video']
    if videos:
        latest = videos[-1]
        print(f'标题: {latest[\"title\"][:30]}...')
        print(f'类型: {latest[\"media_type\"]}')
        print(f'视频URL: {latest[\"video_url\"]}')
        print(f'评论数: {len(latest[\"comments\"])}')
    else:
        print('暂无视频素材')
"
```

**预期输出**:
```
标题: AI工具推荐...
类型: video
视频URL: http://sns-video-bd.xhscdn.com/spectrum/1040g0k03kqi67uhg7g5g5os4ugnb89hgl6lhpfg
评论数: 5
```

---

## 🔍 技术细节

### 视频 URL 提取流程

```
┌─────────────────────────────────────────────────────────────┐
│ 1. 用户浏览视频笔记                                            │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. DOM 快速判断 (data-type="video")                          │
│    - 如果不是视频，直接返回空字符串                              │
│    - 避免不必要的 API 调用                                     │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. 懒加载初始化 API 客户端                                      │
│    - 从浏览器上下文获取 cookies                                 │
│    - 构造请求头 (User-Agent, Cookie, Referer)                │
│    - 初始化 XiaoHongShuClient (仅初始化一次)                   │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ 4. 获取 xsec_token                                           │
│    - 优先从 URL 参数提取 (?xsec_token=...)                    │
│    - 备选从 window.__INITIAL_STATE__ 提取                     │
│    - 兜底使用空 token (有风险，可能被拦截)                       │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ 5. 调用小红书 API                                             │
│    - 端点: POST /api/sns/web/v1/feed                         │
│    - 参数: note_id, xsec_source, xsec_token                 │
│    - 自动签名: X-S, X-T headers (由 temp.py 处理)            │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ 6. 从 API 响应提取视频 URL                                     │
│    - 方法1: origin_video_key (首选，无水印)                    │
│      构造: http://sns-video-bd.xhscdn.com/{key}              │
│    - 方法2: h264 master_url (备选，可能带水印)                 │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ 7. 保存到知识库                                                │
│    - media_type: "video"                                     │
│    - video_url: CDN URL (可直接下载/播放)                      │
│    - 批量写入缓冲区 (5条或60秒刷新)                             │
└─────────────────────────────────────────────────────────────┘
```

### API 响应结构

```json
{
  "items": [{
    "note_card": {
      "note_id": "6788786b000000001203e6b0",
      "type": "video",
      "title": "AI工具推荐...",
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

### 错误处理策略

| 场景 | 处理方式 | 影响 |
|------|----------|------|
| API 客户端初始化失败 | 记录警告日志，跳过视频提取 | 视频URL为空，其他数据正常 |
| xsec_token 缺失 | 使用空token尝试调用 | 可能被拦截，记录警告 |
| API 调用失败 | 记录错误日志，返回空URL | 视频URL为空，其他数据正常 |
| origin_video_key 缺失 | 尝试h264 master_url | 可能获取带水印版本 |
| 两种方法都失败 | 记录警告，返回空URL | 视频URL为空，其他数据正常 |

**设计理念**: **优雅降级**，即使视频 URL 提取失败，也不影响图片、评论等其他数据的抓取。

---

## 📊 数据结构变化

### 改造前 (DOM-based)

```json
{
  "title": "AI工具推荐",
  "media_type": "video",
  "video_url": "blob:https://www.xiaohongshu.com/abc-123-def",
  "image_urls": [],
  "comments": [...]
}
```
❌ **问题**: blob URL 是临时内存地址，无法下载或保存

### 改造后 (API-based)

```json
{
  "title": "AI工具推荐",
  "media_type": "video",
  "video_url": "http://sns-video-bd.xhscdn.com/spectrum/1040g0k03kqi67uhg7g5g5os4ugnb89hgl6lhpfg",
  "image_urls": [],
  "comments": [...]
}
```
✅ **优势**: 真实 CDN URL，可直接下载、播放、分享

---

## ⚠️ 注意事项

### 1. API 频率限制

- 小红书可能限制 API 调用频率
- **当前策略**: 只在检测到视频类型时才调用 API
- **未来优化**: 可添加请求间隔控制

### 2. xsec_token 时效性

- token 可能有时效限制（具体时长未知，估计 1小时）
- **当前策略**: 优先使用 URL 中的 token（最新）
- **降级方案**: token 失效时记录警告但继续运行

### 3. 登录态依赖

- API 调用需要登录 cookies
- **建议**: 定期检查登录状态
- **处理**: 登录失效时暂停 API 调用，等待重新登录

### 4. 网络异常

- API 调用可能超时或失败
- **当前策略**: 30秒超时，失败时记录错误日志
- **未来优化**: 可添加重试机制 (3次)

---

## 🚀 后续优化方向 (Phase 2)

### 1. 鲁棒性优化

- [ ] 添加 API 调用重试机制 (3次，间隔1秒)
- [ ] token 失效时自动从新页面获取
- [ ] 网络异常时的优雅降级

### 2. 性能优化

- [ ] 缓存 note_id → video_url 映射（避免重复调用）
- [ ] API 客户端连接池复用
- [ ] 视频 URL 提取与评论抓取并行

### 3. 功能增强

- [ ] 支持下载视频到本地（可选）
- [ ] 提取视频封面图（thumbnail）
- [ ] 记录视频时长、分辨率等元信息

### 4. 监控与统计

- [ ] 统计 API 调用成功率
- [ ] 记录平均响应时间
- [ ] 跟踪 token 失效频率

---

## 📋 快速排查清单

如果视频 URL 提取失败，按以下顺序排查：

1. **检查是否为视频笔记**
   - 查看日志是否有 "确认为视频笔记"
   - 手动检查页面是否真的是视频（不是图文）

2. **检查 API 客户端是否初始化成功**
   - 查找日志: `✅ [API客户端] 初始化成功`
   - 如果失败，检查 cookies 是否有效

3. **检查 xsec_token 是否获取到**
   - 查找日志: `从 URL 获取 token` 或 `从 __INITIAL_STATE__ 获取 token`
   - 如果都没有，可能是访问方式问题（非搜索进入）

4. **检查 API 调用是否成功**
   - 查找日志: `API 调用成功`
   - 如果失败，查看错误信息（可能是 token 失效或频率限制）

5. **检查响应数据结构**
   - 查找日志: `使用 origin_video_key` 或 `使用 h264 master_url`
   - 如果都没有，API 响应可能不包含视频数据

6. **验证 CDN URL 可访问性**
   - 复制日志中的 CDN URL
   - 在浏览器中访问或使用 curl 测试
   ```bash
   curl -I "http://sns-video-bd.xhscdn.com/spectrum/..."
   # 应返回 200 OK
   ```

---

## 📚 相关文档

- [视频URL提取方案分析.md](./视频URL提取方案分析.md) - 详细的技术方案和设计文档
- [知识库批量写入优化说明.md](./知识库批量写入优化说明.md) - 批量写入缓冲区机制
- `temp.py` - XiaoHongShuClient 实现（API 签名、请求封装）

---

## ✅ 验收标准

- [x] ✅ 代码通过语法检查 (py_compile)
- [ ] 🧪 测试脚本成功提取视频 CDN URL
- [ ] 🧪 CDN URL 可通过 curl/浏览器访问
- [ ] 🧪 主程序运行时能正确保存视频 URL 到 inspiration.json
- [ ] 📊 数据文件中 video_url 不再是 blob URL

---

**下一步**: 运行 `test_video_extraction.py` 进行功能验证
