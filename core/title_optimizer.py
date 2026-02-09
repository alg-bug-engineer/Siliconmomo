"""
标题优化器 - 提升小红书笔记标题吸引力

功能：
1. 爆款标题模板库（数字型、疑问型、对比型）
2. 标题吸引力评分
3. A/B测试生成多个版本
4. 情感化表达增强
"""

import random
import re
from typing import List, Dict
from core.llm_client import LLMClient


class TitleOptimizer:
    """小红书标题优化器"""

    def __init__(self, recorder):
        self.recorder = recorder
        # LLM client 延迟初始化，只在需要时创建
        self.llm = None

        # 爆款标题模板库
        self.templates = {
            "数字型": [
                "5个{关键词}神器，打工人必看！",
                "3款{关键词}工具，效率翻倍！",
                "这{数字}个{关键词}，相见恨晚！",
                "{数字}种{关键词}方法，第{数字}个绝了！",
                "亲测！这{数字}款{关键词}太好用了！",
            ],
            "疑问型": [
                "为什么你的{关键词}总是不够快？",
                "还在用传统{关键词}？试试这个！",
                "你知道{关键词}的正确打开方式吗？",
                "{关键词}真的有用吗？亲测告诉你！",
                "怎么用{关键词}提高效率？看这篇就够了！",
            ],
            "对比型": [
                "用了{关键词}后，再也回不去了！",
                "没用{关键词}前 vs 用了之后",
                "后悔没有早点用这个{关键词}！",
                "这个{关键词}吊打其他工具！",
                "同样是{关键词}，为什么我比你快？",
            ],
            "痛点型": [
                "加班到深夜？试试这个{关键词}！",
                "效率低？这个{关键词}能救命！",
                "任务太多？{关键词}帮你轻松搞定！",
                "时间不够用？{关键词}让你效率起飞！",
                "懒人必备！{关键词}让你躺赢！",
            ],
            "干货型": [
                "保姆级教程！{关键词}从入门到精通",
                "建议收藏！{关键词}使用全攻略",
                "手把手教你用{关键词}提升效率",
                "{关键词}避坑指南，新手必看！",
                "吐血整理！{关键词}最全使用技巧",
            ],
            "情感型": [
                "相见恨晚！这个{关键词}太香了！",
                "被问爆了！都在用这个{关键词}",
                "绝了！这个{关键词}改变了我",
                "按头安利！这个{关键词}一定要试",
                "真香！{关键词}让我效率起飞",
            ],
        }

        # 情感化前缀
        self.emotional_prefixes = [
            "😭", "😍", "🤯", "🔥", "⚡", "✨", "💡", "🚀",
            "救命", "绝了", "太香了", "被问爆了", "相见恨晚"
        ]

        # 紧迫性词汇
        self.urgency_words = [
            "必看", "必备", "赶紧", "马上", "立即", "速看",
            "建议收藏", "错过后悔", "手慢无"
        ]

    def optimize_title(self, original_title: str, content_summary: str = "") -> Dict:
        """
        优化标题

        Args:
            original_title: 原始标题
            content_summary: 内容摘要（可选，用于生成更精准的标题）

        Returns:
            优化结果字典，包含：
            - original: 原始标题
            - optimized: 优化后的标题
            - alternatives: 其他备选标题
            - score: 吸引力评分
        """
        # 1. 分析原始标题
        keywords = self._extract_keywords(original_title)
        category = self._guess_category(content_summary or original_title)

        # 2. 生成优化标题
        optimized_title = self._generate_optimized_title(keywords, category)

        # 3. 生成备选标题
        alternative_titles = self._generate_alternatives(keywords, category)

        # 4. 计算吸引力评分
        score = self._calculate_score(optimized_title)

        return {
            "original": original_title,
            "optimized": optimized_title,
            "alternatives": alternative_titles,
            "score": score,
            "category": category
        }

    def _extract_keywords(self, title: str) -> List[str]:
        """从标题中提取关键词"""
        # 常见关键词
        common_keywords = [
            "AI工具", "AI", "插件", "浏览器", "效率",
            "写作", "绘图", "自动化", "神器", "推荐"
        ]

        keywords = []
        title_lower = title.lower()

        for keyword in common_keywords:
            if keyword.lower() in title_lower:
                keywords.append(keyword)

        # 如果没有找到常见关键词，提取主要名词
        if not keywords:
            # 简单提取：提取2-4个字的词组
            words = re.findall(r'[\u4e00-\u9fa5]{2,4}', title)
            if words:
                keywords.append(words[0])

        return keywords[:3]  # 最多返回3个关键词

    def _guess_category(self, text: str) -> str:
        """猜测内容类别"""
        if any(word in text for word in ["工具", "插件", "软件", "APP"]):
            return "工具推荐"
        elif any(word in text for word in ["教程", "方法", "技巧", "怎么"]):
            return "使用教程"
        elif any(word in text for word in ["避坑", "注意", "不要", "错误"]):
            return "避坑指南"
        elif any(word in text for word in ["款", "个", "种", "系列"]):
            return "合集推荐"
        else:
            return "工具推荐"

    def _generate_optimized_title(self, keywords: List[str], category: str) -> str:
        """生成优化标题"""
        if not keywords:
            return self._add_emotion_and_urgency("AI工具推荐")

        keyword = keywords[0]  # 使用第一个关键词

        # 根据类别选择模板
        if category == "工具推荐":
            template_type = random.choice(["数字型", "情感型", "对比型"])
        elif category == "使用教程":
            template_type = random.choice(["干货型", "疑问型"])
        elif category == "避坑指南":
            template_type = random.choice(["痛点型", "干货型"])
        else:
            template_type = random.choice(list(self.templates.keys()))

        # 获取模板
        templates = self.templates.get(template_type, self.templates["数字型"])
        template = random.choice(templates)

        # 填充模板
        if "{数字}" in template:
            number = random.randint(3, 10)
            title = template.format(关键词=keyword, 数字=number)
        else:
            title = template.format(关键词=keyword)

        # 添加情感和紧迫性
        title = self._add_emotion_and_urgency(title)

        return title

    def _generate_alternatives(self, keywords: List[str], category: str) -> List[str]:
        """生成多个备选标题"""
        alternatives = []

        if not keywords:
            keywords = ["AI工具"]

        keyword = keywords[0]

        # 从不同类型模板中生成
        template_types = list(self.templates.keys())[:4]  # 取前4种类型

        for template_type in template_types:
            templates = self.templates.get(template_type, [])
            if templates:
                template = random.choice(templates)

                if "{数字}" in template:
                    number = random.randint(3, 10)
                    title = template.format(关键词=keyword, 数字=number)
                else:
                    title = template.format(关键词=keyword)

                title = self._add_emotion_and_urgency(title)
                alternatives.append(title)

        return alternatives

    def _add_emotion_and_urgency(self, title: str) -> str:
        """添加情感和紧迫性元素"""
        # 30% 概率添加前缀
        if random.random() < 0.3:
            prefix = random.choice(self.emotional_prefixes)
            title = f"{prefix} {title}"

        # 20% 概率添加紧迫性词汇
        if random.random() < 0.2:
            urgency = random.choice(self.urgency_words)
            if not title.endswith(urgency):
                title = f"{title}{urgency}！"

        # 添加表情符号（如果没有）
        if not any(emoji in title for emoji in ["😭", "😍", "🤯", "🔥", "⚡", "✨", "💡", "🚀"]):
            emoji = random.choice(["🔥", "⚡", "✨", "🚀"])
            title = f"{title}{emoji}"

        return title

    def _calculate_score(self, title: str) -> float:
        """
        计算标题吸引力评分

        评分维度：
        - 长度控制（10-25字最佳）
        - 数字使用
        - 情感词汇
        - 紧迫性词汇
        - 疑问句式
        """
        score = 0.0

        # 1. 长度评分（15-25字最佳）
        length = len(title)
        if 15 <= length <= 25:
            score += 30
        elif 10 <= length < 15 or 25 < length <= 30:
            score += 20
        elif length < 10:
            score += 10

        # 2. 数字评分
        if re.search(r'\d+', title):
            score += 20

        # 3. 情感词汇评分
        emotion_count = sum(1 for word in self.emotional_prefixes if word in title)
        score += min(emotion_count * 10, 20)

        # 4. 紧迫性词汇评分
        urgency_count = sum(1 for word in self.urgency_words if word in title)
        score += min(urgency_count * 5, 15)

        # 5. 疑问句式评分
        if "?" in title or "吗" in title or "怎么" in title:
            score += 10

        # 6. 表情符号评分
        emoji_count = len(re.findall(r'[😭😍🤯🔥⚡✨💡🚀]', title))
        score += min(emoji_count * 5, 10)

        return min(score, 100)  # 最高100分

    def generate_ab_test_titles(self, original_title: str, count: int = 3) -> List[Dict]:
        """
        生成A/B测试标题

        Args:
            original_title: 原始标题
            count: 生成数量

        Returns:
            标题列表，每个包含标题和评分
        """
        result = self.optimize_title(original_title)

        ab_titles = [
            {"title": result["optimized"], "score": result["score"]},
        ]

        # 添加备选标题
        for alt_title in result["alternatives"][:count-1]:
            score = self._calculate_score(alt_title)
            ab_titles.append({"title": alt_title, "score": score})

        # 按评分排序
        ab_titles.sort(key=lambda x: x["score"], reverse=True)

        return ab_titles


