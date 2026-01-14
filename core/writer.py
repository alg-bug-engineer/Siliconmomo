import json
import random
import time
from pathlib import Path
from config.settings import INSPIRATION_FILE, DRAFTS_FILE
from core.llm_client import LLMClient

class WriterAgent:
    """
    笔杆子 - 基于素材仿写模式
    核心逻辑：从素材库抽取优质内容，AI分析风格后仿写
    """
    def __init__(self, recorder):
        self.recorder = recorder
        self.llm = LLMClient(recorder)
        self._ensure_draft_file()

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
        style_hint = inspiration.get("ai_analysis", {}).get("style_hint", "共情")
        
        # 构建仿写 Prompt - AI 杂货店定位，专注工具推荐
        prompt = f"""
你是一个小红书 AI 杂货店博主"Momo"，专注于推荐各类 AI 工具、浏览器插件、效率神器。

【任务】
基于以下参考素材，创作一篇风格相似但内容原创的小红书笔记。

【参考素材】
标题：{ref_title}
正文：{ref_content[:800]}
风格提示：{style_hint}

【创作要求】
1. **仿写风格**：保持原素材的内容类型（{style_hint}），但内容必须原创
2. **文案特点**：
   - 多用 Emoji（🚀🔧💡⚡✨🎯等，根据风格选择）
   - 多用短句，结构清晰
   - 语气专业但亲和：
     * 工具推荐：专业热情、突出价值
     * 功能介绍：详细科技感
     * 使用教程：耐心清晰、教导性
     * 避坑指南：真诚实用、提醒性
     * 合集推荐：丰富全面
3. **字数控制**：正文 150-350 字
4. **绘画提示词**：根据内容类型生成封面图描述（必须是英文）
   - **工具推荐类**：科技工作空间、AI 界面、现代桌面、极简设计、专业光效
   - **功能介绍类**：软件界面特写、现代 UI 设计、科技美学
   - **使用教程类**：步骤教程插图、清晰信息图、现代设计
   - **避坑指南类**：警示图标、对比插图、清晰信息传达
   - **合集推荐类**：集合展示、网格布局、现代极简设计
   - 提示词必须包含：主体、光影、风格、氛围

【输出格式 (JSON Only)】
{{
    "title": "原创标题（带emoji）",
    "content": "原创正文...",
    "image_prompt": "English image prompt for AI art generation...",
    "style": "{style_hint}",
    "tags": ["#tag1", "#tag2", "#tag3"]
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