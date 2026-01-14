import asyncio
import aiohttp
import random
import re
from pathlib import Path
from playwright.async_api import Page, expect
from config.settings import JIMENG_GENERATE_URL, IMAGES_DIR, JIMENG_SELECTORS

class ArtistAgent:
    def __init__(self, page: Page, recorder):
        self.page = page
        self.recorder = recorder

    async def open_studio(self):
        """打开即梦工作台"""
        if "jimeng.jianying.com" not in self.page.url:
            self.recorder.log("info", "🎨 [美术师] 前往即梦工作台...")
            await self.page.goto(JIMENG_GENERATE_URL)
        
        # 强力清理弹窗
        await asyncio.sleep(2)
        await self.page.keyboard.press("Escape")

    async def generate_image(self, prompt):
        self.recorder.log("info", f"🎨 [美术师] 收到需求: {prompt[:30]}...")
        
        try:
            # 1. 定位输入框
            textarea = self.page.locator(JIMENG_SELECTORS["prompt_textarea"]).first
            await textarea.wait_for(state="visible", timeout=10000)

            # === [新增] 强制清空逻辑 ===
            self.recorder.log("debug", "正在清空历史内容...")
            await textarea.click()
            await asyncio.sleep(0.2)
            
            # 针对 Mac 环境使用 Meta+A 全选
            # 如果是 Windows 环境则使用 Control+A
            # 为了兼容性，我们可以都执行一次，或者只执行 Meta+A (因为你是 Mac)
            await self.page.keyboard.press("Meta+A") 
            await asyncio.sleep(0.1)
            await self.page.keyboard.press("Backspace")
            
            # 双重保险：再用 fill 确保清空
            await textarea.fill("") 
            await asyncio.sleep(0.5)
            # =========================
            
            # # 2. 模拟真人输入 使用 type 逐字输入，确保触发 JS 事件
            self.recorder.log("debug", "正在输入提示词...")
            if len(prompt) > 10:
                # 长文本：先 fill 大部分，最后几个字 type，兼顾速度和事件触发
                await textarea.fill(prompt[:-5])
                await asyncio.sleep(0.5)
                await textarea.type(prompt[-5:], delay=50)
            else:
                await textarea.type(prompt, delay=50)
            
            # 输入后，点击一下空白处或者按个空格，确保状态同步
            await self.page.keyboard.press("Space")
            await self.page.keyboard.press("Backspace")

            # 3. 定位并点击生成 (关键修复)
            # 使用 settings.py 更新后的选择器 (带 visible=true)
            generate_btn = self.page.locator(JIMENG_SELECTORS["generate_btn"])
            
            # 增加显式等待，确保它出现在屏幕上
            self.recorder.log("debug", "寻找可见的生成按钮...")
            try:
                await generate_btn.wait_for(state="visible", timeout=5000)
            except:
                self.recorder.log("warning", "⚠️ 未找到可见按钮，尝试点击输入框激活...")
                await textarea.click()
                await textarea.type(" ") # 补个空格唤醒按钮
                await asyncio.sleep(1)

            # 再次检查是否置灰 (disabled)
            # 注意：Playwright 的 is_disabled() 会自动处理 DOM 属性
            if await generate_btn.is_disabled():
                self.recorder.log("warning", "⚠️ 按钮仍置灰，尝试再次激活...")
                await textarea.press("Backspace") # 删掉刚才的空格
                await asyncio.sleep(1)

            self.recorder.log("info", "🚀 点击生成...")
            # 此时 generate_btn 必定是那个可见的黑色箭头按钮
            await generate_btn.click()

            # 4. 等待结果
            # === [优化开始] ===
            self.recorder.log("info", "⏳ 等待渲染 (检测首图变化)...")
            
            # 1. 获取"旧"的第一张图特征
            result_cards = self.page.locator(JIMENG_SELECTORS["result_card"])
            first_img_locator = result_cards.first.locator("img").first
            
            old_src = ""
            if await result_cards.count() > 0:
                # 如果本来就有图，记录旧图 URL
                try:
                    old_src = await first_img_locator.get_attribute("src")
                except:
                    pass
            
            # 2. 轮询检测：第一张图是否变了？
            is_new_image_arrived = False
            
            # 给足耐心，AI 作画有时候很慢 (60s)
            for i in range(20): 
                await asyncio.sleep(3)
                
                # 重新获取当前第一张图
                current_count = await result_cards.count()
                if current_count == 0:
                    continue
                    
                current_src = await first_img_locator.get_attribute("src")
                
                # 情况 A: 之前没图，现在有图了 -> 成功
                if not old_src and current_src:
                    is_new_image_arrived = True
                    break
                
                # 情况 B: 之前有图，现在的图跟之前不一样 -> 成功
                if old_src and current_src and current_src != old_src:
                    is_new_image_arrived = True
                    break
                    
                self.recorder.log("debug", f"渲染中... {i*3}s")
            
            # === [优化结束] ===

            if not is_new_image_arrived:
                 self.recorder.log("error", "⚠️ 生成超时或失败 (首图未更新)")
                 # 这里可以选择 return None，避免下载旧图
                 # 但如果你想硬着头皮下，也可以继续
                 # return None 
            else:
                 self.recorder.log("success", "✨ 捕捉到新生成的图片！")

            # 5. 下载最新图片
            # 获取第一个卡片里的图片
            # HTML: <div class="image-card-wrapper..."> ... <img class="image-C3mkAg" src="...">
            first_img = self.page.locator(f"{JIMENG_SELECTORS['result_card']} img").first
            
            # 等待图片加载出 http 链接 (而不是 base64 占位)
            await expect(first_img).to_have_attribute("src", re.compile(r"^http"), timeout=15000)
            
            image_url = await first_img.get_attribute("src")
            # 即梦的 URL 有时候带参数，我们只取 clean url 或者直接下
            self.recorder.log("info", f"🔗 捕获图片 URL: {image_url[:40]}...")

            return await self._download_image(image_url)

        except Exception as e:
            self.recorder.log("error", f"🎨 [美术师] 作画流程异常: {e}")
            await self.recorder.record_error(self.page, "生图失败")
            return None

    async def _download_image(self, url):
        """下载 helper"""
        try:
            timestamp = int(random.random() * 100000)
            filename = f"jimeng_{timestamp}.webp" # 即梦通常是 webp
            filepath = IMAGES_DIR / filename
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        content = await resp.read()
                        with open(filepath, "wb") as f:
                            f.write(content)
                        self.recorder.log("success", f"💾 图片已保存: {filename}")
                        return filepath
        except Exception as e:
            self.recorder.log("error", f"下载失败: {e}")
            return None