"""
A/B 测试框架 - 测试不同内容版本的效果

功能：
1. 创建和管理 A/B 测试实验
2. 追踪不同版本的表现数据
3. 自动分析测试结果
4. 生成优化建议
5. 集成到内容创作流程
"""

import json
import time
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from enum import Enum


class TestStatus(Enum):
    """测试状态枚举"""
    PENDING = "pending"  # 待启动
    RUNNING = "running"  # 运行中
    COMPLETED = "completed"  # 已完成
    INCONCLUSIVE = "inconclusive"  # 无结论


class ABTestFramework:
    """A/B 测试框架"""

    def __init__(self, recorder):
        self.recorder = recorder
        self.test_data_file = Path(__file__).parent.parent / "data" / "ab_tests.json"
        self._ensure_data_file()

    def _ensure_data_file(self):
        """确保数据文件存在"""
        if not self.test_data_file.exists():
            with open(self.test_data_file, 'w', encoding='utf-8') as f:
                json.dump([], f)

    def create_test(
        self,
        test_name: str,
        test_type: str,
        variants: List[Dict],
        duration_days: int = 7,
        min_sample_size: int = 100
    ) -> Dict:
        """
        创建 A/B 测试实验

        Args:
            test_name: 测试名称
            test_type: 测试类型（title/content/image/tag）
            variants: 测试变体列表
                每个 variant: {"id": "A", "content": "...", "metadata": {...}}
            duration_days: 测试持续天数
            min_sample_size: 最小样本量

        Returns:
            创建的测试对象
        """
        test_id = f"test_{int(time.time())}"

        test = {
            "test_id": test_id,
            "name": test_name,
            "type": test_type,
            "status": TestStatus.PENDING.value,
            "created_at": str(time.time()),
            "duration_days": duration_days,
            "min_sample_size": min_sample_size,
            "variants": variants,
            "results": {},
            "winner": None,
            "insights": []
        }

        # 初始化每个变体的统计数据
        for variant in variants:
            variant["stats"] = {
                "impressions": 0,
                "views": 0,
                "likes": 0,
                "collects": 0,
                "comments": 0,
                "engagement_rate": 0.0,
                "score": 0.0
            }

        self._save_test(test)
        self.recorder.log("info", f"🧪 [A/B测试] 创建测试: {test_name} ({len(variants)} 个变体)")

        return test

    def start_test(self, test_id: str) -> bool:
        """启动测试"""
        test = self._get_test(test_id)
        if not test:
            return False

        test["status"] = TestStatus.RUNNING.value
        test["started_at"] = str(time.time())
        self._update_test(test)

        self.recorder.log("info", f"🧪 [A/B测试] 启动测试: {test['name']}")
        return True

    def record_impression(self, test_id: str, variant_id: str):
        """记录曝光"""
        test = self._get_test(test_id)
        if not test:
            return

        for variant in test["variants"]:
            if variant["id"] == variant_id:
                variant["stats"]["impressions"] += 1
                break

        self._update_test(test)

    def record_performance(
        self,
        test_id: str,
        variant_id: str,
        views: int = 0,
        likes: int = 0,
        collects: int = 0,
        comments: int = 0
    ):
        """
        记录变体的表现数据

        Args:
            test_id: 测试ID
            variant_id: 变体ID
            views: 浏览量
            likes: 点赞数
            collects: 收藏数
            comments: 评论数
        """
        test = self._get_test(test_id)
        if not test:
            return

        for variant in test["variants"]:
            if variant["id"] == variant_id:
                variant["stats"]["views"] += views
                variant["stats"]["likes"] += likes
                variant["stats"]["collects"] += collects
                variant["stats"]["comments"] += comments

                # 计算互动率
                total_views = variant["stats"]["views"]
                if total_views > 0:
                    engagement = (likes + collects + comments) / total_views * 100
                    variant["stats"]["engagement_rate"] = round(engagement, 2)

                # 计算综合评分
                variant["stats"]["score"] = self._calculate_variant_score(variant["stats"])
                break

        self._update_test(test)

    def _calculate_variant_score(self, stats: Dict) -> float:
        """计算变体综合评分"""
        score = 0.0

        # 互动率评分 (50分)
        engagement = stats.get("engagement_rate", 0)
        score += min(engagement * 5, 50)

        # 绝对数据评分 (30分)
        views = stats.get("views", 0)
        if views >= 10000:
            score += 30
        elif views >= 5000:
            score += 25
        elif views >= 1000:
            score += 20
        elif views >= 500:
            score += 15
        elif views >= 100:
            score += 10

        # 收藏点赞比 (20分)
        likes = stats.get("likes", 0)
        collects = stats.get("collects", 0)
        if likes > 0:
            ratio = collects / likes
            score += min(ratio * 10, 20)

        return round(score, 2)

    def analyze_test(self, test_id: str) -> Dict:
        """
        分析测试结果

        Returns:
            分析结果字典
        """
        test = self._get_test(test_id)
        if not test:
            return {"error": "测试不存在"}

        if test["status"] != TestStatus.RUNNING.value:
            return {"error": "测试未运行"}

        # 检查是否满足结束条件
        analysis = {
            "test_id": test_id,
            "test_name": test["name"],
            "status": test["status"],
            "can_conclude": False,
            "recommendation": None,
            "variant_comparison": [],
            "insights": []
        }

        # 检查样本量
        total_views = sum(v["stats"]["views"] for v in test["variants"])
        if total_views < test["min_sample_size"]:
            analysis["can_conclude"] = False
            analysis["recommendation"] = f"样本量不足 (当前: {total_views}, 需要: {test['min_sample_size']})"
            return analysis

        # 检查测试时长
        if "started_at" in test:
            elapsed_days = (time.time() - float(test["started_at"])) / 86400
            if elapsed_days < test["duration_days"]:
                analysis["can_conclude"] = False
                analysis["recommendation"] = f"测试时长不足 (当前: {elapsed_days:.1f}天, 需要: {test['duration_days']}天)"
                return analysis

        # 变体对比
        variants_with_scores = []
        for variant in test["variants"]:
            variants_with_scores.append({
                "id": variant["id"],
                "content": variant.get("content", ""),
                "score": variant["stats"]["score"],
                "views": variant["stats"]["views"],
                "engagement_rate": variant["stats"]["engagement_rate"],
                "stats": variant["stats"]
            })

        # 按评分排序
        variants_with_scores.sort(key=lambda x: x["score"], reverse=True)
        analysis["variant_comparison"] = variants_with_scores

        # 判断是否有显著差异
        if len(variants_with_scores) >= 2:
            winner = variants_with_scores[0]
            runner_up = variants_with_scores[1]
            score_diff = winner["score"] - runner_up["score"]

            if score_diff >= 10:  # 评分差异 >= 10 分
                analysis["can_conclude"] = True
                analysis["winner"] = winner["id"]
                analysis["recommendation"] = f"推荐使用变体 {winner['id']} (评分: {winner['score']}, 胜出优势: {score_diff:.1f}分)"

                # 生成洞察
                analysis["insights"] = self._generate_insights(test, variants_with_scores)

                # 更新测试状态
                test["status"] = TestStatus.COMPLETED.value
                test["winner"] = winner["id"]
                test["results"] = analysis
                test["insights"] = analysis["insights"]
                self._update_test(test)

            else:
                analysis["can_conclude"] = False
                analysis["recommendation"] = f"差异不显著 (最大分差: {score_diff:.1f}分)，建议继续测试"
                test["status"] = TestStatus.INCONCLUSIVE.value
                self._update_test(test)

        return analysis

    def _generate_insights(self, test: Dict, variants: List[Dict]) -> List[str]:
        """生成测试洞察"""
        insights = []

        test_type = test["type"]
        winner = variants[0]

        if test_type == "title":
            insights.append(f"📌 标题优化：{winner['content']} 表现最佳")
            if winner["engagement_rate"] > 5:
                insights.append(f"✨ 高互动率 ({winner['engagement_rate']:.1f}%)，标题吸引力强")

        elif test_type == "content":
            insights.append(f"📝 内容优化：变体 {winner['id']} 内容结构更有效")
            if winner["stats"]["collects"] > winner["stats"]["likes"] * 0.5:
                insights.append(f"💎 收藏比例高，内容实用性强")

        elif test_type == "image":
            insights.append(f"🎨 视觉优化：变体 {winner['id']} 视觉表现更佳")

        # 对比分析
        if len(variants) >= 2:
            runner_up = variants[1]
            score_diff = winner["score"] - runner_up["score"]
            lift = (score_diff / runner_up["score"] * 100) if runner_up["score"] > 0 else 0
            insights.append(f"📊 相比第二名提升 {lift:.1f}%")

        return insights

    def get_winning_variant(self, test_id: str) -> Optional[Dict]:
        """获取获胜变体"""
        test = self._get_test(test_id)
        if not test or not test.get("winner"):
            return None

        for variant in test["variants"]:
            if variant["id"] == test["winner"]:
                return variant

        return None

    def get_all_tests(self, status: str = None) -> List[Dict]:
        """获取所有测试"""
        try:
            with open(self.test_data_file, 'r', encoding='utf-8') as f:
                tests = json.load(f)

            if status:
                tests = [t for t in tests if t["status"] == status]

            return tests
        except:
            return []

    def _get_test(self, test_id: str) -> Optional[Dict]:
        """获取指定测试"""
        tests = self.get_all_tests()
        for test in tests:
            if test["test_id"] == test_id:
                return test
        return None

    def _save_test(self, test: Dict):
        """保存测试"""
        tests = self.get_all_tests()

        # 查找是否已存在
        existing_idx = None
        for i, t in enumerate(tests):
            if t["test_id"] == test["test_id"]:
                existing_idx = i
                break

        if existing_idx is not None:
            tests[existing_idx] = test
        else:
            tests.append(test)

        with open(self.test_data_file, 'w', encoding='utf-8') as f:
            json.dump(tests, f, indent=2, ensure_ascii=False)

    def _update_test(self, test: Dict):
        """更新测试"""
        self._save_test(test)

    def delete_test(self, test_id: str) -> bool:
        """删除测试"""
        tests = self.get_all_tests()
        original_count = len(tests)

        tests = [t for t in tests if t["test_id"] != test_id]

        if len(tests) < original_count:
            with open(self.test_data_file, 'w', encoding='utf-8') as f:
                json.dump(tests, f, indent=2, ensure_ascii=False)
            self.recorder.log("info", f"🧪 [A/B测试] 删除测试: {test_id}")
            return True

        return False

    def generate_summary_report(self) -> Dict:
        """生成测试摘要报告"""
        tests = self.get_all_tests()

        summary = {
            "total_tests": len(tests),
            "by_status": {},
            "completed_tests": [],
            "key_insights": []
        }

        # 按状态统计
        for status in TestStatus:
            count = sum(1 for t in tests if t["status"] == status.value)
            summary["by_status"][status.value] = count

        # 已完成的测试
        completed = [t for t in tests if t["status"] == TestStatus.COMPLETED.value]
        for test in completed:
            winner = self.get_winning_variant(test["test_id"])
            summary["completed_tests"].append({
                "name": test["name"],
                "type": test["type"],
                "winner": winner["id"] if winner else None,
                "insights": test.get("insights", [])
            })

        # 关键洞察
        all_insights = []
        for test in completed:
            all_insights.extend(test.get("insights", []))

        # 去重并统计
        from collections import Counter
        insight_counter = Counter(all_insights)
        summary["key_insights"] = [
            {"insight": insight, "frequency": count}
            for insight, count in insight_counter.most_common(5)
        ]

        return summary


