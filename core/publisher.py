"""
发布Agent - 封装小红书发布逻辑
直接使用传入的page对象，不重新初始化浏览器
"""
import asyncio
from playwright.async_api import Page
from config.settings import XHS_CREATOR_URL, PUBLISH_SELECTORS

class PublisherAgent:
    def __init__(self, page: Page, recorder):
        self.page = page
        self.recorder = recorder

    async def publish_draft(self, draft):
        """
        发布草稿
        :param draft: 草稿对象，包含 title, content, image_local_path
        :return: True/False
        """
        title = draft.get("title", "")
        content = draft.get("content", "")
        image_path = draft.get("image_local_path", "")
        
        if not title or not content:
            self.recorder.log("error", "📤 [发布员] 草稿缺少标题或内容")
            return False
        
        try:
            self.recorder.log("info", f"📤 [发布员] 开始发布: 《{title[:30]}...》")
            
            # 1. 导航到发布页面
            await self.page.goto(XHS_CREATOR_URL, wait_until="networkidle")
            await asyncio.sleep(3)
            
            # 2. 检查登录状态
            if "login" in self.page.url:
                self.recorder.log("error", "📤 [发布员] 需要登录，跳过发布")
                return False
            
            # 3. 切换到图文Tab（如果需要）
            try:
                tab_image = self.page.locator(PUBLISH_SELECTORS["tab_image"]).first
                if await tab_image.count() > 0:
                    await tab_image.click()
                    await asyncio.sleep(2)
            except Exception as e:
                self.recorder.log("warning", f"📤 [发布员] 切换Tab失败（可能已在图文Tab）: {e}")
            
            # 4. 上传图片
            if image_path:
                upload_success = await self._upload_image(image_path)
                if not upload_success:
                    self.recorder.log("warning", "📤 [发布员] 图片上传失败，继续发布文字内容")
            
            # 5. 输入标题
            title_filled = await self._fill_title(title)
            if not title_filled:
                self.recorder.log("warning", "📤 [发布员] 标题输入失败，尝试继续")
            
            # 6. 输入内容
            content_filled = await self._fill_content(content)
            if not content_filled:
                self.recorder.log("error", "📤 [发布员] 内容输入失败，发布中止")
                return False
            
            # 7. 等待用户手动发布（或自动发布）
            # 注意：这里不自动点击发布按钮，避免风控
            self.recorder.log("info", "📤 [发布员] 内容已填写完成，等待手动发布...")
            await asyncio.sleep(5)  # 给用户5秒时间检查
            
            # 可选：自动发布（如果配置允许）
            # await self._click_publish_button()
            
            self.recorder.log("success", f"📤 [发布员] 发布流程完成: 《{title[:30]}...》")
            return True
            
        except Exception as e:
            self.recorder.log("error", f"📤 [发布员] 发布失败: {e}")
            await self.recorder.record_error(self.page, "发布异常")
            return False

    async def _upload_image(self, image_path):
        """上传图片"""
        try:
            # 等待上传区域
            upload_input = self.page.locator(PUBLISH_SELECTORS["upload_input"]).first
            await upload_input.wait_for(state="attached", timeout=10000)
            
            # 设置文件
            await upload_input.set_input_files(image_path)
            await asyncio.sleep(5)  # 等待上传完成
            
            self.recorder.log("info", "📤 [发布员] 图片上传成功")
            return True
        except Exception as e:
            self.recorder.log("error", f"📤 [发布员] 图片上传失败: {e}")
            return False

    async def _fill_title(self, title):
        """填写标题"""
        try:
            title_input = self.page.locator(PUBLISH_SELECTORS["title_input"]).first
            await title_input.wait_for(state="visible", timeout=10000)
            await title_input.fill(title)
            await asyncio.sleep(1)
            self.recorder.log("info", "📤 [发布员] 标题填写成功")
            return True
        except Exception as e:
            self.recorder.log("error", f"📤 [发布员] 标题填写失败: {e}")
            return False

    async def _fill_content(self, content):
        """填写内容"""
        try:
            content_editor = self.page.locator(PUBLISH_SELECTORS["content_editor"]).first
            await content_editor.wait_for(state="visible", timeout=10000)
            await content_editor.fill(content)
            await asyncio.sleep(1)
            self.recorder.log("info", "📤 [发布员] 内容填写成功")
            return True
        except Exception as e:
            self.recorder.log("error", f"📤 [发布员] 内容填写失败: {e}")
            return False

    async def _click_publish_button(self):
        """点击发布按钮（可选，默认不自动发布）"""
        try:
            publish_btn = self.page.locator(PUBLISH_SELECTORS["publish_btn"]).first
            await publish_btn.wait_for(state="visible", timeout=5000)
            await publish_btn.click()
            await asyncio.sleep(3)
            
            # 检查是否发布成功
            success_element = self.page.locator(PUBLISH_SELECTORS["success_element"]).first
            if await success_element.count() > 0:
                self.recorder.log("success", "📤 [发布员] 发布成功！")
                return True
            else:
                self.recorder.log("warning", "📤 [发布员] 发布按钮已点击，但未检测到成功提示")
                return False
        except Exception as e:
            self.recorder.log("error", f"📤 [发布员] 点击发布按钮失败: {e}")
            return False
