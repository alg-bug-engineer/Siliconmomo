import json
import time
import random
from datetime import datetime
from pathlib import Path
from config.settings import INSPIRATION_FILE, INSPIRATION_THRESHOLD

class KnowledgeBase:
    def __init__(self, recorder):
        self.recorder = recorder
        self.file_path = INSPIRATION_FILE
        self._ensure_file()

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

    def save_inspiration(self, title, content, analysis_result, source_url="", image_urls=None):
        """
        保存灵感素材
        :param title: 帖子标题
        :param content: 帖子正文
        :param analysis_result: LLM 的分析结果 (包含是否相关、评论内容等)
        :param source_url: 帖子链接 (可选)
        :param image_urls: 帖子配图URL列表 (可选)
        """
        try:
            data = self._load_data()
            
            # 查重 (避免重复存储同一个标题)
            for item in data:
                if item["title"] == title:
                    self.recorder.log("info", "📚 [知识库] 素材已存在，跳过保存")
                    return

            # 构造新的记录
            new_record = {
                "id": str(int(time.time())),
                "collected_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "source_type": "xhs_note",
                "title": title,
                "content": content,
                "url": source_url,
                "image_urls": image_urls or [],  # 保存配图URL用于风格分析
                # 存储 LLM 的思考结晶
                "ai_analysis": {
                    "is_relevant": analysis_result.get("is_relevant"),
                    "is_high_quality": analysis_result.get("is_high_quality", False),  # 是否高质量素材
                    "generated_comment": analysis_result.get("comment_text"),
                    "style_hint": analysis_result.get("style_hint", "")  # 风格提示
                },
                "tags": [], 
                "status": "unused"  # unused: 待使用, used: 已转化发帖
            }
            
            data.append(new_record)
            self._save_data(data)
            
            self.recorder.log("info", f"💾 [知识库] +1 新素材: {title[:15]}...")
            
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