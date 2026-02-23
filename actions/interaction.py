import asyncio
import random
import re
from core.knowledge_base import KnowledgeBase
from config.settings import (
    SELECTORS, SEARCH_KEYWORDS, SEARCH_INTERVAL,
    PROB_LIKE, PROB_COLLECT, PROB_COMMENT, PROB_POST_COMMENT, PROB_TRIGGER_THINKING, PROB_LAZY_LIKE, PROB_LAZY_COLLECT,
    ENABLE_CONTENT_SCRAPING, SCRAPE_COMMENTS, COMMENT_SCROLL_TIMES
)
from core.llm_client import LLMClient
from core.video_downloader import VideoDownloader

class ActionExecutor:
    def __init__(self, page, human, recorder, llm_client):
        self.page = page
        self.human = human
        self.recorder = recorder
        self.kb = KnowledgeBase(recorder) # <--- 初始化知识库
        self.llm = llm_client # Use the passed llm_client instance

        self.posts_processed_count = 0
        self.current_keyword_index = 0

        # 视频下载器
        self.video_downloader = VideoDownloader(save_dir="videos")

    async def execute_one_cycle(self):
        # 1. 搜索轮转（首次运行或达到间隔时执行搜索）
        if self.posts_processed_count == 0 or self.posts_processed_count % SEARCH_INTERVAL == 0:
            await self._rotate_search()
        
        # 2. 环境自检
        if "xiaohongshu.com" not in self.page.url:
             raise RuntimeError(f"环境偏离: {self.page.url}")
             
        # 3. 等待搜索结果加载（搜索后需要等待）
        if self.posts_processed_count == 0 or self.posts_processed_count % SEARCH_INTERVAL == 0:
            await asyncio.sleep(3)  # 等待搜索结果加载
             
        # 4. 寻找帖子
        notes = await self.page.locator(SELECTORS["note_card"]).all()
        if not notes:
            self.recorder.log("warning", "视口无帖子，滚动寻找...")
            await self.human.human_scroll(500)
            await asyncio.sleep(2)
            notes = await self.page.locator(SELECTORS["note_card"]).all()
            if not notes:
                raise RuntimeError("视觉丢失: 未检测到笔记")

        # 5. 随机选贴并点击
        target_note = random.choice(notes[:4])
        await target_note.scroll_into_view_if_needed()
        await asyncio.sleep(0.5)
        await target_note.click()
        
        try:
            await self.page.wait_for_selector(SELECTORS["note_detail_mask"], timeout=5000)
        except:
             await self.page.keyboard.press("Escape")
             return

        # 6. 详情页互动
        await self._smart_interact()
        self.posts_processed_count += 1

    async def _rotate_search(self):
        keyword = SEARCH_KEYWORDS[self.current_keyword_index % len(SEARCH_KEYWORDS)]
        self.current_keyword_index += 1
        self.recorder.log("info", f"🔄 [轮转] 切换关键词: {keyword}")
        
        await self.human.click_element(SELECTORS["search_input"], "搜索框")
        await asyncio.sleep(0.5)
        await self.page.locator(SELECTORS["search_input"]).clear()
        for char in keyword:
            await self.page.keyboard.type(char, delay=random.randint(50, 150))
        await self.page.keyboard.press("Enter")
        await asyncio.sleep(3)

    async def _extract_content(self):
        """提取帖子完整内容：标题、正文、作者、图片、视频、评论"""
        detail = {
            "title": "", "content": "", "author": "",
            "image_urls": [], "video_url": "", "video_local_path": "", "media_type": "image",
            "comments": []
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

            # 增强抓取：图片、视频、评论
            if ENABLE_CONTENT_SCRAPING:
                detail["image_urls"] = await self._extract_images()

                # 提取并下载视频
                video_info = await self._extract_video()
                detail["video_url"] = video_info.get("video_url", "")
                detail["video_local_path"] = video_info.get("local_path", "")
                detail["media_type"] = "video" if detail["video_url"] else "image"

                if SCRAPE_COMMENTS:
                    # 1. 滚动加载更多一级评论
                    for _ in range(COMMENT_SCROLL_TIMES):
                        await self._scroll_comment_area()

                    # 2. 展开所有折叠的二级评论
                    await self._expand_all_replies()

                    # 3. 提取评论
                    detail["comments"] = await self._extract_comments()

                # 提取帖子ID
                url_match = re.search(r'/explore/([a-f0-9]+)', self.page.url)
                note_id = url_match.group(1) if url_match else "unknown"

                media_count = len(detail["image_urls"]) if detail["media_type"] == "image" else 1
                author_preview = detail['author'][:15] if detail['author'] else '(未知作者)'
                self.recorder.log("info",
                    f"📸 [抓取] ID:{note_id[:8]}... | 作者:{author_preview} | {detail['media_type']}x{media_count} | 评论x{len(detail['comments'])}")

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

    async def _smart_interact(self):
        self.recorder.log("info", ">>> [详情页] 正在阅读...")

        # 1. 提取完整内容（标题、正文、图片、视频、评论）
        detail = await self._extract_content()

        # 模拟阅读（基础滚动）
        await self.human.human_scroll(random.randint(100, 300))
        await asyncio.sleep(random.uniform(1.5, 3.0))

        # === 🎲 决策点 1: 要不要动脑子？ ===
        should_think = random.random() < PROB_TRIGGER_THINKING

        if not should_think:
            await self._lazy_mode_interact(detail["title"])
        else:
            await self._deep_mode_interact(detail)

        # 退出详情页
        await asyncio.sleep(1)
        if not await self.human.click_element(SELECTORS["btn_close"], "关闭详情"):
            await self.page.keyboard.press("Escape")

    async def _lazy_mode_interact(self, title):
        """
        😴 懒人模式：只看，不走心，随机点赞，绝不评论
        """
        self.recorder.log("info", "💤 [模式] 懒人浏览 (不调用LLM)")
        
        # 简单划两下
        scrolls = random.randint(1, 3)
        for _ in range(scrolls):
            await self.human.human_scroll(random.randint(200, 500))
            await asyncio.sleep(random.uniform(1, 3))
            
        # 凭直觉（随机）点赞收藏，概率比深思模式低
        if random.random() < PROB_LAZY_LIKE:
            if await self.human.click_element(SELECTORS["btn_like"], "点赞"):
                self.recorder.record_action("like", f"[Lazy] {title}")

        if random.random() < PROB_LAZY_COLLECT:
            if await self.human.click_element(SELECTORS["btn_collect"], "收藏"):
                self.recorder.record_action("collect", f"[Lazy] {title}")

    async def _deep_mode_interact(self, detail):
        """
        🧠 深思模式：调用 LLM，判断相关性，精准互动，发表评论
        """
        title = detail["title"]
        content = detail["content"]

        self.recorder.log("info", "🧠 [模式] 深度分析 (调用LLM)")

        # 更多阅读时间
        await asyncio.sleep(random.uniform(2, 4))

        # 1. 召唤大脑
        analysis = self.llm.analyze_and_comment(title, content)

        # 2. 判断相关性
        if not analysis.get("is_relevant"):
            self.recorder.log("info", "🧠 [大脑] 判断: 内容不相关，溜了")
            return

        # === 💾 保存素材（含图片、视频、评论、本地路径） ===
        current_url = self.page.url
        self.kb.save_inspiration(
            title, content, analysis,
            source_url=current_url,
            image_urls=detail.get("image_urls", []),
            video_url=detail.get("video_url", ""),
            video_local_path=detail.get("video_local_path", ""),
            media_type=detail.get("media_type", "image"),
            comments=detail.get("comments", [])
        )

        # 打印前3条评论供查看
        comments = detail.get("comments", [])
        if comments:
            self.recorder.log("info", f"💬 [评论预览] 前{min(3, len(comments))}条:")
            for i, cmt in enumerate(comments[:3], 1):
                user = cmt.get("user", "匿名")
                content_text = cmt.get("content", "")[:40]  # 最多40字
                likes = cmt.get("likes", 0)
                sub_count = len(cmt.get("sub_comments", []))
                self.recorder.log("info",
                    f"   {i}. {user}: {content_text}{'...' if len(cmt.get('content', '')) > 40 else ''} "
                    f"[❤️{likes}] [回复x{sub_count}]"
                )

        # 3. 相关内容，认真看完
        read_time = random.uniform(5, 10)
        steps = int(read_time / 2)
        for _ in range(steps):
            await self.human.human_scroll(random.randint(100, 200))

        # 4. 基于价值的互动
        if random.random() < PROB_LIKE:
            if await self.human.click_element(SELECTORS["btn_like"], "点赞"):
                self.recorder.record_action("like", f"[Deep] {title}")

        if random.random() < PROB_COLLECT:
            if await self.human.click_element(SELECTORS["btn_collect"], "收藏"):
                self.recorder.record_action("collect", f"[Deep] {title}")

        # === 🎲 决策点 2: 要不要张嘴说话？ ===
        if analysis.get("should_comment"):
            if random.random() < PROB_POST_COMMENT:
                comment_text = analysis.get("comment_text")
                login_mask = self.page.locator(SELECTORS["comment_area_login_mask"])
                if await login_mask.count() > 0 and await login_mask.is_visible():
                    self.recorder.log("warning", "评论区受限，放弃")
                else:
                    await self._post_comment(comment_text, title)
            else:
                self.recorder.log("info", "🤐 [社恐] 算了，不想说话 (放弃评论)")

    async def _post_comment(self, text, post_title):
        if not text: return
        self.recorder.log("info", f"✍️ [评论] 尝试发表: {text}")
        
        try:
            # === 步骤 1: 激活评论框 ===
            # 直接调用 human.click_element，它内部会遍历列表尝试点击
            # 如果点击成功，会返回 True；如果列表里都找不到，返回 False
            activated = await self.human.click_element(
                SELECTORS["comment_input_area"], 
                "激活评论框"
            )
            
            if not activated:
                self.recorder.log("warning", "未找到评论输入框 (无法激活)")
                # 截图留证，方便二次确认选择器是否又变了
                await self.recorder.record_error(self.page, "评论框定位失败")
                return

            # 激活后，稍微等待 DOM 变换 (从占位符变成输入框)
            await asyncio.sleep(random.uniform(0.8, 1.5))
            
            # === 步骤 2: 输入文字 ===
            # 寻找可编辑区域
            editable_found = False
            editable_selectors = SELECTORS["comment_editable"]
            if isinstance(editable_selectors, str): editable_selectors = [editable_selectors]
            
            for sel in editable_selectors:
                try:
                    target = self.page.locator(sel).first
                    if await target.count() > 0 and await target.is_visible():
                        # 模拟打字
                        await target.type(text, delay=random.randint(50, 150))
                        editable_found = True
                        break
                except:
                    continue
            
            if not editable_found:
                # 尝试一种兜底方案：直接向当前焦点元素输入 (因为刚才已经点击激活了)
                self.recorder.log("warning", "未定位到明确的编辑区，尝试向当前焦点输入")
                await self.page.keyboard.type(text, delay=random.randint(50, 150))

            await asyncio.sleep(random.uniform(0.5, 1.0))
            
            # === 步骤 3: 发送 ===
            # 寻找发送按钮
            submit_clicked = await self.human.click_element(
                SELECTORS["comment_submit"], 
                "发送按钮"
            )
            
            if submit_clicked:
                self.recorder.record_action("comment", f"[{post_title}] {text}")
                self.recorder.log("info", "✅ 评论发送动作已执行")
            else:
                self.recorder.log("warning", "未找到发送按钮 (可能是未输入成功或按钮置灰)")
            
        except Exception as e:
            self.recorder.log("error", f"❌ 评论过程出错: {e}")
            await self.recorder.record_error(self.page, "评论异常")