import asyncio
import random
from core.knowledge_base import KnowledgeBase
from config.settings import (
    SELECTORS, SEARCH_KEYWORDS, SEARCH_INTERVAL, 
    PROB_LIKE, PROB_COLLECT, PROB_COMMENT, PROB_POST_COMMENT, PROB_TRIGGER_THINKING, PROB_LAZY_LIKE, PROB_LAZY_COLLECT
)
from core.llm_client import LLMClient

class ActionExecutor:
    def __init__(self, page, human, recorder):
        self.page = page
        self.human = human
        self.recorder = recorder
        self.kb = KnowledgeBase(recorder) # <--- 初始化知识库
        self.llm = LLMClient(recorder)
        
        self.posts_processed_count = 0
        self.current_keyword_index = 0

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
        """提取标题和正文"""
        try:
            # 标题
            title = ""
            if await self.page.locator(SELECTORS["detail_title"]).count() > 0:
                title = await self.page.locator(SELECTORS["detail_title"]).inner_text()

            # 正文
            desc = ""
            if await self.page.locator(SELECTORS["detail_desc"]).count() > 0:
                desc = await self.page.locator(SELECTORS["detail_desc"]).inner_text()
                
            return title, desc
        except Exception as e:
            self.recorder.log("warning", f"内容提取微小异常: {e}")
            return "", ""

    async def _smart_interact(self):
        self.recorder.log("info", ">>> [详情页] 正在阅读...")
        
        # 1. 提取内容
        title, content = await self._extract_content()
        
        # 模拟阅读（基础滚动）
        await self.human.human_scroll(random.randint(100, 300))
        await asyncio.sleep(random.uniform(1.5, 3.0))

        # === 🎲 决策点 1: 要不要动脑子？ ===
        # 模拟真人：大部分时候只是“看个热闹”，不会每条都去分析
        should_think = random.random() < PROB_TRIGGER_THINKING
        
        if not should_think:
            await self._lazy_mode_interact(title)
        else:
            await self._deep_mode_interact(title, content)

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

    async def _deep_mode_interact(self, title, content):
        """
        🧠 深思模式：调用 LLM，判断相关性，精准互动，发表评论
        """
        self.recorder.log("info", "🧠 [模式] 深度分析 (调用LLM)")
        
        # 更多阅读时间
        await asyncio.sleep(random.uniform(2, 4))
        
        # 1. 召唤大脑
        analysis = self.llm.analyze_and_comment(title, content)
        
        # 2. 判断相关性
        if not analysis.get("is_relevant"):
            self.recorder.log("info", "🧠 [大脑] 判断: 内容不相关，溜了")
            return

        # === 💾 [新增] 核心修改点：保存素材 ===
        # 只要是相关的内容，无论是否发评论，都值得存下来作为未来的发帖参考
        # 比如：虽然不想评论，但这篇关于DeepSeek的文章写得很好，存下来以后我也可以写一篇
        current_url = self.page.url
        self.kb.save_inspiration(title, content, analysis, source_url=current_url)
        # ==================================
        
        # 3. 相关内容，认真看完
        read_time = random.uniform(5, 10)
        steps = int(read_time / 2)
        for _ in range(steps):
            await self.human.human_scroll(random.randint(100, 200))
        
        # 4. 基于价值的互动 (这里复用之前的 PROB_LIKE，或者你可以设高一点，因为内容相关)
        if random.random() < PROB_LIKE:
            if await self.human.click_element(SELECTORS["btn_like"], "点赞"):
                self.recorder.record_action("like", f"[Deep] {title}")

        if random.random() < PROB_COLLECT:
            if await self.human.click_element(SELECTORS["btn_collect"], "收藏"):
                self.recorder.record_action("collect", f"[Deep] {title}")

        # === 🎲 决策点 2: 要不要张嘴说话？ ===
        # LLM 觉得值得评，且随机数命中
        if analysis.get("should_comment"):
            if random.random() < PROB_POST_COMMENT:
                comment_text = analysis.get("comment_text")
                # 再次检查权限
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