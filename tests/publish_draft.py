#!/usr/bin/env python3
"""
草稿发布器 - 将 SiliconMomo 草稿发布到小红书

使用方法：
1. 先启动 Chrome 并开启远程调试：
   /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222

2. 在 Chrome 中手动登录小红书创作者中心

3. 运行本程序：
   cd /Users/zhangqilai/project/vibe-code-100-projects/guiji/SiliconMomo
   python tests/publish_draft.py
"""

import sys
import os
import asyncio
import json
from pathlib import Path
from datetime import datetime

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from actions.publisher import XiaohongshuPoster
from core.content_cleaner import ContentCleaner


class DraftPublisher:
    """草稿发布器"""

    def __init__(self, cdp_url="http://localhost:9222", auto_publish=True):
        self.cdp_url = cdp_url
        self.drafts_file = project_root / "data" / "drafts.json"
        self.poster = None
        self.auto_publish = auto_publish  # 是否自动点击发布按钮

    def load_drafts(self):
        """加载草稿文件"""
        if not self.drafts_file.exists():
            print(f"❌ 草稿文件不存在: {self.drafts_file}")
            return []

        try:
            with open(self.drafts_file, 'r', encoding='utf-8') as f:
                drafts = json.load(f)
            return drafts
        except Exception as e:
            print(f"❌ 读取草稿文件失败: {e}")
            return []

    def save_drafts(self, drafts):
        """保存草稿文件"""
        try:
            with open(self.drafts_file, 'w', encoding='utf-8') as f:
                json.dump(drafts, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"❌ 保存草稿文件失败: {e}")
            return False

    def list_drafts(self, status_filter=None):
        """列出草稿

        Args:
            status_filter: 状态过滤器 (None=全部, "ready_to_publish"=待发布, "published"=已发布)
        """
        drafts = self.load_drafts()

        if status_filter:
            drafts = [d for d in drafts if d.get("status") == status_filter]

        if not drafts:
            print("📭 没有找到草稿")
            return []

        print(f"\n{'='*80}")
        print(f"📋 草稿列表 (共 {len(drafts)} 个)")
        print(f"{'='*80}")

        for idx, draft in enumerate(drafts, 1):
            status = draft.get("status", "unknown")
            status_icon = "✅" if status == "published" else "📝" if status == "ready_to_publish" else "❓"

            print(f"\n{status_icon} [{idx}] {draft.get('title', '无标题')}")
            print(f"    状态: {status}")
            print(f"    创建时间: {self._format_timestamp(draft.get('created_at'))}")

            if status == "published":
                pub_time = draft.get("published_at")
                if pub_time:
                    print(f"    发布时间: {self._format_timestamp(pub_time)}")

            # 显示内容预览
            content = draft.get("content", "")
            preview = content[:100] + "..." if len(content) > 100 else content
            print(f"    内容预览: {preview}")

            # 显示图片路径
            image_path = draft.get("image_local_path")
            if image_path:
                exists = "✅" if os.path.exists(image_path) else "❌"
                print(f"    图片: {exists} {image_path}")

            # 显示标签
            tags = draft.get("tags", [])
            if tags:
                print(f"    标签: {' '.join(tags[:5])}")

        print(f"\n{'='*80}\n")
        return drafts

    def _format_timestamp(self, timestamp):
        """格式化时间戳"""
        try:
            ts = float(timestamp)
            return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
        except:
            return str(timestamp)

    async def publish_draft(self, draft):
        """发布单个草稿

        Args:
            draft: 草稿字典

        Returns:
            bool: 发布是否成功
        """
        title = draft.get("title", "")
        content = draft.get("content", "")
        image_path = draft.get("image_local_path", "")

        if not title or not content:
            print("❌ 草稿缺少标题或内容")
            return False

        if image_path and not os.path.exists(image_path):
            print(f"⚠️  警告: 图片文件不存在: {image_path}")
            print("   将继续发布文字内容...")

        print(f"\n{'='*80}")
        print(f"🚀 开始发布: 《{title}》")
        mode_str = "自动发布" if self.auto_publish else "手动发布"
        print(f"📌 模式: {mode_str}")
        print(f"{'='*80}\n")

        try:
            # 初始化发布器
            if not self.poster:
                self.poster = XiaohongshuPoster(
                    cdp_url=self.cdp_url,
                    auto_publish=self.auto_publish
                )
                await self.poster.initialize()
                print("✅ 浏览器连接成功")
                await self.poster.login()
                print("✅ 登录状态检查完成")

            # 准备图片列表
            images = [image_path] if image_path and os.path.exists(image_path) else []

            # 发布文章
            await self.poster.post_article(
                title=title,
                content=content,
                images=images if images else None
            )

            print(f"\n{'='*80}")
            print(f"✅ 发布流程完成: 《{title}》")
            print(f"{'='*80}\n")

            return True

        except Exception as e:
            print(f"\n❌ 发布失败: {e}")
            import traceback
            traceback.print_exc()
            return False

    async def mark_as_published(self, draft_index):
        """标记草稿为已发布

        Args:
            draft_index: 草稿索引（从1开始）

        Returns:
            bool: 是否成功标记
        """
        drafts = self.load_drafts()

        if draft_index < 1 or draft_index > len(drafts):
            print(f"❌ 无效的草稿索引: {draft_index}")
            return False

        draft = drafts[draft_index - 1]

        # 更新状态
        draft["status"] = "published"
        draft["published_at"] = str(datetime.now().timestamp())

        # 保存
        if self.save_drafts(drafts):
            print(f"✅ 已标记草稿为已发布: 《{draft.get('title')}》")
            return True
        else:
            print(f"❌ 保存草稿状态失败")
            return False

    async def close(self):
        """关闭浏览器连接"""
        if self.poster:
            await self.poster.close()
            self.poster = None


