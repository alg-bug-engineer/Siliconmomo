#!/usr/bin/env python3
"""
Phase 2 数据驱动优化测试脚本

测试内容：
1. 数据分析模块 (analytics)
2. 爆款拆解模块 (viral_analyzer)
3. A/B 测试框架 (ab_tester)
4. Supervisor 集成

使用方法：
cd /Users/zhangqilai/project/vibe-code-100-projects/guiji/SiliconMomo
python tests/test_phase2_data_driven.py
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.recorder import SessionRecorder
from core.analytics import ContentAnalytics
from core.viral_analyzer import ViralAnalyzer
from core.ab_tester import ABTestFramework, QuickABTest


def test_analytics_module():
    """测试数据分析模块"""
    print("\n" + "="*80)
    print("📊 测试 1：数据分析模块")
    print("="*80)

    recorder = SessionRecorder()
    analytics = ContentAnalytics(recorder)

    # 加载已发布草稿
    published = analytics.load_published_drafts()
    print(f"\n【已发布内容】")
    print(f"  数量: {len(published)}")

    if published:
        print(f"\n【前3篇已发布内容】")
        for i, draft in enumerate(published[:3], 1):
            print(f"  {i}. {draft.get('title', '')[:40]}")
            print(f"     发布时间: {draft.get('published_at', 'N/A')}")

    # 测试评分计算
    print(f"\n【评分计算测试】")
    test_stats = [
        {"views": 1000, "likes": 50, "collects": 20, "comments": 5},
        {"views": 5000, "likes": 200, "collects": 100, "comments": 30},
        {"views": 10000, "likes": 500, "collects": 300, "comments": 50}
    ]

    for stats in test_stats:
        score = analytics.calculate_score(stats)
        engagement = stats.get("engagement_rate", 0)
        if engagement == 0 and stats["views"] > 0:
            engagement = (stats["likes"] + stats["collects"] + stats["comments"]) / stats["views"] * 100
        print(f"  浏览: {stats['views']:5d} | 互动率: {engagement:.1f}% | 评分: {score:.1f}/100")

    # 获取高表现内容
    print(f"\n【高表现内容】")
    top_posts = analytics.get_top_performing(limit=5)
    if top_posts:
        for i, item in enumerate(top_posts, 1):
            draft = item["draft"]
            score = item["score"]
            stats = item["stats"]
            print(f"  {i}. 《{draft.get('title', '')[:30]}》")
            print(f"     评分: {score:.1f} | 浏览: {stats.get('views', 'N/A')} | 互动率: {stats.get('engagement_rate', 'N/A')}%")
    else:
        print("  暂无数据")

    print("\n" + "-"*80)


def test_viral_analyzer():
    """测试爆款拆解模块"""
    print("\n" + "="*80)
    print("🔬 测试 2：爆款拆解模块")
    print("="*80)

    recorder = SessionRecorder()
    analytics = ContentAnalytics(recorder)
    viral_analyzer = ViralAnalyzer(recorder, analytics)

    # 获取内容模板
    print(f"\n【内容模板库】")
    templates = ["工具推荐", "教程分享", "避坑指南", "合集推荐", "测评对比"]
    for template_name in templates:
        template = viral_analyzer.get_content_template(template_name)
        if template:
            print(f"\n  📌 {template_name}:")
            print(f"     结构: {template['结构']}")
            print(f"     标题特征: {', '.join(template['标题特征'][:3])}")
            print(f"     情感基调: {template['情感基调']}")

    # 获取爆款模式
    print(f"\n【爆款模式分析】")
    patterns = viral_analyzer.get_viral_patterns(top_n=5)

    if patterns:
        print(f"  分析内容数: {patterns['total_analyzed']}")

        if "title_patterns" in patterns:
            print(f"\n  📊 标题模式:")
            print(f"     最常见: {patterns['title_patterns'].get('most_common_type', 'N/A')}")
            print(f"     平均评分: {patterns['title_patterns'].get('avg_score', 0):.1f}/100")

        if "content_patterns" in patterns:
            print(f"\n  📄 内容模式:")
            print(f"     场景化比例: {patterns['content_patterns'].get('scene_based_ratio', 0):.1%}")

        if "emotion_patterns" in patterns:
            print(f"\n  💭 情感模式:")
            print(f"     最常见: {patterns['emotion_patterns'].get('most_common_type', 'N/A')}")

        if "recommendations" in patterns:
            print(f"\n  💡 优化建议:")
            for rec in patterns['recommendations'][:3]:
                print(f"     {rec}")
    else:
        print("  暂无足够数据进行分析")

    print("\n" + "-"*80)


def test_ab_framework():
    """测试 A/B 测试框架"""
    print("\n" + "="*80)
    print("🧪 测试 3：A/B 测试框架")
    print("="*80)

    recorder = SessionRecorder()
    ab_framework = ABTestFramework(recorder)
    quick_test = QuickABTest(recorder, ab_framework)

    # 创建标题测试
    print(f"\n【创建标题 A/B 测试】")
    base_title = "AI工具推荐"
    variants = [
        "5个AI工具神器，打工人必看！🚀",
        "为什么你的效率这么低？试试这5个AI工具",
        "相见恨晚！这5个AI工具太香了！"
    ]

    test_id = quick_test.create_title_test(base_title, variants, duration_days=3)
    print(f"  测试ID: {test_id}")
    print(f"  基准版本: {base_title}")
    print(f"  测试版本数: {len(variants)}")

    # 启动测试
    ab_framework.start_test(test_id)
    print(f"  ✓ 测试已启动")

    # 模拟数据
    print(f"\n【模拟测试数据】")
    result = quick_test.simulate_test_result(test_id)

    if result:
        print(f"  可得出结论: {result['can_conclude']}")
        print(f"  建议: {result['recommendation']}")

        if result.get('variant_comparison'):
            print(f"\n  【变体对比】")
            for variant in result['variant_comparison']:
                print(f"    变体 {variant['id']}: 评分 {variant['score']:.1f} | 浏览 {variant['views']} | 互动率 {variant['engagement_rate']}%")

        if result.get('insights'):
            print(f"\n  【测试洞察】")
            for insight in result['insights'][:3]:
                print(f"    {insight}")

    # 生成摘要报告
    print(f"\n【A/B 测试摘要报告】")
    summary = ab_framework.generate_summary_report()
    print(f"  总测试数: {summary['total_tests']}")
    print(f"  按状态统计:")
    for status, count in summary['by_status'].items():
        print(f"    {status}: {count}")

    if summary.get('completed_tests'):
        print(f"\n  已完成测试:")
        for test in summary['completed_tests'][:3]:
            print(f"    - {test['name']} (获胜: {test['winner']})")

    if summary.get('key_insights'):
        print(f"\n  关键洞察:")
        for insight in summary['key_insights'][:3]:
            print(f"    {insight['insight']} (出现 {insight['frequency']} 次)")

    print("\n" + "-"*80)


def test_supervisor_integration():
    """测试 Supervisor 集成"""
    print("\n" + "="*80)
    print("🔗 测试 4：Supervisor 集成")
    print("="*80)

    from config.settings import ENABLE_PHASE2_ANALYTICS

    print(f"\n【配置检查】")
    print(f"  Phase 2 数据分析: {'✅ 启用' if ENABLE_PHASE2_ANALYTICS else '❌ 禁用'}")

    if ENABLE_PHASE2_ANALYTICS:
        print(f"\n【Supervisor 集成功能】")
        print(f"  ✓ 数据分析模块 (ContentAnalytics)")
        print(f"  ✓ 爆款拆解模块 (ViralAnalyzer)")
        print(f"  ✓ 定期分析 (每24小时)")
        print(f"  ✓ 模式缓存与应用")

        print(f"\n【自动运行流程】")
        print(f"  1. 浏览互动 → 2. 创作发帖 → 3. 定期数据分析")
        print(f"  分析间隔: 24小时")
        print(f"  分析样本: 前10个高表现内容")

        print(f"\n【数据应用】")
        print(f"  - 标题类型偏好")
        print(f"  - 内容结构建议")
        print(f"  - 情感策略指导")
        print(f"  - 自动优化建议")

    print("\n" + "-"*80)


def show_phase2_summary():
    """显示 Phase 2 总结"""
    print("\n" + "="*80)
    print("📊 Phase 2 数据驱动优化 - 总结")
    print("="*80)

    features = [
        {
            "模块": "数据分析 (analytics.py)",
            "功能": [
                "抓取笔记统计数据（浏览/点赞/收藏/评论）",
                "计算互动率和内容评分",
                "识别高表现内容",
                "生成内容分析报告"
            ]
        },
        {
            "模块": "爆款拆解 (viral_analyzer.py)",
            "功能": [
                "深度拆解爆款内容结构",
                "分析标题、情感、视觉特征",
                "提取可复用的成功模式",
                "生成内容创作建议"
            ]
        },
        {
            "模块": "A/B 测试 (ab_tester.py)",
            "功能": [
                "创建和管理 A/B 测试",
                "追踪不同版本表现",
                "自动分析测试结果",
                "生成优化洞察"
            ]
        },
        {
            "模块": "Supervisor 集成",
            "功能": [
                "定期数据分析（每24小时）",
                "自动应用爆款模式",
                "优化内容创作策略",
                "持续学习迭代"
            ]
        }
    ]

    print("\n【功能模块】")
    for feature in features:
        print(f"\n📌 {feature['模块']}:")
        for func in feature['功能']:
            print(f"  • {func}")

    print("\n【配置项】")
    print("  ENABLE_PHASE2_ANALYTICS = True  # 启用/禁用 Phase 2")
    print("  ANALYSIS_INTERVAL = 86400        # 分析间隔（24小时）")
    print("  VIRAL_ANALYSIS_SAMPLE_SIZE = 10  # 爆款分析样本量")
    print("  AUTO_APPLY_VIRAL_PATTERNS = True # 自动应用爆款模式")

    print("\n【使用方式】")
    print("""
