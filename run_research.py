import asyncio
import argparse
from config.settings import BASE_URL, DEEP_RESEARCH_ENABLED
from core.browser_manager import BrowserManager
from core.human_motion import HumanMotion
from actions.interaction import ActionExecutor # Still needed for its kb for now
from core.recorder import SessionRecorder
from core.supervisor import Supervisor
from core.llm_client import LLMClient

async def main():
    parser = argparse.ArgumentParser(description="Run deep research workflow.")
    parser.add_argument("keyword", type=str, help="The keyword for deep research.")
    args = parser.parse_args()

    if not DEEP_RESEARCH_ENABLED:
        print("Deep research mode is disabled in config/settings.py. Please enable it to run this workflow.")
        return

    recorder = SessionRecorder()
    bm = BrowserManager()
    
    try:
        await bm.start()
        
        # Ensure we are on a valid page (e.g., base URL) before starting operations
        if "xiaohongshu.com" not in bm.page.url:
            await bm.page.goto(BASE_URL)
            await asyncio.sleep(2) # Give some time to load

        human = HumanMotion(bm.page)
        llm_client = LLMClient(recorder)
        
        # ActionExecutor is needed to satisfy Supervisor's constructor,
        # but its main cycle won't be run in this script.
        # Its KB might still be relevant if deep research uses it.
        worker = ActionExecutor(bm.page, human, recorder, llm_client) 
        
        director = Supervisor(bm, human, worker, recorder, llm_client, max_duration=300) # Set a reasonable max_duration
        
        # Trigger the deep research workflow
        await director.start_deep_research_workflow(args.keyword)

    except KeyboardInterrupt:
        recorder.log("warning", "用户手动中断")
    finally:
        # worker.kb.force_flush() # Only if KB was used and needs flushing
        recorder.save_report()
        await bm.disconnect()

if __name__ == "__main__":
    asyncio.run(main())