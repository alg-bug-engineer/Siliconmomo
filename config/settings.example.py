import random
import os
from pathlib import Path

# === 基础配置 ===
CDP_URL = "http://localhost:9222"  # 必须与你启动 Chrome 的参数一致
BASE_URL = "https://www.xiaohongshu.com"
SEARCH_KEYWORD = "AI工具推荐"  # 默认搜索关键词（AI 杂货店定位）
RUN_DURATION = 86400  # 24小时持续运营

# === 💾 数据存储配置 ===
# 获取当前项目根目录
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
# 素材库文件路径
INSPIRATION_FILE = DATA_DIR / "inspiration.json"

# 确保数据目录存在
DATA_DIR.mkdir(exist_ok=True)

# === 🧠 大模型配置 ===
# ⚠️ 请替换为你的智谱 AI API Key
# 获取地址：https://open.bigmodel.cn/
ZHIPU_AI_KEY = "your-zhipu-ai-key-here"  # 替换为你的真实 Key
LLM_MODEL = "glm-4.6"         # 文本分析与评论生成
ASR_SERVER_URL = "http://localhost:8000/transcribe" # 音频转录服务地址

# === 🎯 目标领域与搜索 ===
# AI 杂货店定位：专注于 AI 工具/插件推荐
TARGET_TOPICS = [
    "AI工具", "浏览器插件", "ChatGPT插件", "AI助手",
    "效率工具", "自动化工具", "AI写作", "AI绘画",
    "小红书工具", "插件推荐", "Chrome插件", "AI生成"
]
# 搜索关键词池 (随机轮转) - AI 工具与插件
SEARCH_KEYWORDS = [
    "AI工具推荐", "浏览器插件", "ChatGPT插件", "AI助手",
    "效率工具", "自动化工具", "AI写作工具", "AI绘画工具",
    "小红书工具", "插件推荐", "Chrome插件", "AI生成工具",
    "AI办公", "智能插件", "免费AI工具", "神器推荐"
]
# 每浏览多少个帖子后，执行一次新的搜索
SEARCH_INTERVAL = random.randint(3, 6)

# === 📅 自动发帖配置 ===
# 发帖时间点 (24小时制)
PUBLISH_HOURS = [8, 12, 21]
# 每日发帖上限
DAILY_PUBLISH_LIMIT = 3
# 触发创作的素材阈值（积累多少条高质量素材后创作一篇）
INSPIRATION_THRESHOLD = 3  # 改为3个高质量素材触发创作

# === 深度研究配置 ===
DEEP_RESEARCH_ENABLED = False # 是否启用深度研究模式
DEEP_RESEARCH_POST_LIMIT = 20 # 深度研究模式下阅读的帖子数量
DEEP_RESEARCH_LLM_MODEL = "kimi" # 深度研究使用的LLM模型 (例如: kimi, gpt-4)
DEEP_RESEARCH_COMMENT_LIMIT = 100 # 每个帖子下载的评论数量上限
DEEP_RESEARCH_OUTPUT_DIR = DATA_DIR / "deep_research_reports" # 深度研究报告输出目录
DEEP_RESEARCH_OUTPUT_DIR.mkdir(exist_ok=True) # 确保目录存在

# === 🎲 拟人化概率漏斗 ===
# 第一层：动脑概率 (是否调用 LLM 进行深度分析)
# 类似于：这时候你是只是想随便划划水，还是想认真看？
PROB_TRIGGER_THINKING = 0.4  # 40% 的概率会唤醒大脑进行分析

# 第二层：表达概率 (分析后，如果 LLM 觉得值得评，实际发出的概率)
# 类似于：虽然心里有想法，但有时候懒得打字就划走了
PROB_POST_COMMENT = 0.7      # 70% 的概率会把心里话发出去

# 懒人互动概率 (在不动脑模式下，仅凭直觉点赞收藏的概率)
PROB_LAZY_LIKE = 0.2
PROB_LAZY_COLLECT = 0.1

# === 概率控制 (MVP设定) ===
PROB_LIKE = 0.4      # 40% 点赞
PROB_COLLECT = 0.2   # 20% 收藏
PROB_FLIP_IMG = 0.5  # 50% 看多图
PROB_READ_LONG = 0.8 # 80% 长阅读
PROB_COMMENT = 0.3  # 30% 的概率在符合条件的帖子下评论

# === 🎨 创作配置 ===
JIMENG_GENERATE_URL = "https://jimeng.jianying.com/ai-tool/generate?type=image"

