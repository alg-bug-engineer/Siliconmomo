# 小红书帖子发布日期抓取与去重优化设计

**设计日期**: 2026-02-09
**目标**: 优化深度研究功能，新增发布日期抓取，实现去重机制，处理环境偏离场景

---

## 1. 背景与目标

### 当前问题
1. 研究报告中的参考文献显示 `[发布日期不详]`，缺乏时效性信息
2. 环境偏离时（URL 不在 search_result 页面）直接中断研究
3. 可能重复抓取同一帖子，浪费配额和时间

### 解决目标
1. 从详情页抓取帖子发布日期（格式如 "昨天 14:53 福建"）
2. 环境偏离时自动恢复（导航回主页 → 重新搜索）
3. 基于 note ID 实现去重，跳过已抓取帖子

---

## 2. 核心设计

### 2.1 数据结构扩展

#### 扩展帖子数据字典
在 `_extract_content_from_page()` 返回的 `detail` 字典中新增：

```python
detail = {
    "url": self.page.url,
    "title": "",
    "content": "",
    "publish_date": "",  # 新增：发布日期
    "image_urls": [],
    "video_url": "",
    "video_local_path": "",
    "media_type": "image",
    "comments": [],
    "ocr_results": {},
    "asr_results": ""
}
```

#### 添加已访问帖子集合
在 `ResearchAgent.__init__()` 中初始化：

```python
self.visited_note_ids = set()  # 已访问的 note ID 集合
```

---

### 2.2 发布日期抓取

#### 新增方法：`_extract_publish_date()`

```python
async def _extract_publish_date(self) -> str:
    """从详情页提取发布日期

    Returns:
        发布日期字符串（如 "昨天 14:53 福建"）
        如果提取失败，返回 "[发布日期抓取失败]"
    """
    try:
        # 尝试多个可能的选择器（容错）
        selectors = [
            '.bottom-container .date',
            '.notedetail-menu + .date',
            '[class*="bottom"] .date'
        ]
        for selector in selectors:
            element = self.page.locator(selector).first
            if await element.count() > 0:
                date_text = await element.inner_text()
                if date_text.strip():
                    return date_text.strip()
        return "[发布日期抓取失败]"
    except Exception as e:
        self.recorder.log("warning", f"日期提取异常: {e}")
        return "[发布日期抓取失败]"
```

#### 集成到内容提取流程
在 `_extract_content_from_page()` 中调用：

```python
# 提取发布日期
detail["publish_date"] = await self._extract_publish_date()
```

---

### 2.3 去重机制

#### 新增辅助方法：`_extract_note_id_from_url()`

```python
def _extract_note_id_from_url(self, url: str) -> str:
    """从 URL 中提取 note ID

    Args:
        url: 帖子 URL（如 https://www.xiaohongshu.com/explore/690b1814000000000703527b）

    Returns:
        note ID（如 690b1814000000000703527b），提取失败返回空字符串
    """
    match = re.search(r'/explore/([a-f0-9]+)', url)
    return match.group(1) if match else ""
```

#### 新增方法：`_find_unvisited_note()`

```python
async def _find_unvisited_note(self, notes):
    """从笔记列表中找到第一个未访问的笔记

    Args:
        notes: 帖子元素列表

    Returns:
        (target_note, note_id) 元组，未找到则返回 (None, None)
    """
    for note in notes:
        href = await note.get_attribute('href')
        note_id = self._extract_note_id_from_url(href or "")
        if note_id and note_id not in self.visited_note_ids:
            return note, note_id
    return None, None
```

#### 主循环集成去重逻辑

```python
# 3. 寻找未访问的帖子
target_note, note_id = await self._find_unvisited_note(notes[:6])

if not target_note:
    consecutive_no_new_posts += 1
    if consecutive_no_new_posts >= MAX_RETRY_WITHOUT_NEW_POST:
        self.recorder.log("warning", "⚠️ [深度研究] 连续多次无新帖子，可能已抓取完所有相关内容")
        break
    # 当前视口全是已抓取的，滚动加载新内容
    self.recorder.log("info", "📜 [去重] 当前视口无新帖子，滚动加载...")
    await self.human.human_scroll(random.randint(800, 1200))
    await asyncio.sleep(random.uniform(1.5, 2.5))
    continue

# 找到新帖子，重置计数器并记录访问
consecutive_no_new_posts = 0
self.visited_note_ids.add(note_id)
```

---

### 2.4 环境偏离处理

#### 新增方法：`_recover_from_environment_drift()`

```python
async def _recover_from_environment_drift(self, search_term: str) -> bool:
    """环境偏离后的恢复逻辑

    当检测到不在 search_result 页面时，导航回主页并重新搜索

    Args:
        search_term: 搜索关键词

    Returns:
        True 表示恢复成功，False 表示恢复失败
    """
    try:
        self.recorder.log("warning", f"⚠️ [环境偏离] 当前URL: {self.page.url}")
        self.recorder.log("info", "🔄 [恢复] 导航回主页并重新搜索...")

        # 导航回主页
        await self.page.goto("https://www.xiaohongshu.com/explore")
        await asyncio.sleep(2)

        # 重新执行搜索
        await self._perform_search(search_term)

        self.recorder.log("info", "✅ [恢复] 环境恢复成功")
        return True
    except Exception as e:
        self.recorder.log("error", f"❌ [恢复] 环境恢复失败: {e}")
        return False
```

