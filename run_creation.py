import asyncio
from config.settings import CDP_URL
from core.browser_manager import BrowserManager
from core.recorder import SessionRecorder
from core.writer import WriterAgent
from core.artist import ArtistAgent

async def main():
    recorder = SessionRecorder()
    recorder.log("info", "=== 硅基Momo v2.1 创作工坊启动 ===")
    
    # 1. 连接浏览器
    bm = BrowserManager()
    await bm.start() # 确保你已经打开了 Chrome 且可能的话手动打开了即梦并登录
    
    # 2. 初始化智能体
    writer = WriterAgent(recorder)
    artist = ArtistAgent(bm.page, recorder) # 这里 bm.page 可能会被复用，注意
    
    # 3. 选题
    topic, ref_content = writer.pick_topic()
    
    # 4. 写作与构思
    draft = writer.write_article_and_prompt(topic, ref_content)
    if not draft:
        recorder.log("error", "文案生成失败，退出")
        return
        
    recorder.log("info", f"📝 文案已生成: 《{draft['title']}》")
    recorder.log("info", f"🎨 绘画提示词: {draft['image_prompt']}")
    
    # 5. 切换到美术师工作台
    # 注意：这里最好新建一个 page 给 artist，或者复用当前 page 跳转
    # 为了稳妥，我们在当前 page 跳转
    await artist.open_studio()
    
    # 6. 生图
    image_path = await artist.generate_image(draft['image_prompt'])
    
    if image_path:
        # 7. 归档
        writer.save_draft(draft, image_path)
        recorder.log("success", "🎉 创作闭环完成！草稿已存入 data/drafts.json")
    else:
        recorder.log("error", "生图失败，未能归档")

    await bm.disconnect()

if __name__ == "__main__":
    asyncio.run(main())