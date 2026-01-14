import asyncio
import traceback
from playwright.async_api import Page
from zai import ZhipuAiClient
from config.settings import ZHIPU_AI_KEY, LLM_MODEL
from core.dom_helper import SmartLocator

class RecoveryAgent:
    def __init__(self, page: Page, recorder):
        self.page = page
        self.recorder = recorder
        self.client = ZhipuAiClient(api_key=ZHIPU_AI_KEY)
        self.dom_helper = SmartLocator(recorder)

    async def diagnose_and_fix(self, error):
        """
        维修工总入口：接收任何异常，尝试自愈
        Returns: True (修好了), False (没救了)
        """
        error_msg = str(error)
        self.recorder.log("warning", f"🔧 [维修工] 介入处理异常: {error_msg}")
        
        # 1. 截图留证
        await self.recorder.record_error(self.page, "recovery_start")

        # 2. 致命伤检查 (Fatal Error)
        if "Target closed" in error_msg or "Session closed" in error_msg:
            self.recorder.log("error", "💀 浏览器已断开，拒绝维修，申请重启")
            return False

        # 3. 上帝模式 (God Mode) - 尝试 AI 修复
        # 策略变更：除了明确的网络错误，其他大部分 DOM/逻辑错误都尝试修复
        if not await self._is_network_error(error_msg):
            self.recorder.log("warning", "☢️ 启动 L4 级 AI 动态修复...")
            if await self._ai_dynamic_fix(error_msg):
                return True

        # 4. 兜底方案 (Fallback) - 刷新大法
        self.recorder.log("warning", "🔧 AI 修复无效，执行兜底策略：刷新页面")
        try:
            await self.page.reload()
            await self.page.wait_for_load_state("domcontentloaded")
            await asyncio.sleep(3)
            return True
        except Exception as e:
            self.recorder.log("error", f"❌ 刷新失败: {e}")
            return False

    async def _is_network_error(self, error_msg):
        """简单判断是否为纯网络问题 (无需 AI 介入)"""
        keywords = ["Connection refused", "NS_ERROR", "net::ERR"]
        return any(k in error_msg for k in keywords)

    async def _ai_dynamic_fix(self, error_msg):
        """
        L4 级动态修复：感知 -> 决策 -> 执行 -> 验证
        """
        try:
            # 1. 感知
            raw_html = await self.page.content()
            cleaned_html = self.dom_helper.clean_dom(raw_html) 
            current_url = self.page.url

            # 2. 决策 (Prompt 升级：严防死守 AI 写独立脚本)
            prompt = f"""
            你是一个 Playwright 修复专家。
            当前脚本在 URL: {current_url} 抛出异常："{error_msg}"
            
            【上下文】
            - 全局变量 `page` (Page对象) 和 `asyncio` **已存在**，直接使用！
            - **严禁**使用 `asyncio.run()`。
            - **严禁**使用 `async with async_playwright()` 或重新 launch 浏览器。
            - **严禁**定义函数后不调用。请直接写操作逻辑。

            【DOM 片段】
            {cleaned_html}

            【任务】
            编写一段 Python 代码修复错误。
            针对“无法填写标题”：
            1. 可能是上传文件后，DOM 还没渲染出标题框。请使用 `await page.wait_for_selector('input[placeholder*="标题"]', timeout=5000)`。
            2. 如果找不到元素，尝试更宽泛的选择器如 `input.d-text`。
            3. 确保使用 `await`。

            【代码格式要求】
            只输出 Python 代码，不含 Markdown。代码最后必须打印 "FIX_SUCCESS"。
            """

            self.recorder.log("info", "🔧 [维修工] 思考解决方案...")
            response = self.client.chat.completions.create(
                model=LLM_MODEL, 
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1
            )
            code_snippet = response.choices[0].message.content.strip()
            # 清洗 markdown
            code_snippet = code_snippet.replace("```python", "").replace("```", "")
            
            self.recorder.log("info", f"📜 [Patch] AI 建议方案:\n{code_snippet}")

            # === 3. 代码防御性清洗 (新增) ===
            lines = []
            for line in code_snippet.splitlines():
                # 过滤掉危险的 asyncio.run 和 import playwright
                if "asyncio.run" in line or "async_playwright" in line:
                    self.recorder.log("warning", f"🛡️ 剔除危险代码行: {line.strip()}")
                    continue
                if line.strip():
                    lines.append(line)
            
            # 重新组装，并强制缩进
            indented_code_block = '\n'.join(['        ' + line for line in lines])
            
            # 4. 动态代码包装
            output_buffer = []
            exec_globals = {
                'page': self.page,
                'asyncio': asyncio,
                'print': lambda x: output_buffer.append(str(x))
            }
            
            wrapped_code = f"""
async def __ai_patch():
    try:
{indented_code_block}
        return True
    except Exception as e:
        print(f"PATCH_ERROR: {{e}}")
        return False
"""
            # 5. 执行
            exec(wrapped_code, exec_globals)
            
            self.recorder.log("info", "⚡️ 应用修复补丁...")
            await exec_globals['__ai_patch']()
            
            # 6. 验证
            logs = " | ".join(output_buffer)
            self.recorder.log("info", f"🤖 [Result] {logs}")
            
            if "FIX_SUCCESS" in logs and "PATCH_ERROR" not in logs:
                return True
            else:
                return False

        except Exception as e:
            self.recorder.log("error", f"❌ 维修工自身崩溃: {e}")
            return False