def print_banner():
    """打印程序标题"""
    banner = """
    ╔═══════════════════════════════════════════════════════════════╗
    ║                                                               ║
    ║           🧠 SiliconMomo 草稿发布器 v1.0                     ║
    ║                                                               ║
    ║           将草稿发布到小红书创作者中心                        ║
    ║                                                               ║
    ╚═══════════════════════════════════════════════════════════════╝
    """
    print(banner)


def print_help():
    """打印帮助信息"""
    help_text = """
    📖 命令说明:
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    list [all|ready|published]  - 列出草稿 (默认: all)
    publish <编号>              - 发布指定草稿
    mark <编号>                 - 标记草稿为已发布（不实际发布）
    preview <编号>              - 预览草稿内容（含清洗效果）
    clean <编号>                - 预览内容清洗效果
    auto [on|off]               - 设置发布模式 (on=自动发布, off=手动发布)
    help                        - 显示帮助信息
    quit/exit                   - 退出程序
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    """
    print(help_text)


def preview_draft(draft):
    """预览草稿详情"""
    print(f"\n{'='*80}")
    print(f"📄 草稿详情: 《{draft.get('title', '无标题')}》")
    print(f"{'='*80}\n")

    print(f"标题: {draft.get('title', '')}")
    print(f"状态: {draft.get('status', 'unknown')}")
    print(f"创建时间: {datetime.fromtimestamp(float(draft.get('created_at', 0))).strftime('%Y-%m-%d %H:%M:%S')}")

    if draft.get('status') == 'published':
        pub_time = draft.get('published_at')
        if pub_time:
            print(f"发布时间: {datetime.fromtimestamp(float(pub_time)).strftime('%Y-%m-%d %H:%M:%S')}")

    image_path = draft.get('image_local_path', '')
    if image_path:
        exists = "✅" if os.path.exists(image_path) else "❌"
        print(f"图片: {exists} {image_path}")

    print(f"\n内容:")
    print("─" * 80)

    # 显示原始内容
    original_content = draft.get('content', '')
    print("【原始内容】")
    print(original_content)

    # 显示清洗后的内容
    cleaned_content = ContentCleaner.clean_for_xiaohongshu(original_content)
    if original_content != cleaned_content:
        print("\n【清洗后内容】（去除 ** 等格式符号）")
        print(cleaned_content)

    print("─" * 80)

    tags = draft.get('tags', [])
    if tags:
        print(f"\n标签: {' '.join(tags)}")

    print(f"\n{'='*80}\n")


