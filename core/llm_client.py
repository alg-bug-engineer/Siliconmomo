import json
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
        1. 帖子必须属于以下领域之一：{", ".join(TARGET_TOPICS)}。如果帖子是无关的（如情感、穿搭、娱乐），请标记为不相关。
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