# 便捷函数
def optimize_title(title: str, content_summary: str = "") -> str:
    """便捷的标题优化函数"""
    from core.recorder import SessionRecorder

    recorder = SessionRecorder()
    optimizer = TitleOptimizer(recorder)

    result = optimizer.optimize_title(title, content_summary)
    return result["optimized"]


if __name__ == "__main__":
    # 测试用例
    test_titles = [
        "AI工具推荐",
        "浏览器插件分享",
        "效率工具介绍",
        "AI写作工具使用教程",
        "5款AI摘要神器",
    ]

    from core.recorder import SessionRecorder

    recorder = SessionRecorder()
    optimizer = TitleOptimizer(recorder)

    print("=" * 80)
    print("🎯 标题优化测试")
    print("=" * 80)

    for title in test_titles:
        print(f"\n【原始标题】")
        print(f"  {title}")

        result = optimizer.optimize_title(title)

        print(f"\n【优化标题】")
        print(f"  {result['optimized']}")

        print(f"\n【备选标题】")
        for i, alt in enumerate(result['alternatives'][:3], 1):
            print(f"  {i}. {alt}")

        print(f"\n【评分】")
        print(f"  {result['score']}/100")

        print(f"\n【类别】")
        print(f"  {result['category']}")

        print("-" * 80)

    # A/B测试示例
    print("\n" + "=" * 80)
    print("🔬 A/B测试示例")
    print("=" * 80)

    ab_titles = optimizer.generate_ab_test_titles("AI工具推荐", count=5)

    for i, item in enumerate(ab_titles, 1):
        print(f"\n版本 {i}（评分: {item['score']}/100）:")
        print(f"  {item['title']}")
