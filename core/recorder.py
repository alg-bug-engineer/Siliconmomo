import os
import json
import logging
import time
from datetime import datetime
from pathlib import Path

class SessionRecorder:
    def __init__(self):
        # 1. 创建本次会话的专属目录
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_dir = Path(f"logs/session_{self.session_id}")
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # 2. 初始化统计数据
        self.stats = {
            "start_time": str(datetime.now()),
            "end_time": None,
            "duration_seconds": 0,
            "notes_viewed": 0,    # 浏览帖子数
            "actions": {
                "like": 0,
                "collect": 0,
                "next_image": 0,
                "search": 0,
                "comment": 0
            },
            "comments_log": [], # <--- 新增：专门记录发过的评论
            "errors": []
        }

        # 3. 配置 Logger
        self.logger = self._setup_logger()
        self.logger.info(f"=== 会话启动: {self.session_id} ===")
        self.logger.info(f"日志目录: {self.log_dir.absolute()}")

    def _setup_logger(self):
        logger = logging.getLogger("SiliconMomo")
        logger.setLevel(logging.DEBUG)
        
        # 防止重复添加 handler
        if logger.handlers:
            return logger

        # 文件处理器
        file_handler = logging.FileHandler(self.log_dir / "run.log", encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter('%(asctime)s [%(levelname)s] [%(module)s] %(message)s')
        file_handler.setFormatter(file_formatter)

        # 控制台处理器 (保留彩色输出或标准输出)
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter('[%(levelname)s] %(message)s')
        console_handler.setFormatter(console_formatter)

        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        return logger

    def log(self, level, message):
        """通用日志接口"""
        if level.lower() == "info":
            self.logger.info(message)
        elif level.lower() == "debug":
            self.logger.debug(message)
        elif level.lower() == "warning":
            self.logger.warning(message)
        elif level.lower() == "error":
            self.logger.error(message)
    
    # 修改 record_action 方法，如果是评论，额外记录到 comments_log
    def record_action(self, action_type: str, details: str = ""):
        if action_type in self.stats["actions"]:
            self.stats["actions"][action_type] += 1
        elif action_type == "view_note":
            self.stats["notes_viewed"] += 1
        
        if action_type == "comment":
            self.stats["comments_log"].append({
                "time": str(datetime.now()),
                "content": details
            })
            
        self.logger.info(f"[ACTION] {action_type.upper()} | {details}")

    async def record_error(self, page, error_msg: str):
        """记录错误并截图"""
        timestamp = datetime.now().strftime("%H%M%S")
        screenshot_path = self.log_dir / f"error_{timestamp}.png"
        
        self.stats["errors"].append({
            "time": str(datetime.now()),
            "msg": str(error_msg),
            "screenshot": str(screenshot_path)
        })
        
        self.logger.error(f"[ERROR] {error_msg}")
        try:
            await page.screenshot(path=str(screenshot_path))
            self.logger.error(f"  └─ 现场截图已保存: {screenshot_path.name}")
        except Exception as e:
            self.logger.error(f"  └─ 截图失败: {e}")

    def save_report(self):
        """会话结束，保存 JSON 报告"""
        self.stats["end_time"] = str(datetime.now())
        start = datetime.fromisoformat(self.stats["start_time"])
        end = datetime.fromisoformat(self.stats["end_time"])
        self.stats["duration_seconds"] = (end - start).seconds

        report_path = self.log_dir / "report.json"
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(self.stats, f, indent=4, ensure_ascii=False)
        
        self.logger.info(f"=== 会话结束 ===")
        self.logger.info(f"统计报告已生成: {report_path.name}")
        self.logger.info(f"总浏览: {self.stats['notes_viewed']}, 点赞: {self.stats['actions']['like']}, 收藏: {self.stats['actions']['collect']}")