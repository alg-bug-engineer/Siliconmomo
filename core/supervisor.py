import asyncio
import time
import random
from datetime import datetime
from typing import Dict, List
from core.recovery import RecoveryAgent
from core.writer import WriterAgent
from core.artist import ArtistAgent
from core.publisher import PublisherAgent
from core.product_manager import ProductManager
from core.content_strategy import ContentStrategy
from core.smart_interact import SmartInteractAgent
from core.analytics import ContentAnalytics
from core.viral_analyzer import ViralAnalyzer
from core.trend_tracker import TrendTracker
from config.settings import BASE_URL, PUBLISH_HOURS, INSPIRATION_THRESHOLD, ENABLE_PHASE2_ANALYTICS, ANALYSIS_INTERVAL, ENABLE_PHASE4_TRENDS

class Supervisor:
    def __init__(self, browser_manager, human, executor, recorder, max_duration=3600):
        self.bm = browser_manager
        self.human = human
        self.executor = executor
        self.recorder = recorder
        # 实例化维修工
        self.recovery = RecoveryAgent(browser_manager.page, recorder)
        self.max_duration = max_duration

        # === 新增：产品管理和内容策略 ===
        self.product_manager = ProductManager(recorder)
        self.content_strategy = ContentStrategy(recorder, self.product_manager)
        self.smart_interact = SmartInteractAgent(recorder, self.product_manager)

        # 初始化创作相关Agent（传入 product_manager）
        self.writer = WriterAgent(recorder, self.product_manager)
        self.artist = ArtistAgent(browser_manager.page, recorder)
        self.publisher = PublisherAgent(browser_manager.page, recorder)

        # === Phase 2: 数据分析和爆款拆解 ===
        if ENABLE_PHASE2_ANALYTICS:
            self.analytics = ContentAnalytics(recorder)
            self.viral_analyzer = ViralAnalyzer(recorder, self.analytics)
            self.last_analysis_time = 0
            self.analysis_interval = ANALYSIS_INTERVAL  # 从配置读取，默认4小时
            self.viral_patterns = {}  # 缓存的爆款模式
            self.recorder.log("info", "📊 [车间主任] Phase 2 数据分析已启用")
        else:
            self.analytics = None
            self.viral_analyzer = None

        # === Phase 4: 热点趋势追踪 ===
        if ENABLE_PHASE4_TRENDS:
            self.trend_tracker = TrendTracker(recorder)
            self.recorder.log("info", "🔥 [车间主任] Phase 4 热点追踪已启用")
        else:
            self.trend_tracker = None

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

                # === Phase 2: 定期数据分析（每天一次） ===
                if self.analytics and current_time - self.last_analysis_time > self.analysis_interval:
                    await self._perform_data_analysis()
                    self.last_analysis_time = current_time

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
        """创作+发帖流程（支持产品宣传）"""
        try:
            self.recorder.log("info", "🎨 [创作流程] 开始创作+发帖流程...")

            # 显示素材库统计
            stats = self.executor.kb.get_stats()
            self.recorder.log("info",
                f"📊 [素材库] 总计:{stats['total']} | "
                f"未使用:{stats['unused']} | "
                f"高质量未使用:{stats['high_quality_unused']} | "
                f"已使用:{stats['used']}"
            )

            # 1. 决定内容类型（价值内容 vs 产品宣传）
            content_type, product = self.content_strategy.decide_content_type()
            self.recorder.log("info", f"🎨 [创作流程] 内容类型: {content_type}")

            # 2. 根据类型创作
            if content_type == "promo" and product:
                # 产品宣传
                style = self.content_strategy.get_content_style(content_type, product)
                draft = self.writer.write_from_product(product, style)

                if draft:
                    self.recorder.log("info", f"🎨 [创作流程] 产品宣传已生成: 《{draft.get('title', '')}》")
                    # 记录宣传
                    self.product_manager.record_promo(product.get("id"), success=True, context="post")
                else:
                    self.recorder.log("error", "🎨 [创作流程] 产品宣传创作失败")
                    return

            else:
                # 价值内容（从素材库）
                inspiration, error = self.writer.pick_inspiration()
                if not inspiration:
                    self.recorder.log("warning", "🎨 [创作流程] 素材库不足，跳过创作")
                    return

                draft = self.writer.write_from_inspiration(inspiration)
                if not draft:
                    self.recorder.log("error", "🎨 [创作流程] 文案创作失败")
                    return

                self.recorder.log("info", f"🎨 [创作流程] 价值内容已生成: 《{draft.get('title', '')}》")

                # 创作完成后，批量标记多条高质量素材为已使用（避免素材堆积）
                marked_count = self.executor.kb.mark_multiple_as_used(count=INSPIRATION_THRESHOLD)
                self.recorder.log("info", f"🎨 [创作流程] 已批量标记 {len(marked_count)} 条素材为已使用")

                # 显示更新后的素材库统计
                stats_after = self.executor.kb.get_stats()
                self.recorder.log("info",
                    f"📊 [素材库-更新] 总计:{stats_after['total']} | "
                    f"未使用:{stats_after['unused']} | "
                    f"高质量未使用:{stats_after['high_quality_unused']} | "
                    f"已使用:{stats_after['used']}"
                )

            # 3. 生图
            await self.artist.open_studio()
            image_path = await self.artist.generate_image(draft['image_prompt'])

            # 生图后立即返回小红书环境（防止停留在即梦平台）
            if image_path:
                await self.artist.ensure_back_to_xhs()

            if not image_path:
                self.recorder.log("error", "🎨 [创作流程] 生图失败，但继续保存草稿")

            # 4. 保存草稿
            if image_path:
                self.writer.save_draft(draft, image_path)
                self.recorder.log("info", "🎨 [创作流程] 草稿已保存")
            else:
                self.recorder.log("warning", "🎨 [创作流程] 生图失败，未保存草稿")
                return

            # 5. 判断是否应该发布（在配置的发布时间点）
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

    # === Phase 2 & 4: 数据分析方法 ===

    async def _perform_data_analysis(self):
        """执行定期数据分析（每4小时）"""
        try:
            self.recorder.log("info", "📊 [数据分析] 开始执行定期分析...")

            # 1. Phase 2: 获取爆款模式
            if self.viral_analyzer:
                self.viral_patterns = self.viral_analyzer.get_viral_patterns(top_n=10)

                if self.viral_patterns:
                    self.recorder.log("info", "📊 [数据分析] 爆款模式分析完成")

                    # 记录关键发现
                    if "title_patterns" in self.viral_patterns:
                        most_common = self.viral_patterns["title_patterns"].get("most_common_type", "")
                        self.recorder.log("info", f"   - 最常见标题类型: {most_common}")

                    if "recommendations" in self.viral_patterns:
                        self.recorder.log("info", "   - 优化建议已生成")
                        for rec in self.viral_patterns["recommendations"][:3]:
                            self.recorder.log("info", f"     * {rec}")

                    # 保存分析结果
                    self.viral_analyzer.save_analysis(self.viral_patterns)
                else:
                    self.recorder.log("warning", "📊 [数据分析] 数据不足，无法生成模式")

                # 获取高表现内容
                top_posts = self.analytics.get_top_performing(limit=5)
                if top_posts:
                    self.recorder.log("info", f"📊 [数据分析] 找到 {len(top_posts)} 个高表现内容")

            # 2. Phase 4: 分析热点趋势
            if self.trend_tracker:
                self.recorder.log("info", "🔥 [热点追踪] 开始分析热点趋势...")

                # 清理过期热点
                self.trend_tracker.cleanup_expired_trends()

                # 获取当前热点
                active_trends = self.trend_tracker.get_active_trends(limit=10)
                if active_trends:
                    self.recorder.log("info", f"🔥 [热点追踪] 当前热点数: {len(active_trends)}")

                    # 获取热门话题
                    hot_topics = self.trend_tracker.get_trending_topics(5)
                    if hot_topics:
                        self.recorder.log("info", f"🔥 [热点追踪] 热门话题:")
                        for topic, score in hot_topics:
                            self.recorder.log("info", f"   - {topic}: {score:.0f} 热度")

                    # 分析热点模式
                    trend_patterns = self.trend_tracker.analyze_trend_patterns()
                    if "title_patterns" in trend_patterns:
                        self.recorder.log("info", f"🔥 [热点追踪] 标题模式分布: {trend_patterns['title_patterns']}")

                    # 打印热点摘要
                    summary = self.trend_tracker.get_trend_summary()
                    self.recorder.log("info", f"\n{summary}")
                else:
                    self.recorder.log("info", "🔥 [热点追踪] 暂无热点数据")

        except Exception as e:
            self.recorder.log("error", f"📊 [数据分析] 分析失败: {e}")

    def get_viral_insights(self) -> Dict:
        """获取当前爆款模式洞察（供内容创作使用）"""
        return self.viral_patterns if hasattr(self, 'viral_patterns') else {}

    def get_content_recommendations(self) -> List[str]:
        """获取内容创作建议"""
        insights = self.get_viral_insights()
        return insights.get("recommendations", [])

    # === Phase 4: 热点追踪方法 ===

    def record_hot_post(self, title: str, content: str, url: str,
                       likes: int, collects: int, comments: int, views: int,
                       image_urls: List[str] = None):
        """记录热点帖子（供浏览模块调用）"""
        if self.trend_tracker:
            return self.trend_tracker.record_hot_post(
                title, content, url, likes, collects, comments, views, image_urls
            )
        return False

    def get_trend_inspirations(self, limit: int = 5) -> List[Dict]:
        """获取热点仿写灵感"""
        if self.trend_tracker:
            return self.trend_tracker.get_trend_inspirations(limit)
        return []

    def get_active_trends(self, limit: int = 10) -> List[Dict]:
        """获取活跃热点"""
        if self.trend_tracker:
            return self.trend_tracker.get_active_trends(limit)
        return []

    def get_trending_topics(self, limit: int = 5) -> List[tuple]:
        """获取热门话题"""
        if self.trend_tracker:
            return self.trend_tracker.get_trending_topics(limit)
        return []