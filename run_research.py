import asyncio
import argparse
import json
import os
from pathlib import Path
from datetime import datetime
from config.settings import BASE_URL, DEEP_RESEARCH_ENABLED, DEEP_RESEARCH_OUTPUT_DIR, DEEP_RESEARCH_LLM_MODEL
from core.recorder import SessionRecorder
from core.llm_client import LLMClient
from core.researcher import ResearchAgent


async def generate_report_from_file(json_file_path: str, recorder: SessionRecorder):
    """
    从已有的 JSON 数据文件直接生成深度调研报告
    
    Args:
        json_file_path: JSON 数据文件路径
        recorder: 会话记录器
    """
    if not DEEP_RESEARCH_ENABLED:
        print("Deep research mode is disabled in config/settings.py. Please enable it to run this workflow.")
        return
    
    # 检查文件是否存在
    json_path = Path(json_file_path)
    if not json_path.exists():
        recorder.log("error", f"❌ 数据文件不存在: {json_file_path}")
        return
    
    # 检查文件扩展名
    if not json_path.suffix.lower() == '.json':
        recorder.log("error", f"❌ 不支持的文件格式: {json_path.suffix}，请提供 .json 文件")
        return
    
    recorder.log("info", f"📂 [报告生成] 从文件加载数据: {json_file_path}")
    
    # 加载 JSON 数据
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            research_data = json.load(f)
        
        if not isinstance(research_data, list):
            recorder.log("error", "❌ 数据格式错误: 期望 JSON 数组格式")
            return
        
        if len(research_data) == 0:
            recorder.log("error", "❌ 数据为空，无法生成报告")
            return
        
        recorder.log("info", f"✅ [报告生成] 成功加载 {len(research_data)} 条帖子数据")
        
    except json.JSONDecodeError as e:
        recorder.log("error", f"❌ JSON 解析失败: {e}")
        return
    except Exception as e:
        recorder.log("error", f"❌ 读取文件失败: {e}")
        return
    
    # 初始化 LLM 客户端
    llm_client = LLMClient(recorder)
    
    # 创建输出目录
    output_dir = DEEP_RESEARCH_OUTPUT_DIR / datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir.mkdir(parents=True, exist_ok=True)
    recorder.log("info", f"📂 [报告生成] 输出目录: {output_dir}")
    
    # 从文件名提取关键词
    keyword = json_path.stem.replace('research_data_', '')
    recorder.log("info", f"🏷️ [报告生成] 研究主题: {keyword}")
    
    # 创建 ResearchAgent 实例（用于调用报告生成方法）
    # 创建一个模拟的 BrowserManager 来绕过初始化检查
    class MockBrowserManager:
        def __init__(self):
            self.page = None
    
    mock_bm = MockBrowserManager()
    research_agent = ResearchAgent(mock_bm, llm_client, recorder)
    
    # 手动设置输出目录（覆盖默认的时间戳目录）
    research_agent.output_dir = output_dir
    
    # 生成报告
    try:
        recorder.log("info", "🧠 [报告生成] 正在调用 LLM 生成调研报告...")
        report = await research_agent._generate_report(research_data)
        
        # 保存报告
        await research_agent._save_report(report, keyword)
        
        recorder.log("success", f"✅ [报告生成] 报告已保存到: {output_dir}")
        
    except Exception as e:
        recorder.log("error", f"❌ [报告生成] 生成报告失败: {e}")
        raise


async def main():
    parser = argparse.ArgumentParser(description="Run deep research workflow.")
    parser.add_argument("keyword_or_file", type=str, help="关键词或 JSON 数据文件路径（支持 .json 文件直接生成报告）")
    args = parser.parse_args()

    if not DEEP_RESEARCH_ENABLED:
        print("Deep research mode is disabled in config/settings.py. Please enable it to run this workflow.")
        return

    # 判断参数是文件路径还是关键词
    input_path = Path(args.keyword_or_file)
    
    # 如果是存在的 .json 文件，直接进入报告生成模式
    if input_path.exists() and input_path.suffix.lower() == '.json':
        recorder = SessionRecorder()
        try:
            await generate_report_from_file(str(input_path), recorder)
        except Exception as e:
            recorder.log("error", f"❌ [报告生成] 工作流失败: {e}")
        finally:
            recorder.save_report()
        return

    # 否则，按照原来的关键词模式运行（需要浏览器）
    from core.browser_manager import BrowserManager
    from core.human_motion import HumanMotion
    from actions.interaction import ActionExecutor
    from core.supervisor import Supervisor

    recorder = SessionRecorder()
    bm = BrowserManager()
    
    try:
        await bm.start()
        
        # Ensure we are on a valid page (e.g., base URL) before starting operations
        if "xiaohongshu.com" not in bm.page.url:
            await bm.page.goto(BASE_URL)
            await asyncio.sleep(2)  # Give some time to load

        human = HumanMotion(bm.page)
        llm_client = LLMClient(recorder)
        
        # ActionExecutor is needed to satisfy Supervisor's constructor,
        # but its main cycle won't be run in this script.
        # Its KB might still be relevant if deep research uses it.
        worker = ActionExecutor(bm.page, human, recorder, llm_client) 
        
        director = Supervisor(bm, human, worker, recorder, llm_client, max_duration=300)  # Set a reasonable max_duration
        
        # Trigger the deep research workflow
        await director.start_deep_research_workflow(args.keyword_or_file)

    except KeyboardInterrupt:
        recorder.log("warning", "用户手动中断")
    finally:
        # worker.kb.force_flush() # Only if KB was used and needs flushing
        recorder.save_report()
        await bm.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
