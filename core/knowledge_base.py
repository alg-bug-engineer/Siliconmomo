import json
import re
import time
import random
from datetime import datetime
from pathlib import Path
from config.settings import INSPIRATION_FILE, INSPIRATION_THRESHOLD, KB_BUFFER_SIZE, KB_FLUSH_INTERVAL

class KnowledgeBase:
    def __init__(self, recorder):
        self.recorder = recorder
        self.file_path = INSPIRATION_FILE
        self._ensure_file()

        # 批量写入缓冲区
        self._buffer = []
        self._buffer_max_size = KB_BUFFER_SIZE
        self._flush_interval = KB_FLUSH_INTERVAL
        self._last_flush_time = time.time()

    def _ensure_file(self):
        """确保 JSON 文件存在且格式正确"""
        if not self.file_path.exists():
            self._save_data([])
        else:
            # 尝试读取一次，如果文件损坏则重置
            try:
                self._load_data()
            except Exception:
                self.recorder.log("warning", "📚 [知识库] 文件损坏或格式错误，已重置")
                self._save_data([])

    def _load_data(self):
        """读取 JSON"""
        with open(self.file_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _save_data(self, data):
        """写入 JSON"""
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

    def save_inspiration(self, title, content, analysis_result, source_url="",
                         image_urls=None, video_url="", video_local_path="", media_type="image", comments=None):
        """
        保存灵感素材（含图片、视频、评论）
        :param title: 帖子标题
        :param content: 帖子正文
        :param analysis_result: LLM 的分析结果
        :param source_url: 帖子链接
        :param image_urls: 配图URL列表
        :param video_url: 视频CDN链接（视频帖）
        :param video_local_path: 视频本地路径（已下载）
        :param media_type: 媒体类型 image/video
        :param comments: 评论列表 [{user, content, likes, sub_comments}]
        """
        try:
            data = self._load_data()

            # 从URL提取note_id用于精确去重
            note_id = ""
            url_match = re.search(r'/explore/([a-f0-9]+)', source_url)
            if url_match:
                note_id = url_match.group(1)

            # 查重（优先按note_id，其次按标题）
            for item in data:
                if (note_id and item.get("note_id") == note_id) or item["title"] == title:
                    self.recorder.log("info", "📚 [知识库] 素材已存在，跳过保存")
                    return

            new_record = {
                "id": str(int(time.time())),
                "note_id": note_id,
                "collected_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "source_type": "xhs_note",
                "title": title,
                "content": content,
                "url": source_url,
                # 媒体信息
                "media_type": media_type,
                "image_urls": image_urls or [],
                "video_url": video_url,
                "video_local_path": video_local_path,  # 视频本地路径
                # 评论数据
                "comments": comments or [],
                # LLM分析
                "ai_analysis": {
                    "is_relevant": analysis_result.get("is_relevant"),
                    "is_high_quality": analysis_result.get("is_high_quality", False),
                    "generated_comment": analysis_result.get("comment_text"),
                    "style_hint": analysis_result.get("style_hint", "")
                },
                "tags": [],
                "status": "unused"
            }

            # 添加到缓冲区（而非立即写入）
            self._buffer.append(new_record)

            # 日志：显示抓取到的媒体和评论数量
            img_count = len(image_urls or [])
            cmt_count = len(comments or [])
            media_info = f"视频" if media_type == "video" else f"图片x{img_count}"
            self.recorder.log("info",
                f"💾 [知识库-缓存] +1 新素材: {title[:15]}... | {media_info} | 评论x{cmt_count} (缓冲区:{len(self._buffer)})")

            # 检查是否需要刷新到磁盘
            if self._should_flush():
                self._flush_to_disk()

        except Exception as e:
            self.recorder.log("error", f"📚 [知识库] 保存失败: {e}")

    def get_unused_count(self):
        """获取未使用素材数量"""
        try:
            data = self._load_data()
            return len([item for item in data if item.get("status") == "unused"])
        except Exception:
            return 0

    def should_publish(self):
        """判断是否达到发帖阈值（已废弃，保留兼容性）"""
        return self.get_unused_count() >= INSPIRATION_THRESHOLD
    
    def should_create_content(self):
        """
        判断是否应该创作新内容
        基于高质量素材数量，而非所有素材数量
        """
        try:
            data = self._load_data()
            high_quality_count = len([
                item for item in data 
                if item.get("ai_analysis", {}).get("is_high_quality") 
                and item.get("status") == "unused"
            ])
            should_create = high_quality_count >= INSPIRATION_THRESHOLD
            if should_create:
                self.recorder.log("info", f"📚 [知识库] 高质量素材积累到 {high_quality_count} 条，触发创作")
            return should_create
        except Exception as e:
            self.recorder.log("error", f"📚 [知识库] 判断创作条件失败: {e}")
            return False

    def get_random_unused(self, count=1):
        """
        随机获取未使用的素材
        :param count: 获取数量
        :return: 素材列表
        """
        try:
            data = self._load_data()
            unused = [item for item in data if item.get("status") == "unused"]
            if not unused:
                return []
            return random.sample(unused, min(count, len(unused)))
        except Exception as e:
            self.recorder.log("error", f"📚 [知识库] 获取素材失败: {e}")
            return []

    def mark_as_used(self, item_id):
        """标记素材为已使用"""
        try:
            data = self._load_data()
            for item in data:
                if item.get("id") == item_id:
                    item["status"] = "used"
                    item["used_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    break
            self._save_data(data)
            self.recorder.log("info", f"📚 [知识库] 素材 {item_id} 已标记为已使用")
        except Exception as e:
            self.recorder.log("error", f"📚 [知识库] 标记失败: {e}")

    def mark_multiple_as_used(self, count=INSPIRATION_THRESHOLD):
        """
        批量标记多条高质量素材为已使用
        创作后调用，避免素材堆积
        :param count: 标记数量，默认为阈值数量
        :return: 实际标记的素材ID列表
        """
        try:
            data = self._load_data()

            # 筛选高质量未使用的素材
            high_quality_unused = [
                item for item in data
                if item.get("ai_analysis", {}).get("is_high_quality")
                and item.get("status") == "unused"
            ]

            if not high_quality_unused:
                self.recorder.log("info", "📚 [知识库] 没有可标记的高质量素材")
                return []

            # 随机选择指定数量
            to_mark = random.sample(high_quality_unused, min(count, len(high_quality_unused)))
            marked_ids = []

            for item in to_mark:
                item["status"] = "used"
                item["used_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                item["used_in_batch"] = True  # 标记为批量使用
                marked_ids.append(item.get("id"))

            self._save_data(data)
            self.recorder.log("info", f"📚 [知识库] 批量标记 {len(marked_ids)} 条素材为已使用")

            return marked_ids

        except Exception as e:
            self.recorder.log("error", f"📚 [知识库] 批量标记失败: {e}")
            return []

    def get_stats(self):
        """获取素材库统计信息"""
        try:
            data = self._load_data()
            total = len(data)
            unused = len([item for item in data if item.get("status") == "unused"])
            used = len([item for item in data if item.get("status") == "used"])
            high_quality_unused = len([
                item for item in data 
                if item.get("ai_analysis", {}).get("is_high_quality") 
                and item.get("status") == "unused"
            ])
            return {
                "total": total,
                "unused": unused,
                "used": used,
                "high_quality_unused": high_quality_unused,  # 新增：高质量未使用素材数
                "threshold": INSPIRATION_THRESHOLD,
                "ready_to_publish": unused >= INSPIRATION_THRESHOLD,
                "ready_to_create": high_quality_unused >= INSPIRATION_THRESHOLD  # 新增：是否可创作
            }
        except Exception:
            return {
                "total": 0,
                "unused": 0,
                "used": 0,
                "high_quality_unused": 0,
                "threshold": INSPIRATION_THRESHOLD,
                "ready_to_publish": False,
                "ready_to_create": False
            }

    def _should_flush(self):
        """判断是否应该刷新到磁盘"""
        return (
            len(self._buffer) >= self._buffer_max_size or
            time.time() - self._last_flush_time > self._flush_interval
        )

    def _flush_to_disk(self):
        """批量写入磁盘"""
        if not self._buffer:
            return

        try:
            # 读取现有数据
            data = self._load_data()

            # 批量追加缓冲区数据
            data.extend(self._buffer)

            # 写入磁盘
            self._save_data(data)

            count = len(self._buffer)
            self._buffer.clear()
            self._last_flush_time = time.time()

            self.recorder.log("info", f"💾 [知识库-写入] ✅ 已刷新 {count} 条到磁盘")

        except Exception as e:
            self.recorder.log("error", f"📚 [知识库] 刷新失败: {e}")

    def force_flush(self):
        """强制刷新缓冲区（程序退出时调用）"""
        if self._buffer:
            self.recorder.log("info", f"💾 [知识库-强制刷新] 缓冲区还有 {len(self._buffer)} 条待写入")
            self._flush_to_disk()
        else:
            self.recorder.log("info", "💾 [知识库-强制刷新] 缓冲区为空，无需刷新")