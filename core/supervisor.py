import asyncio
import time
import random
from datetime import datetime
from core.recovery import RecoveryAgent
from core.writer import WriterAgent
from core.artist import ArtistAgent
from core.publisher import PublisherAgent
from config.settings import BASE_URL, PUBLISH_HOURS

class Supervisor:
    def __init__(self, browser_manager, human, executor, recorder, max_duration=3600):
        self.bm = browser_manager
        self.human = human
        self.executor = executor
        self.recorder = recorder
        # 实例化维修工
        self.recovery = RecoveryAgent(browser_manager.page, recorder)
        self.max_duration = max_duration
        
        # 初始化创作相关Agent
        self.writer = WriterAgent(recorder)
        self.artist = ArtistAgent(browser_manager.page, recorder)
        self.publisher = PublisherAgent(browser_manager.page, recorder)
        
        # 故障计数器（用于日志记录，但不设上限）
        self.consecutive_failures = 0
        
        # 创作相关状态
        self.last_creation_time = 0
        self.creation_cooldown = 3600  # 创作冷却时间：1小时 

    async def start_shift(self):
        """开始轮班 - 持续运营循环（24小时）"""
        start_time = time.time()
        self.recorder.log("info", "👨‍✈️ [车间主任] 24小时运营启动，维修工待命")

        while time.time() - start_time < self.max_duration:
            try:
                # === 模式1：浏览互动（主要时间） ===
                await self.executor.execute_one_cycle()
                
                # === 模式2：创作发帖（条件触发） ===
                kb = self.executor.kb
                current_time = time.time()
                
                # 检查是否需要创作（积累3个高质量素材 + 冷却时间）
                if (kb.should_create_content() and 
                    current_time - self.last_creation_time > self.creation_cooldown):
                    await self._create_and_publish_cycle()
                    self.last_creation_time = current_time
                
                # 成功执行，重置故障计数器
                self.consecutive_failures = 0
                
                rest_time = random.uniform(2, 5)
                self.recorder.log("info", f"☕ [车间主任] 休息 {rest_time:.1f}s")
                await asyncio.sleep(rest_time)

            except KeyboardInterrupt:
                # 只有用户手动中断才退出
                self.recorder.log("warning", "用户手动中断")
                break
                
            except Exception as e:
                # === 异常处理：持续修复模式 ===
                self.consecutive_failures += 1
                self.recorder.log("error", f"🚨 异常发生 (连续第 {self.consecutive_failures} 次): {e}")
                
                # 致命伤检查（只有浏览器断开才放弃）
                error_msg = str(e)
                if "Target closed" in error_msg or "Session closed" in error_msg:
                    self.recorder.log("critical", "💀 浏览器已断开，无法继续")
                    break
                
                # 呼叫维修工（持续修复，不设上限）
                is_fixed = await self.recovery.diagnose_and_fix(e)
                
                if is_fixed:
                    self.recorder.log("info", "✅ 维修成功，继续运营")
                    self.consecutive_failures = 0  # 重置计数，给机会
                    await asyncio.sleep(2)
                    continue
                else:
                    # 维修失败，但不退出，而是执行深度恢复
                    self.recorder.log("warning", "⚠️ 维修失败，执行深度恢复...")
                    await self._deep_recovery()
                    await asyncio.sleep(10)  # 等待更长时间
                    continue  # 继续循环，不退出
        
        self.recorder.log("info", "👨‍✈️ [车间主任] 下班时间到")
    
    async def _create_and_publish_cycle(self):
        """创作+发帖流程"""
        try:
            self.recorder.log("info", "🎨 [创作流程] 开始创作+发帖流程...")
            
            # 1. 从素材库选一个高质量素材
            inspiration, error = self.writer.pick_inspiration()
            if not inspiration:
                self.recorder.log("warning", "🎨 [创作流程] 素材库不足，跳过创作")
                return
            
            # 2. 创作文案
            draft = self.writer.write_from_inspiration(inspiration)
            if not draft:
                self.recorder.log("error", "🎨 [创作流程] 文案创作失败")
                return
            
            self.recorder.log("info", f"🎨 [创作流程] 文案已生成: 《{draft.get('title', '')}》")
            
            # 3. 生图
            await self.artist.open_studio()
            image_path = await self.artist.generate_image(draft['image_prompt'])
            if not image_path:
                self.recorder.log("error", "🎨 [创作流程] 生图失败，但继续保存草稿")
                # 即使生图失败，也保存草稿（可以后续手动配图）
            
            # 4. 保存草稿
            if image_path:
                self.writer.save_draft(draft, image_path)
                self.recorder.log("info", "🎨 [创作流程] 草稿已保存")
            else:
                self.recorder.log("warning", "🎨 [创作流程] 生图失败，未保存草稿")
                return
            
            # 5. 标记素材为已使用
            kb = self.executor.kb
            kb.mark_as_used(inspiration.get("id"))
            
            # 6. 判断是否应该发布（在配置的发布时间点）
            current_hour = datetime.now().hour
            if current_hour in PUBLISH_HOURS:
                # 在发布时间点，尝试发布
                self.recorder.log("info", f"📤 [发布流程] 当前时间 {current_hour} 点在发布时间点，尝试发布...")
                publish_success = await self.publisher.publish_draft(draft)
                if publish_success:
                    self.writer.mark_draft_published(draft.get("created_at"))
                    self.recorder.log("success", "🎉 [创作流程] 创作+发布完成！")
                else:
                    self.recorder.log("warning", "📤 [发布流程] 发布失败，但草稿已保存，可后续手动发布")
            else:
                # 不在发布时间点，只保存草稿
                self.recorder.log("info", f"📤 [发布流程] 当前时间 {current_hour} 点不在发布时间点 {PUBLISH_HOURS}，草稿已保存待发布")
            
        except Exception as e:
            self.recorder.log("error", f"🎨 [创作流程] 创作流程异常: {e}")
            # 创作流程失败不影响主循环，继续浏览互动
    
    async def _deep_recovery(self):
        """深度恢复：刷新页面、重新初始化"""
        try:
            self.recorder.log("info", "🔄 [深度恢复] 开始执行...")
            await self.bm.page.reload()
            await self.bm.page.wait_for_load_state("domcontentloaded")
            await asyncio.sleep(3)
            
            # 确保回到小红书首页
            if "xiaohongshu.com" not in self.bm.page.url:
                await self.bm.page.goto(BASE_URL)
                await asyncio.sleep(2)
            
            self.recorder.log("info", "🔄 [深度恢复] 完成，环境已重置")
        except Exception as e:
            self.recorder.log("error", f"🔄 [深度恢复] 失败: {e}")