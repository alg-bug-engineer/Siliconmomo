import json
import random
from zai import ZhipuAiClient  # 更新 SDK 引入
from config.settings import ZHIPU_AI_KEY, LLM_MODEL, TARGET_TOPICS

class LLMClient:
    def __init__(self, recorder):
        # 初始化新的 Client
        self.client = ZhipuAiClient(api_key=ZHIPU_AI_KEY)
        self.recorder = recorder

    def analyze_and_comment(self, title, content):
        """
        分析帖子内容，判断是否相关，并生成评论
        """
        # 构造 Prompt - AI 杂货店主定位
        prompt = f"""
        你是一个活跃在小红书的 AI 杂货店博主"Momo"，你的专家人设是：专注于推荐各类 AI 工具、浏览器插件、效率神器的博主。

        【任务目标】
        分析给定的帖子内容，判断是否值得互动和收藏作为素材，如果值得，生成一条真实的、口语化的评论。

        【判断标准】
        1. 帖子必须属于以下领域之一：{", ".join(TARGET_TOPICS)}。如果帖子是无关的（如情感、穿搭、娱乐、游戏），请标记为不相关。
        2. 如果帖子正文文字太少（少于10个字），或者是纯图片无意义内容，请标记为不需要评论。
        3. **高质量标准**：文案有实用价值、信息清晰、有推荐意义、适合仿写创作。只有同时满足以下条件的才算高质量：
           - 文案有明确的内容类型（工具推荐/功能介绍/使用教程/避坑指南/合集推荐）
           - 有实用价值，能提供工具或效率提升信息
           - 结构清晰，适合作为创作参考
           - 字数适中（50-500字）

        【帖子信息】
        标题：{title}
        正文：{content}

        【输出要求】
        请仅返回一个标准的 JSON 格式字符串，不要包含 Markdown 标记：
        {{
            "is_relevant": true/false,
            "is_high_quality": true/false,  // 是否高质量素材（用于后续创作参考）
            "should_comment": true/false,
            "comment_text": "你的评论内容", // 50字以内，口语化，不要带引号
            "style_hint": "工具推荐/功能介绍/使用教程/避坑指南/合集推荐" // 内容类型提示，用于后续创作参考
        }}
        """

        try:
            # 使用新的调用方式
            response = self.client.chat.completions.create(
                model=LLM_MODEL,
                messages=[
                    {"role": "system", "content": "你是一个严格遵循JSON输出格式的AI助手。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                # 如果需要启用深度思考，可以解开下面注释，但简单任务不建议开启以节省时间
                # thinking={"type": "enabled"} 
            )
            
            # 获取结果
            result_text = response.choices[0].message.content.strip()
            
            # 清洗 Markdown 标记
            if result_text.startswith("```json"):
                result_text = result_text.split("```json")[1]
            if result_text.endswith("```"):
                result_text = result_text.rsplit("```", 1)[0]
            
            result = json.loads(result_text.strip())
            # 确保返回所有必需字段（兼容旧格式）
            if "is_high_quality" not in result:
                result["is_high_quality"] = result.get("is_relevant", False)
            if "style_hint" not in result:
                result["style_hint"] = ""
            return result

        except Exception as e:
            self.recorder.log("error", f"🧠 [大脑] 思考失败: {e}")
            return {
                "is_relevant": False,
                "is_high_quality": False,
                "should_comment": False,
                "comment_text": "",
                "style_hint": ""
            }

    # === 软广评论生成 ===

    def generate_promo_comment(self, title: str, content: str, product: dict, interaction_type: str = "help_first") -> dict:
        """
        生成软广评论
        :param title: 帖子标题
        :param content: 帖子内容
        :param product: 产品对象
        :param interaction_type: 互动类型（help_first/value_share/direct_promo）
        :return: 评论结果字典
        """
        product_name = product.get("name", "")
        product_tagline = product.get("tagline", "")
        product_category = product.get("category", "")

        # 根据互动类型调整策略
        if interaction_type == "help_first":
            strategy_desc = "先提供帮助和解决方案，然后自然地提及产品作为更高效的替代方案"
            tone_desc = "热心助人、真诚分享"
        elif interaction_type == "value_share":
            strategy_desc = "分享自己的使用经验和心得，在合适的时候提及使用过的工具"
            tone_desc = "经验分享、真诚交流"
        else:  # direct_promo
            strategy_desc = "直接但克制地推荐产品，强调它正好能解决帖子中的问题"
            tone_desc = "直接推荐、解决问题"

        prompt = f"""
你是一个活跃在小红书的 AI 杂货店博主"Momo"，你有一款产品：{product_name}（{product_tagline}）。

【任务目标】
针对下面的帖子，生成一条软广评论。不要明显像广告，要像真实的用户交流。

【帖子信息】
标题：{title}
正文：{content[:500]}

【你的产品】
名称：{product_name}
卖点：{product_tagline}
分类：{product_category}

【评论策略】
{strategy_desc}

【要求】
1. **语气**：{tone_desc}，像真人博主在聊天
2. **开头**：先回应帖子的内容或问题，表示理解
3. **产品提及**：
   - help_first：回答问题 → 顺带说"我用过一个工具能简化这个"
   - value_share：分享经历 → 提及"我用XX工具，效率提升不少"
   - direct_promo：说明产品正好解决这个问题
4. **自然度**：不要堆砌产品信息，不要频繁重复产品名
5. **长度**：30-80字
6. **Emoji**：适当使用 1-2 个（🚀💡✨等）

【避免】
- 不要像硬广一样罗列功能
- 不要过分强调价格或购买链接
- 不要夸大效果

【输出格式 (JSON Only)】
{{
    "comment_text": "评论内容...",
    "is_natural": true,  // 评论是否自然不过分像广告
    "product_mentioned": true  // 是否提到了产品
}}
"""

        try:
            response = self.client.chat.completions.create(
                model=LLM_MODEL,
                messages=[
                    {"role": "system", "content": "你是一个擅长软性推广的小红书博主。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.8
            )

            result_text = response.choices[0].message.content.strip()

            # 清洗 Markdown
            if result_text.startswith("```json"):
                result_text = result_text.split("```json")[1]
            if result_text.endswith("```"):
                result_text = result_text.rsplit("```", 1)[0]

            result = json.loads(result_text.strip())

            # 添加额外信息
            result["interaction_type"] = interaction_type
            result["product_id"] = product.get("id")

            self.recorder.log("info", f"🧠 [软广评论] 生成完成: {result.get('comment_text', '')[:30]}...")
            return result

        except Exception as e:
            self.recorder.log("error", f"🧠 [软广评论] 生成失败: {e}")
            # 返回简单的兜底评论
            fallback_comments = [
                f"这个问题我也遇到过，后来用一个工具能一键处理，省事多了 🚀",
                f"推荐试试我用的这个，效率提升很明显 💡",
                f"我之前也手动搞过，后来发现{product_name}能自动处理 ✨"
            ]
            return {
                "comment_text": random.choice(fallback_comments),
                "is_natural": True,
                "product_mentioned": True,
                "interaction_type": interaction_type,
                "product_id": product.get("id")
            }

        return None

    async def generate_text(self, prompt: str, model: str = LLM_MODEL) -> str:
        """
        生成通用文本响应。
        :param prompt: 文本生成提示词。
        :param model: 使用的 LLM 模型名称。
        :return: 生成的文本内容。
        """
        messages = [
            {"role": "user", "content": prompt}
        ]
        try:
            # ZhipuAiClient 使用同步调用，不需要 await
            response = self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.7,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            self.recorder.log("error", f"🧠 [LLM文本生成] 调用 LLM 失败 (模型: {model}): {e}")
            return f"Error: LLM failed to generate text for model {model}."
