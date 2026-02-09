"""
热点趋势追踪模块 - 追踪高赞/高互动的热门内容

功能：
1. 记录高互动的帖子作为热点
2. 分析热点话题趋势
3. 基于热点生成仿写建议
4. 支持借势营销
"""

import json
import time
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from collections import Counter
from config.settings import DATA_DIR


class TrendTracker:
    """热点趋势追踪器"""

    def __init__(self, recorder):
        self.recorder = recorder
        self.trends_file = DATA_DIR / "trends.json"
        self._ensure_file()

        # 热点阈值配置
        self.hot_thresholds = {
            "likes": 500,        # 500+ 点赞视为热点
            "collects": 100,     # 100+ 收藏视为热点
            "comments": 50,      # 50+ 评论视为热点
            "views": 5000        # 5000+ 浏览视为热点
        }

        # 趋势时效（小时）
        self.trend_ttl = 72  # 热点保留3天

    def _ensure_file(self):
        """确保趋势文件存在"""
        if not self.trends_file.exists():
            with open(self.trends_file, 'w', encoding='utf-8') as f:
                json.dump([], f)

    def _load_data(self) -> List[Dict]:
        """加载趋势数据"""
        try:
            with open(self.trends_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return []

    def _save_data(self, data: List[Dict]):
        """保存趋势数据"""
        with open(self.trends_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def is_hot_post(self, likes: int, collects: int, comments: int, views: int) -> bool:
        """
        判断是否为热点帖子

        Args:
            likes: 点赞数
            collects: 收藏数
            comments: 评论数
            views: 浏览数

        Returns:
            是否为热点
        """
        # 任一指标达到阈值即视为热点
        if likes >= self.hot_thresholds["likes"]:
            return True
        if collects >= self.hot_thresholds["collects"]:
            return True
        if comments >= self.hot_thresholds["comments"]:
            return True
        if views >= self.hot_thresholds["views"]:
            return True

        return False

    def record_hot_post(
        self,
        title: str,
        content: str,
        url: str,
        likes: int,
        collects: int,
        comments: int,
        views: int,
        image_urls: List[str] = None
    ) -> bool:
        """
        记录热点帖子

        Args:
            title: 标题
            content: 内容
            url: 链接
            likes: 点赞数
            collects: 收藏数
            comments: 评论数
            views: 浏览数
            image_urls: 图片URL列表

        Returns:
            是否记录成功
        """
        try:
            # 检查是否为热点
            if not self.is_hot_post(likes, collects, comments, views):
                return False

            # 查重
            data = self._load_data()
            for item in data:
                if item.get("url") == url:
                    self.recorder.log("info", f"🔥 [热点追踪] 热点已存在，更新数据")
                    # 更新互动数据
                    item["likes"] = likes
                    item["collects"] = collects
                    item["comments"] = comments
                    item["views"] = views
                    item["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    self._save_data(data)
                    return True

            # 创建新记录
            trend_record = {
                "id": str(int(time.time())),
                "collected_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "title": title,
                "content": content,
                "url": url,
                "image_urls": image_urls or [],
                "stats": {
                    "likes": likes,
                    "collects": collects,
                    "comments": comments,
                    "views": views
                },
                "trend_score": self._calculate_trend_score(likes, collects, comments, views),
                "topics": self._extract_topics(title, content),
                "status": "active"  # active, used, expired
            }

            data.append(trend_record)
            self._save_data(data)

            self.recorder.log("info", f"🔥 [热点追踪] +1 新热点: 《{title[:30]}》")
            self.recorder.log("info", f"   互动: 👍{likes} ⭐{collects} 💬{comments} 👁️{views}")

            return True

        except Exception as e:
            self.recorder.log("error", f"🔥 [热点追踪] 记录失败: {e}")
            return False

    def _calculate_trend_score(self, likes: int, collects: int, comments: int, views: int) -> float:
        """计算热度评分"""
        score = 0.0

        # 互动权重
        score += likes * 1
        score += collects * 3  # 收藏权重更高
        score += comments * 2

        # 浏览量权重（较低）
        score += views * 0.01

        return round(score, 2)

    def _extract_topics(self, title: str, content: str) -> List[str]:
        """提取话题标签"""
        topics = []

        # 常见 AI 工具相关关键词
        keywords = [
            "AI", "ChatGPT", "插件", "工具", "神器",
            "效率", "自动化", "办公", "浏览器",
            "免费", "神器", "推荐", "教程",
            "避坑", "合集", "测评"
        ]

        text = title + " " + content
        for keyword in keywords:
            if keyword in text:
                topics.append(keyword)

        return list(set(topics))  # 去重

    def get_active_trends(self, limit: int = 10) -> List[Dict]:
        """获取活跃热点"""
        try:
            data = self._load_data()

            # 过滤活跃热点
            active = []
            for item in data:
                if item.get("status") != "active":
                    continue

                # 检查是否过期
                collected_at = datetime.strptime(item["collected_at"], "%Y-%m-%d %H:%M:%S")
                if datetime.now() - collected_at > timedelta(hours=self.trend_ttl):
                    item["status"] = "expired"
                    continue

                active.append(item)

            # 更新过期状态
            self._save_data(data)

            # 按热度评分排序
            active.sort(key=lambda x: x.get("trend_score", 0), reverse=True)

            return active[:limit]

        except Exception as e:
            self.recorder.log("error", f"🔥 [热点追踪] 获取失败: {e}")
            return []

    def get_trending_topics(self, limit: int = 5) -> List[tuple]:
        """获取热门话题"""
        trends = self.get_active_trends(limit=20)

        # 统计话题频率
        topic_counter = Counter()
        for trend in trends:
            topics = trend.get("topics", [])
            for topic in topics:
                topic_counter[topic] += trend.get("trend_score", 0)

        # 返回最热门的话题
        return topic_counter.most_common(limit)

    def get_trend_inspirations(self, limit: int = 5) -> List[Dict]:
        """
        获取热点仿写灵感

        Returns:
            仿写建议列表
        """
        trends = self.get_active_trends(limit)

        inspirations = []
        for trend in trends:
            inspiration = {
                "source_title": trend["title"],
                "source_content": trend["content"][:200],
                "trend_score": trend["trend_score"],
                "topics": trend["topics"],
                "stats": trend["stats"],
                "rewrite_suggestion": self._generate_rewrite_suggestion(trend)
            }
            inspirations.append(inspiration)

        return inspirations

    def _generate_rewrite_suggestion(self, trend: Dict) -> str:
        """生成仿写建议"""
        title = trend["title"]
        topics = trend.get("topics", [])
        stats = trend["stats"]

        suggestions = []

        # 分析标题类型
        if "数字" in title or any(char.isdigit() for char in title):
            suggestions.append("标题类型：数字型，建议使用具体数量")

        if "？" in title or "？" in title:
            suggestions.append("标题类型：疑问型，建议制造悬念")

        if "神器" in title or "必备" in title:
            suggestions.append("标题类型：推荐型，强调工具价值")

        # 分析热点话题
        if topics:
            suggestions.append(f"热门话题：{' · '.join(topics[:3])}")

        # 分析互动特征
        if stats["collects"] > stats["likes"] * 0.3:
            suggestions.append("收藏比例高，内容实用性强，适合做教程类")

        if stats["comments"] > 50:
            suggestions.append("讨论度高，适合做话题引导类")

        return " | ".join(suggestions) if suggestions else "常规热点内容"

    def analyze_trend_patterns(self) -> Dict:
        """分析热点模式"""
        trends = self.get_active_trends(limit=20)

        if not trends:
            return {"message": "暂无热点数据"}

        analysis = {
            "total_trends": len(trends),
            "avg_likes": sum(t["stats"]["likes"] for t in trends) // len(trends),
            "avg_collects": sum(t["stats"]["collects"] for t in trends) // len(trends),
            "avg_comments": sum(t["stats"]["comments"] for t in trends) // len(trends),
            "top_topics": self.get_trending_topics(5),
            "title_patterns": self._analyze_title_patterns(trends),
            "content_themes": self._analyze_content_themes(trends)
        }

        return analysis

    def _analyze_title_patterns(self, trends: List[Dict]) -> Dict:
        """分析标题模式"""
        patterns = {
            "数字型": 0,
            "疑问型": 0,
            "情感型": 0,
            "推荐型": 0,
            "干货型": 0
        }

        for trend in trends:
            title = trend["title"]

            if any(char.isdigit() for char in title):
                patterns["数字型"] += 1
            if "？" in title or "？" in title:
                patterns["疑问型"] += 1
            if any(word in title for word in ["绝了", "太香", "相见恨晚", "真香"]):
                patterns["情感型"] += 1
            if any(word in title for word in ["推荐", "神器", "必备"]):
                patterns["推荐型"] += 1
            if any(word in title for word in ["教程", "攻略", "保姆级"]):
                patterns["干货型"] += 1

        return patterns

    def _analyze_content_themes(self, trends: List[Dict]) -> Dict:
        """分析内容主题"""
        theme_counter = Counter()

        for trend in trends:
            topics = trend.get("topics", [])
            for topic in topics:
                theme_counter[topic] += 1

        return dict(theme_counter.most_common(5))

    def mark_trend_used(self, trend_id: str):
        """标记热点已使用"""
        try:
            data = self._load_data()

            for item in data:
                if item.get("id") == trend_id:
                    item["status"] = "used"
                    item["used_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    self.recorder.log("info", f"🔥 [热点追踪] 热点已标记为使用")
                    break

            self._save_data(data)

        except Exception as e:
            self.recorder.log("error", f"🔥 [热点追踪] 标记失败: {e}")

    def cleanup_expired_trends(self):
        """清理过期热点"""
        try:
            data = self._load_data()
            original_count = len(data)

            # 过滤掉过期且已使用的
            active_data = []
            for item in data:
                if item.get("status") == "expired":
                    # 已过期且超过7天的删除
                    collected_at = datetime.strptime(item["collected_at"], "%Y-%m-%d %H:%M:%S")
                    if datetime.now() - collected_at > timedelta(days=7):
                        continue
                active_data.append(item)

            if len(active_data) < original_count:
                self._save_data(active_data)
                self.recorder.log("info", f"🔥 [热点追踪] 清理了 {original_count - len(active_data)} 条过期热点")

        except Exception as e:
            self.recorder.log("error", f"🔥 [热点追踪] 清理失败: {e}")

    def get_trend_summary(self) -> str:
        """获取热点摘要报告"""
        trends = self.get_active_trends()
        hot_topics = self.get_trending_topics(5)

        summary = f"""
🔥 热点追踪摘要
{'='*50}

📊 当前热点数: {len(trends)}
🔥 热门话题:
"""

        for topic, score in hot_topics:
            summary += f"   - {topic}: {score:.0f} 热度\n"

        if trends:
            summary += f"\n📈 TOP 3 热点:\n"
            for i, trend in enumerate(trends[:3], 1):
                summary += f"   {i}. 《{trend['title'][:30]}》\n"
                summary += f"      👍{trend['stats']['likes']} ⭐{trend['stats']['collects']} 💬{trend['stats']['comments']}\n"

        return summary


# 便捷函数
def get_trend_tracker(recorder):
    """便捷的热点追踪器获取函数"""
    return TrendTracker(recorder)


if __name__ == "__main__":
    # 测试热点追踪功能
    from core.recorder import SessionRecorder

    recorder = SessionRecorder()
    tracker = TrendTracker(recorder)

    print("="*80)
    print("🔥 热点追踪测试")
    print("="*80)

    # 模拟热点数据
    print("\n【添加测试热点】")
    test_hot_posts = [
        {
            "title": "5个AI工具神器，打工人必看！🚀",
            "content": "分享5个超好用的AI工具，让效率起飞...",
            "url": "https://example.com/post1",
            "likes": 800,
            "collects": 200,
            "comments": 80,
            "views": 8000
        },
        {
            "title": "为什么你的AI总是不够快？",
            "content": "教你几个技巧让AI响应更快...",
            "url": "https://example.com/post2",
            "likes": 600,
            "collects": 150,
            "comments": 60,
            "views": 6000
        },
        {
            "title": "相见恨晚！这3个AI工具太香了！",
            "content": "用完就回不去的AI神器...",
            "url": "https://example.com/post3",
            "likes": 1200,
            "collects": 300,
            "comments": 120,
            "views": 12000
        }
    ]

    for post in test_hot_posts:
        tracker.record_hot_post(**post)

    # 获取活跃热点
    print("\n【活跃热点】")
    active_trends = tracker.get_active_trends(limit=10)
    for i, trend in enumerate(active_trends, 1):
        print(f"\n{i}. {trend['title']}")
        print(f"   热度评分: {trend['trend_score']}")
        print(f"   互动: 👍{trend['stats']['likes']} ⭐{trend['stats']['collects']} 💬{trend['stats']['comments']}")
        print(f"   话题: {', '.join(trend['topics'])}")

    # 获取热门话题
    print("\n【热门话题】")
    hot_topics = tracker.get_trending_topics(5)
    for topic, score in hot_topics:
        print(f"   {topic}: {score:.0f}")

    # 分析热点模式
    print("\n【热点模式分析】")
    patterns = tracker.analyze_trend_patterns()
    print(f"   总热点数: {patterns['total_analyzed']}")
    print(f"   平均点赞: {patterns['avg_likes']}")
    print(f"   平均收藏: {patterns['avg_collects']}")
    print(f"   标题模式分布: {patterns['title_patterns']}")

    # 获取仿写灵感
    print("\n【仿写灵感】")
    inspirations = tracker.get_trend_inspirations(limit=3)
    for i, insp in enumerate(inspirations, 1):
        print(f"\n{i}. 来源: {insp['source_title']}")
        print(f"   热度: {insp['trend_score']}")
        print(f"   仿写建议: {insp['rewrite_suggestion']}")

    # 打印摘要
    print("\n" + tracker.get_trend_summary())

    print("\n" + "="*80)
