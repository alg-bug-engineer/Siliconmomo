# 音频转录服务设计文档

**日期**: 2026-02-07
**状态**: 已确认

## 概述

开发一个基于 ffmpeg + whisper.cpp 的音频转录服务，支持纯 CPU 环境，使用 small 规模模型。服务既可独立运行，也可集成到 SiliconMomo 项目中用于小红书视频内容分析。

## 目标

- 提供 HTTP REST API 接收音频文件，返回转录文本
- 支持任意音频/视频格式自动转换
- 纯 CPU 环境运行，使用 whisper small 模型
- 提供 Python 客户端 SDK
- 易于部署和集成

## 技术栈

- **服务端框架**: FastAPI（异步、自动文档、类型验证）
- **音频转换**: ffmpeg + ffmpeg-python
- **转录引擎**: whisper.cpp（通过 subprocess 调用）
- **通信协议**: HTTP REST API
- **文件上传**: multipart/form-data
- **模型**: ggml-small.bin (~500MB)

## 目录结构

```
server/
├── README.md              # 安装和使用文档
├── requirements.txt       # Python 依赖
├── config.py             # 配置文件
├── server.py             # FastAPI 服务端
├── client.py             # Python 客户端示例
├── transcriber.py        # 转录核心逻辑
├── utils/
│   ├── audio_converter.py  # ffmpeg 音频转换
│   └── file_manager.py     # 临时文件管理
├── models/               # whisper 模型存放目录（gitignore）
│   └── .gitkeep
├── whisper.cpp/          # whisper.cpp 源码和编译产物（gitignore）
└── test_data/            # 测试音频文件
    └── sample.mp3
```

## API 设计

### 1. POST /transcribe

转录音频文件

**请求**:
- Content-Type: multipart/form-data
- 参数:
  - `file`: 音频/视频文件（必需）
  - `language`: 语言代码，如 "zh", "en"（可选，默认 auto）
  - `task`: "transcribe" 或 "translate"（可选，默认 transcribe）

**响应**:
```json
{
  "text": "转录的完整文本",
  "language": "zh",
  "duration": 125.6,
  "processing_time": 8.3
}
```

**错误响应**:
- 400: 文件格式错误、文件损坏
- 413: 文件过大
- 500: 转换或转录失败
- 503: 服务未就绪（模型未加载）
- 504: 转录超时

### 2. GET /health

健康检查

**响应**:
```json
{
  "status": "healthy",
  "whisper_ready": true,
  "model_loaded": true
}
```

### 3. GET /info

服务信息

**响应**:
```json
{
  "model": "small",
  "whisper_version": "1.5.4",
  "supported_languages": ["zh", "en", "ja", ...],
  "max_file_size_mb": 100
}
```

## 核心组件

### 1. transcriber.py - 转录核心

```python
class WhisperTranscriber:
    def __init__(self, model_path, whisper_cpp_path):
        """初始化转录器，验证路径"""

    def transcribe(self, audio_path, language="auto"):
        """
        调用 whisper.cpp 进行转录
        命令: ./main -m model.bin -f audio.wav -l zh
        解析输出文本并返回结果
        """
```

### 2. audio_converter.py - 音频转换

```python
class AudioConverter:
    @staticmethod
    def convert_to_wav(input_path, output_path):
        """
        使用 ffmpeg 转换音频
        - 转换为 16kHz 采样率
        - 单声道
        - 16-bit PCM WAV 格式
        - 支持视频文件（自动提取音频轨）
        命令: ffmpeg -i input -ar 16000 -ac 1 -c:a pcm_s16le output.wav
        """
```

### 3. file_manager.py - 临时文件管理

```python
class TempFileManager:
    """
    - 生成唯一临时文件名（UUID）
    - 上下文管理器自动清理
    - 定期清理过期文件（>1小时）
    """
```

### 4. server.py - FastAPI 服务

- 异步处理请求
- 文件大小限制（默认 100MB）
- 错误处理和日志记录
- CORS 支持（可选）
- Prometheus metrics（可选）

### 5. client.py - Python 客户端

```python
class TranscriptionClient:
    def __init__(self, base_url="http://localhost:8000"):
        """初始化客户端"""

    def transcribe(self, file_path, language=None):
        """同步转录"""

    async def transcribe_async(self, file_path, language=None):
        """异步转录"""
```

## 配置项

在 `config.py` 中定义：

```python
# whisper.cpp 配置
WHISPER_CPP_PATH = "./whisper.cpp/main"
MODEL_PATH = "./whisper.cpp/models/ggml-small.bin"

# 服务配置
HOST = "0.0.0.0"
PORT = 8000
MAX_FILE_SIZE_MB = 100

# 临时文件
TEMP_DIR = "./temp"
TEMP_FILE_EXPIRE_HOURS = 1

# 日志
LOG_LEVEL = "INFO"
LOG_FILE = "./logs/transcription.log"
```