#### 主循环集成恢复机制

```python
# 1. 检查环境
if "xiaohongshu.com" not in self.page.url or "search_result" not in self.page.url:
    if not await self._recover_from_environment_drift(search_term):
        break  # 恢复失败，结束研究
    continue  # 恢复成功，重新开始循环
```

---

### 2.5 报告生成集成

#### 修改 LLM 提示词构建
在 `_prepare_llm_prompt()` 中添加发布日期展示：

```python
for i, post in enumerate(research_data, 1):
    prompt_parts.append(f"### 📄 帖子 {i}\n\n")
    prompt_parts.append(f"- **URL**: {post.get('url', 'N/A')}\n")
    prompt_parts.append(f"- **标题**: {post.get('title', '(无标题)')}\n")
    prompt_parts.append(f"- **发布时间**: {post.get('publish_date', '[发布日期抓取失败]')}\n")  # 新增
    prompt_parts.append(f"- **类型**: {post.get('media_type', 'image')}\n\n")
```

#### 更新参考文献格式示例

```python
prompt_parts.append("### 参考文献格式示例：\n")
prompt_parts.append("```\n")
prompt_parts.append("## 参考文献\n\n")
prompt_parts.append("[1] 小红书用户. 帖子标题. 小红书, 昨天 14:53 福建. [URL]\n")
prompt_parts.append("[2] 小红书用户. 帖子标题. 小红书, 2026-02-08 10:20 北京. [URL]\n")
prompt_parts.append("```\n\n")
```

---

## 3. 错误处理与边界情况

### 3.1 防止无限循环
添加连续未找到新帖子的计数器：

```python
consecutive_no_new_posts = 0
MAX_RETRY_WITHOUT_NEW_POST = 5  # 连续5次未找到新帖子则终止
```

### 3.2 日期提取容错
- 尝试多个 CSS 选择器（应对 DOM 结构变化）
- 验证提取内容非空
- 异常时返回占位符 `[发布日期抓取失败]`

### 3.3 环境恢复容错
- 捕获导航异常
- 恢复失败时优雅终止研究（避免无限重试）

---

## 4. 数据流图

```
开始研究
  ↓
执行搜索 (search_term)
  ↓
主循环开始 ←─────────────┐
  ↓                      │
检查环境                 │
  ├─ 偏离 → 恢复 ────────┤
  └─ 正常                │
      ↓                  │
  获取视口帖子           │
      ↓                  │
  查找未访问帖子         │
      ├─ 无 → 滚动 ─────┤
      └─ 有              │
          ↓              │
      点击帖子           │
          ↓              │
      提取内容           │
      (含发布日期)       │
          ↓              │
      记录到集合         │
          ↓              │
      关闭详情           │
          ↓              │
  posts_processed++ ─────┤
          ↓
达到限制？
  ├─ 否 ────────────────┘
  └─ 是
      ↓
  生成报告
      ↓
  保存报告
      ↓
    结束
```

---

## 5. 实现要点

### 5.1 修改的文件
- `core/researcher.py`: 主要修改文件

### 5.2 新增方法
- `_extract_publish_date()`: 提取发布日期
- `_extract_note_id_from_url()`: 提取 note ID
- `_find_unvisited_note()`: 查找未访问帖子
- `_recover_from_environment_drift()`: 环境恢复

### 5.3 修改的方法
- `__init__()`: 添加 `visited_note_ids` 集合
- `run_deep_research()`: 集成去重和恢复逻辑
- `_extract_content_from_page()`: 调用日期提取
- `_prepare_llm_prompt()`: 展示发布日期

### 5.4 关键常量
```python
MAX_RETRY_WITHOUT_NEW_POST = 5  # 最大连续无新帖子次数
```

---

## 6. 测试计划

### 6.1 功能测试
- [ ] 发布日期正确提取（相对时间格式）
- [ ] 发布日期提取失败时使用占位符
- [ ] 去重机制生效（跳过已访问帖子）
- [ ] 环境偏离后成功恢复
- [ ] 视口无新帖子时正确滚动

### 6.2 边界测试
- [ ] 搜索结果少于 `DEEP_RESEARCH_POST_LIMIT` 的情况
- [ ] 连续5次无新帖子后正确终止
- [ ] 环境恢复失败时优雅退出
- [ ] 日期元素不存在时的容错

### 6.3 集成测试
- [ ] 报告中正确显示发布日期
- [ ] 参考文献格式符合预期
- [ ] 整体研究流程正常运行

---

## 7. 成功标准

1. ✅ 报告参考文献中显示真实发布日期（如 "昨天 14:53 福建"）
2. ✅ 日期抓取失败时显示 `[发布日期抓取失败]`
3. ✅ 不重复抓取同一帖子
4. ✅ 环境偏离后自动恢复并继续研究
5. ✅ 无新帖子时正确终止研究

---

**设计审批**: ✅ 已通过用户确认
**实现开始日期**: 2026-02-09
