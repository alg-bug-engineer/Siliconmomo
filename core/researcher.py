import asyncio
import os
from datetime import datetime
import random
import re
from pathlib import Path
import json
import traceback
import aiohttp
import io

import httpx
try:
    from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError
except ModuleNotFoundError:  # 允许“仅从 JSON 生成报告”场景不安装 playwright
    Page = object  # type: ignore

    class PlaywrightTimeoutError(Exception):
        pass

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
from core.report_renderer import render_deep_research_html
from rapidocr import RapidOCR

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
        self.ocr_engine = None
        if DEEP_RESEARCH_ENABLED:
            self.ocr_engine = RapidOCR()
            self.recorder.log("info", "🧠 OCR 引擎已加载")

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
        attempts = 0  # 尝试次数计数器

        while posts_processed < DEEP_RESEARCH_POST_LIMIT:
            # 1. 检查环境
            if "xiaohongshu.com" not in self.page.url or "search_result" not in self.page.url:
                self.recorder.log("error", f"❌ [深度研究] 环境偏离: {self.page.url}")
                break

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

            # 3. 防御性检查：确保没有遮罩层存在（避免上次关闭失败）
            try:
                mask_visible = await self.page.locator(SELECTORS["note_detail_mask"]).is_visible()
                if mask_visible:
                    self.recorder.log("warning", "⚠️ 检测到残留遮罩层，强制关闭...")
                    await self.page.keyboard.press("Escape")
                    await self.page.wait_for_selector(
                        SELECTORS["note_detail_mask"],
                        state="hidden",
                        timeout=3000
                    )
                    await asyncio.sleep(0.5)
            except Exception as e:
                self.recorder.log("debug", f"遮罩层检查: {e}")

            # 4. 选择一个帖子并点击（研究模式：加速浏览）
            target_note = random.choice(notes[:6])  # 从前6个中随机选择
            await target_note.scroll_into_view_if_needed()
            await asyncio.sleep(random.uniform(0.3, 0.5))  # 减半延迟

            # 提前获取 note_id 用于日志（从子元素 <a> 标签获取 href）
            note_id_preview = "unknown"
            try:
                # 正确获取：先定位所有 <a> 标签，然后取第一个的 href
                note_links = target_note.locator('a[href*="/explore/"]')
                if await note_links.count() > 0:
                    note_href = await note_links.first.get_attribute('href') or ""
                    if note_href:
                        note_id_preview = self._extract_note_id_from_url(note_href)[:8] or "unknown"
            except Exception as e:
                self.recorder.log("debug", f"获取 note_id 失败: {e}")

            attempts += 1
            self.recorder.log("info", f"👆 [深度研究] 点击第 {attempts} 个帖子 | 已收集: {posts_processed}/{DEEP_RESEARCH_POST_LIMIT} (ID: {note_id_preview}...)")
            await target_note.click()

            # 5. 等待详情页加载，并尝试从URL获取ID
            try:
                await self.page.wait_for_selector(SELECTORS["note_detail_mask"], timeout=5000)
                # 如果之前没获取到ID，尝试从当前页面URL获取
                if note_id_preview == "unknown":
                    current_url = self.page.url
                    note_id_from_url = self._extract_note_id_from_url(current_url)
                    if note_id_from_url:
                        note_id_preview = note_id_from_url[:8]
            except:
                self.recorder.log("warning", "⏱️ [深度研究] 详情页加载超时，跳过此帖")
                await self.page.keyboard.press("Escape")
                continue

            # 6. 提取帖子内容（不调用 LLM，仅提取数据）
            post_data = await self._extract_content_from_page()

            # 判断帖子是否有价值：文字、图片、视频、评论任一存在即可收集
            # 纯图片帖子、有评论的帖子都是有价值的内容！
            has_value = False
            if post_data:
                has_value = bool(
                    post_data.get("content") or          # 有文字内容
                    post_data.get("image_urls") or       # 有图片
                    post_data.get("video_url") or        # 有视频
                    post_data.get("comments")            # 有评论
                )

            if has_value:
                research_data.append(post_data)
                posts_processed += 1
                note_id = self._extract_note_id_from_url(post_data.get('url', ''))
                self.recorder.log("info", f"✅ [深度研究] 已收集 {posts_processed}/{DEEP_RESEARCH_POST_LIMIT} 个帖子 (ID: {note_id[:8] if note_id else 'unknown'}...)")
            else:
                # 记录跳过原因
                skip_reason = "无数据" if not post_data else "完全无内容（无文字、图片、视频、评论）"
                self.recorder.log("warning", f"⚠️ [深度研究] 跳过帖子: {skip_reason} (尝试 {attempts})")

            # 7. 关闭详情页，返回搜索结果页（研究模式：快速关闭）
            await asyncio.sleep(random.uniform(0.5, 0.8))  # 减半延迟
            if await self.human.click_element(SELECTORS["btn_close"], "关闭详情"):
                self.recorder.log("debug", "使用按钮关闭详情页")
            else:
                await self.page.keyboard.press("Escape")
                self.recorder.log("debug", "使用 Escape 关闭详情页")

            # 8. 等待遮罩层完全消失，避免拦截下一次点击
            try:
                await self.page.wait_for_selector(
                    SELECTORS["note_detail_mask"],
                    state="hidden",
                    timeout=5000
                )
                self.recorder.log("debug", "✅ 遮罩层已消失")
            except Exception as e:
                self.recorder.log("warning", f"⚠️ 等待遮罩层消失超时: {e}")
                # 如果遮罩层仍然存在，强制等待更长时间
                await asyncio.sleep(1.0)

            # 9. 如果还需要更多帖子，偶尔滚动页面加载新内容
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

        self.recorder.log("info", f"Sending {video_local_path.name} to ASR server for transcription (language=zh)...")
        try:
            async with httpx.AsyncClient(timeout=300.0) as client: # Increased timeout for large files
                with open(video_local_path, "rb") as f:
                    files = {'file': (video_local_path.name, f, 'audio/mpeg')}
                    data = {'language': 'zh', 'task': 'transcribe'}  # 强制使用中文
                    response = await client.post(ASR_SERVER_URL, files=files, data=data)
                response.raise_for_status() # Raise an exception for HTTP errors
                
                result = response.json()
                transcription = result.get("text", "")
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

    async def _download_image(self, url: str) -> bytes | None:
        """从URL异步下载图片"""
        if not url:
            return None
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=30) as response:
                    response.raise_for_status()
                    return await response.read()
        except aiohttp.ClientError as e:
            self.recorder.log("warning", f"图片下载失败 {url}: {e}")
            return None
        except asyncio.TimeoutError:
            self.recorder.log("warning", f"图片下载超时 {url}")
            return None

    async def _perform_ocr_on_bytes(self, image_bytes: bytes) -> list[str]:
        """对图片字节数据执行 OCR"""
        if not self.ocr_engine or not image_bytes:
            return []
        
        try:
            # RapidOCR expects a file path or a numpy array.
            # We can convert bytes to a file-like object in memory.
            # A more direct approach might be to save to a temp file and pass the path,
            # but given the prompt, let's try to keep it in memory if possible.
            # RapidOCR also accepts PIL Image.
            from PIL import Image
            img = Image.open(io.BytesIO(image_bytes))
            
            # The demo showed engine("filepath.webp") which returns result.txts
            # If we pass PIL Image, it might return a different structure.
            # Let's assume it still returns a structure from which txts can be extracted.
            ocr_results = await asyncio.to_thread(self.ocr_engine, img)
            
            if ocr_results and hasattr(ocr_results, 'txts'):
                return ocr_results.txts
            elif isinstance(ocr_results, list) and all(isinstance(item, tuple) for item in ocr_results):
                # RapidOCR's default output when directly calling engine(image) is often
                # a list of tuples: (bbox, text, score)
                return [item[1] for item in ocr_results]
            else:
                self.recorder.log("warning", f"OCR 结果格式未知: {ocr_results}")
                return []

        except Exception as e:
            self.recorder.log("error", f"OCR 执行异常: {e}")
            return []

    async def _extract_content_from_page(self):
        """提取帖子完整内容：标题、正文、作者、图片、视频、评论"""
        detail = {
            "url": self.page.url,  # 添加当前页面URL
            "title": "", "content": "",
            "author": "",  # 新增：博主名字
            "author_avatar": "",  # 新增：博主头像
            "publish_date": "",  # 新增：发布日期
            "image_urls": [], "video_url": "", "video_local_path": "", "media_type": "image",
            "comments": [],
            "ocr_results": [],  # Placeholder for OCR, changed to list
            "asr_results": ""   # Placeholder for ASR
        }
        try:
            if await self.page.locator(SELECTORS["detail_title"]).count() > 0:
                detail["title"] = await self.page.locator(SELECTORS["detail_title"]).inner_text()

            if await self.page.locator(SELECTORS["detail_desc"]).count() > 0:
                detail["content"] = await self.page.locator(SELECTORS["detail_desc"]).inner_text()

            # 提取作者信息（使用.first避免多个匹配）
            author_locator = self.page.locator(SELECTORS["detail_author"]).first
            if await author_locator.count() > 0:
                try:
                    detail["author"] = await author_locator.inner_text()
                except:
                    detail["author"] = ""
            
            # 提取作者头像
            avatar_locator = self.page.locator(SELECTORS["author_avatar"]).first
            if await avatar_locator.count() > 0:
                try:
                    detail["author_avatar"] = await avatar_locator.get_attribute("src") or ""
                except:
                    detail["author_avatar"] = ""

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

            # OCR 处理图片
            if detail["image_urls"] and self.ocr_engine:
                all_ocr_texts = []
                self.recorder.log("info", f"✨ [OCR] 开始处理 {len(detail['image_urls'])} 张图片...")
                for img_url in detail["image_urls"]:
                    image_bytes = await self._download_image(img_url)
                    if image_bytes:
                        ocr_texts = await self._perform_ocr_on_bytes(image_bytes)
                        if ocr_texts:
                            all_ocr_texts.extend(ocr_texts)
                            self.recorder.log("debug", f"📸 [OCR] 从图片 '{img_url[:50]}...' 提取文本: {ocr_texts[:3]}...")
                if all_ocr_texts:
                    detail["ocr_results"] = all_ocr_texts
                    self.recorder.log("info", f"✅ [OCR] 从 {len(detail['image_urls'])} 张图片中提取到 {len(all_ocr_texts)} 条OCR文本。")
                else:
                    self.recorder.log("info", f"ℹ️ [OCR] 未能从图片中提取到文本。")


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
            note_id = self._extract_note_id_from_url(self.page.url)
            note_id_short = note_id[:8] if note_id else "unknown"

            media_count = len(detail["image_urls"]) if detail["media_type"] == "image" else 1
            content_preview = detail['content'][:30].replace('\n', ' ') if detail['content'] else '(无正文)'
            author_preview = detail['author'][:15] if detail['author'] else '(未知作者)'
            self.recorder.log("info", 
                f"📸 [抓取完成] 帖子 {note_id_short}... | 作者:{author_preview} | {detail['media_type']}x{media_count} | 评论x{len(detail['comments'])} | 内容: {content_preview}...")

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

            # 步骤2: 获取当前 URL 和 note_id
            current_url = self.page.url
            note_id = self._extract_note_id_from_url(current_url)
            note_id_short = note_id[:8] if note_id else "unknown"
            self.recorder.log("info", f"📹 [视频下载] 帖子 {note_id_short}... 检测到视频，开始提取...")

            # 步骤3: 提取视频信息并下载
            result = await self.video_downloader.extract_and_download(current_url)

            if result:
                self.recorder.log("info", f"✅ [视频下载] 帖子 {note_id_short}... 下载成功")
                self.recorder.log("info", f"   视频URL: {result['video_url'][:50]}...")
                self.recorder.log("info", f"   保存路径: {result['local_path']}")
                return {
                    "video_url": result["video_url"],
                    "local_path": result["local_path"],
                }
            else:
                self.recorder.log("warning", f"⚠️ [视频下载] 帖子 {note_id_short}... 提取或下载失败")
                return {"video_url": "", "local_path": ""}

        except Exception as e:
            note_id = self._extract_note_id_from_url(self.page.url if self.page else "")
            note_id_short = note_id[:8] if note_id else "unknown"
            self.recorder.log("error", f"❌ [视频下载] 帖子 {note_id_short}... 异常: {e}")
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
        return self._postprocess_report(report, research_data)

    def _postprocess_report(self, report: str, research_data: list[dict]) -> str:
        """
        目标：把 LLM 常见的“引用写法”强制修正为可点击链接，避免参考文献/正文出现纯文本 URL 或反引号包裹引用。
        - 将 `见[帖子[3]]评论` / 见[帖子[3]]评论 → 见[帖子[3]](URL)评论
        - 将 [帖子[3]]（未带链接）→ [帖子[3]](URL)
        - 尽量跳过 fenced code block（```...```）以免污染代码/mermaid
        """
        if not report or not research_data:
            return report

        idx_to_url: dict[int, str] = {}
        for i, post in enumerate(research_data, 1):
            url = (post.get("url") or "").strip()
            if url:
                idx_to_url[i] = url

        if not idx_to_url:
            return report

        def _fix_line(line: str) -> str:
            # 去掉引用外层反引号（仅针对“见[帖子[..]]”这类片段）
            line = re.sub(r"`\s*(见\s*\[帖子\[(\d+)\]\][^`]*)\s*`", r"\1", line)

            # 见[帖子[3]]评论 → 见[帖子[3]](URL)评论
            def repl_seen(m: re.Match):
                idx = int(m.group(2))
                url = idx_to_url.get(idx)
                if not url:
                    return m.group(0)
                tail = m.group(3) or ""
                return f"见[帖子[{idx}]]({url}){tail}"

            # 若已经是 Markdown 链接（]后紧跟(），则不重复注入 URL
            line = re.sub(r"(见\s*)\[帖子\[(\d+)\]\](?!\()(评论)?", repl_seen, line)

            # [帖子[3]]（未带链接）→ [帖子[3]](URL)
            def repl_bare(m: re.Match):
                idx = int(m.group(1))
                url = idx_to_url.get(idx)
                if not url:
                    return m.group(0)
                return f"[帖子[{idx}]]({url})"

            line = re.sub(r"\[帖子\[(\d+)\]\](?!\()", repl_bare, line)

            # 参考文献常见写法：链接(URL) → [帖子链接](URL)
            line = re.sub(r"链接\((https?://[^\s)]+)\)", r"[帖子链接](\1)", line)
            return line

        def _convert_mermaid_bar_to_xychart(mermaid_src: str) -> str:
            """
            将非标准的
              bar
                title xxx
                x-axis ...
                y-axis ...
                bar "A": 10
            转为 mermaid@10 支持的 xychart-beta。
            """
            lines = [ln.rstrip() for ln in mermaid_src.splitlines()]
            # 找到首个非空行
            i0 = next((i for i, ln in enumerate(lines) if ln.strip()), None)
            if i0 is None:
                return mermaid_src
            if lines[i0].strip() != "bar":
                return mermaid_src

            title = ""
            y_label = "次数"
            points: list[tuple[str, float]] = []
            for ln in lines[i0 + 1 :]:
                s = ln.strip()
                if not s:
                    continue
                if s.startswith("title"):
                    title = s[len("title") :].strip()
                    continue
                if s.startswith("y-axis"):
                    # y-axis 次数
                    y_label = s[len("y-axis") :].strip() or y_label
                    continue
                m = re.match(r'^bar\s+"?(.*?)"?\s*:\s*([0-9]+(?:\.[0-9]+)?)\s*$', s)
                if m:
                    points.append((m.group(1), float(m.group(2))))

            if not points:
                return mermaid_src

            labels = [p[0].replace('"', '\\"') for p in points]
            values = [p[1] for p in points]
            y_max = max(values) if values else 0
            y_max_int = int(y_max) if float(y_max).is_integer() else int(y_max) + 1
            if y_max_int <= 0:
                y_max_int = 1

            # 让 y 轴上限更“好看”
            step = 10
            y_max_int = ((y_max_int + step - 1) // step) * step

            values_str = ", ".join(str(int(v)) if float(v).is_integer() else str(v) for v in values)
            labels_str = ", ".join(f'"{lab}"' for lab in labels)
            title_escaped = title.replace('"', '\\"') if title else "提及频次TOP"

            return "\n".join(
                [
                    "xychart-beta",
                    f'    title "{title_escaped}"',
                    f"    x-axis [{labels_str}]",
                    f'    y-axis "{y_label}" 0 --> {y_max_int}',
                    f"    bar [{values_str}]",
                ]
            )

        def _rebuild_references_section() -> str:
            lines: list[str] = ["## 参考文献", ""]
            for i, post in enumerate(research_data, 1):
                url = (post.get("url") or "").strip()
                title = (post.get("title") or "(无标题)").strip()
                author = (post.get("author") or "").strip()
                publish_date = (post.get("publish_date") or "").strip()
                author = author if author else "作者未提供"
                publish_date = publish_date if publish_date else "发布日期未提供"
                if url:
                    lines.append(f"[{i}] @{author}. 《{title}》. 小红书, {publish_date}. [帖子链接]({url})")
                else:
                    lines.append(f"[{i}] @{author}. 《{title}》. 小红书, {publish_date}. （链接缺失）")
            return "\n".join(lines).rstrip() + "\n"

        raw_lines = report.splitlines()
        out: list[str] = []
        in_fence = False
        fence_lang = ""
        mermaid_buf: list[str] = []

        # 参考文献段落替换：遇到 "## 参考文献" 后，跳过直到下一个 "## " 或 EOF
        i = 0
        while i < len(raw_lines):
            line = raw_lines[i]
            if not in_fence and line.strip() == "## 参考文献":
                out.append(_rebuild_references_section().rstrip())
                i += 1
                while i < len(raw_lines):
                    nxt = raw_lines[i]
                    if nxt.startswith("## ") and nxt.strip() != "## 参考文献":
                        break
                    i += 1
                continue

            if line.strip().startswith("```"):
                if not in_fence:
                    in_fence = True
                    fence_lang = line.strip()[3:].strip().lower()
                    out.append(line)
                    if fence_lang == "mermaid":
                        mermaid_buf = []
                    i += 1
                    continue
                else:
                    # fence close
                    if fence_lang == "mermaid" and mermaid_buf is not None:
                        src = "\n".join(mermaid_buf)
                        src2 = _convert_mermaid_bar_to_xychart(src)
                        out.append(src2)
                        mermaid_buf = []
                    out.append(line)
                    in_fence = False
                    fence_lang = ""
                    i += 1
                    continue

            if in_fence and fence_lang == "mermaid":
                mermaid_buf.append(line)
                i += 1
                continue

            if in_fence:
                out.append(line)
                i += 1
                continue

            out.append(_fix_line(line))
            i += 1

        return "\n".join(out).rstrip() + "\n"

    async def _save_report(self, report: str, keyword: str):
        report_filename = self.output_dir / f"research_report_{keyword}.md"
        with open(report_filename, "w", encoding="utf-8") as f:
            f.write(report)
        self.recorder.log("info", f"Research report saved to {report_filename}")

        # 参考 data/demo.html 的模板样式：同步输出对应 HTML
        try:
            html_filename = self.output_dir / f"research_report_{keyword}.html"
            html_text = render_deep_research_html(
                report,
                title_fallback=f"深度调研报告：{keyword}",
                subtitle=f"基于抓取数据的深度研究 | 关键词：{keyword}",
                generated_at=datetime.now(),
            )
            with open(html_filename, "w", encoding="utf-8") as f:
                f.write(html_text)
            self.recorder.log("info", f"Research report HTML saved to {html_filename}")
        except Exception as e:
            self.recorder.log("warning", f"HTML 报告输出失败（已保留 Markdown）：{e}")

    def _prepare_llm_prompt(self, research_data: list[dict]) -> str:
        """
        构建 LLM 提示词：生成专业的数据调研分析报告
        目标：基于小红书数据生成数据鲜明、论证严谨的专业调研报告
        """
        def _truncate(text: str, limit: int) -> str:
            text = (text or "").strip()
            if len(text) <= limit:
                return text
            return text[:limit] + "…"

        def _safe_list(v):
            return v if isinstance(v, list) else []

        # 关键词：尽量从 URL 解析（若失败则回退为“主题”）
        keyword = "主题"
        if research_data:
            url0 = (research_data[0].get("url") or "").strip()
            if "keyword=" in url0:
                keyword = url0.split("keyword=")[-1].split("&")[0] or keyword
                try:
                    from urllib.parse import unquote
                    keyword = unquote(keyword)
                except Exception:
                    pass

        posts_cnt = len(research_data)
        total_comments = sum(len(_safe_list(p.get("comments"))) for p in research_data)
        posts_with_video = sum(1 for p in research_data if (p.get("video_url") or "").strip())
        posts_with_images = sum(1 for p in research_data if len(_safe_list(p.get("image_urls"))) > 0)
        posts_with_asr = sum(1 for p in research_data if (p.get("asr_results") or "").strip())
        posts_with_ocr = sum(1 for p in research_data if len(_safe_list(p.get("ocr_results"))) > 0)
        posts_with_text = sum(1 for p in research_data if (p.get("content") or "").strip())

        # === 额外统计：用于“图表/对比/量化”输出（避免模型只写空洞论述） ===
        def _collect_text(post: dict) -> str:
            parts: list[str] = []
            for k in ("title", "content", "asr_results"):
                v = (post.get(k) or "").strip()
                if v:
                    parts.append(v)
            ocr = _safe_list(post.get("ocr_results"))
            if ocr:
                parts.append(" ".join([str(x) for x in ocr if str(x).strip()]))
            for c in _safe_list(post.get("comments")):
                cv = (c.get("content") or "").strip()
                if cv:
                    parts.append(cv)
            return "\n".join(parts)

        all_text = "\n".join([_collect_text(p) for p in research_data])

        # 简易“短语”抽取：用中文连续串近似（不依赖外部分词库）
        import collections

        stop = {
            "这个", "一个", "我们", "你们", "他们", "就是", "因为", "所以", "但是", "然后", "真的", "感觉", "比较",
            "如果", "还是", "可以", "不是", "没有", "很多", "特别", "以及", "一些", "这种", "那种", "怎么", "为什么",
            "时候", "现在", "已经", "不会", "可能", "需要", "觉得", "问题", "内容", "评论", "帖子", "小红书", "春晚",
        }
        tokens = [t for t in re.findall(r"[\u4e00-\u9fff]{2,6}", all_text) if t not in stop]
        term_counter = collections.Counter(tokens)

        # term -> 出现在哪些帖子（最多给 5 个索引，方便模型引用）
        term_posts: dict[str, list[int]] = {}
        for term, _ in term_counter.most_common(40):
            posts_idx = []
            for idx, post in enumerate(research_data, 1):
                if term in _collect_text(post):
                    posts_idx.append(idx)
                if len(posts_idx) >= 5:
                    break
            term_posts[term] = posts_idx

        top_terms = term_counter.most_common(15)
        top_terms_table = "\n".join(
            ["| 短语 | 提及次数 | 主要来源帖子 |", "|---|---:|---|"]
            + [
                f"| {term} | {cnt} | {', '.join([f'帖子[{i}]' for i in term_posts.get(term, [])]) or '—'} |"
                for term, cnt in top_terms
            ]
        )

        # 评论互动强度：每帖评论数、点赞Top
        per_post_stats_rows = []
        for i, post in enumerate(research_data, 1):
            comments = _safe_list(post.get("comments"))
            like_max = 0
            if comments:
                like_max = max(int(c.get("likes") or 0) for c in comments)
            per_post_stats_rows.append(
                f"| 帖子[{i}] | {len((post.get('content') or '').strip())} | {len(comments)} | {like_max} | {'视频' if (post.get('video_url') or '').strip() else '图文/图片'} |"
            )
        per_post_stats_table = "\n".join(
            ["| 帖子 | 正文字数(粗略) | 评论数 | 评论最高赞 | 形态 |", "|---|---:|---:|---:|---|"]
            + per_post_stats_rows[: min(20, len(per_post_stats_rows))]
            + ([f"| … | … | … | … | … |"] if len(per_post_stats_rows) > 20 else [])
        )

        # 结构化证据包：让模型更容易“引用证据”而不是复述全文
        evidence_blocks: list[str] = []
        for i, post in enumerate(research_data, 1):
            comments = _safe_list(post.get("comments"))
            top_comments = sorted(comments, key=lambda c: int(c.get("likes") or 0), reverse=True)[:8]

            top_comments_md = "\n".join(
                [
                    f"- （👍{int(c.get('likes') or 0)}）**{(c.get('user') or '匿名').strip()}**：{_truncate(c.get('content') or '', 160)}"
                    for c in top_comments
                    if (c.get("content") or "").strip()
                ]
            ).strip()

            evidence_blocks.append(
                "\n".join(
                    [
                        f"### 帖子[{i}]",
                        f"- URL：{post.get('url', 'N/A')}",
                        f"- 正文/引用链接（必须用于报告引用）：[帖子[{i}]]({post.get('url', 'N/A')})",
                        f"- 标题：{(post.get('title') or '(无标题)').strip()}",
                        f"- 作者：{(post.get('author') or '(未知作者)').strip()}",
                        f"- 发布日期：{(post.get('publish_date') or '(未知)').strip()}",
                        f"- 媒体：{'视频' if (post.get('video_url') or '').strip() else '图文/图片'}（图片{len(_safe_list(post.get('image_urls')))}张）",
                        f"- 正文摘录：{_truncate(post.get('content') or '', 420) or '(无正文)'}",
                        f"- ASR摘录：{_truncate(post.get('asr_results') or '', 420) or '(无)'}",
                        f"- OCR摘录：{_truncate(' '.join(_safe_list(post.get('ocr_results'))), 420) or '(无)'}",
                        f"- 评论数：{len(comments)}",
                        f"- Top评论：\n{top_comments_md if top_comments_md else '(无可用评论摘录)'}",
                    ]
                )
            )

        prompt = f"""你是一位**资深用户研究/行业分析师**。你将基于“证据包”撰写一份**深度调研报告（Markdown）**。

## 研究主题
{keyword}

## 数据样本概况（必须在报告中复述并用于计算口径）
- 样本：{posts_cnt} 篇帖子
- 评论总量（抓取到的可见评论）：{total_comments} 条
- 帖子形态：含视频 {posts_with_video} / 含图片 {posts_with_images}
- 可用文本：正文可用 {posts_with_text} / ASR可用 {posts_with_asr} / OCR可用 {posts_with_ocr}
- 研究时间：{datetime.now().strftime("%Y-%m-%d")}

## 写作协议（深度研究风格，必须严格执行）
1. **证据链优先**：所有结论必须落到“帖子[X]”或“帖子[X]的评论”证据；无法证实时必须写“证据不足/样本外推风险”。
2. **量化口径清晰**：所有比例/频次要说明分母（例如“在 {posts_cnt} 篇帖子中，有 8 篇提及…占比 40%”）。
3. **反例/分歧不可缺**：每个关键结论至少给出 1 个反例或对立观点，并解释为什么出现分歧（人群/场景/成本/认知差异）。
4. **不确定性与局限**：单列章节写出样本偏差、抓取缺失（例如登录限制、评论展示限制）、OCR/ASR噪声等。
5. **高密度引用**：每个二级标题（`##`）至少包含 3 处引用（例如：见[帖子[3]](URL)、帖子[7]评论）；全文引用数量至少为 {max(12, posts_cnt)} 处。
6. **可操作**：建议必须“动作+适用人群+触发条件+风险提示+证据引用”，避免泛泛而谈。
7. **输出必须是 Markdown**，并至少包含：
   - Mermaid 图 **至少 3 个**：分别用于（1）观点/情绪分布（pie 或 bar），（2）提及频次TOP（bar 或 xychart-beta），（3）用户决策路径（flowchart）
   - 表格 **至少 4 个**：样本概览表、对比分析表、风险清单表、行动建议矩阵表
8. **引用与链接格式（必须严格）**：
   - **禁止**使用反引号包裹引用（例如不要写：`见[帖子[3]]评论`）
   - 正文引用：必须用可点击链接，例如 `见[帖子[3]](https://...)` 或 `（来源：见[帖子[3]](URL) 评论）`
   - 参考文献：必须是 Markdown 超链接，禁止输出纯文本 URL

## 快速统计摘要（必须在正文中引用并用图表/表格展开）
### 高频短语（来自抓取文本的粗粒度统计）
{top_terms_table}

### 帖子层面的互动与形态（用于对比分析）
{per_post_stats_table}

## 报告结构（请按此顺序与标题层级输出，便于后续 HTML 目录生成）
# 深度调研报告：{keyword}

## 执行摘要
- 3-5 条“结论先行”的关键发现（每条含量化与引用：帖子[X]…）
- 3 条最重要建议（可执行）

## 研究设计与方法
- 数据来源/采集方式/样本说明
- 分析框架（你采用的分类口径：需求/动机/顾虑/决策因子…）

## 数据概览与样本画像
- 样本结构（图文/视频、内容密度、评论活跃度）
- 可能的人群线索（从内容与评论推断，但要写“推断”并给证据）

## 核心发现（分 3-6 个小节）
每个小节必须包含：
- 小结论（1 句话）
- 证据：引用帖子[X]、评论摘录（短句即可）
- 量化：频次/占比/排序
- 反例/分歧：至少 1 个

## 观点分布与争议点（含 Mermaid）
必须输出 2 个 Mermaid 图：
- 图1：观点/情绪/态度分布（pie 或 bar，必须有数值）
- 图2：提及频次TOP10（**必须用 xychart-beta**，数据源可用“高频短语表”或你基于证据计算的统计）

## 用户声音（VoC）
- Top 诉求/Top 顾虑/Top 误区（分别给引用）
- 典型原话摘录（注明来源：帖子[X]评论）

## 风险、局限与外推边界
- 样本偏差/抓取缺失/OCR-ASR 噪声
- 结论适用范围与不适用范围

## 行动建议（分人群/分场景）
建议采用表格呈现，并包含“适用人群、触发条件、推荐动作、风险提示、证据引用”。

## 参考文献（必须覆盖全部 {posts_cnt} 篇帖子）
- 格式示例（必须可点击）：
  - `[1] @作者. 《标题》. 小红书, 发布日期. [帖子链接](URL)`
  - 正文引用也建议用同一 URL：`[帖子[1]](URL)`

---

## 证据包（只许引用，不要在报告里复写全文）
{chr(10).join(evidence_blocks)}
"""

        return prompt

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