支持环境变量覆盖配置。

## 处理流程

1. **接收请求**: FastAPI 接收文件上传
2. **保存临时文件**: 使用 UUID 生成唯一文件名
3. **格式检测**: 检查文件是否为有效媒体文件
4. **音频转换**: ffmpeg 转换为 16kHz WAV
5. **转录**: 调用 whisper.cpp 进行转录
6. **解析结果**: 提取文本和元数据
7. **返回响应**: JSON 格式返回
8. **清理文件**: 删除临时文件

## 错误处理

### 文件上传阶段
- 文件过大 → 413 Payload Too Large
- 无效文件类型 → 400 Bad Request
- 文件损坏 → 400 Bad Request

### 音频转换阶段
- ffmpeg 转换失败 → 500 Internal Server Error
- 无音频轨道 → 400 Bad Request

### 转录阶段
- whisper.cpp 进程失败 → 500 Internal Server Error
- 模型文件丢失 → 503 Service Unavailable
- 转录超时 → 504 Gateway Timeout

### 资源管理
- 磁盘空间不足 → 507 Insufficient Storage
- 使用 try-finally 确保临时文件清理

## 日志设计

使用 Python logging 模块：

- **级别**: INFO（正常）、ERROR（失败）、DEBUG（调试）
- **内容**: 请求 ID、文件大小、处理时长、转录字数
- **轮转**: 按天轮转日志文件
- **格式**: `[时间] [级别] [请求ID] 消息`

每个请求记录：
- 上传耗时
- 转换耗时
- 转录耗时
- 总耗时

## 安装部署

### 系统依赖

```bash
# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt-get install ffmpeg
```

### whisper.cpp 编译

```bash
cd server
git clone https://github.com/ggerganov/whisper.cpp
cd whisper.cpp
make
bash ./models/download-ggml-model.sh small
cd ..
```

### Python 依赖

```bash
pip install -r requirements.txt
# 包含: fastapi, uvicorn, python-multipart, ffmpeg-python
```

### 配置

编辑 `config.py` 或设置环境变量：
```bash
export WHISPER_CPP_PATH="./whisper.cpp/main"
export MODEL_PATH="./whisper.cpp/models/ggml-small.bin"
```

### 启动服务

```bash
# 开发环境
python server.py

# 生产环境
uvicorn server:app --host 0.0.0.0 --port 8000 --workers 4
```

## 集成到 SiliconMomo

在当前项目中使用：

```python
# core/transcription_client.py
from server.client import TranscriptionClient

class VideoTranscriber:
    def __init__(self):
        self.client = TranscriptionClient("http://localhost:8000")

    async def transcribe_video(self, video_path):
        """小红书视频转文字"""
        result = await self.client.transcribe_async(video_path, language="zh")
        return result['text']
```

## 性能考虑

### CPU 优化
- whisper.cpp 已针对 CPU 优化（支持 AVX2）
- small 模型平衡速度和准确度
- 约 1 分钟音频需要 5-10 秒处理（取决于 CPU）

### 并发控制
- 限制同时转录数量（避免 CPU 过载）
- 使用异步队列处理请求
- 可配置最大并发数

### 磁盘管理
- 定期清理过期临时文件
- 监控磁盘空间
- 临时文件使用 UUID 避免冲突

## 测试策略

### 单元测试
- `test_audio_converter.py`: 测试格式转换
- `test_file_manager.py`: 测试文件管理
- `test_transcriber.py`: 测试转录逻辑（使用测试音频）

### 集成测试
- 完整 API 测试（上传 → 转录 → 返回）
- 错误场景测试（无效文件、超大文件等）

### 性能测试
- 不同长度音频的处理时间
- 并发请求测试
- 资源使用监控

### 测试数据
在 `server/test_data/` 提供：
- 短音频（10秒）
- 中等音频（1分钟）
- 长音频（5分钟）
- 视频文件（mp4）
- 各种格式（mp3, m4a, wav, flac）

## 生产环境建议

1. **反向代理**: Nginx 处理静态文件和负载均衡
2. **进程管理**: systemd 或 supervisor 管理服务
3. **监控**: Prometheus + Grafana 监控性能
4. **日志**: 集中日志收集（如 ELK）
5. **限流**: 防止滥用（rate limiting）
6. **认证**: API key 或 JWT 认证（如需要）

## 未来扩展

- 支持更大模型（medium, large）
- 流式转录（WebSocket）
- GPU 加速支持
- 多语言翻译
- 说话人识别（diarization）
- 时间戳对齐
- Docker 容器化部署

## 文档清单

- `server/README.md`: 快速开始、安装、使用
- API 文档: FastAPI 自动生成（/docs）
- 故障排查指南
- 性能调优建议