# 图片保存目录
ASSETS_DIR = BASE_DIR / "assets"
IMAGES_DIR = ASSETS_DIR / "images"
DRAFTS_FILE = DATA_DIR / "drafts.json"

# 确保目录存在
IMAGES_DIR.mkdir(parents=True, exist_ok=True)

# === 🤖 选题配置 ===
# AI 杂货店定位：工具推荐类内容
DEFAULT_TOPICS = [
    "AI工具推荐", "浏览器插件", "效率神器", "AI助手",
    "自动化工具", "AI办公神器", "ChatGPT插件", "AI绘画工具"
]

JIMENG_SELECTORS = {
    # 输入框 (保持不变，已验证有效)
    "prompt_textarea": "textarea[placeholder='请描述你想生成的图片']",

    # [核心修复] 发送按钮：
    # 1. 匹配 class 包含 submit-button
    # 2. 必须不包含 disabled 属性 (确保已激活) - 可选，但 visible=true 最重要
    # 3. >> visible=true : 这是一个 Playwright 专用语法，只选可见的那个！
    "generate_btn": "button[class*='submit-button'] >> visible=true",

    # 结果网格
    "result_grid": "div[class*='responsive-image-grid']",

    # 结果卡片
    "result_card": "div[class*='image-card-wrapper']",

    # 结果图片
    "result_image": "img[class*='image-']"
}

# === 🚀 发布配置 ===
# 发布页面 URL (直接访问这个比点按钮更稳)
# XHS_CREATOR_URL = "https://creator.xiaohongshu.com/publish/publish"
XHS_CREATOR_URL = "https://creator.xiaohongshu.com/publish/publish?from=tab_switch&target=image"

# 针对小红书最新版 DOM 结构的选择器配置
PUBLISH_SELECTORS = {
    # 优化 Tab 选择器：直接找包含文字的 span 或 div，不强依赖 class
    "tab_video": ":text('上传视频')",
    "tab_image": "div.creator-tab:has-text('上传图文')",

    # 上传按钮维持原状
    "upload_input": "input[type=file]",

    # 标题维持原状
    "title_input": "input.d-text[placeholder*='标题']",

    # 【关键修改】适配新的 ProseMirror 编辑器
    "content_editor": ".ProseMirror",

    # 发布按钮 (根据经验推断，如果 HTML 中没变的话)
    "publish_btn": "button.publish-btn, button:has-text('发布')",

    # 成功检测
    "success_element": ".publish-success, :text('发布成功')"
}

# === 选择器 ===
SELECTORS = {
    # 首页/搜索
    "search_input": "#search-input",
    "search_btn": ".search-icon",
    "note_card": "section.note-item",

    # 详情页内容提取 (根据你提供的HTML确认)
    "detail_title": "#detail-title",
    "detail_desc": "#detail-desc", # 稍微放宽，获取 desc 下所有文本

    # 评论区核心元素
    # 注意：如果出现 .comments-login 说明没登录或被限制，无法评论
    "comment_area_login_mask": ".comments-login",

    # === 评论区关键修改 ===
    # 1. 激活评论框：这是未点击时的占位符
    # 策略：优先匹配类名，其次匹配文字内容
    "comment_input_area": [
        ".inner-when-not-active",       # 优先：你抓取的 HTML 类名
        "div:has-text('说点什么')",       # 备选：根据文字内容定位
        ".comment-input",               # 备选：旧版选择器
        ".comment-inner-container"      # 备选：容器
    ],

    # 2. 实际输入区域：点击激活后，这里通常是一个 contenteditable 的 div
    "comment_editable": [
        ".content-edit",                # 常见类名
        "[contenteditable='true']",     # 通用属性选择器 (最稳)
        "div.not-empty"                 # 输入文字后可能会变的类名
    ],

    # 3. 发送按钮
    "comment_submit": [
        ".comment-submit",
        "div.post-btn:has-text('发送')", # 结合类名和文字
        "button:has-text('发送')"
    ],

    # 详情页
    "note_detail_mask": ".note-detail-mask", # 详情页遮罩
    "btn_like": [
        "div.interactions.engage-bar span.like-lottie",
        "span.like-wrapper"
    ],
    "btn_collect": [
        "div.interactions.engage-bar span.collect-wrapper",
        "span.collect-wrapper"
    ],
    "btn_close": [
        "div.close-circle",
        "div.close",
        "xpath=//use[@xlink:href='#close']"
    ],
    "btn_next_img": ".media-container .arrow-right",
}
