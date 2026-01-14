import json
from bs4 import BeautifulSoup, Comment, Tag
from zai import ZhipuAiClient
from config.settings import ZHIPU_AI_KEY, LLM_MODEL

class SmartLocator:
    def __init__(self, recorder):
        self.client = ZhipuAiClient(api_key=ZHIPU_AI_KEY)
        self.recorder = recorder

    def clean_dom(self, html_content):
        """
        DOM 瘦身术 (健壮版)：只保留可能有用的交互元素
        """
        if not html_content:
            return ""

        try:
            soup = BeautifulSoup(html_content, "html.parser")

            # 1. 移除无用标签
            for element in soup(["script", "style", "noscript", "iframe", "svg", "path", "link", "meta"]):
                element.decompose()

            # 2. 移除注释
            for comment in soup.find_all(text=lambda text: isinstance(text, Comment)):
                comment.extract()

            # 3. 属性清洗
            allowed_attrs = ['id', 'class', 'name', 'placeholder', 'type', 'role', 'aria-label', 'value', 'title', 'alt']
            
            # 使用 list() 复制迭代器，防止在修改树结构时出错
            for tag in soup.find_all(True):
                # 关键修复：确保 tag 是 Tag 类型且有 attrs 属性
                if not isinstance(tag, Tag) or not hasattr(tag, 'attrs') or tag.attrs is None:
                    continue

                # 复制 keys 防止运行时字典大小改变报错
                current_attrs = list(tag.attrs.keys())
                for attr in current_attrs:
                    if attr not in allowed_attrs:
                        del tag.attrs[attr]
                
                # 移除空标签 (没有属性且没有文本的 div/span)
                if tag.name in ['div', 'span'] and not tag.attrs and not tag.get_text(strip=True):
                    tag.decompose()

            # 4. 压缩与截断
            cleaned_html = str(soup).replace('\n', '').replace('  ', '')
            # 保留前 30k 字符，防止 Token 爆炸
            return cleaned_html[:30000]

        except Exception as e:
            self.recorder.log("error", f"🧹 [SmartLocator] DOM 清洗失败: {e}")
            # 降级策略：如果清洗失败，返回原始 HTML 的前 5000 个字符
            return html_content[:5000]

    async def find_element(self, page, task_description):
        """
        对外暴露的方法：智能查找 (增加异常捕获)
        """
        self.recorder.log("debug", f"🔍 [SmartLocator] 正在分析页面以寻找: {task_description}")
        
        try:
            # 1. 获取并清洗 DOM
            raw_html = await page.content()
            cleaned_html = self.clean_dom(raw_html)
            
            # 2. 询问 AI
            prompt = f"""
            你是一个前端自动化测试专家。
            【任务】
            在以下 HTML DOM 中找到能完成此任务的 CSS 选择器：{task_description}

            【DOM 片段】
            {cleaned_html}

            【要求】
            1. 返回且仅返回一个 CSS 选择器字符串。
            2. 优先使用 id, placeholder, name, aria-label 等语义化属性。
            3. 如果必须使用 class，请选取看起来比较稳定的部分。
            4. 不要返回 JSON，不要返回代码块，直接返回选择器字符串。
            5. 如果找不到，返回 "NOT_FOUND"。
            """
            
            response = self.client.chat.completions.create(
                model=LLM_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1
            )
            selector = response.choices[0].message.content.strip().replace("`", "")
            
            if not selector or selector == "NOT_FOUND":
                self.recorder.log("warning", f"❌ AI 未能定位到元素: {task_description}")
                return None
            
            # 3. 验证有效性
            self.recorder.log("info", f"🧠 AI 建议选择器: {selector}")
            count = await page.locator(selector).count()
            if count > 0:
                self.recorder.log("success", f"✅ 选择器验证通过 (匹配 {count} 个)")
                return selector
            else:
                self.recorder.log("warning", f"❌ AI 提供的选择器无效 (匹配 0 个): {selector}")
                return None

        except Exception as e:
            self.recorder.log("error", f"🧠 [SmartLocator] 分析过程崩溃: {e}")
            return None