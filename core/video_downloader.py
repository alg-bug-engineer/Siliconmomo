"""
视频下载模块
支持从小红书下载视频到本地
"""
import asyncio
import json
import re
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass

try:
    import httpx
except ImportError:
    raise SystemExit("缺少依赖: httpx. 安装命令: pip install httpx")


@dataclass
class VideoInfo:
    """视频信息"""
    note_id: str
    title: str
    video_url: str
    local_path: Optional[str] = None
    filesize: Optional[int] = None
    duration: Optional[float] = None
    width: Optional[int] = None
    height: Optional[int] = None


class VideoDownloader:
    """
    视频下载器
    支持从小红书下载视频到本地
    """

    def __init__(self, save_dir: str = "videos", timeout: int = 300):
        """
        初始化下载器

        Args:
            save_dir: 视频保存目录
            timeout: 下载超时时间（秒）
        """
        self.save_dir = Path(save_dir)
        self.save_dir.mkdir(exist_ok=True, parents=True)
        self.timeout = timeout

        # 用户代理
        self.user_agent = (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )

    async def extract_video_info_from_url(self, url: str) -> Optional[VideoInfo]:
        """
        从小红书 URL 提取视频信息

        Args:
            url: 小红书笔记 URL (https://www.xiaohongshu.com/explore/<id>)

        Returns:
            VideoInfo 或 None（如果提取失败）
        """
        # 提取 note_id
        match = re.search(r'/explore/([a-f0-9]+)', url)
        if not match:
            print(f"❌ 无效的小红书 URL: {url}")
            return None

        note_id = match.group(1)

        try:
            # 下载网页
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                headers = {
                    "User-Agent": self.user_agent,
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                }
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                webpage = response.text

            # 提取 window.__INITIAL_STATE__
            initial_state = self._extract_initial_state(webpage)
            if not initial_state:
                print(f"❌ 无法提取 __INITIAL_STATE__: {note_id}")
                return None

            # 提取笔记信息
            note_info = (
                initial_state.get("note", {})
                .get("noteDetailMap", {})
                .get(note_id, {})
                .get("note")
            ) or {}

            if not note_info:
                print(f"❌ 笔记信息为空: {note_id}")
                return None

            # 提取视频流
            streams = (
                note_info.get("video", {})
                .get("media", {})
                .get("stream", {})
            ) or {}

            # 优先使用 h264
            video_url = None
            video_meta = {}

            for codec_key in ("h264", "av1", "h265"):
                codec_data = streams.get(codec_key)
                if not codec_data:
                    continue

                # 处理列表
                if isinstance(codec_data, list) and len(codec_data) > 0:
                    video_meta = codec_data[0]
                    video_url = video_meta.get("mediaUrl") or video_meta.get("masterUrl")
                    if video_url:
                        break

                # 处理字典
                elif isinstance(codec_data, dict):
                    # 有时是 {quality: [videos]}
                    for quality_videos in codec_data.values():
                        if isinstance(quality_videos, list) and len(quality_videos) > 0:
                            video_meta = quality_videos[0]
                            video_url = video_meta.get("mediaUrl") or video_meta.get("masterUrl")
                            if video_url:
                                break
                    if video_url:
                        break

            if not video_url:
                print(f"⚠️  未找到视频 URL: {note_id}")
                return None

            # 提取标题
            title = note_info.get("title", "") or note_info.get("desc", "")[:50] or f"video_{note_id}"

            # 创建 VideoInfo
            return VideoInfo(
                note_id=note_id,
                title=title,
                video_url=video_url,
                filesize=video_meta.get("size"),
                duration=video_meta.get("duration", 0) / 1000.0 if video_meta.get("duration") else None,
                width=video_meta.get("width"),
                height=video_meta.get("height"),
            )

        except Exception as e:
            print(f"❌ 提取视频信息失败: {e}")
            return None

    def _extract_initial_state(self, webpage: str) -> Optional[Dict[str, Any]]:
        """
        从网页中提取 window.__INITIAL_STATE__

        Args:
            webpage: 网页 HTML

        Returns:
            初始状态字典或 None
        """
        # 查找 window.__INITIAL_STATE__ = {...}
        match = re.search(r'window\.__INITIAL_STATE__\s*=\s*(\{.+?\})\s*</script>', webpage, re.DOTALL)
        if not match:
            return None

        js_obj = match.group(1)

        # 清理 JS 对象
        # 替换 undefined -> null
        js_obj = re.sub(r'\bundefined\b', 'null', js_obj)

        # 尝试解析 JSON
        try:
            return json.loads(js_obj)
        except json.JSONDecodeError:
            # 如果失败，尝试简单的 JS 到 JSON 转换
            # 这里只处理基本情况，复杂的可能需要更强的解析器
            try:
                # 去除注释
                js_obj = re.sub(r'//[^\n]*', '', js_obj)
                js_obj = re.sub(r'/\*.*?\*/', '', js_obj, flags=re.DOTALL)
                return json.loads(js_obj)
            except Exception:
                return None

    async def download_video(self, video_info: VideoInfo) -> bool:
        """
        下载视频到本地

        Args:
            video_info: 视频信息

        Returns:
            bool: 下载是否成功
        """
        try:
            # 文件名: {note_id}.mp4
            filename = f"{video_info.note_id}.mp4"
            filepath = self.save_dir / filename

            # 如果文件已存在，跳过
            if filepath.exists():
                print(f"⏭️  视频已存在，跳过下载: {filename}")
                video_info.local_path = str(filepath)
                return True

            print(f"📥 开始下载视频: {filename}")
            print(f"   URL: {video_info.video_url[:60]}...")

            # 下载视频
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                headers = {
                    "User-Agent": self.user_agent,
                    "Referer": "https://www.xiaohongshu.com",
                }

                async with client.stream("GET", video_info.video_url, headers=headers) as response:
                    response.raise_for_status()

                    # 获取文件大小
                    total_size = int(response.headers.get("content-length", 0))
                    downloaded_size = 0

                    # 写入文件
                    with open(filepath, "wb") as f:
                        async for chunk in response.aiter_bytes(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                                downloaded_size += len(chunk)

                                # 打印进度（每 1MB 打印一次）
                                if downloaded_size % (1024 * 1024) < 8192:
                                    progress = downloaded_size / total_size * 100 if total_size > 0 else 0
                                    print(f"   进度: {downloaded_size / 1024 / 1024:.1f}MB / {total_size / 1024 / 1024:.1f}MB ({progress:.1f}%)")

            print(f"✅ 下载完成: {filename} ({downloaded_size / 1024 / 1024:.2f}MB)")
            video_info.local_path = str(filepath)
            return True

        except Exception as e:
            print(f"❌ 下载失败: {e}")
            # 删除不完整的文件
            if filepath.exists():
                filepath.unlink()
            return False

    async def extract_and_download(self, url: str) -> Optional[Dict[str, Any]]:
        """
        提取视频信息并下载

        Args:
            url: 小红书笔记 URL

        Returns:
            Dict: 包含视频 URL 和本地路径的字典，失败返回 None
        """
        # 提取视频信息
        video_info = await self.extract_video_info_from_url(url)
        if not video_info:
            return None

        # 下载视频
        success = await self.download_video(video_info)
        if not success:
            return None

        # 返回结果
        return {
            "note_id": video_info.note_id,
            "title": video_info.title,
            "video_url": video_info.video_url,
            "local_path": video_info.local_path,
            "filesize": video_info.filesize,
            "duration": video_info.duration,
            "width": video_info.width,
            "height": video_info.height,
        }


# === 便捷函数 ===

async def download_video_from_url(url: str, save_dir: str = "videos") -> Optional[Dict[str, Any]]:
    """
    便捷函数：从 URL 下载视频

    Args:
        url: 小红书笔记 URL
        save_dir: 保存目录

    Returns:
        Dict: 包含视频信息的字典，失败返回 None

    Example:
        result = await download_video_from_url("https://www.xiaohongshu.com/explore/6975f858...")
        if result:
            print(f"视频已下载到: {result['local_path']}")
    """
    downloader = VideoDownloader(save_dir=save_dir)
    return await downloader.extract_and_download(url)


# === 测试代码 ===

async def test_download():
    """测试下载功能"""
    test_url = "https://www.xiaohongshu.com/explore/6975f85800000000220088d7"

    print("=" * 60)
    print("测试视频下载功能")
    print("=" * 60)

    result = await download_video_from_url(test_url)

    if result:
        print("\n下载结果:")
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("\n下载失败")


if __name__ == "__main__":
    asyncio.run(test_download())
