import json
import time
import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class ProductManager:
    """
    产品管理器 - 管理插件产品库和宣传策略
    """

    def __init__(self, recorder):
        self.recorder = recorder
        self.file_path = Path(__file__).parent.parent / "data" / "products.json"
        self.data = self._load_data()
        self.current_promo_index = 0  # 轮播索引

    def _load_data(self) -> dict:
        """加载产品库数据"""
        try:
            if not self.file_path.exists():
                self.recorder.log("error", "📦 [产品库] 文件不存在，使用默认配置")
                return self._get_default_data()

            with open(self.file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            self.recorder.log("info", f"📦 [产品库] 已加载 {len(data.get('products', []))} 个产品")
            return data

        except Exception as e:
            self.recorder.log("error", f"📦 [产品库] 加载失败: {e}")
            return self._get_default_data()

    def _get_default_data(self) -> dict:
        """获取默认数据结构"""
        return {
            "products": [],
            "content_strategy": {
                "promo_ratio": 0.3,
                "value_ratio": 0.5,
                "others_ratio": 0.2,
                "max_daily_promo": 2,
                "promo_interval_hours": 6,
                "daily_publish_limit": 4
            },
            "interaction_strategy": {
                "help_first_ratio": 0.6,
                "value_share_ratio": 0.3,
                "direct_promo_ratio": 0.1,
                "max_daily_direct_promo": 1,
                "trigger_keywords": {}
            }
        }

    def _save_data(self):
        """保存产品库数据"""
        try:
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            self.recorder.log("error", f"📦 [产品库] 保存失败: {e}")

    # === 产品查询 ===

    def get_all_products(self) -> List[dict]:
        """获取所有产品"""
        return self.data.get("products", [])

    def get_product_by_id(self, product_id: str) -> Optional[dict]:
        """根据ID获取产品"""
        for product in self.get_all_products():
            if product.get("id") == product_id:
                return product
        return None

    def get_products_by_category(self, category: str) -> List[dict]:
        """根据分类获取产品"""
        return [
            p for p in self.get_all_products()
            if p.get("category") == category
        ]

    # === 宣传策略 ===

    def get_next_promo_product(self) -> Optional[dict]:
        """
        获取下一个要宣传的产品（轮播策略）
        返回产品对象，如果没有产品则返回 None
        """
        products = self.get_all_products()
        if not products:
            return None

        # 轮播策略：按顺序选择
        product = products[self.current_promo_index % len(products)]
        self.current_promo_index += 1

        self.recorder.log("info", f"📦 [产品库] 轮播宣传: {product.get('name')}")
        return product

    def get_random_product(self) -> Optional[dict]:
        """随机获取一个产品"""
        products = self.get_all_products()
        if not products:
            return None
        return random.choice(products)

    def match_product_by_content(self, title: str, content: str) -> Optional[dict]:
        """
        根据帖子内容匹配合适的产品
        通过关键词匹配和语义分析
        """
        if not title and not content:
            return None

        combined_text = f"{title} {content}".lower()
        products = self.get_all_products()

        if not products:
            return None

        # 计算每个产品的匹配分数
        scores = []
        for product in products:
            score = 0
            keywords = product.get("keywords", [])

            # 关键词匹配
            for keyword in keywords:
                if keyword.lower() in combined_text:
                    score += 1

            if score > 0:
                scores.append((score, product))

        # 返回匹配分数最高的产品
        if scores:
            scores.sort(key=lambda x: x[0], reverse=True)
            best_product = scores[0][1]
            self.recorder.log("info", f"📦 [产品库] 内容匹配: {best_product.get('name')} (分数: {scores[0][0]})")
            return best_product

        return None

    # === 宣传统计 ===

    def record_promo(self, product_id: str, success: bool = True, context: str = ""):
        """
        记录宣传行为
        :param product_id: 产品ID
        :param success: 是否成功
        :param context: 上下文（comment/post/review）
        """
        product = self.get_product_by_id(product_id)
        if not product:
            return

        stats = product.get("promo_stats", {})
        stats["total_mentions"] = stats.get("total_mentions", 0) + 1
        stats["last_promote"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if success:
            stats["success_count"] = stats.get("success_count", 0) + 1

        product["promo_stats"] = stats
        self._save_data()

        self.recorder.log("info", f"📦 [产品库] 记录宣传: {product.get('name')} (总计: {stats['total_mentions']})")

    # === 配额检查 ===

    def get_content_strategy(self) -> dict:
        """获取内容策略配置"""
        return self.data.get("content_strategy", {})

    def get_interaction_strategy(self) -> dict:
        """获取互动策略配置"""
        return self.data.get("interaction_strategy", {})

    def can_promote_now(self, product_id: Optional[str] = None) -> Tuple[bool, str]:
        """
        检查现在是否可以宣传
        :return: (是否可以, 原因说明)
        """
        strategy = self.get_content_strategy()

        # 检查每日宣传上限
        max_daily = strategy.get("max_daily_promo", 2)
        today_count = self._get_today_promo_count()

        if today_count >= max_daily:
            return False, f"今日宣传次数已达上限 ({max_daily})"

        # 检查宣传间隔
        interval_hours = strategy.get("promo_interval_hours", 6)
        last_promo_time = self._get_last_promo_time()

        if last_promo_time:
            time_diff = datetime.now() - last_promo_time
            if time_diff < timedelta(hours=interval_hours):
                remaining_hours = interval_hours - time_diff.total_seconds() / 3600
                return False, f"距离上次宣传不足 {interval_hours} 小时 (剩余 {remaining_hours:.1f} 小时)"

        return True, "可以宣传"

    def _get_today_promo_count(self) -> int:
        """获取今日宣传次数"""
        count = 0
        today = datetime.now().strftime("%Y-%m-%d")

        for product in self.get_all_products():
            last_promote = product.get("promo_stats", {}).get("last_promote", "")
            if last_promote and last_promote.startswith(today):
                count += 1

        return count

    def _get_last_promo_time(self) -> Optional[datetime]:
        """获取最后一次宣传时间"""
        last_time = None

        for product in self.get_all_products():
            last_promote_str = product.get("promo_stats", {}).get("last_promote")
            if last_promote_str:
                try:
                    promo_time = datetime.strptime(last_promote_str, "%Y-%m-%d %H:%M:%S")
                    if last_time is None or promo_time > last_time:
                        last_time = promo_time
                except:
                    pass

        return last_time

    # === 数据统计 ===

    def get_stats(self) -> dict:
        """获取产品库统计信息"""
        products = self.get_all_products()
        strategy = self.get_content_strategy()

        total_promos = sum(
            p.get("promo_stats", {}).get("total_mentions", 0)
            for p in products
        )

        today_count = self._get_today_promo_count()

        return {
            "total_products": len(products),
            "total_promotions": total_promos,
            "today_promotions": today_count,
            "max_daily_promo": strategy.get("max_daily_promo", 2),
            "can_promote_now": self.can_promote_now()[0]
        }

    # === 内容辅助 ===

    def get_product_content_template(self, product_id: str, style: str = "推荐") -> dict:
        """
        获取产品内容模板
        :param product_id: 产品ID
        :param style: 风格（推荐/教程/案例）
        """
        product = self.get_product_by_id(product_id)
        if not product:
            return {}

        templates = {
            "推荐": {
                "title_template": f"效率神器：{product.get('tagline', '')}",
                "content_structure": "痛点介绍 → 解决方案 → 产品介绍 → 使用场景 → 引导购买",
                "emoji_pool": ["🚀", "⚡", "💡", "🔧", "✨", "🎯"]
            },
            "教程": {
                "title_template": f"保姆级教程：3分钟学会{product.get('name', '')}",
                "content_structure": "问题引入 → 准备工作 → 操作步骤 → 注意事项 → 总结",
                "emoji_pool": ["📝", "📸", "✅", "💪", "🎓", "📚"]
            },
            "案例": {
                "title_template": f"我是如何用{product.get('name', '')}提升效率的",
                "content_structure": "遇到的问题 → 尝试过的方案 → 最终解决方案 → 效果对比",
                "emoji_pool": ["💼", "📈", "🎯", "⭐", "🏆", "💎"]
            }
        }

        base_template = templates.get(style, templates["推荐"])
        base_template["product"] = product

        return base_template

    def get_trigger_keywords_map(self) -> dict:
        """获取触发关键词映射（用于互动匹配）"""
        return self.data.get("interaction_strategy", {}).get("trigger_keywords", {})

    def decide_interaction_type(self) -> str:
        """
        决定互动类型（保守策略）
        :return: 'help_first' / 'value_share' / 'direct_promo'
        """
        strategy = self.get_interaction_strategy()

        ratios = [
            (strategy.get("help_first_ratio", 0.6), "help_first"),
            (strategy.get("value_share_ratio", 0.3), "value_share"),
            (strategy.get("direct_promo_ratio", 0.1), "direct_promo")
        ]

        rand = random.random()
        cumulative = 0

        for ratio, interaction_type in ratios:
            cumulative += ratio
            if rand <= cumulative:
                return interaction_type

        return "help_first"
