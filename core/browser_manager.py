from playwright.async_api import async_playwright
from config.settings import CDP_URL, BASE_URL
import httpx

class BrowserManager:
    def __init__(self):
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None

    async def start(self):
        """连接到已运行的 Chrome 实例"""
        print(f"[Init] 正在连接 Chrome CDP ({CDP_URL})...")
        self.playwright = await async_playwright().start()

        try:
            # 获取 WebSocket 端点（Playwright 新版本需要完整的 WS URL）
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{CDP_URL}/json/version")
                data = response.json()
                ws_endpoint = data['webSocketDebuggerUrl']
                print(f"[Init] WebSocket 端点: {ws_endpoint}")

            # 使用 WebSocket 端点连接
            self.browser = await self.playwright.chromium.connect_over_cdp(ws_endpoint)
        except Exception as e:
            print(f"❌ 连接失败: {e}")
            print("请检查：终端是否运行了 '/Applications/Google\\ Chrome.app/... --remote-debugging-port=9222'")
            raise e

        # 获取上下文 (通常只有一个默认的 Profile)
        if not self.browser.contexts:
            self.context = await self.browser.new_context()
        else:
            self.context = self.browser.contexts[0]
            
        # 注入防检测脚本 (CDP模式下的双重保险)
        await self.context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        """)

        # 智能页面获取：复用小红书标签页，否则新建
        await self._get_or_create_page()
        print("[Init] 浏览器连接成功，准备就绪")

    async def _get_or_create_page(self):
        """寻找是否已有小红书页面，没有则新建"""
        # 遍历现有页面
        for p in self.context.pages:
            if "xiaohongshu.com" in p.url:
                self.page = p
                await self.page.bring_to_front()
                print(f"[Page] 复用已存在的标签页: {await self.page.title()}")
                return

        # 如果没找到，新建一个
        self.page = await self.context.new_page()
        print("[Page] 创建新标签页")

    async def disconnect(self):
        """断开连接（不关闭浏览器窗口）"""
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        print("[System] 已断开 CDP 连接")