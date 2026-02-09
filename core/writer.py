import json
import random
import time
from pathlib import Path
from config.settings import INSPIRATION_FILE, DRAFTS_FILE, ENABLE_TITLE_OPTIMIZATION
from core.llm_client import LLMClient
from core.product_manager import ProductManager
from core.title_optimizer import TitleOptimizer

class WriterAgent:
    """
    笔杆子 - 支持多种创作模式
    1. 素材仿写模式：从素材库抽取优质内容，AI分析风格后仿写
    2. 产品宣传模式：基于产品信息创作宣传内容
    """
    def __init__(self, recorder, product_manager=None):
        self.recorder = recorder
        self.llm = LLMClient(recorder)
        self.pm = product_manager or ProductManager(recorder)  # 产品管理器
        self._ensure_draft_file()
        self._load_emotions()  # 加载情感/风格模板

        # 初始化标题优化器
        if ENABLE_TITLE_OPTIMIZATION:
            self.title_optimizer = TitleOptimizer(recorder)
            self.recorder.log("info", "🎯 [笔杆子] 标题优化器已启用")
        else:
            self.title_optimizer = None

    def _load_emotions(self):
        """加载风格模板"""
        emotions_file = Path(__file__).parent.parent / "data" / "emotions.json"
        try:
            if emotions_file.exists():
                with open(emotions_file, "r", encoding="utf-8") as f:
                    self.emotions = json.load(f)
            else:
                self.emotions = {}
        except Exception as e:
            self.recorder.log("warning", f"⚠️ [笔杆子] 风格模板加载失败: {e}")
            self.emotions = {}

    def _ensure_draft_file(self):
        if not DRAFTS_FILE.exists():
            with open(DRAFTS_FILE, "w", encoding="utf-8") as f:
                json.dump([], f)

    def _load_inspirations(self):
        """读取素材库"""
        if not INSPIRATION_FILE.exists():
            return []
        with open(INSPIRATION_FILE, "r", encoding="utf-8") as f:
            return json.load(f)

    def pick_inspiration(self):
        """
        从素材库选取未使用的优质素材
        返回: (素材对象, None) 或 (None, 错误信息)
        """
        inspirations = self._load_inspirations()
        
        # 筛选未使用的素材
        unused = [item for item in inspirations if item.get("status") == "unused"]
        
        if not unused:
            self.recorder.log("warning", "💡 [笔杆子] 素材库为空或已全部使用")
            return None, "素材不足"
        
        # 随机选一个
        seed = random.choice(unused)
        self.recorder.log("info", f"💡 [笔杆子] 选中灵感种子: {seed.get('title', '')[:20]}...")
        return seed, None

    def write_from_inspiration(self, inspiration):
        """
        基于素材仿写：分析素材风格后创作
        :param inspiration: 素材对象（包含 title, content, image_urls 等）
        :return: 创作结果 dict 或 None
        """
        ref_title = inspiration.get("title", "")
        ref_content = inspiration.get("content", "")
        ref_images = inspiration.get("image_urls", [])
        # 从素材的AI分析中提取风格提示
        style_hint = inspiration.get("ai_analysis", {}).get("style_hint", "工具推荐")
        
        # 构建仿写 Prompt - AI 杂货店定位，专注工具推荐
        prompt = f"""
你是一个小红书 AI 杂货店博主"Momo"，专注于推荐各类 AI 工具、浏览器插件、效率神器。
你的目标用户是打工人和创作者，他们面临时间紧、任务多、效率低的痛点。

【任务】
基于以下参考素材，创作一篇风格相似但内容原创的小红书笔记。

【参考素材】
标题：{ref_title}
正文：{ref_content[:800]}
风格提示：{style_hint}

【创作要求】
1. **仿写风格**：保持原素材的内容类型（{style_hint}），但内容必须原创

2. **情感共鸣（核心要求）**：
   - ❌ 不要冷冰冰的技术介绍
   - ✅ 要用真实场景切入，让读者产生"这就是在说我"的感觉
   - 常用场景模板：
     * "深夜加班时，面对堆积如山的任务..."
     * "每到月底总结时，才发现效率太低..."
     * "看着同事用10分钟搞定我1小时的工作..."
     * "尝试了无数工具，终于找到这个神器..."
   - 情感词汇：
     * 痛点：折磨、崩溃、头秃、抓狂、焦虑
     * 解决：救命、绝了、太香了、相见恨晚、真香
     * 效果：起飞、翻倍、轻松、搞定、解放

3. **文案特点**：
   - 多用 Emoji（🚀🔥💡⚡✨🎯😭😍🤯等，根据情感选择）
   - 多用短句，节奏明快
   - 语气风格：
     * 工具推荐：热情推荐、突出效率提升
     * 功能介绍：场景化描述、真实使用体验
     * 使用教程：耐心教导、保姆级步骤
     * 避坑指南：真诚提醒、像朋友一样关心
     * 合集推荐：丰富全面、按需取用

4. **字数控制**：正文 200-400 字

5. **绘画提示词**：根据内容类型生成封面图描述（必须是英文）
   - **统一视觉风格**：科技蓝、工具界面、效率场景
   - **工具推荐类**：现代工作空间、软件界面、屏幕展示、专业光效
   - **功能介绍类**：软件操作界面、清晰UI展示、现代科技感
   - **使用教程类**：步骤演示、信息图表、清晰引导
   - **避坑指南类**：对比展示、警示元素、清晰说明
   - **合集推荐类**：网格布局、工具展示、极简设计
   - 提示词必须包含：主体、场景、风格、氛围、色调

【输出格式 (JSON Only)】
{{
    "title": "原创标题（带emoji，吸引眼球）",
    "content": "原创正文（场景化、情感化）",
    "image_prompt": "English image prompt for AI art generation...",
    "style": "{style_hint}",
    "tags": ["#AI工具", "#效率神器", "#打工人必备", "#tag3"]
}}
"""
        
        try:
            self.recorder.log("info", "✍️ [笔杆子] 正在仿写创作...")
            response = self.llm.client.chat.completions.create(
                model="glm-4.6",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.85  # 稍高的温度增加创意
            )
            content = response.choices[0].message.content
            
            # 清洗 markdown
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            
            result = json.loads(content.strip())
            result["source_inspiration_id"] = inspiration.get("id")

            # 🎯 应用标题优化器
            if self.title_optimizer:
                original_title = result.get("title", "")
                if original_title:
                    self.recorder.log("debug", f"🎯 [笔杆子] 原始标题: {original_title}")

                    # 优化标题
                    optimization_result = self.title_optimizer.optimize_title(
                        original_title,
                        result.get("content", "")[:100]  # 内容摘要
                    )

                    optimized_title = optimization_result.get("optimized", original_title)
                    score = optimization_result.get("score", 0)

                    # 如果优化后的标题评分更高，使用优化后的标题
                    if score > 60 and optimized_title != original_title:
                        result["title"] = optimized_title
                        self.recorder.log("info", f"🎯 [笔杆子] 标题已优化 (评分: {score}/100)")
                        self.recorder.log("info", f"   原始: {original_title}")
                        self.recorder.log("info", f"   优化: {optimized_title}")
                    else:
                        self.recorder.log("debug", f"🎯 [笔杆子] 标题已足够好 (评分: {score}/100)，保持原样")

            self.recorder.log("info", f"✍️ [笔杆子] 创作完成: 《{result.get('title', '')}》")
            return result
            
        except Exception as e:
            self.recorder.log("error", f"✍️ [笔杆子] 仿写失败: {e}")
            return None

    def save_draft(self, article_data, image_path):
        """保存草稿到待发布队列"""
        try:
            with open(DRAFTS_FILE, "r", encoding="utf-8") as f:
                drafts = json.load(f)
            
            article_data["image_local_path"] = str(image_path)
            article_data["created_at"] = str(time.time())
            article_data["status"] = "ready_to_publish"
            
            drafts.append(article_data)
            
            with open(DRAFTS_FILE, "w", encoding="utf-8") as f:
                json.dump(drafts, f, indent=4, ensure_ascii=False)
                
            self.recorder.log("info", "💾 [笔杆子] 草稿已归档")
            return True
        except Exception as e:
            self.recorder.log("error", f"💾 保存草稿失败: {e}")
            return False

    def get_ready_draft(self):
        """获取一篇待发布的草稿"""
        try:
            with open(DRAFTS_FILE, "r", encoding="utf-8") as f:
                drafts = json.load(f)
            
            ready = [d for d in drafts if d.get("status") == "ready_to_publish"]
            if ready:
                return ready[0]
            return None
        except Exception:
            return None

    def mark_draft_published(self, draft_created_at):
        """标记草稿为已发布"""
        try:
            with open(DRAFTS_FILE, "r", encoding="utf-8") as f:
                drafts = json.load(f)
            
            for draft in drafts:
                if draft.get("created_at") == draft_created_at:
                    draft["status"] = "published"
                    draft["published_at"] = str(time.time())
                    break
            
            with open(DRAFTS_FILE, "w", encoding="utf-8") as f:
                json.dump(drafts, f, indent=4, ensure_ascii=False)
                
            self.recorder.log("info", "📤 [笔杆子] 草稿已标记为已发布")
        except Exception as e:
            self.recorder.log("error", f"标记发布状态失败: {e}")

    # === 产品宣传模式 ===

    def write_from_product(self, product: dict, style: str = "产品宣传") -> dict:
        """
        基于产品创作宣传内容
        :param product: 产品对象
        :param style: 创作风格（产品宣传/用户案例）
        :return: 创作结果 dict 或 None
        """
        # 获取风格模板
        style_config = self.emotions.get("styles", {}).get(style, {})

        if not style_config:
            self.recorder.log("warning", f"⚠️ [笔杆子] 未找到风格模板: {style}")
            # 使用默认 prompt
            return self._write_product_default(product, style)

        # 构建产品信息
        product_info = self._format_product_info(product)

        # 获取 prompt 模板
        prompt_template = style_config.get("prompt_template", "")

        # 替换模板变量
        prompt = prompt_template.format(
            product_info=product_info,
            name=product.get("name", ""),
            tagline=product.get("tagline", ""),
            price=product.get("price", ""),
            pain_points="、".join(product.get("pain_points", [])[:3]),
            use_cases="、".join(product.get("use_cases", [])[:3])
        )

        # 如果是用户案例，添加场景
        if style == "用户案例":
            scenario = random.choice(product.get("use_cases", ["日常使用"]))
            prompt = prompt.replace("{scenario}", scenario)

        try:
            self.recorder.log("info", f"✍️ [笔杆子] 正在创作产品宣传: {product.get('name')}")

            response = self.llm.client.chat.completions.create(
                model="glm-4.6",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.8
            )

            content = response.choices[0].message.content

            # 清洗 markdown
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            result = json.loads(content.strip())
            result["product_id"] = product.get("id")
            result["product_name"] = product.get("name")
            result["source_type"] = "product_promo"

            # 🎯 应用标题优化器（产品宣传）
            if self.title_optimizer:
                original_title = result.get("title", "")
                if original_title:
                    # 优化标题
                    optimization_result = self.title_optimizer.optimize_title(
                        original_title,
                        result.get("content", "")[:100]  # 内容摘要
                    )

                    optimized_title = optimization_result.get("optimized", original_title)
                    score = optimization_result.get("score", 0)

                    # 如果优化后的标题评分更高，使用优化后的标题
                    if score > 60 and optimized_title != original_title:
                        result["title"] = optimized_title
                        self.recorder.log("info", f"🎯 [笔杆子] 产品标题已优化 (评分: {score}/100)")

            # 添加图片提示词（如果 LLM 没有生成）
            if "image_prompt" not in result or not result.get("image_prompt"):
                result["image_prompt"] = self._get_product_image_prompt(style)

            self.recorder.log("info", f"✍️ [笔杆子] 产品宣传创作完成: 《{result.get('title', '')}》")
            return result

        except Exception as e:
            self.recorder.log("error", f"✍️ [笔杆子] 产品宣传创作失败: {e}")
            return None

    def _write_product_default(self, product: dict, style: str) -> dict:
        """默认产品宣传创作（当没有模板时）"""
        prompt = f"""
你是一个小红书 AI 杂货店博主"Momo"，正在推荐自己的产品。

【产品信息】
产品名称：{product.get('name', '')}
核心卖点：{product.get('tagline', '')}
价格：{product.get('price', '')}
解决痛点：{', '.join(product.get('pain_points', [])[:3])}
使用场景：{', '.join(product.get('use_cases', [])[:3])}

【任务】
创作一篇小红书产品推荐笔记，{style}风格。

【要求】
1. 语气真诚，像朋友分享好物
2. 突出产品解决的问题
3. 多用Emoji：🚀💡⚡✨🎯
4. 字数：200-400字
5. 不要过度推销，要真实可信

【输出格式 (JSON Only)】
{{
    "title": "标题（带emoji）",
    "content": "正文...",
    "image_prompt": "clean product showcase, modern design, professional lighting",
    "style": "{style}",
    "tags": ["#效率神器", "#工具推荐"]
}}
"""

        try:
            response = self.llm.client.chat.completions.create(
                model="glm-4.6",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.8
            )

            content = response.choices[0].message.content

            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            result = json.loads(content.strip())
            result["product_id"] = product.get("id")
            result["product_name"] = product.get("name")
            result["source_type"] = "product_promo"

            return result

        except Exception as e:
            self.recorder.log("error", f"✍️ [笔杆子] 默认创作失败: {e}")
            return None

    def _format_product_info(self, product: dict) -> str:
        """格式化产品信息"""
        return f"""
名称：{product.get('name', '')}
卖点：{product.get('tagline', '')}
价格：{product.get('price', '')}
分类：{product.get('category', '')}
""".strip()

    def _get_product_image_prompt(self, style: str) -> str:
        """获取产品图片提示词"""
        prompts = self.emotions.get("image_prompts", {}).get(style, [])
        if prompts:
            return random.choice(prompts)

        # 默认提示词
        defaults = {
            "产品宣传": "clean product showcase, modern minimal design, professional lighting",
            "用户案例": "productivity comparison, clean layout, modern design"
        }
        return defaults.get(style, "modern tech design, clean minimal, professional")

    def get_product_style_templates(self) -> list:
        """获取可用的产品宣传风格"""
        return ["产品宣传", "用户案例"]