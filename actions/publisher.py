# 小红书的自动发稿
from playwright.async_api import async_playwright
import json
import os
import logging
import asyncio
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.content_cleaner import ContentCleaner

log_path = os.path.expanduser('~/Desktop/xhsai_error.log')
logging.basicConfig(filename=log_path, level=logging.DEBUG)

class XiaohongshuPoster:
    def __init__(self, user_id: int = None, browser_environment=None, cdp_url=None, auto_publish=True):
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.loop = None
        self.user_id = user_id
        self.browser_environment = browser_environment
        self.cdp_url = cdp_url or os.environ.get("XHS_CDP_URL")
        self.auto_publish = auto_publish  # 是否自动点击发布按钮

    def _get_env_value(self, key, default=None):
        env = self.browser_environment
        if env is None:
            return default
        if isinstance(env, dict):
            return env.get(key, default)
        return getattr(env, key, default)

    def _get_user_storage_dir(self) -> str:
        home_dir = os.path.expanduser('~')
        base_dir = os.path.join(home_dir, '.xhs_system')
        if self.user_id is None:
            return base_dir
        return os.path.join(base_dir, "users", str(self.user_id))

    async def initialize(self):
        """初始化浏览器 - 使用CDP连接现有浏览器"""
        if self.playwright is not None:
            return

        try:
            print("开始初始化Playwright...")
            self.playwright = await async_playwright().start()

            # 使用CDP连接到现有浏览器
            if not self.cdp_url:
                raise Exception("未提供CDP URL。请设置环境变量 XHS_CDP_URL 或传入 cdp_url 参数。"
                              "\n启动Chrome时请使用: chrome --remote-debugging-port=9222")

            print(f"通过CDP连接浏览器: {self.cdp_url}")
            self.browser = await self.playwright.chromium.connect_over_cdp(self.cdp_url)

            # 获取现有的context和page，或创建新的
            contexts = self.browser.contexts
            if contexts:
                self.context = contexts[0]
                pages = self.context.pages
                if pages:
                    self.page = pages[0]
                else:
                    self.page = await self.context.new_page()
            else:
                self.context = await self.browser.new_context()
                self.page = await self.context.new_page()

            print("浏览器连接成功！")
            logging.debug("浏览器连接成功！")

            # 注入stealth.min.js
            webgl_vendor = self._get_env_value("webgl_vendor") or "Intel Open Source Technology Center"
            webgl_renderer = self._get_env_value("webgl_renderer") or "Mesa DRI Intel(R) HD Graphics (SKL GT2)"
            platform = self._get_env_value("platform") or ""
            webgl_vendor_js = json.dumps(webgl_vendor, ensure_ascii=False)
            webgl_renderer_js = json.dumps(webgl_renderer, ensure_ascii=False)
            platform_js = json.dumps(platform, ensure_ascii=False)
            stealth_js = """
            (function(){
                const __xhs_webgl_vendor = %s;
                const __xhs_webgl_renderer = %s;
                const __xhs_platform = %s;

                const originalQuery = window.navigator.permissions.query;
                window.navigator.permissions.query = (parameters) => (
                    parameters.name === 'notifications' ?
                        Promise.resolve({ state: Notification.permission }) :
                        originalQuery(parameters)
                );

                const getParameter = WebGLRenderingContext.prototype.getParameter;
                WebGLRenderingContext.prototype.getParameter = function(parameter) {
                    if (parameter === 37445) {
                        return __xhs_webgl_vendor;
                    }
                    if (parameter === 37446) {
                        return __xhs_webgl_renderer;
                    }
                    return getParameter.apply(this, arguments);
                };

                if (__xhs_platform) {
                    try {
                        Object.defineProperty(navigator, 'platform', { get: () => __xhs_platform });
                    } catch (e) {}
                }

                const originalGetBoundingClientRect = Element.prototype.getBoundingClientRect;
                Element.prototype.getBoundingClientRect = function() {
                    const rect = originalGetBoundingClientRect.apply(this, arguments);
                    rect.width = Math.round(rect.width);
                    rect.height = Math.round(rect.height);
                    return rect;
                };

                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });

                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5]
                });

                Object.defineProperty(navigator, 'languages', {
                    get: () => ['zh-CN', 'zh']
                });

                window.chrome = {
                    runtime: {}
                };

                // 禁用Service Worker注册以避免错误
                if ('serviceWorker' in navigator) {
                    const originalRegister = navigator.serviceWorker.register;
                    navigator.serviceWorker.register = function() {
                        return Promise.reject(new Error('Service Worker registration disabled'));
                    };

                    // 也可以完全移除serviceWorker
                    Object.defineProperty(navigator, 'serviceWorker', {
                        get: () => undefined
                    });
                }

                // 捕获并忽略Service Worker相关错误
                window.addEventListener('error', function(e) {
                    if (e.message && e.message.includes('serviceWorker')) {
                        e.preventDefault();
                        return false;
                    }
                });

                // 捕获未处理的Promise拒绝（Service Worker相关）
                window.addEventListener('unhandledrejection', function(e) {
                    if (e.reason && e.reason.message && e.reason.message.includes('serviceWorker')) {
                        e.preventDefault();
                        return false;
                    }
                });
            })();
            """ % (webgl_vendor_js, webgl_renderer_js, platform_js)
            await self.page.add_init_script(stealth_js)

        except Exception as e:
            print(f"初始化过程中出现错误: {str(e)}")
            logging.debug(f"初始化过程中出现错误: {str(e)}")
            await self.close(force=True)
            raise

    async def login(self, phone=None, country_code="+86"):
        """登录检查 - CDP模式下假设用户已在浏览器中登录"""
        await self.ensure_browser()

        # 导航到创作者中心检查登录状态
        await self.page.goto("https://creator.xiaohongshu.com", wait_until="networkidle")

        current_url = self.page.url
        if "login" in current_url:
            print("检测到未登录，请在浏览器中手动完成登录")
            print("等待用户登录...")

            # 等待用户手动登录
            max_wait = 300  # 最多等待5分钟
            waited = 0
            while waited < max_wait:
                await asyncio.sleep(2)
                waited += 2
                current_url = self.page.url
                if "login" not in current_url:
                    print("检测到登录成功！")
                    break

            if "login" in self.page.url:
                raise Exception("等待登录超时，请重新运行程序")

        print("登录状态检查完成")

    async def post_article(self, title, content, images=None):
        """发布文章
        Args:
            title: 文章标题
            content: 文章内容
            images: 图片路径列表
        """
        await self.ensure_browser()

        try:
            # 首先导航到创作者中心
            print("导航到创作者中心...")
            await self.page.goto("https://creator.xiaohongshu.com", wait_until="networkidle")
            await asyncio.sleep(3)

            # 检查是否需要登录
            current_url = self.page.url
            if "login" in current_url:
                print("需要重新登录...")
                raise Exception("用户未登录，请先登录")

            print("点击发布笔记按钮...")
            # 根据实际HTML结构点击发布按钮
            publish_selectors = [
                ".publish-video .btn",
                "button:has-text('发布笔记')",
                ".btn:text('发布笔记')",
                "//div[contains(@class, 'btn')][contains(text(), '发布笔记')]"
            ]

            publish_clicked = False
            for selector in publish_selectors:
                try:
                    print(f"尝试发布按钮选择器: {selector}")
                    await self.page.wait_for_selector(selector, timeout=5000)
                    await self.page.click(selector)
                    print(f"成功点击发布按钮: {selector}")
                    publish_clicked = True
                    break
                except Exception as e:
                    print(f"发布按钮选择器 {selector} 失败: {e}")
                    continue

            if not publish_clicked:
                await self.page.screenshot(path="debug_publish_button.png")
                raise Exception("无法找到发布按钮")

            await asyncio.sleep(3)

            # 切换到上传图文选项卡
            print("切换到上传图文选项卡...")
            try:
                # 等待选项卡加载
                await self.page.wait_for_selector(".creator-tab", timeout=10000)

                # 使用JavaScript直接获取第二个选项卡并点击
                await self.page.evaluate("""
                    () => {
                        const tabs = document.querySelectorAll('.creator-tab');
                        if (tabs.length > 1) {
                            tabs[1].click();
                            return true;
                        }
                        return false;
                    }
                """)
                print("使用JavaScript方法点击第二个选项卡")

                await asyncio.sleep(2)
            except Exception as e:
                print(f"切换选项卡失败: {e}")
                await self.page.screenshot(path="debug_tabs.png")

            # 等待页面切换完成
            await asyncio.sleep(3)

            # 上传图片（如果有）
            print("--- 开始图片上传流程 ---")
            if images:
                print("--- 开始图片上传流程 ---")
                try:
                    # 等待上传区域关键元素（如上传按钮）出现
                    print("等待上传按钮 '.upload-button' 出现...")
                    await self.page.wait_for_selector(".upload-button", timeout=20000)
                    await asyncio.sleep(1.5)

                    upload_success = False

                    # --- 首选方法: 点击明确的 "上传图片" 按钮 ---
                    if not upload_success:
                        print("尝试首选方法: 点击 '.upload-button'")
                        try:
                            button_selector = ".upload-button"
                            await self.page.wait_for_selector(button_selector, state="visible", timeout=10000)
                            print(f"按钮 '{button_selector}' 可见，准备点击.")

                            async with self.page.expect_file_chooser(timeout=15000) as fc_info:
                                await self.page.click(button_selector, timeout=7000)
                                print(f"已点击 '{button_selector}'. 等待文件选择器...")

                            file_chooser = await fc_info.value
                            print(f"文件选择器已出现: {file_chooser}")
                            await file_chooser.set_files(images)
                            print(f"已通过文件选择器设置文件: {images}")
                            upload_success = True
                            print(" 首选方法成功: 点击 '.upload-button' 并设置文件")
                        except Exception as e:
                            print(f" 首选方法 (点击 '.upload-button') 失败: {e}")
                            if self.page: await self.page.screenshot(path="debug_upload_button_click_failed.png")

                    # --- 方法0.5 (新增): 点击拖拽区域的文字提示区 ---
                    if not upload_success:
                        print("尝试方法0.5: 点击拖拽提示区域 ( '.wrapper' 或 '.drag-over')")
                        try:
                            clickable_area_selectors = [".wrapper", ".drag-over"]
                            clicked_area_successfully = False
                            for area_selector in clickable_area_selectors:
                                try:
                                    print(f"尝试点击区域: '{area_selector}'")
                                    await self.page.wait_for_selector(area_selector, state="visible", timeout=5000)
                                    print(f"区域 '{area_selector}' 可见，准备点击.")
                                    async with self.page.expect_file_chooser(timeout=10000) as fc_info:
                                        await self.page.click(area_selector, timeout=5000)
                                        print(f"已点击区域 '{area_selector}'. 等待文件选择器...")
                                    file_chooser = await fc_info.value
                                    print(f"文件选择器已出现 (点击区域 '{area_selector}'): {file_chooser}")
                                    await file_chooser.set_files(images)
                                    print(f"已通过文件选择器 (点击区域 '{area_selector}') 设置文件: {images}")
                                    upload_success = True
                                    clicked_area_successfully = True
                                    print(f" 方法0.5成功: 点击区域 '{area_selector}' 并设置文件")
                                    break
                                except Exception as inner_e:
                                    print(f"尝试点击区域 '{area_selector}' 失败: {inner_e}")

                            if not clicked_area_successfully:
                                print(f" 方法0.5 (点击拖拽提示区域) 所有内部尝试均失败")
                                if self.page: await self.page.screenshot(path="debug_upload_all_area_clicks_failed.png")

                        except Exception as e:
                            print(f"❌方法0.5 (点击拖拽提示区域) 步骤发生意外错误: {e}")
                            if self.page: await self.page.screenshot(path="debug_upload_method0_5_overall_failure.png")

                    # --- 方法1 (备选): 直接操作 .upload-input (使用 set_input_files) ---
                    if not upload_success:
                        print("尝试方法1: 直接操作 '.upload-input' 使用 set_input_files")
                        try:
                            input_selector = ".upload-input"
                            # 对于 set_input_files，元素不一定需要可见，但必须存在于DOM中
                            await self.page.wait_for_selector(input_selector, state="attached", timeout=5000)
                            print(f"找到 '{input_selector}'. 尝试通过 set_input_files 设置文件...")
                            await self.page.set_input_files(input_selector, files=images, timeout=10000)
                            print(f"已通过 set_input_files 为 '{input_selector}' 设置文件: {images}")
                            upload_success = True # 假设 set_input_files 成功即代表文件已选择
                            print(" 方法1成功: 直接通过 set_input_files 操作 '.upload-input'")
                        except Exception as e:
                            print(f" 方法1 (set_input_files on '.upload-input') 失败: {e}")
                            if self.page: await self.page.screenshot(path="debug_upload_input_set_files_failed.png")

                    # --- 方法3 (备选): JavaScript直接触发隐藏的input点击 ---
                    if not upload_success:
                        print("尝试方法3: JavaScript点击隐藏的 '.upload-input'")
                        try:
                            input_selector = ".upload-input"
                            await self.page.wait_for_selector(input_selector, state="attached", timeout=5000)
                            print(f"找到 '{input_selector}'. 尝试通过JS点击...")
                            async with self.page.expect_file_chooser(timeout=10000) as fc_info:
                                await self.page.evaluate(f"document.querySelector('{input_selector}').click();")
                                print(f"已通过JS点击 '{input_selector}'. 等待文件选择器...")
                            file_chooser = await fc_info.value
                            print(f"文件选择器已出现 (JS点击): {file_chooser}")
                            await file_chooser.set_files(images)
                            print(f"已通过文件选择器 (JS点击后) 设置文件: {images}")
                            upload_success = True
                            print(" 方法3成功: JavaScript点击 '.upload-input' 并设置文件")
                        except Exception as e:
                            print(f"方法3 (JavaScript点击 '.upload-input') 失败: {e}")
                            if self.page: await self.page.screenshot(path="debug_upload_js_input_click_failed.png")

                    # --- 上传后检查 ---
                    if upload_success:
                        print("图片已通过某种方法设置/点击，进入上传后检查流程，等待处理和预览...")
                        await asyncio.sleep(7)  # 增加等待时间，等待图片在前端处理和预览

                        upload_check_js = '''
                            () => {
                                const indicators = [
                                    '.img-card', '.image-preview', '.uploaded-image',
                                    '.upload-success', '[class*="preview"]', 'img[src*="blob:"]',
                                    '.banner-img', '.thumbnail', '.upload-display-item',
                                    '.note-image-item', /*小红书笔记图片项*/
                                    '.preview-item', /*通用预览项*/
                                    '.gecko-modal-content img' /* 可能是某种弹窗内的预览 */
                                ];
                                let foundVisible = false;
                                console.log("JS: Checking for upload indicators...");
                                for (let selector of indicators) {
                                    const elements = document.querySelectorAll(selector);
                                    if (elements.length > 0) {
                                        for (let el of elements) {
                                            const rect = el.getBoundingClientRect();
                                            const style = getComputedStyle(el);
                                            if (rect.width > 0 && rect.height > 0 && style.display !== 'none' && style.visibility !== 'hidden' && style.opacity !== '0') {
                                                console.log("JS: Found visible indicator:", selector, el);
                                                foundVisible = true;
                                                break;
                                            }
                                        }
                                    }
                                    if (foundVisible) break;
                                }
                                console.log("JS: Upload indicator check result (foundVisible):", foundVisible);
                                return foundVisible;
                            }
                        '''
                        print("执行JS检查图片预览...")
                        upload_check_successful = await self.page.evaluate(upload_check_js)

                        if upload_check_successful:
                            print(" 图片上传并处理成功 (检测到可见的预览元素)")
                        else:
                            print(" 图片可能未成功处理或预览未出现(JS检查失败)，请检查截图")
                            if self.page: await self.page.screenshot(path="debug_upload_preview_missing_after_js_check.png")
                    else:
                        print(" 所有主要的图片上传方法均失败。无法进行预览检查。")
                        if self.page: await self.page.screenshot(path="debug_upload_all_methods_failed_final.png")

                except Exception as e:
                    print(f"整个图片上传过程出现严重错误: {e}")
                    import traceback
                    traceback.print_exc()
                    if self.page: await self.page.screenshot(path="debug_image_upload_critical_error_outer.png")

            # 输入标题和内容
            print("--- 开始输入标题和内容 ---")
            await asyncio.sleep(5)

            # 🔧 清洗内容：去除 Markdown 格式符号
            print("🧹 清洗内容，去除 Markdown 格式...")
            original_title = title
            original_content = content

            # 清洗标题（去除 ** 等符号）
            title = ContentCleaner.clean_for_xiaohongshu(title)
            # 清洗内容（去除 Markdown 格式）
            content = ContentCleaner.clean_for_xiaohongshu(content)

            if title != original_title:
                print(f"   标题已清洗: {original_title[:50]}... → {title[:50]}...")
            if content != original_content:
                print(f"   内容已清洗 (去除 ** 等格式符号)")

            # 输入标题
            print("输入标题...")
            try:
                # 使用具体的标题选择器
                title_selectors = [
                    "input.d-text[placeholder='填写标题会有更多赞哦～']",
                    "input.d-text",
                    "input[placeholder='填写标题会有更多赞哦～']",
                    "input.title",
                    "[data-placeholder='标题']",
                    "[contenteditable='true']:first-child",
                    ".note-editor-wrapper input",
                    ".edit-wrapper input"
                ]

                title_filled = False
                for selector in title_selectors:
                    try:
                        print(f"尝试标题选择器: {selector}")
                        await self.page.wait_for_selector(selector, timeout=5000)
                        await self.page.fill(selector, title)
                        print(f"标题输入成功，使用选择器: {selector}")
                        title_filled = True
                        break
                    except Exception as e:
                        print(f"标题选择器 {selector} 失败: {e}")
                        continue

                if not title_filled:
                    # 尝试使用键盘快捷键输入
                    try:
                        await self.page.keyboard.press("Tab")
                        await self.page.keyboard.type(title)
                        print("使用键盘输入标题")
                    except Exception as e:
                        print(f"键盘输入标题失败: {e}")
                        print("无法输入标题")

            except Exception as e:
                print(f"标题输入失败: {e}")

            # 输入内容
            print("输入内容...")
            try:
                # 尝试更多可能的内容选择器
                content_selectors = [
                    "[contenteditable='true']:nth-child(2)",
                    ".note-content",
                    "[data-placeholder='添加正文']",
                    "[role='textbox']",
                    ".DraftEditor-root"
                ]

                content_filled = False
                for selector in content_selectors:
                    try:
                        print(f"尝试内容选择器: {selector}")
                        await self.page.wait_for_selector(selector, timeout=5000)
                        await self.page.fill(selector, content)
                        print(f"内容输入成功，使用选择器: {selector}")
                        content_filled = True
                        break
                    except Exception as e:
                        print(f"内容选择器 {selector} 失败: {e}")
                        continue

                if not content_filled:
                    # 尝试使用键盘快捷键输入
                    try:
                        await self.page.keyboard.press("Tab")
                        await self.page.keyboard.press("Tab")
                        await self.page.keyboard.type(content)
                        print("使用键盘输入内容")
                    except Exception as e:
                        print(f"键盘输入内容失败: {e}")
                        print("无法输入内容")

            except Exception as e:
                print(f"内容输入失败: {e}")

            # 🚀 自动点击发布按钮
            if self.auto_publish:
                print("\n" + "="*60)
                print("🚀 准备自动点击发布按钮...")
                print("="*60)

                success = await self._click_publish_button()

                if success:
                    print("✅ 发布按钮已点击！")
                    print("⏳ 等待发布完成...")

                    # 等待发布完成
                    await asyncio.sleep(5)

                    # 检查是否有确认弹窗
                    await self._handle_confirm_dialog()

                    # 等待发布成功提示
                    await self._wait_for_publish_success()

                    print("\n" + "="*60)
                    print("🎉 发布流程完成！")
                    print("="*60 + "\n")
                else:
                    print("⚠️  自动点击发布按钮失败")
                    print("💡 提示：请手动点击发布按钮")

                    # 失败时也等待一段时间让用户手动操作
                    print("\n等待 30 秒供手动发布...")
                    await asyncio.sleep(30)
            else:
                # 等待用户手动发布
                print("请手动检查内容并点击发布按钮完成发布...")
                await asyncio.sleep(60)

        except Exception as e:
            print(f"发布文章时出错: {str(e)}")
            # 截图用于调试
            try:
                if self.page:
                    await self.page.screenshot(path="error_screenshot.png")
                    print("已保存错误截图: error_screenshot.png")
            except:
                pass
            raise

    async def _click_publish_button(self):
        """点击发布按钮"""
        try:
            print("🔍 查找发布按钮...")

            # 多种发布按钮选择器
            publish_selectors = [
                # 根据配置文件
                "button.publish-btn",
                # 按钮文字包含"发布"
                "button:has-text('发布')",
                # 通用按钮选择器
                ".publish-btn",
                # 可能的类名组合
                "button[class*='publish']",
                "button[class*='btn-publish']",
                # 最后尝试：通过CSS类和文字组合
                ".btn:has-text('发布')",
            ]

            for selector in publish_selectors:
                try:
                    print(f"  尝试选择器: {selector}")
                    await self.page.wait_for_selector(selector, state="visible", timeout=5000)

                    # 滚动到按钮可见
                    element = self.page.locator(selector).first
                    await element.scroll_into_view_if_needed()
                    await asyncio.sleep(1)

                    # 点击按钮
                    await element.click()
                    print(f"  ✅ 成功点击发布按钮 (选择器: {selector})")
                    return True

                except Exception as e:
                    print(f"  ❌ 选择器失败: {selector} - {str(e)}")
                    continue

            # 如果所有选择器都失败，尝试JavaScript点击
            print("  🔄 尝试 JavaScript 方式点击...")
            try:
                result = await self.page.evaluate("""
                    () => {
                        // 查找所有可能的发布按钮
                        const buttons = document.querySelectorAll('button');
                        for (let btn of buttons) {
                            const text = btn.textContent || '';
                            const className = btn.className || '';

                            // 检查按钮文字或类名是否包含"发布"
                            if (text.includes('发布') || className.includes('publish')) {
                                // 确保按钮可见且可点击
                                const rect = btn.getBoundingClientRect();
                                if (rect.width > 0 && rect.height > 0) {
                                    btn.click();
                                    return {
                                        success: true,
                                        text: text,
                                        className: className
                                    };
                                }
                            }
                        }
                        return { success: false };
                    }
                """)

                if result.get('success'):
                    print(f"  ✅ JavaScript 点击成功 (文字: {result.get('text')}, 类名: {result.get('className')})")
                    return True
                else:
                    print("  ❌ JavaScript 点击失败：未找到发布按钮")

            except Exception as e:
                print(f"  ❌ JavaScript 点击异常: {str(e)}")

            # 所有方法都失败，截保存 Debug
            print("  📸 保存发布按钮截图: debug_publish_button.png")
            await self.page.screenshot(path="debug_publish_button.png")

            return False

        except Exception as e:
            print(f"❌ 点击发布按钮时出错: {str(e)}")
            return False

    async def _handle_confirm_dialog(self):
        """处理确认弹窗（如果有）"""
        try:
            print("🔍 检查确认弹窗...")

            # 等待一小段时间让弹窗出现
            await asyncio.sleep(2)

            # 常见的确认弹窗选择器
            confirm_selectors = [
                "button:has-text('确认发布')",
                "button:has-text('确定')",
                "button:has-text('发布')",
                ".confirm-btn",
                ".dialog-btn:has-text('确认')",
            ]

            for selector in confirm_selectors:
                try:
                    if await self.page.locator(selector).count() > 0:
                        print(f"  ✅ 发现确认弹窗，点击确认: {selector}")
                        await self.page.click(selector)
                        await asyncio.sleep(2)
                        return True
                except:
                    continue

            print("  ℹ️  未发现确认弹窗")
            return False

        except Exception as e:
            print(f"  ⚠️  处理确认弹窗时出错: {str(e)}")
            return False

    async def _wait_for_publish_success(self):
        """等待发布成功"""
        try:
            print("⏳ 等待发布成功提示...")

            # 等待最多15秒
            for i in range(15):
                await asyncio.sleep(1)

                # 检查是否有成功提示
                success_indicators = [
                    ".publish-success",
                    ":text('发布成功')",
                    ":text('笔记已发布')",
                    ":text('发布完成')",
                ]

                for indicator in success_indicators:
                    try:
                        if await self.page.locator(indicator).count() > 0:
                            print(f"  ✅ 检测到发布成功: {indicator}")
                            return True
                    except:
                        continue

                # 检查URL是否跳转（发布成功后可能会跳转到笔记详情页）
                current_url = self.page.url
                if "xiaohongshu.com" in current_url and "/explore/" in current_url:
                    print(f"  ✅ 检测到页面跳转，可能已发布成功")
                    return True

            print("  ℹ️  未检测到明确的成功提示，但可能已发布")
            return False

        except Exception as e:
            print(f"  ⚠️  等待发布成功时出错: {str(e)}")
            return False

    async def close(self, force=False):
        """关闭浏览器连接
        Args:
            force: 是否强制关闭浏览器，默认为False
        """
        try:
            # CDP模式下，我们只断开连接，不关闭浏览器
            if self.playwright:
                await self.playwright.stop()
                self.playwright = None
                self.browser = None
                self.context = None
                self.page = None
        except Exception as e:
            logging.debug(f"关闭浏览器时出错: {str(e)}")

    async def ensure_browser(self):
        """确保浏览器已初始化"""
        if not self.playwright:
            await self.initialize()


if __name__ == "__main__":
    async def main():
        # 使用 CDP 模式，需要先启动 Chrome 并开启远程调试
        # 启动命令: /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222
        # 或者设置环境变量: export XHS_CDP_URL="http://localhost:9222"

        poster = XiaohongshuPoster(cdp_url="http://localhost:9222")
        try:
            print("开始初始化...")
            await poster.initialize()
            print("初始化完成")

            print("检查登录状态...")
            await poster.login()
            print("登录检查完成")

            print("开始发布文章...")
            await poster.post_article("测试文章", "这是一个测试内容，用于验证自动发布功能。", ["/Users/zhangqilai/project/vibe-code-100-projects/guiji/xhs_ai_publisher/assets/system_templates/template_showcase/showcase_biz_announcement_cool.png"])
            print("文章发布流程完成")

        except Exception as e:
            print(f"程序执行出错: {str(e)}")
            import traceback
            traceback.print_exc()
            try:
                if poster.page:
                    await poster.page.screenshot(path="error_debug.png")
                    print("已保存错误截图: error_debug.png")
            except:
                pass
        finally:
            print("等待10秒后断开连接...")
            await asyncio.sleep(10)
            await poster.close(force=True)
            print("程序结束")

    asyncio.run(main())
