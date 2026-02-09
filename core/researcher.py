import asyncio
import os
from datetime import datetime
import random
import re
from pathlib import Path
import json
import traceback

import httpx
from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError

from config.settings import (
    DEEP_RESEARCH_ENABLED,
    DEEP_RESEARCH_POST_LIMIT,
    DEEP_RESEARCH_LLM_MODEL,
    DEEP_RESEARCH_COMMENT_LIMIT,
    DEEP_RESEARCH_OUTPUT_DIR,
    SEARCH_KEYWORDS,
    BASE_URL,
    SELECTORS,
    ASR_SERVER_URL
)
from core.browser_manager import BrowserManager
from core.llm_client import LLMClient
from core.human_motion import HumanMotion
from core.video_downloader import VideoDownloader

class ResearchAgent:
    def __init__(self, browser_manager: BrowserManager, llm_client: LLMClient, recorder):
        self.browser_manager = browser_manager
        self.llm_client = llm_client
        self.page = browser_manager.page
        self.recorder = recorder  # 统一使用 recorder 日志系统
        self.human = HumanMotion(self.page)

        if not DEEP_RESEARCH_ENABLED:
            self.recorder.log("info", "深度研究模式未启用")
            return

        self.output_dir = DEEP_RESEARCH_OUTPUT_DIR / datetime.now().strftime("%Y%m%d_%H%M%S")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.recorder.log("info", f"📂 [深度研究] 输出目录: {self.output_dir}")

        self.video_downloader = VideoDownloader(save_dir=self.output_dir / "videos")
        self.visited_note_ids = set()  # 新增：已访问帖子ID集合

    async def run_deep_research(self, keyword: str = None):
        if not DEEP_RESEARCH_ENABLED:
            self.recorder.log("info", "Deep research mode is disabled. Skipping run.")
            return

        self.recorder.log("info", f"📚 [深度研究] 开始深度研究: {keyword if keyword else 'configured keywords'}")

        search_term = keyword if keyword else random.choice(SEARCH_KEYWORDS)

        # 执行搜索
        await self._perform_search(search_term)

        # 模拟真实用户浏览行为：逐个点击帖子
        research_data = []
        posts_processed = 0
        consecutive_no_new_posts = 0  # 新增：连续未找到新帖子的次数
        MAX_RETRY_WITHOUT_NEW_POST = 5  # 新增：最大重试次数

        while posts_processed < DEEP_RESEARCH_POST_LIMIT:
            # 1. 检查环境
            if "xiaohongshu.com" not in self.page.url or "search_result" not in self.page.url:
                if not await self._recover_from_environment_drift(search_term):
                    break  # 恢复失败，结束研究
                continue  # 恢复成功，重新开始循环

            # 2. 寻找视口内的帖子
            notes = await self.page.locator(SELECTORS["note_card"]).all()
            if not notes:
                self.recorder.log("warning", "📍 [深度研究] 视口无帖子，滚动寻找...")
                await self.human.human_scroll(500)
                await asyncio.sleep(2)
                notes = await self.page.locator(SELECTORS["note_card"]).all()
                if not notes:
                    self.recorder.log("error", "❌ [深度研究] 未检测到笔记，结束研究")
                    break

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

            # 4. 等待详情页加载
            try:
                await self.page.wait_for_selector(SELECTORS["note_detail_mask"], timeout=5000)
            except:
                self.recorder.log("warning", "⏱️ [深度研究] 详情页加载超时，跳过此帖")
                await self.page.keyboard.press("Escape")
                continue

            # 5. 提取帖子内容（不调用 LLM，仅提取数据）
            post_data = await self._extract_content_from_page()
            if post_data and post_data.get("content"):
                research_data.append(post_data)
                posts_processed += 1
                self.recorder.log("info", f"✅ [深度研究] 已收集 {posts_processed}/{DEEP_RESEARCH_POST_LIMIT} 个帖子")

            # 6. 关闭详情页，返回搜索结果页（研究模式：快速关闭）
            await asyncio.sleep(random.uniform(0.5, 0.8))  # 减半延迟
            if await self.human.click_element(SELECTORS["btn_close"], "关闭详情"):
                self.recorder.log("debug", "使用按钮关闭详情页")
            else:
                await self.page.keyboard.press("Escape")
                self.recorder.log("debug", "使用 Escape 关闭详情页")

            # 7. 等待返回搜索结果页（研究模式：快速切换）
            await asyncio.sleep(random.uniform(0.5, 1.0))  # 减半延迟

            # 8. 如果还需要更多帖子，偶尔滚动页面加载新内容
            if posts_processed < DEEP_RESEARCH_POST_LIMIT and posts_processed % 3 == 0:
                self.recorder.log("info", "📜 [深度研究] 滚动加载更多帖子...")
                await self.human.human_scroll(random.randint(800, 1200))
                await asyncio.sleep(random.uniform(1.0, 1.5))  # 减半延迟

        # 保存研究数据
        if research_data:
            data_filename = self.output_dir / f"research_data_{search_term}.json"
            with open(data_filename, "w", encoding="utf-8") as f:
                serializable_data = []
                for item in research_data:
                    serializable_item = item.copy()
                    if 'video_local_path' in serializable_item and isinstance(serializable_item['video_local_path'], Path):
                        serializable_item['video_local_path'] = str(serializable_item['video_local_path'])
                    serializable_data.append(serializable_item)
                json.dump(serializable_data, f, ensure_ascii=False, indent=4)
            self.recorder.log("info", f"💾 [深度研究] 原始数据已保存: {data_filename}")

            report = await self._generate_report(research_data)
            await self._save_report(report, search_term)
        else:
            self.recorder.log("warning", "⚠️ [深度研究] 未收集到数据，跳过报告生成")

        self.recorder.log("info", f"🎉 [深度研究] 深度研究完成！共收集 {len(research_data)} 个帖子")


    async def _perform_search(self, keyword: str):
        self.recorder.log("info", f"🔍 [搜索] 开始搜索关键词: '{keyword}'")

        try:
            # 1. 确保在小红书首页
            if "xiaohongshu.com" not in self.page.url or "/search_result" in self.page.url:
                self.recorder.log("info", "🔍 [搜索] 导航到小红书首页...")
                await self.page.goto(BASE_URL)
                await asyncio.sleep(1)

            # 2. 点击搜索框
            await self.human.click_element(SELECTORS["search_input"], "搜索框")
            await asyncio.sleep(random.uniform(0.5, 1.0))

            # 3. 清空并输入关键词
            await self.page.locator(SELECTORS["search_input"]).clear()
            for char in keyword:
                await self.page.keyboard.type(char, delay=random.randint(50, 150))

            # 4. 提交搜索
            self.recorder.log("info", f"🔍 [搜索] 提交搜索: '{keyword}'")
            await self.page.keyboard.press("Enter")

            # 5. 等待搜索结果页面加载（关键！）
            await self.page.wait_for_load_state("networkidle", timeout=15000)

            # 6. 额外等待，确保笔记卡片渲染完成
            await asyncio.sleep(3)

            self.recorder.log("info", f"✅ [搜索] 搜索完成，当前URL: {self.page.url}")
        except Exception as e:
            self.recorder.log("error", f"❌ [搜索] 搜索失败 '{keyword}': {e}")
            raise


    async def _transcribe_video(self, video_local_path: Path) -> str:
        """Sends a local video file to the ASR server for transcription."""
        if not ASR_SERVER_URL:
            self.recorder.log("warning", "ASR_SERVER_URL is not configured. Skipping video transcription.")
            return ""

        if not video_local_path.exists():
            self.recorder.log("warning", f"Video file not found for transcription: {video_local_path}")
            return ""

        self.recorder.log("info", f"Sending {video_local_path.name} to ASR server for transcription...")
        try:
            async with httpx.AsyncClient(timeout=300.0) as client: # Increased timeout for large files
                with open(video_local_path, "rb") as f:
                    files = {'file': (video_local_path.name, f, 'audio/mpeg')} # Assumes mp3, adjust as needed
                    response = await client.post(ASR_SERVER_URL, files=files)
                response.raise_for_status() # Raise an exception for HTTP errors
                
                result = response.json()
                transcription = result.get("transcribed_text", "")
                if transcription:
                    self.recorder.log("info", f"ASR successful for {video_local_path.name}: {transcription[:50]}...")
                else:
                    self.recorder.log("warning", f"ASR returned empty transcription for {video_local_path.name}.")
                return transcription
        except httpx.RequestError as exc:
            self.recorder.log("error", f"ASR request error for {video_local_path.name}: {exc}")
        except httpx.HTTPStatusError as exc:
            self.recorder.log("error", f"ASR HTTP error for {video_local_path.name} - {exc.response.status_code}: {exc.response.text}")
        except Exception as e:
            self.recorder.log("error", f"Unexpected error during ASR for {video_local_path.name}: {e}")
        return ""

    async def _extract_content_from_page(self):
        """提取帖子完整内容：标题、正文、图片、视频、评论"""
        detail = {
            "url": self.page.url,  # 添加当前页面URL
            "title": "", "content": "",
            "publish_date": "",  # 新增：发布日期
            "image_urls": [], "video_url": "", "video_local_path": "", "media_type": "image",
            "comments": [],
            "ocr_results": {},  # Placeholder for OCR
            "asr_results": ""   # Placeholder for ASR
        }
        try:
            if await self.page.locator(SELECTORS["detail_title"]).count() > 0:
                detail["title"] = await self.page.locator(SELECTORS["detail_title"]).inner_text()

            if await self.page.locator(SELECTORS["detail_desc"]).count() > 0:
                detail["content"] = await self.page.locator(SELECTORS["detail_desc"]).inner_text()

            # 提取发布日期
            detail["publish_date"] = await self._extract_publish_date()

            detail["image_urls"] = await self._extract_images()

            # 提取并下载视频
            video_info = await self._extract_video()
            detail["video_url"] = video_info.get("video_url", "")
            detail["video_local_path"] = video_info.get("local_path", "")
            detail["media_type"] = "video" if detail["video_url"] else "image"

            # 执行 ASR 转录（如果有视频）
            if detail["video_local_path"] and os.path.exists(detail["video_local_path"]):
                detail["asr_results"] = await self._transcribe_video(Path(detail["video_local_path"]))

            # OCR Placeholder
            if detail["image_urls"]:
                self.recorder.log("debug", "OCR 功能待开发，当前跳过")
                detail["ocr_results"] = {"status": "skipped", "reason": "OCR service not integrated yet"}

            # 1. 滚动加载更多一级评论 (最多 DEEP_RESEARCH_COMMENT_LIMIT)
            for _ in range(3): # Scroll a few times to get initial comments
                await self._scroll_comment_area()
                await asyncio.sleep(random.uniform(1, 2))

            # 2. 展开所有折叠的二级评论
            await self._expand_all_replies()
            await asyncio.sleep(random.uniform(1, 2))

            # 3. 提取评论
            all_comments = await self._extract_comments()
            detail["comments"] = all_comments[:DEEP_RESEARCH_COMMENT_LIMIT] # Limit comments

            # 提取帖子ID
            url_match = re.search(r'/explore/([a-f0-9]+)', self.page.url)
            note_id = url_match.group(1) if url_match else "unknown"

            media_count = len(detail["image_urls"]) if detail["media_type"] == "image" else 1
            self.recorder.log("info", 
                f"📸 [抓取] ID:{note_id[:8]}... | {detail['media_type']}x{media_count} | 评论x{len(detail['comments'])}")

        except Exception as e:
            self.recorder.log("warning", f"内容提取异常: {e}")
        return detail

    async def _extract_images(self):
        """从详情页DOM提取所有图片URL"""
        try:
            return await self.page.evaluate("""
                () => {
                    const urls = new Set();
                    // 在媒体容器中查找图片
                    const containers = document.querySelectorAll(
                        '.note-detail-mask .swiper-slide img, ' +
                        '.note-detail-mask .media-container img, ' +
                        '.note-detail-mask [class*="carousel"] img, ' +
                        '.note-detail-mask [class*="slider"] img'
                    );
                    containers.forEach(img => {
                        const src = img.src || img.dataset.src || img.getAttribute('data-src') || '';
                        if (src && (src.includes('xhscdn') || src.includes('xiaohongshu') || src.includes('sns-'))
                            && !src.includes('avatar') && !src.includes('emoji')) {
                            urls.add(src);
                        }
                    });
                    // 备选：detail mask 内所有大图
                    if (urls.size === 0) {
                        document.querySelectorAll('.note-detail-mask img').forEach(img => {
                            const src = img.src || img.dataset.src || '';
                            if (src && (src.includes('xhscdn') || src.includes('xiaohongshu'))
                                && !src.includes('avatar') && !src.includes('emoji')
                                && img.naturalWidth > 100) {
                                urls.add(src);
                            }
                        });
                    }
                    return [...urls];
                }
            """) or []
        except Exception as e:
            self.recorder.log("warning", f"图片提取异常: {e}")
            return []

    async def _extract_video(self):
        """
        提取并下载视频
        使用 VideoDownloader 从网页 __INITIAL_STATE__ 提取视频信息并下载
        返回包含 video_url 和 local_path 的字典
        """
        try:
            # 步骤1: DOM 快速判断是否为视频笔记
            is_video = await self.page.evaluate("""
                () => {
                    const noteContainer = document.querySelector('#noteContainer, [data-type="video"]');
                    return noteContainer && noteContainer.getAttribute('data-type') === 'video';
                }
            """)

            if not is_video:
                return {"video_url": "", "local_path": ""}  # 不是视频笔记

            # 步骤2: 获取当前 URL
            current_url = self.page.url
            self.recorder.log("info", f"📹 [视频下载] 检测到视频笔记，开始提取...")

            # 步骤3: 提取视频信息并下载
            result = await self.video_downloader.extract_and_download(current_url)

            if result:
                self.recorder.log("info", f"✅ [视频下载] 成功")
                self.recorder.log("info", f"   URL: {result['video_url'][:60]}...")
                self.recorder.log("info", f"   本地: {result['local_path']}")
                return {
                    "video_url": result["video_url"],
                    "local_path": result["local_path"],
                }
            else:
                self.recorder.log("warning", "⚠️ [视频下载] 提取或下载失败")
                return {"video_url": "", "local_path": ""}

        except Exception as e:
            self.recorder.log("error", f"❌ [视频下载] 异常: {e}")
            return {"video_url": "", "local_path": ""}

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

    def _extract_note_id_from_url(self, url: str) -> str:
        """从 URL 中提取 note ID

        Args:
            url: 帖子 URL（如 https://www.xiaohongshu.com/explore/690b1814...)

        Returns:
            note ID（如 690b1814...），提取失败返回空字符串
        """
        match = re.search(r'/explore/([a-f0-9]+)', url)
        return match.group(1) if match else ""

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

    async def _extract_comments(self):
        """从详情页DOM提取可见评论（一级+二级）"""
        try:
            return await self.page.evaluate("""
                () => {
                    const results = [];
                    // 查找所有一级评论容器
                    const parentComments = document.querySelectorAll('.note-detail-mask .parent-comment');

                    parentComments.forEach(parentItem => {
                        try {
                            // 提取一级评论
                            const mainComment = parentItem.querySelector('.comment-item:not(.comment-item-sub)');
                            if (!mainComment) return;

                            const userEl = mainComment.querySelector('.author-wrapper .name, a.name');
                            const user = userEl ? userEl.textContent.trim() : '';

                            const contentEl = mainComment.querySelector('.content .note-text');
                            const content = contentEl ? contentEl.textContent.trim() : '';

                            const likeEl = mainComment.querySelector('.like-wrapper .count');
                            const likesText = likeEl ? likeEl.textContent.trim() : '0';

                            // 提取二级评论（子评论）
                            const sub_comments = [];
                            const replyContainer = parentItem.querySelector('.reply-container');
                            if (replyContainer) {
                                const subItems = replyContainer.querySelectorAll('.comment-item-sub');
                                subItems.forEach(sub => {
                                    const sUserEl = sub.querySelector('.author-wrapper .name, a.name');
                                    const sUser = sUserEl ? sUserEl.textContent.trim() : '';

                                    const sContentEl = sub.querySelector('.content .note-text');
                                    const sContent = sContentEl ? sContentEl.textContent.trim() : '';

                                    if (sContent) {
                                        sub_comments.push({ user: sUser, content: sContent });
                                    }
                                });
                            }

                            if (content) {
                                results.push({
                                    user,
                                    content,
                                    likes: parseInt(likesText.replace(/[^0-9]/g, '')) || 0,
                                    sub_comments
                                });
                            }
                        } catch(e) {
                            console.error('评论提取错误:', e);
                        }
                    });
                    return results;
                }
            """) or []
        except Exception as e:
            self.recorder.log("warning", f"评论提取异常: {e}")
            return []

    async def _scroll_comment_area(self):
        """滚动详情页右侧面板，加载更多评论"""
        try:
            scrolled = await self.page.evaluate("""
                () => {
                    const containers = [
                        document.querySelector('.note-detail-mask .interaction-container'),
                        document.querySelector('.note-detail-mask .note-scroller'),
                        document.querySelector('.note-detail-mask [class*="contentContainer"]'),
                        document.querySelector('.note-detail-mask .right-container')
                    ];
                    for (const c of containers) {
                        if (c && c.scrollHeight > c.clientHeight) {
                            c.scrollBy({ top: 500, behavior: 'smooth' });
                            return true;
                        }
                    }
                    return false;
                }
            """)
            if scrolled:
                await asyncio.sleep(random.uniform(0.8, 1.5))
        except Exception:
            pass

    async def _expand_all_replies(self):
        """展开所有折叠的二级评论（点击"展开X条回复"按钮）"""
        try:
            expanded_count = await self.page.evaluate("""
                () => {
                    const showMoreButtons = document.querySelectorAll('.note-detail-mask .show-more');
                    let count = 0;
                    showMoreButtons.forEach(btn => {
                        if (btn && btn.textContent.includes('展开') && btn.textContent.includes('回复')) {
                            btn.click();
                            count++;
                        }
                    });
                    return count;
                }
            """)
            if expanded_count > 0:
                self.recorder.log("info", f"💬 [评论] 展开了 {expanded_count} 个折叠的回复")
                # 等待展开的评论加载
                await asyncio.sleep(random.uniform(1.0, 2.0))
        except Exception as e:
            self.recorder.log("warning", f"展开回复失败: {e}")

    async def _generate_report(self, research_data: list[dict]) -> str:
        # Placeholder for LLM report generation
        self.recorder.log("info", "Generating research report using LLM.")
        prompt = self._prepare_llm_prompt(research_data)
        # Assuming llm_client has a method like generate_text
        report = await self.llm_client.generate_text(prompt, model=DEEP_RESEARCH_LLM_MODEL)
        return report

    async def _save_report(self, report: str, keyword: str):
        report_filename = self.output_dir / f"research_report_{keyword}.md"
        with open(report_filename, "w", encoding="utf-8") as f:
            f.write(report)
        self.recorder.log("info", f"Research report saved to {report_filename}")

    def _prepare_llm_prompt(self, research_data: list[dict]) -> str:
        """
        构建 LLM 提示词：生成数据驱动的问题解决报告
        目标：帮助用户快速获取答案，避免阅读大量帖子的焦虑
        """
        # 提取关键词（用户的问题）
        keyword = research_data[0].get('url', '').split('keyword=')[-1].split('&')[0] if research_data else '未知主题'
        try:
            from urllib.parse import unquote
            keyword = unquote(keyword)
        except:
            pass

        prompt_parts = [
            f"# 🔬 深度研究报告生成任务\n\n",
            f"## 研究背景\n",
            f"用户在小红书搜索了「**{keyword}**」，面临信息过载的困扰（需阅读大量帖子才能获得答案）。\n\n",
            f"## 你的角色\n",
            f"你是一位**专业的研究分析师**，需要以学术研究的严谨态度，基于 {len(research_data)} 篇小红书帖子及其评论数据，生成一份**循证医学级别**的深度分析报告。\n\n",
            f"## 研究方法论\n",
            f"- **数据来源**：{len(research_data)} 篇小红书真实用户帖子（含评论）\n",
            f"- **分析方法**：定量统计 + 定性分析 + 内容聚类\n",
            f"- **输出标准**：客观、量化、可验证、可操作\n",
            f"- **研究目标**：直接解决用户问题，消除决策焦虑\n\n",
            f"## 报告要求\n\n",
            f"### 1. 核心结论（必须量化）\n",
            f"- 用**具体数据**回答用户问题（例如：\"约 75% 的帖子推荐了 XX 品牌\"）\n",
            f"- 总结**主流观点**及其**支撑理由**\n",
            f"- 列出**少数派观点**及其**独特视角**\n",
            f"- 标注**数据来源**：每个结论必须引用具体帖子URL\n\n",
            f"### 2. 详细分析\n",
            f"按以下维度深度分析：\n",
            f"- **推荐度排名**：哪些选项被提及最多？各占比多少？\n",
            f"- **关键选择因素**：用户最看重哪些方面？（价格/品质/功效/安全性等）\n",
            f"- **常见误区**：用户容易踩的坑有哪些？\n",
            f"- **争议点**：哪些方面存在不同意见？各方观点是什么？\n",
            f"- **实用建议**：基于数据给出的可操作建议\n\n",
            f"### 3. 数据统计表格\n",
            f"| 维度 | 统计结果 | 占比 | 数据来源（帖子数量） |\n",
            f"|------|----------|------|---------------------|\n",
            f"| 示例：推荐品牌A | 15篇提及 | 75% | [帖子1](url), [帖子2](url)... |\n\n",
            f"### 4. 评论洞察\n",
            f"从评论区提炼：\n",
            f"- 真实用户体验（正面/负面）\n",
            f"- 高频提问的问题\n",
            f"- 未被解答的疑虑\n\n",
            f"---\n\n",
            f"## 原始数据（共 {len(research_data)} 篇帖子）\n\n"
        ]

        # 附加详细的帖子数据供 LLM 分析
        for i, post in enumerate(research_data, 1):
            prompt_parts.append(f"### 📄 帖子 {i}\n\n")
            prompt_parts.append(f"- **URL**: {post.get('url', 'N/A')}\n")
            prompt_parts.append(f"- **标题**: {post.get('title', '(无标题)')}\n")
            prompt_parts.append(f"- **类型**: {post.get('media_type', 'image')}\n\n")

            # 正文内容
            content = post.get('content', '').strip()
            if content:
                prompt_parts.append(f"**正文内容**：\n```\n{content}\n```\n\n")

            # 视频转录（如果有）
            asr_text = post.get('asr_results', '').strip()
            if asr_text:
                prompt_parts.append(f"**视频转录内容**：\n```\n{asr_text}\n```\n\n")

            # 图片信息
            images = post.get('image_urls', [])
            if images:
                prompt_parts.append(f"**图片数量**: {len(images)} 张\n\n")

            # 评论数据
            comments = post.get('comments', [])
            if comments:
                prompt_parts.append(f"**评论区 ({len(comments)} 条)**：\n")
                for idx, comment in enumerate(comments[:DEEP_RESEARCH_COMMENT_LIMIT], 1):
                    user = comment.get('user', '匿名')
                    content = comment.get('content', '')
                    likes = comment.get('likes', 0)
                    sub_comments = comment.get('sub_comments', [])

                    prompt_parts.append(f"{idx}. **{user}**")
                    if likes > 0:
                        prompt_parts.append(f" (👍 {likes})")
                    prompt_parts.append(f": {content}\n")

                    # 二级评论
                    if sub_comments:
                        for sub in sub_comments[:3]:  # 最多显示3条二级评论
                            sub_user = sub.get('user', '匿名')
                            sub_content = sub.get('content', '')
                            prompt_parts.append(f"   └─ **{sub_user}**: {sub_content}\n")

                prompt_parts.append("\n")
            else:
                prompt_parts.append("**评论区**: 无评论\n\n")

            prompt_parts.append("---\n\n")

        # 最后的指令
        prompt_parts.append("\n## ⚠️ 重要提醒\n\n")
        prompt_parts.append("1. **所有结论必须有数据支撑**：不能凭空推测，必须基于上述帖子内容\n")
        prompt_parts.append("2. **必须引用来源**：每个观点都要标注来源帖子编号（例如：[1][3][5]）\n")
        prompt_parts.append("3. **量化表达**：用百分比、具体数字描述趋势（例如：\"20篇中有15篇提到...，占75%\"）\n")
        prompt_parts.append("4. **客观中立**：呈现多元观点，不偏袒某一立场\n")
        prompt_parts.append("5. **解决问题**：最终目标是帮助用户快速做出决策或获得答案\n")
        prompt_parts.append("6. **学术严谨**：以研究者的态度，进行深度分析和论证\n\n")

        prompt_parts.append("## 📝 报告格式要求\n\n")
        prompt_parts.append("报告必须包含以下部分：\n\n")
        prompt_parts.append("1. **摘要**：200字以内的核心结论\n")
        prompt_parts.append("2. **问题背景**：用户为什么搜索这个话题\n")
        prompt_parts.append("3. **数据统计**：量化分析（表格形式）\n")
        prompt_parts.append("4. **详细分析**：多维度深度解读\n")
        prompt_parts.append("5. **结论与建议**：可操作的决策指南\n")
        prompt_parts.append("6. **参考文献**：列出所有引用的帖子（学术论文格式）\n\n")

        prompt_parts.append("### 参考文献格式示例：\n")
        prompt_parts.append("```\n")
        prompt_parts.append("## 参考文献\n\n")
        prompt_parts.append("[1] 小红书用户. 帖子标题. 小红书, 发布日期. [URL]\n")
        prompt_parts.append("[2] 小红书用户. 帖子标题. 小红书, 发布日期. [URL]\n")
        prompt_parts.append("...\n")
        prompt_parts.append("```\n\n")

        prompt_parts.append("请现在开始生成报告，使用 Markdown 格式输出。\n")

        return "".join(prompt_parts)

    async def _transcribe_video(self, video_local_path: Path) -> str:
        """Sends a local video file to the ASR server for transcription."""
        if not ASR_SERVER_URL:
            self.recorder.log("warning", "ASR_SERVER_URL is not configured. Skipping video transcription.")
            return ""

        if not video_local_path.exists():
            self.recorder.log("warning", f"Video file not found for transcription: {video_local_path}")
            return ""

        self.recorder.log("info", f"Sending {video_local_path.name} to ASR server for transcription...")
        try:
            async with httpx.AsyncClient(timeout=300.0) as client: # Increased timeout for large files
                with open(video_local_path, "rb") as f:
                    # The ASR server expects 'file' parameter in multipart/form-data
                    # The filename part of the tuple should ideally be the original filename
                    files = {'file': (video_local_path.name, f, 'audio/mpeg')} 
                    response = await client.post(ASR_SERVER_URL, files=files)
                response.raise_for_status() # Raise an exception for HTTP errors
                
                result = response.json()
                transcription = result.get("transcribed_text", "")
                if transcription:
                    self.recorder.log("info", f"ASR successful for {video_local_path.name}: {transcription[:50]}...")
                else:
                    self.recorder.log("warning", f"ASR returned empty transcription for {video_local_path.name}.")
                return transcription
        except httpx.RequestError as exc:
            self.recorder.log("error", f"ASR request error for {video_local_path.name}: {exc}")
        except httpx.HTTPStatusError as exc:
            self.recorder.log("error", f"ASR HTTP error for {video_local_path.name} - {exc.response.status_code}: {exc.response.text}")
        except Exception as e:
            self.recorder.log("error", f"Unexpected error during ASR for {video_local_path.name}: {e}")
        return ""

# Example usage (for testing purposes)
async def main():
    # This requires a running Chrome instance with remote debugging on port 9222
    # and a valid Zhipu AI Key (or Kimi if LLMClient is adapted)
    
    # Temporarily set some settings for testing
    from unittest.mock import MagicMock
    browser_manager = MagicMock(spec=BrowserManager)
    browser_manager.page = MagicMock(spec=Page) # Mock the page object
    
    # Mock LLMClient to return dummy text
    llm_client = MagicMock(spec=LLMClient)
    llm_client.generate_text.return_value = "这是一个模拟的深度研究报告。"

    research_agent = ResearchAgent(browser_manager, llm_client)
    await research_agent.run_deep_research("月龄宝宝推荐奶粉")

if __name__ == "__main__":
    asyncio.run(main())
