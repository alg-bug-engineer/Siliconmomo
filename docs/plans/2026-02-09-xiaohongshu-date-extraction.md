# Xiaohongshu Date Extraction and Deduplication Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add publish date extraction, deduplication, and environment recovery to Xiaohongshu deep research

**Architecture:** Extend ResearchAgent with date extraction method, add visited note ID tracking, implement environment drift recovery with search replay

**Tech Stack:** Python 3.x, Playwright, asyncio, regex

---

## Task 1: Add Date Extraction Method

**Files:**
- Modify: `core/researcher.py:209-266`

**Step 1: Add the `_extract_publish_date()` method**

Add this method after `_extract_video()` method (around line 346):

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

**Step 2: Update `_extract_content_from_page()` to add publish_date field**

Find the `detail` dictionary initialization (line 211-218) and add `publish_date`:

```python
detail = {
    "url": self.page.url,
    "title": "", "content": "",
    "publish_date": "",  # 新增：发布日期
    "image_urls": [], "video_url": "", "video_local_path": "", "media_type": "image",
    "comments": [],
    "ocr_results": {},
    "asr_results": ""
}
```

**Step 3: Call `_extract_publish_date()` in content extraction**

Add after extracting title and content (around line 224):

```python
if await self.page.locator(SELECTORS["detail_desc"]).count() > 0:
    detail["content"] = await self.page.locator(SELECTORS["detail_desc"]).inner_text()

# 提取发布日期
detail["publish_date"] = await self._extract_publish_date()

detail["image_urls"] = await self._extract_images()
```

**Step 4: Test manually**

Since this requires browser interaction, manual testing is needed:
1. Run the research agent on a test keyword
2. Check that `research_data_{keyword}.json` contains `publish_date` field
3. Verify dates are extracted or show `[发布日期抓取失败]`

**Step 5: Commit**

```bash
git add core/researcher.py
git commit -m "feat: add publish date extraction from post detail pages

- Add _extract_publish_date() method with fallback selectors
- Integrate date extraction into _extract_content_from_page()
- Return '[发布日期抓取失败]' on extraction failure"
```

---

## Task 2: Add Deduplication Infrastructure

**Files:**
- Modify: `core/researcher.py:29-43`

**Step 1: Add visited_note_ids set in __init__**

In the `__init__` method (around line 43), add:

```python
self.output_dir = DEEP_RESEARCH_OUTPUT_DIR / datetime.now().strftime("%Y%m%d_%H%M%S")
self.output_dir.mkdir(parents=True, exist_ok=True)
self.recorder.log("info", f"📂 [深度研究] 输出目录: {self.output_dir}")

self.video_downloader = VideoDownloader(save_dir=self.output_dir / "videos")
self.visited_note_ids = set()  # 新增：已访问帖子ID集合
```

**Step 2: Add `_extract_note_id_from_url()` helper method**

Add this method after `_extract_publish_date()`:

```python
def _extract_note_id_from_url(self, url: str) -> str:
    """从 URL 中提取 note ID

    Args:
        url: 帖子 URL（如 https://www.xiaohongshu.com/explore/690b1814...)

    Returns:
        note ID（如 690b1814...），提取失败返回空字符串
    """
    match = re.search(r'/explore/([a-f0-9]+)', url)
    return match.group(1) if match else ""
```

**Step 3: Add `_find_unvisited_note()` helper method**

Add this method after `_extract_note_id_from_url()`:

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

**Step 4: Commit**

```bash
git add core/researcher.py
git commit -m "feat: add deduplication infrastructure

- Add visited_note_ids set to track processed posts
- Add _extract_note_id_from_url() helper
- Add _find_unvisited_note() to filter visited posts"
```

---

## Task 3: Add Environment Drift Recovery

**Files:**
- Modify: `core/researcher.py:47-139`

**Step 1: Add `_recover_from_environment_drift()` method**

Add this method after the helper methods from Task 2:

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

**Step 2: Commit**

