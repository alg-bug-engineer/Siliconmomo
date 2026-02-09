import random
import time
from datetime import datetime
from typing import Optional, Tuple
from pathlib import Path
import json


class ContentStrategy:
    """
    内容策略引擎 - 决定发布什么类型的内容
    平衡价值内容、产品宣传和互动内容
    """

    def __init__(self, recorder, product_manager):
        self.recorder = recorder
        self.pm = product_manager
        self.stats_file = Path(__file__).parent.parent / "data" / "content_stats.json"
        self.stats = self._load_stats()

    def _load_stats(self) -> dict:
        """加载内容统计"""
        try:
            if self.stats_file.exists():
                with open(self.stats_file, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            self.recorder.log("warning", f"📊 [内容策略] 统计文件加载失败: {e}")

        # 默认统计结构
        return {
            "daily_stats": {},
            "promo_count_today": 0,
            "value_count_today": 0,
            "others_count_today": 0,
            "last_content_date": None,
            "last_promo_time": None
        }

    def _save_stats(self):
        """保存内容统计"""
        try:
            with open(self.stats_file, "w", encoding="utf-8") as f:
                json.dump(self.stats, f, indent=4, ensure_ascii=False)
        except Exception as e:
            self.recorder.log("error", f"📊 [内容策略] 保存统计失败: {e}")

    def _check_and_reset_daily(self):
        """检查是否需要重置每日统计"""
        today = datetime.now().strftime("%Y-%m-%d")
        last_date = self.stats.get("last_content_date")

        if last_date != today:
            # 新的一天，重置统计
            self.stats["daily_stats"][today] = {
                "promo": 0,
                "value": 0,
                "others": 0
            }
            self.stats["promo_count_today"] = 0
            self.stats["value_count_today"] = 0
            self.stats["others_count_today"] = 0
            self.stats["last_content_date"] = today
            self._save_stats()
            self.recorder.log("info", f"📊 [内容策略] 新的一天，统计已重置")

    # === 核心决策 ===

    def decide_content_type(self) -> Tuple[str, Optional[dict]]:
        """
        决定发布什么类型的内容
        :return: (内容类型, 相关产品)
        内容类型: 'value' / 'promo' / 'others'
        """
        self._check_and_reset_daily()

        strategy = self.pm.get_content_strategy()
        promo_ratio = strategy.get("promo_ratio", 0.3)
        value_ratio = strategy.get("value_ratio", 0.5)
        max_daily = strategy.get("max_daily_promo", 2)

        # 获取今日统计
        today_stats = self.stats.get("daily_stats", {}).get(
            self.stats.get("last_content_date", ""),
            {"promo": 0, "value": 0, "others": 0}
        )

        promo_count = today_stats.get("promo", 0)
        value_count = today_stats.get("value", 0)
        total_count = promo_count + value_count + today_stats.get("others", 0)

        # 1. 检查产品宣传配额
        if promo_count >= max_daily:
            # 已达宣传上限，只能发布价值内容或其他
            self.recorder.log("info", f"📊 [内容策略] 今日宣传已达上限 ({max_daily})，选择价值内容")
            return self._create_value_content()

        # 2. 检查宣传间隔
        can_promote, reason = self.pm.can_promote_now()
        if not can_promote:
            self.recorder.log("info", f"📊 [内容策略] {reason}")
            return self._create_value_content()

        # 3. 根据比例决定内容类型
        # 计算当前比例
        if total_count > 0:
            current_promo_ratio = promo_count / total_count
        else:
            current_promo_ratio = 0

        # 如果宣传比例不足，优先宣传
        if current_promo_ratio < promo_ratio:
            # 有一定概率发布宣传内容
            if random.random() < 0.7:  # 70% 概率
                return self._create_promo_content()

        # 根据随机数决定
        rand = random.random()
        if rand < promo_ratio and promo_count < max_daily:
            return self._create_promo_content()
        elif rand < promo_ratio + value_ratio:
            return self._create_value_content()
        else:
            return self._create_others_content()

    def _create_promo_content(self) -> Tuple[str, Optional[dict]]:
        """创建产品宣传内容"""
        product = self.pm.get_next_promo_product()

        # 记录统计
        self._record_content("promo")

        self.recorder.log("info", f"📦 [内容策略] 决定: 产品宣传 - {product.get('name', '')}")
        return "promo", product

    def _create_value_content(self) -> Tuple[str, Optional[dict]]:
        """创建价值内容（工具推荐、技巧分享等）"""
        # 记录统计
        self._record_content("value")

        self.recorder.log("info", "📊 [内容策略] 决定: 价值内容（建立信任）")
        return "value", None

    def _create_others_content(self) -> Tuple[str, Optional[dict]]:
        """创建其他内容（问答、互动等）"""
        # 记录统计
        self._record_content("others")

        self.recorder.log("info", "💬 [内容策略] 决定: 互动内容（活跃账号）")
        return "others", None

    def _record_content(self, content_type: str):
        """记录内容发布"""
        today = datetime.now().strftime("%Y-%m-%d")

        if today not in self.stats.get("daily_stats", {}):
            self.stats["daily_stats"][today] = {"promo": 0, "value": 0, "others": 0}

        self.stats["daily_stats"][today][content_type] = \
            self.stats["daily_stats"][today].get(content_type, 0) + 1

        if content_type == "promo":
            self.stats["promo_count_today"] += 1
            self.stats["last_promo_time"] = time.time()
        elif content_type == "value":
            self.stats["value_count_today"] += 1
        else:
            self.stats["others_count_today"] += 1

        self.stats["last_content_date"] = today
        self._save_stats()

    # === 辅助方法 ===

    def get_content_style(self, content_type: str, product: Optional[dict] = None) -> str:
        """
        根据内容类型获取推荐的风格
        :return: 风格名称
        """
        if content_type == "promo":
            # 产品宣传：推荐/教程/案例
            styles = ["工具推荐", "使用教程", "合集推荐"]
            return random.choice(styles)
        elif content_type == "value":
            # 价值内容：工具推荐、功能介绍、合集
            styles = ["工具推荐", "功能介绍", "合集推荐", "使用教程"]
            return random.choice(styles)
        else:
            # 互动内容
            styles = ["避坑指南", "使用教程", "工具推荐"]
            return random.choice(styles)

    def get_content_angle(self, product: dict, style: str) -> str:
        """
        获取产品内容的切入角度
        """
        angles = product.get("content_angles", [])
        if angles:
            return random.choice(angles)

        # 默认角度
        if style == "使用教程":
            return f"保姆级教程：3分钟学会{product.get('name', '')}"
        elif style == "合集推荐":
            return f"效率神器合集：{product.get('name', '')}"
        else:
            return product.get("tagline", "")

    def should_publish_now(self) -> Tuple[bool, str]:
        """
        判断现在是否应该发布内容
        考虑因素：
        1. 每日发布上限
        2. 发布时间点
        3. 内容比例平衡
        """
        from config.settings import PUBLISH_HOURS, DAILY_PUBLISH_LIMIT

        current_hour = datetime.now().hour
        today_stats = self.stats.get("daily_stats", {}).get(
            self.stats.get("last_content_date", ""),
            {"promo": 0, "value": 0, "others": 0}
        )
        total_today = sum(today_stats.values())

        # 检查每日上限
        if total_today >= DAILY_PUBLISH_LIMIT:
            return False, f"今日发布已达上限 ({DAILY_PUBLISH_LIMIT})"

        # 检查发布时间点（宽松模式：在时间点附近2小时内都可以）
        in_publish_time = False
        for hour in PUBLISH_HOURS:
            if abs(current_hour - hour) <= 2:
                in_publish_time = True
                break

        if not in_publish_time:
            return False, f"当前时间 {current_hour}点 不在发布时间点附近 {PUBLISH_HOURS}"

        return True, "可以发布"

    # === 统计查询 ===

    def get_today_stats(self) -> dict:
        """获取今日统计"""
        self._check_and_reset_daily()
        today = self.stats.get("last_content_date", "")

        return {
            "date": today,
            "promo": self.stats.get("promo_count_today", 0),
            "value": self.stats.get("value_count_today", 0),
            "others": self.stats.get("others_count_today", 0),
            "total": self.stats.get("promo_count_today", 0) +
                    self.stats.get("value_count_today", 0) +
                    self.stats.get("others_count_today", 0)
        }

    def get_summary(self) -> dict:
        """获取策略摘要"""
        strategy = self.pm.get_content_strategy()
        today_stats = self.get_today_stats()

        return {
            "content_strategy": {
                "promo_ratio": strategy.get("promo_ratio", 0.3),
                "value_ratio": strategy.get("value_ratio", 0.5),
                "max_daily_promo": strategy.get("max_daily_promo", 2),
                "promo_interval_hours": strategy.get("promo_interval_hours", 6)
            },
            "today_stats": today_stats,
            "can_promote_now": self.pm.can_promote_now()[0]
        }
