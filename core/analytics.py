"""
数据分析模块 - 分析已发布笔记的表现数据

功能：
1. 抓取笔记数据（浏览量、点赞、收藏、评论）
2. 计算互动率
3. 找出高表现内容
4. 生成分析报告
"""

import asyncio
import json
import time
from pathlib import Path
from datetime import datetime, timedelta
from playwright.async_api import async_playwright, Page
from typing import Dict, List, Optional
from core.recorder import SessionRecorder
from config.settings import DRAFTS_FILE, DATA_DIR


class ContentAnalytics:
    """内容数据分析器"""

    def __init__(self, recorder):
        self.recorder = recorder
        self.drafts_file = DRAFTS_FILE
        self.analytics_file = DATA_DIR / "content_stats.json"

        # 确保分析文件存在
        if not self.analytics_file.exists():
            with open(self.analytics_file, 'w', encoding='utf-8') as f:
                json.dump({}, f)

    def load_published_drafts(self) -> List[Dict]:
        """加载已发布的草稿"""
        try:
            with open(self.drafts_file, 'r', encoding='utf-8') as f:
                drafts = json.load(f)

            published = [d for d in drafts if d.get("status") == "published"]
            return published
        except Exception as e:
            self.recorder.log("error", f"📊 [数据分析] 加载草稿失败: {e}")
            return []

    async def fetch_note_stats(self, page: Page, note_url: str) -> Optional[Dict]:
        """
        抓取笔记统计数据

        Args:
            page: Playwright 页面对象
            note_url: 笔记URL

        Returns:
            统计数据字典，失败返回 None
        """
        try:
            self.recorder.log("info", f"📊 [数据分析] 抓取笔记数据: {note_url}")

            # 访问笔记页面
            await page.goto(note_url, wait_until="networkidle", timeout=30000)
            await asyncio.sleep(3)

            # 等待数据加载
            stats = {}

            # 尝试多种选择器获取数据
            # 浏览量（通常在标题下方）
            view_selectors = [
                ".view-count", ".count-view", "span[class*='view']",
                ".note-view", "[class*='view']"
            ]

            # 点赞数
            like_selectors = [
                ".like-count", ".count-like", "span[class*='like']",
                ".note-like", "[class*='like']"
            ]

            # 收藏数
            collect_selectors = [
                ".collect-count", ".count-collect", "span[class*='collect']",
                ".note-collect", "[class*='collect']"
            ]

            # 评论数
            comment_selectors = [
                ".comment-count", ".count-comment", "span[class*='comment']",
                ".note-comment", "[class*='comment']"
            ]

            # 提取数字的辅助函数
            def extract_number(text):
                import re
                if not text:
                    return 0
                # 提取所有数字
                numbers = re.findall(r'\d+', text)
                if numbers:
                    # 返回最大的数字（通常是真实数据）
                    return int(numbers[-1])
                return 0

            # 尝试获取浏览量
            for selector in view_selectors:
                try:
                    element = page.locator(selector).first
                    if await element.count() > 0:
                        text = await element.inner_text()
                        views = extract_number(text)
                        if views > 0:
                            stats["views"] = views
                            break
                except:
                    continue

            # 尝试获取点赞数
            for selector in like_selectors:
                try:
                    element = page.locator(selector).first
                    if await element.count() > 0:
                        text = await element.inner_text()
                        likes = extract_number(text)
                        if likes > 0:
                            stats["likes"] = likes
                            break
                except:
                    continue

            # 尝试获取收藏数
            for selector in collect_selectors:
                try:
                    element = page.locator(selector).first
                    if await element.count() > 0:
                        text = await element.inner_text()
                        collects = extract_number(text)
                        if collects > 0:
                            stats["collects"] = collects
                            break
                except:
                    continue

            # 尝试获取评论数
            for selector in comment_selectors:
                try:
                    element = page.locator(selector).first
                    if await element.count() > 0:
                        text = await element.inner_text()
                        comments = extract_number(text)
                        if comments > 0:
                            stats["comments"] = comments
                            break
                except:
                    continue

            # 如果成功获取到数据，计算互动率
            if stats:
                views = stats.get("views", 0)
                likes = stats.get("likes", 0)
                collects = stats.get("collects", 0)
                comments = stats.get("comments", 0)

                if views > 0:
                    engagement = (likes + collects + comments) / views * 100
                    stats["engagement_rate"] = round(engagement, 2)
                else:
                    stats["engagement_rate"] = 0

                stats["fetched_at"] = str(time.time())

                self.recorder.log("info", f"📊 [数据分析] 数据抓取成功: {stats}")
                return stats
            else:
                self.recorder.log("warning", "📊 [数据分析] 未能获取数据")
                return None

        except Exception as e:
            self.recorder.log("error", f"📊 [数据分析] 抓取失败: {e}")
            return None

    def calculate_score(self, stats: Dict) -> float:
        """
        计算内容表现评分

        Args:
            stats: 统计数据字典

        Returns:
            评分 (0-100)
        """
        if not stats:
            return 0.0

        score = 0.0

        # 1. 互动率评分 (40分)
        engagement = stats.get("engagement_rate", 0)
        score += min(engagement * 4, 40)  # 10%互动率 = 40分

        # 2. 绝对数据评分 (40分)
        views = stats.get("views", 0)
        if views >= 10000:
            score += 40
        elif views >= 5000:
            score += 30
        elif views >= 1000:
            score += 20
        elif views >= 500:
            score += 10

        # 3. 收藏点赞比 (20分) - 收藏价值
        likes = stats.get("likes", 0)
        collects = stats.get("collects", 0)
        if likes > 0:
            ratio = collects / likes
            score += min(ratio * 10, 20)

        return min(score, 100)

    def save_stats(self, draft_id: str, stats: Dict):
        """保存统计数据"""
        try:
            with open(self.analytics_file, 'r', encoding='utf-8') as f:
                all_stats = json.load(f)

            all_stats[draft_id] = stats

            with open(self.analytics_file, 'w', encoding='utf-8') as f:
                json.dump(all_stats, f, indent=2, ensure_ascii=False)

            self.recorder.log("info", f"📊 [数据分析] 统计数据已保存")
        except Exception as e:
            self.recorder.log("error", f"📊 [数据分析] 保存失败: {e}")

    def get_stats(self, draft_id: str) -> Optional[Dict]:
        """获取指定草稿的统计数据"""
        try:
            with open(self.analytics_file, 'r', encoding='utf-8') as f:
                all_stats = json.load(f)

            return all_stats.get(draft_id)
        except:
            return None

    def get_top_performing(self, limit: int = 10) -> List[Dict]:
        """获取表现最好的内容"""
        drafts = self.load_published_drafts()

        results = []
        for draft in drafts:
            draft_id = draft.get("created_at", "")
            stats = self.get_stats(draft_id)

            if stats:
                score = self.calculate_score(stats)
                results.append({
                    "draft": draft,
                    "stats": stats,
                    "score": score
                })

        # 按评分排序
        results.sort(key=lambda x: x["score"], reverse=True)

        return results[:limit]

    def analyze_patterns(self, top_posts: List[Dict]) -> Dict:
        """
        分析高表现内容的共同模式

        Args:
            top_posts: 表现最好的帖子列表

        Returns:
            分析结果字典
        """
        if not top_posts:
            return {}

        analysis = {
            "title_patterns": {},
            "content_themes": {},
            "posting_times": {},
            "tag_frequency": {}
        }

        for item in top_posts:
            draft = item["draft"]

            # 分析标题长度
            title = draft.get("title", "")
            title_len = len(title)
            if "short" not in analysis["title_patterns"]:
                analysis["title_patterns"]["short"] = 0
                analysis["title_patterns"]["medium"] = 0
                analysis["title_patterns"]["long"] = 0

            if title_len < 15:
                analysis["title_patterns"]["short"] += 1
            elif title_len < 25:
                analysis["title_patterns"]["medium"] += 1
            else:
                analysis["title_patterns"]["long"] += 1

            # 分析标签
            tags = draft.get("tags", [])
            for tag in tags:
                tag_key = tag.replace("#", "")
                analysis["tag_frequency"][tag_key] = analysis["tag_frequency"].get(tag_key, 0) + 1

            # 分析发布时间
            created_at = draft.get("published_at", "")
            if created_at:
                try:
                    timestamp = float(created_at)
                    hour = datetime.fromtimestamp(timestamp).hour
                    time_key = f"{hour}:00"
                    analysis["posting_times"][time_key] = analysis["posting_times"].get(time_key, 0) + 1
                except:
                    pass

        return analysis