```bash
git add core/researcher.py
git commit -m "feat: add environment drift recovery

- Add _recover_from_environment_drift() method
- Navigate to homepage and re-execute search on drift
- Return success/failure status for caller handling"
```

---

## Task 4: Integrate Deduplication and Recovery into Main Loop

**Files:**
- Modify: `core/researcher.py:47-139`

**Step 1: Add loop state variables**

At the start of `run_deep_research()`, before the main loop (around line 62):

```python
# 执行搜索
await self._perform_search(search_term)

# 模拟真实用户浏览行为：逐个点击帖子
research_data = []
posts_processed = 0
consecutive_no_new_posts = 0  # 新增：连续未找到新帖子的次数
MAX_RETRY_WITHOUT_NEW_POST = 5  # 新增：最大重试次数

while posts_processed < DEEP_RESEARCH_POST_LIMIT:
```

**Step 2: Replace environment check with recovery logic**

Replace lines 65-67:

```python
# OLD CODE:
# if "xiaohongshu.com" not in self.page.url or "search_result" not in self.page.url:
#     self.recorder.log("error", f"❌ [深度研究] 环境偏离: {self.page.url}")
#     break

# NEW CODE:
# 1. 检查环境
if "xiaohongshu.com" not in self.page.url or "search_result" not in self.page.url:
    if not await self._recover_from_environment_drift(search_term):
        break  # 恢复失败，结束研究
    continue  # 恢复成功，重新开始循环
```

**Step 3: Replace random note selection with deduplication logic**

Replace lines 80-86:

```python
# OLD CODE:
# # 3. 选择一个帖子并点击（研究模式：加速浏览）
# target_note = random.choice(notes[:6])  # 从前6个中随机选择
# await target_note.scroll_into_view_if_needed()
# await asyncio.sleep(random.uniform(0.3, 0.5))  # 减半延迟
#
# self.recorder.log("info", f"👆 [深度研究] 点击帖子 {posts_processed + 1}/{DEEP_RESEARCH_POST_LIMIT}")
# await target_note.click()

# NEW CODE:
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

await target_note.scroll_into_view_if_needed()
await asyncio.sleep(random.uniform(0.3, 0.5))

self.recorder.log("info", f"👆 [深度研究] 点击帖子 {posts_processed + 1}/{DEEP_RESEARCH_POST_LIMIT} (ID: {note_id[:8]}...)")
await target_note.click()
```

**Step 4: Commit**

```bash
git add core/researcher.py
git commit -m "feat: integrate deduplication and recovery into main loop

- Add consecutive_no_new_posts counter with MAX_RETRY limit
- Replace environment check with recovery mechanism
- Replace random selection with deduplication logic
- Track visited note IDs to skip duplicates"
```

---

## Task 5: Update Report Generation with Publish Dates

**Files:**
- Modify: `core/researcher.py:470-598`

**Step 1: Add publish_date to post metadata in prompt**

Find the loop in `_prepare_llm_prompt()` (around line 521-526) and update:

```python
# OLD CODE:
# for i, post in enumerate(research_data, 1):
#     prompt_parts.append(f"### 📄 帖子 {i}\n\n")
#     prompt_parts.append(f"- **URL**: {post.get('url', 'N/A')}\n")
#     prompt_parts.append(f"- **标题**: {post.get('title', '(无标题)')}\n")
#     prompt_parts.append(f"- **类型**: {post.get('media_type', 'image')}\n\n")

# NEW CODE:
for i, post in enumerate(research_data, 1):
    prompt_parts.append(f"### 📄 帖子 {i}\n\n")
    prompt_parts.append(f"- **URL**: {post.get('url', 'N/A')}\n")
    prompt_parts.append(f"- **标题**: {post.get('title', '(无标题)')}\n")
    prompt_parts.append(f"- **发布时间**: {post.get('publish_date', '[发布日期抓取失败]')}\n")  # 新增
    prompt_parts.append(f"- **类型**: {post.get('media_type', 'image')}\n\n")
```

**Step 2: Update reference format example**

Find the reference format section (around line 588-593) and update:

```python
# OLD CODE:
# prompt_parts.append("### 参考文献格式示例：\n")
# prompt_parts.append("```\n")
# prompt_parts.append("## 参考文献\n\n")
# prompt_parts.append("[1] 小红书用户. 帖子标题. 小红书, 发布日期. [URL]\n")
# prompt_parts.append("[2] 小红书用户. 帖子标题. 小红书, 发布日期. [URL]\n")

# NEW CODE:
prompt_parts.append("### 参考文献格式示例：\n")
prompt_parts.append("```\n")
prompt_parts.append("## 参考文献\n\n")
prompt_parts.append("[1] 小红书用户. 帖子标题. 小红书, 昨天 14:53 福建. [URL]\n")
prompt_parts.append("[2] 小红书用户. 帖子标题. 小红书, 2026-02-08 10:20 北京. [URL]\n")
prompt_parts.append("...\n")
```

**Step 3: Commit**

```bash
git add core/researcher.py
git commit -m "feat: integrate publish dates into report generation

- Add publish_date to post metadata in LLM prompt
- Update reference format examples to show date formats
- LLM will now use actual publish dates in citations"
```

---

## Task 6: Manual Integration Testing

**Files:**
- N/A (testing only)

**Step 1: Run full research workflow**

```bash
python run_research.py
```

**Step 2: Verify results**

Check the output in `data/deep_research_reports/`:

1. **Data file verification:**
   - Open `research_data_{keyword}.json`
   - Verify each post has `publish_date` field
   - Dates should be like "昨天 14:53 福建" or "[发布日期抓取失败]"

2. **Deduplication verification:**
   - Check logs for "📜 [去重]" messages
   - Verify no duplicate note IDs in the data file

3. **Recovery verification:**
   - If environment drift occurred, check for:
     - "⚠️ [环境偏离]" warning
     - "🔄 [恢复]" recovery attempt
     - "✅ [恢复] 环境恢复成功" confirmation

4. **Report verification:**
   - Open `research_report_{keyword}.md`
   - Check that references include dates (not "[发布日期不详]")
   - Format should be: `[N] 小红书用户. 标题. 小红书, 昨天 14:53 福建. [URL]`

**Step 3: Document test results**

Create a test summary in commit message format:

```
test: verify date extraction and deduplication features

Tested with keyword: [your test keyword]
Results:
- ✅ Publish dates extracted: X/Y posts
- ✅ Deduplication working: 0 duplicates found
- ✅ Environment recovery: [occurred/not occurred]
- ✅ Report references include dates

All features working as expected.
```

**Step 4: Final commit**

```bash
git add -A
git commit -m "test: verify date extraction and deduplication features

[paste your test summary here]"
```

---

## Post-Implementation Checklist

- [ ] All 6 tasks completed and committed
- [ ] Manual testing shows publish dates in reports
- [ ] No duplicate posts in research data
- [ ] Environment recovery works when tested
- [ ] Code follows DRY principles
- [ ] All error cases handled gracefully
- [ ] Ready for PR review

---

## Expected Final State

**Files Modified:** `core/researcher.py`

**New Methods Added:**
1. `_extract_publish_date()` - Extract dates from detail page
2. `_extract_note_id_from_url()` - Parse note ID from URL
3. `_find_unvisited_note()` - Find first unvisited post
4. `_recover_from_environment_drift()` - Recovery logic

**New Instance Variables:**
1. `self.visited_note_ids` - Set of processed note IDs

**Modified Methods:**
1. `__init__()` - Initialize visited_note_ids
2. `run_deep_research()` - Integrate dedup and recovery
3. `_extract_content_from_page()` - Add publish_date extraction
4. `_prepare_llm_prompt()` - Include dates in report

**Report Output:**
- References now show actual publish dates
- Format: `[N] 小红书用户. 标题. 小红书, 昨天 14:53 福建. [URL]`
- Fallback: `[N] 小红书用户. 标题. 小红书, [发布日期抓取失败]. [URL]`