class QuickABTest:
    """快速 A/B 测试助手 - 用于标题等快速测试"""

    def __init__(self, recorder, ab_framework: ABTestFramework):
        self.recorder = recorder
        self.ab_framework = ab_framework

    def create_title_test(
        self,
        base_title: str,
        variants: List[str],
        duration_days: int = 3
    ) -> str:
        """
        创建标题 A/B 测试

        Args:
            base_title: 基准标题
            variants: 备选标题列表
            duration_days: 测试天数

        Returns:
            测试ID
        """
        test_variants = []

        # 添加基准版本
        test_variants.append({
            "id": "A",
            "content": base_title,
            "is_control": True
        })

        # 添加测试版本
        for i, variant in enumerate(variants, start=1):
            test_variants.append({
                "id": chr(65 + i),  # B, C, D, ...
                "content": variant,
                "is_control": False
            })

        test = self.ab_framework.create_test(
            test_name=f"标题测试 - {base_title[:20]}",
            test_type="title",
            variants=test_variants,
            duration_days=duration_days,
            min_sample_size=50  # 标题测试样本量较小
        )

        return test["test_id"]

    def simulate_test_result(self, test_id: str):
        """模拟测试结果（用于测试）"""
        test = self.ab_framework._get_test(test_id)
        if not test:
            return

        # 为每个变体生成模拟数据
        import random
        for variant in test["variants"]:
            views = random.randint(100, 500)
            likes = random.randint(10, 100)
            collects = random.randint(5, 50)
            comments = random.randint(2, 20)

            self.ab_framework.record_performance(
                test_id,
                variant["id"],
                views=views,
                likes=likes,
                collects=collects,
                comments=comments
            )

        # 分析结果
        return self.ab_framework.analyze_test(test_id)


