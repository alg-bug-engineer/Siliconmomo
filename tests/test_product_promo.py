"""
产品宣传功能测试脚本
演示新模块的使用方法
"""

import asyncio
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.recorder import SessionRecorder
from core.product_manager import ProductManager
from core.content_strategy import ContentStrategy
from core.smart_interact import SmartInteractAgent
from core.writer import WriterAgent


class MockRecorder:
    """模拟 Recorder（用于测试）"""
    def __init__(self):
        self.logs = []

    def log(self, level, message):
        print(f"[{level}] {message}")
        self.logs.append({"level": level, "message": message})


async def test_product_manager():
    """测试产品管理器"""
    print("\n" + "="*50)
    print("测试 ProductManager")
    print("="*50)

    recorder = MockRecorder()
    pm = ProductManager(recorder)

    # 1. 获取所有产品
    products = pm.get_all_products()
    print(f"\n📦 产品总数: {len(products)}")
    for p in products:
        print(f"  - {p.get('name')}: {p.get('tagline')}")

    # 2. 轮播获取产品
    print("\n🔄 轮播测试:")
    for i in range(5):
        product = pm.get_next_promo_product()
        print(f"  第{i+1}个: {product.get('name')}")

    # 3. 内容匹配
    print("\n🔍 内容匹配测试:")
    test_cases = [
        ("怎么获取网站的cookies", "我想提取淘宝的cookies做开发"),
        ("小红书采集工具", "有没有好用的插件能采集小红书内容到飞书"),
        ("效率工具推荐", "求推荐好用的浏览器插件")
    ]

    for title, content in test_cases:
        matched = pm.match_product_by_content(title, content)
        if matched:
            print(f"  '{title}' → {matched.get('name')}")
        else:
            print(f"  '{title}' → 无匹配")

    # 4. 配额检查
    print("\n📊 配额检查:")
    can_promote, reason = pm.can_promote_now()
    print(f"  可以宣传: {can_promote}")
    print(f"  原因: {reason}")

    # 5. 统计信息
    stats = pm.get_stats()
    print(f"\n📈 统计信息:")
    print(f"  产品总数: {stats['total_products']}")
    print(f"  总宣传次数: {stats['total_promotions']}")
    print(f"  今日宣传: {stats['today_promotions']}")


async def test_content_strategy():
    """测试内容策略"""
    print("\n" + "="*50)
    print("测试 ContentStrategy")
    print("="*50)

    recorder = MockRecorder()
    pm = ProductManager(recorder)
    cs = ContentStrategy(recorder, pm)

    # 1. 决定内容类型（多次测试）
    print("\n🎲 内容类型决策测试:")
    for i in range(10):
        content_type, product = cs.decide_content_type()
        product_name = product.get('name') if product else "无"
        print(f"  第{i+1}次: {content_type} | 产品: {product_name}")

    # 2. 今日统计
    stats = cs.get_today_stats()
    print(f"\n📊 今日统计:")
    print(f"  价值内容: {stats['value']}")
    print(f"  产品宣传: {stats['promo']}")
    print(f"  互动内容: {stats['others']}")
    print(f"  总计: {stats['total']}")

    # 3. 策略摘要
    summary = cs.get_summary()
    print(f"\n📋 策略摘要:")
    print(f"  宣传比例: {summary['content_strategy']['promo_ratio']*100}%")
    print(f"  价值比例: {summary['content_strategy']['value_ratio']*100}%")
    print(f"  每日宣传上限: {summary['content_strategy']['max_daily_promo']}")


async def test_smart_interact():
    """测试智能互动"""
    print("\n" + "="*50)
    print("测试 SmartInteractAgent")
    print("="*50)

    recorder = MockRecorder()
    pm = ProductManager(recorder)
    agent = SmartInteractAgent(recorder, pm)

    # 测试帖子
    test_posts = [
        {
            "title": "求助：怎么获取淘宝的cookies",
            "content": "想做爬虫但是找不到cookies在哪里，有没有简单的方法？"
        },
        {
            "title": "小红书爆款内容怎么采集",
            "content": "看到很多好的内容想收藏，但是小红书收藏太乱了，想导出到飞书表格"
        },
        {
            "title": "效率工具分享",
            "content": "分享几个我常用的浏览器插件，提升工作效率必备"
        }
    ]

    for i, post in enumerate(test_posts):
        print(f"\n📝 帖子 {i+1}: {post['title']}")

        result = agent.decide_interaction(post['title'], post['content'])

        print(f"  应该互动: {result.get('should_interact')}")
        print(f"  互动类型: {result.get('interaction_type')}")

        if result.get('product'):
            print(f"  匹配产品: {result['product'].get('name')}")

        if result.get('comment'):
            print(f"  评论内容: {result['comment']}")


async def test_writer_product():
    """测试 Writer 产品宣传功能"""
    print("\n" + "="*50)
    print("测试 WriterAgent 产品宣传")
    print("="*50)

    recorder = MockRecorder()
    pm = ProductManager(recorder)
    writer = WriterAgent(recorder, pm)

    # 获取一个产品
    product = pm.get_random_product()
    print(f"\n📦 产品: {product.get('name')}")
    print(f"   卖点: {product.get('tagline')}")

    # 获取可用风格
    styles = writer.get_product_style_templates()
    print(f"\n🎨 可用风格: {', '.join(styles)}")

    print("\n⚠️  注意：实际创作需要调用 LLM API")
    print("   以下是模拟的创作流程演示：")
    print(f"   writer.write_from_product(product, style='产品宣传')")


async def main():
    """主测试函数"""
    print("\n" + "="*60)
    print("  SiliconMomo 产品宣传功能测试")
    print("  AI 杂货店 - 自主运营系统")
    print("="*60)

    try:
        await test_product_manager()
        await test_content_strategy()
        await test_smart_interact()
        await test_writer_product()

        print("\n" + "="*60)
        print("✅ 测试完成！")
        print("="*60)

        print("\n📖 使用说明:")
        print("1. 确保 data/products.json 已配置你的产品信息")
        print("2. 更新产品库中的 store_url 为你的实际商店链接")
        print("3. 运行主程序：python main.py")
        print("4. 系统将自动进行浏览互动和产品宣传")

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
