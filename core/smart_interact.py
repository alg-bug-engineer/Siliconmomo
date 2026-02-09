import random
from core.llm_client import LLMClient
from core.product_manager import ProductManager


class SmartInteractAgent:
    """
    智能互动Agent - 整合产品宣传的智能互动决策
    职责：决定互动类型（纯互动/软广）并生成相应评论
    """

    def __init__(self, recorder, product_manager: ProductManager):
        self.recorder = recorder
        self.pm = product_manager
        self.llm = LLMClient(recorder)

    def decide_interaction(self, title: str, content: str) -> dict:
        """
        决定互动类型并生成评论
        :param title: 帖子标题
        :param content: 帖子内容
        :return: 互动决策字典
        """
        # 1. 基础分析：判断是否相关
        analysis = self.llm.analyze_and_comment(title, content)

        if not analysis.get("is_relevant"):
            return {
                "should_interact": False,
                "reason": "内容不相关",
                "comment": None
            }

        # 2. 匹配产品
        products = self.pm.get_all_products()
        matched_product = self.llm.match_post_to_product(title, content, products)

        # 3. 决定互动类型
        if matched_product:
            # 有匹配产品，决定是否做软广
            return self._decide_promo_interaction(title, content, matched_product, analysis)
        else:
            # 无匹配产品，普通互动
            return self._decide_normal_interaction(title, content, analysis)

    def _decide_promo_interaction(self, title: str, content: str, product: dict, analysis: dict) -> dict:
        """
        决定产品宣传互动
        """
        # 检查今日宣传配额
        can_promote, reason = self.pm.can_promote_now(product.get("id"))

        # 检查今日直接宣传次数
        stats = self.pm.get_stats()
        today_promo = stats.get("today_promotions", 0)
        strategy = self.pm.get_interaction_strategy()
        max_direct = strategy.get("max_daily_direct_promo", 1)

        # 决定互动类型
        interaction_type = self.pm.decide_interaction_type()

        # 如果今日直接宣传已达上限，降级为帮助优先
        if interaction_type == "direct_promo" and today_promo >= max_direct:
            interaction_type = "help_first"
            self.recorder.log("info", f"📊 [智能互动] 今日直接宣传达上限，降级为 help_first")

        # 生成评论
        if can_promote:
            promo_result = self.llm.generate_promo_comment(
                title, content, product, interaction_type
            )

            return {
                "should_interact": True,
                "interaction_type": "promo",
                "promo_type": interaction_type,
                "product": product,
                "comment": promo_result.get("comment_text"),
                "product_id": product.get("id"),
                "is_natural": promo_result.get("is_natural", True)
            }
        else:
            # 达到宣传上限，普通互动但记录产品匹配
            self.recorder.log("info", f"📊 [智能互动] {reason}，执行普通互动")

            return {
                "should_interact": True,
                "interaction_type": "normal",
                "matched_product": product,
                "comment": analysis.get("comment_text"),
                "reason": f"匹配到产品但{reason}"
            }

    def _decide_normal_interaction(self, title: str, content: str, analysis: dict) -> dict:
        """
        决定普通互动（无产品匹配）
        """
        should_comment = analysis.get("should_comment", False)

        if should_comment and random.random() < 0.7:  # 70% 概率评论
            return {
                "should_interact": True,
                "interaction_type": "normal",
                "comment": analysis.get("comment_text"),
                "is_high_quality": analysis.get("is_high_quality", False)
            }
        else:
            return {
                "should_interact": True,
                "interaction_type": "like_only",  # 只点赞收藏，不评论
                "comment": None
            }

    def get_comment_templates(self, interaction_type: str = "normal") -> list:
        """
        获取评论模板
        :param interaction_type: 互动类型（normal/promo/help_first/value_share/direct_promo）
        """
        import json
        from pathlib import Path

        emotions_file = Path(__file__).parent.parent / "data" / "emotions.json"

        try:
            if emotions_file.exists():
                with open(emotions_file, "r", encoding="utf-8") as f:
                    emotions = json.load(f)

                templates = emotions.get("comment_templates", {})

                if interaction_type == "promo":
                    return templates.get("软广推广", [])
                elif interaction_type == "normal":
                    # 合并工具交流和简单互动
                    return templates.get("工具交流", []) + templates.get("简单互动", [])
                else:
                    return templates.get("软广推广", [])

        except Exception as e:
            self.recorder.log("warning", f"⚠️ [智能互动] 加载评论模板失败: {e}")

        # 默认模板
        return [
            "这个工具真的好用！🔧",
            "已收藏，慢慢试 ✨",
            "👍",
            "🔥"
        ]

    def record_interaction(self, interaction_result: dict):
        """
        记录互动行为
        """
        if interaction_result.get("interaction_type") == "promo":
            product_id = interaction_result.get("product_id")
            if product_id:
                success = interaction_result.get("comment") is not None
                self.pm.record_promo(
                    product_id,
                    success=success,
                    context="comment"
                )
                self.recorder.log("info", f"📊 [智能互动] 已记录产品宣传: {product_id}")

    def get_daily_stats(self) -> dict:
        """获取今日互动统计"""
        stats = self.pm.get_stats()
        return {
            "product_promos_today": stats.get("today_promotions", 0),
            "can_promote_now": stats.get("can_promote_now", True),
            "max_daily_promo": stats.get("max_daily_promo", 2)
        }