async def main():
    """主程序"""
    print_banner()

    # 检查 Chrome 是否启动
    import socket
    try:
        sock = socket.create_connection(("localhost", 9222), timeout=2)
        sock.close()
        print("✅ 检测到 Chrome 远程调试端口 (9222)\n")
    except:
        print("⚠️  警告: 未检测到 Chrome 远程调试端口")
        print("   请先启动 Chrome 并开启远程调试:")
        print("   /Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome --remote-debugging-port=9222\n")

    publisher = DraftPublisher()

    print_help()

    # 显示当前发布模式
    mode_str = "✅ 自动发布" if publisher.auto_publish else "⏸️  手动发布"
    print(f"📌 当前模式: {mode_str}")
    print("   使用 'auto on|off' 命令切换发布模式\n")

    # 主循环
    while True:
        try:
            cmd = input("🧠 Momo> ").strip()

            if not cmd:
                continue

            parts = cmd.split()
            command = parts[0].lower()
            args = parts[1:]

            if command in ['quit', 'exit', 'q']:
                print("\n👋 再见！")
                await publisher.close()
                break

            elif command == 'help' or command == 'h':
                print_help()

            elif command == 'list' or command == 'l':
                status = None
                if args:
                    filter_arg = args[0].lower()
                    if filter_arg == 'ready' or filter_arg == 'r':
                        status = 'ready_to_publish'
                    elif filter_arg == 'published' or filter_arg == 'p':
                        status = 'published'
                    elif filter_arg == 'all' or filter_arg == 'a':
                        status = None

                publisher.list_drafts(status_filter=status)

            elif command == 'publish' or command == 'p':
                if not args:
                    print("❌ 请指定要发布的草稿编号")
                    print("   用法: publish <编号>")
                    continue

                try:
                    draft_idx = int(args[0])
                    drafts = publisher.load_drafts()

                    if draft_idx < 1 or draft_idx > len(drafts):
                        print(f"❌ 无效的草稿编号: {draft_idx}")
                        continue

                    draft = drafts[draft_idx - 1]

                    # 确认发布
                    print(f"\n即将发布: 《{draft.get('title')}》")
                    confirm = input("确认发布? (y/n): ").strip().lower()

                    if confirm == 'y' or confirm == 'yes':
                        success = await publisher.publish_draft(draft)

                        if success:
                            # 自动标记为已发布
                            await publisher.mark_as_published(draft_idx)
                        else:
                            print("⚠️  发布失败，草稿状态未更新")
                    else:
                        print("❌ 已取消发布")

                except ValueError:
                    print("❌ 无效的编号，请输入数字")

            elif command == 'mark' or command == 'm':
                if not args:
                    print("❌ 请指定要标记的草稿编号")
                    print("   用法: mark <编号>")
                    continue

                try:
                    draft_idx = int(args[0])
                    await publisher.mark_as_published(draft_idx)
                except ValueError:
                    print("❌ 无效的编号，请输入数字")

            elif command == 'preview' or command == 'v':
                if not args:
                    print("❌ 请指定要预览的草稿编号")
                    print("   用法: preview <编号>")
                    continue

                try:
                    draft_idx = int(args[0])
                    drafts = publisher.load_drafts()

                    if draft_idx < 1 or draft_idx > len(drafts):
                        print(f"❌ 无效的草稿编号: {draft_idx}")
                        continue

                    draft = drafts[draft_idx - 1]
                    preview_draft(draft)

                except ValueError:
                    print("❌ 无效的编号，请输入数字")

            elif command == 'clean' or command == 'c':
                if not args:
                    print("❌ 请指定要预览清洗效果的草稿编号")
                    print("   用法: clean <编号>")
                    continue

                try:
                    draft_idx = int(args[0])
                    drafts = publisher.load_drafts()

                    if draft_idx < 1 or draft_idx > len(drafts):
                        print(f"❌ 无效的草稿编号: {draft_idx}")
                        continue

                    draft = drafts[draft_idx - 1]

                    # 显示清洗对比
                    original_title = draft.get('title', '')
                    original_content = draft.get('content', '')

                    cleaned_title = ContentCleaner.clean_for_xiaohongshu(original_title)
                    cleaned_content = ContentCleaner.clean_for_xiaohongshu(original_content)

                    print(f"\n{'='*80}")
                    print(f"🧹 内容清洗对比: 《{original_title}》")
                    print(f"{'='*80}\n")

                    print("【标题】")
                    if original_title != cleaned_title:
                        print(f"  原始: {original_title}")
                        print(f"  清洗: {cleaned_title}")
                    else:
                        print(f"  (无需清洗)")

                    print(f"\n【内容】")
                    if original_content != cleaned_content:
                        print(f"  原始内容 (前200字):")
                        print(f"  {original_content[:200]}...")
                        print(f"\n  清洗后内容 (前200字):")
                        print(f"  {cleaned_content[:200]}...")
                    else:
                        print(f"  (无需清洗)")

                    print(f"\n{'='*80}\n")

                except ValueError:
                    print("❌ 无效的编号，请输入数字")

            elif command == 'auto' or command == 'a':
                if not args:
                    # 显示当前模式
                    mode_str = "✅ 自动发布 (自动点击发布按钮)" if publisher.auto_publish else "⏸️  手动发布 (需手动点击发布按钮)"
                    print(f"\n当前模式: {mode_str}\n")
                else:
                    # 设置模式
                    mode_arg = args[0].lower()
                    if mode_arg in ['on', 'true', '1', 'yes']:
                        publisher.auto_publish = True
                        print("\n✅ 已切换到自动发布模式")
                        print("   发布后将自动点击发布按钮\n")
                    elif mode_arg in ['off', 'false', '0', 'no']:
                        publisher.auto_publish = False
                        print("\n⏸️  已切换到手动发布模式")
                        print("   发布后需要手动点击发布按钮\n")
                    else:
                        print(f"❌ 无效的模式参数: {mode_arg}")
                        print("   用法: auto on|off")

            else:
                print(f"❌ 未知命令: {command}")
                print("   输入 'help' 查看帮助信息")

        except KeyboardInterrupt:
            print("\n\n👋 程序已中断")
            await publisher.close()
            break
        except Exception as e:
            print(f"❌ 发生错误: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 程序已退出")
