import asyncio
from config.settings import RUN_DURATION, BASE_URL
from core.browser_manager import BrowserManager
from core.human_motion import HumanMotion
from actions.interaction import ActionExecutor
from core.recorder import SessionRecorder
from core.supervisor import Supervisor # 导入车间主任
from core.llm_client import LLMClient # 导入LLMClient

async def main():
    recorder = SessionRecorder()
    bm = BrowserManager()
    
    try:
        await bm.start()
        
        # 确保在目标页面
        if "xiaohongshu.com" not in bm.page.url:
            await bm.page.goto(BASE_URL)
        
        # 初始化各个角色
        human = HumanMotion(bm.page)
        # 初始化LLM客户端
        llm_client = LLMClient(recorder)
        # Worker 只负责干活，不再负责 try-catch
        worker = ActionExecutor(bm.page, human, recorder, llm_client) # worker也需要llm_client
        
        # Supervisor 负责统筹
        director = Supervisor(bm, human, worker, recorder, llm_client, max_duration=RUN_DURATION)
        
        # 启动！
        await director.start_shift()

    except KeyboardInterrupt:
        recorder.log("warning", "用户手动中断")
    finally:
        # 强制刷新知识库缓冲区
        worker.kb.force_flush()
        recorder.save_report()
        await bm.disconnect()

if __name__ == "__main__":
    asyncio.run(main())