# 便捷函数
def get_ab_framework(recorder):
    """便捷的 A/B 测试框架获取函数"""
    return ABTestFramework(recorder)


def get_quick_ab_test(recorder):
    """便捷的快速 A/B 测试获取函数"""
    ab_framework = ABTestFramework(recorder)
    return QuickABTest(recorder, ab_framework)


if __name__ == "__main__":
    # 测试 A/B 测试框架
    from core.recorder import SessionRecorder

    recorder = SessionRecorder()
    ab_framework = ABTestFramework(recorder)
    quick_test = QuickABTest(recorder, ab_framework)

    print("="*80)
    print("🧪 A/B 测试框架测试")
    print("="*80)

    # 1. 创建标题测试
    print("\n【创建标题测试】")
    base_title = "AI工具推荐"
    variants = [
        "5个AI工具神器，打工人必看！🚀",
        "为什么你的效率这么低？试试这5个AI工具",
        "相见恨晚！这5个AI工具太香了！"
    ]

    test_id = quick_test.create_title_test(base_title, variants, duration_days=3)
    print(f"测试ID: {test_id}")

    # 2. 启动测试
    print("\n【启动测试】")
    ab_framework.start_test(test_id)

    # 3. 模拟测试数据
    print("\n【模拟测试数据】")
    result = quick_test.simulate_test_result(test_id)

    if result:
        print(f"\n可以得出结论: {result['can_conclude']}")
        print(f"建议: {result['recommendation']}")

        print(f"\n【变体对比】")
        for variant in result['variant_comparison']:
            print(f"变体 {variant['id']}: 评分 {variant['score']}, 浏览 {variant['views']}, 互动率 {variant['engagement_rate']}%")

        if result.get('insights'):
            print(f"\n【测试洞察】")
            for insight in result['insights']:
                print(f"  {insight}")

    # 4. 生成摘要报告
    print(f"\n{'='*80}")
    print("【摘要报告】")
    summary = ab_framework.generate_summary_report()
    print(f"总测试数: {summary['total_tests']}")
    print(f"按状态统计: {summary['by_status']}")

    print("\n" + "="*80)
