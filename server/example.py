"""
音频转录服务使用示例
"""
import asyncio
from client import TranscriptionClient

async def main():
    # 初始化客户端
    client = TranscriptionClient("http://localhost:8000")

    # 检查服务健康状态
    health = await client.health_check()
    print(f"服务状态: {health}")

    # 获取服务信息
    info = await client.get_info()
    print(f"模型: {info['model']}")
    print(f"支持的语言: {', '.join(info['supported_languages'])}")

    # 转录文件示例（请替换为你的文件路径）
    # result = await client.transcribe_async(
    #     "test_data/sample.mp3",
    #     language="zh"
    # )
    # print(f"转录结果: {result['text']}")
    # print(f"处理时间: {result['processing_time']}秒")

if __name__ == "__main__":
    asyncio.run(main())