# 便捷函数
def get_content_analytics(recorder):
    """便捷的内容分析器获取函数"""
    return ContentAnalytics(recorder)


if __name__ == "__main__":
    # 测试数据分析功能
    from core.recorder import SessionRecorder

    recorder = SessionRecorder()
    analytics = ContentAnalytics(recorder)

    print("="*80)
    print("📊 数据分析测试")
    print("="*80)

    # 加载已发布草稿
    published = analytics.load_published_drafts()
    print(f"\n已发布草稿数: {len(published)}")

    if published:
        print("\n已发布的草稿:")
        for draft in published[:5]:
            print(f"  - {draft.get('title', '')}")
            print(f"    发布时间: {datetime.fromtimestamp(float(draft.get('published_at', 0))).strftime('%Y-%m-%d %H:%M')}")

    # 获取表现最好的内容
    print("\n" + "-"*80)
    print("表现最好的内容:")
    top_posts = analytics.get_top_performing(limit=5)

    for i, item in enumerate(top_posts, 1):
        draft = item["draft"]
        stats = item["stats"]
        score = item["score"]

        print(f"\n{i}. 《{draft.get('title', '')}》")
        print(f"   评分: {score}/100")
        if stats:
            print(f"   浏览: {stats.get('views', 'N/A')}")
            print(f"   点赞: {stats.get('likes', 'N/A')}")
            print(f"   收藏: {stats.get('collects', 'N/A')}")
            print(f"   评论: {stats.get('comments', 'N/A')}")
            print(f"   互动率: {stats.get('engagement_rate', 'N/A')}%")

    # 分析模式
    if top_posts:
        print("\n" + "-"*80)
        print("内容模式分析:")
        patterns = analytics.analyze_patterns(top_posts)

        print(f"\n标题长度分布:")
        for length_type, count in patterns.get("title_patterns", {}).items():
            print(f"  {length_type}: {count}")

        print(f"\n常用标签:")
        tag_freq = patterns.get("tag_frequency", {})
        sorted_tags = sorted(tag_freq.items(), key=lambda x: x[1], reverse=True)
        for tag, count in sorted_tags[:5]:
            print(f"  {tag}: {count}次")

    print("\n" + "="*80)