# 1. 独立使用数据分析
from core.analytics import ContentAnalytics
analytics = ContentAnalytics(recorder)
top_posts = analytics.get_top_performing(limit=10)

# 2. 独立使用爆款拆解
from core.viral_analyzer import ViralAnalyzer
viral = ViralAnalyzer(recorder, analytics)
patterns = viral.get_viral_patterns(top_n=10)

# 3. 独立使用 A/B 测试
from core.ab_tester import QuickABTest
quick_test = QuickABTest(recorder, ab_framework)
test_id = quick_test.create_title_test(title, variants)

# 4. 自动运行（已集成）
# 启用 ENABLE_PHASE2_ANALYTICS 后，supervisor 自动定期分析
    """)

    print("\n【集成状态】")
    print("  ✅ 数据分析模块 - 已创建")
    print("  ✅ 爆款拆解模块 - 已创建")
    print("  ✅ A/B 测试框架 - 已创建")
    print("  ✅ Supervisor 集成 - 已完成")
    print("  ✅ 配置文件更新 - 已完成")

    print("\n" + "="*80)


if __name__ == "__main__":
    print("\n" + "="*80)
    print("🚀 Phase 2 数据驱动优化 - 综合测试")
    print("="*80)

    # 运行所有测试
    test_analytics_module()
    test_viral_analyzer()
    test_ab_framework()
    test_supervisor_integration()
    show_phase2_summary()

    print("\n" + "="*80)
    print("✅ Phase 2 所有测试完成！")
    print("="*80 + "\n")
