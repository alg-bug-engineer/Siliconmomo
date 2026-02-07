# 音频转录服务

基于 ffmpeg 和 whisper.cpp 的音频转录服务，支持纯 CPU 环境运行。

## 功能特性

- ✅ HTTP REST API 接口
- ✅ 支持任意音频/视频格式（自动转换）
- ✅ 使用 whisper.cpp small 模型
- ✅ 纯 CPU 环境运行
- ✅ Python 客户端 SDK
- ✅ 自动清理临时文件
- ✅ 详细日志记录

## 快速开始

### 1. 安装系统依赖

**macOS:**
```bash
brew install ffmpeg
```

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install ffmpeg
```

### 2. 编译 whisper.cpp

```bash
cd server

# 克隆 whisper.cpp
git clone https://github.com/ggerganov/whisper.cpp
cd whisper.cpp

# 编译
make

# 下载 small 模型 (~500MB)
bash ./models/download-ggml-model.sh small

cd ..
```

### 3. 安装 Python 依赖

```bash
pip install -r requirements.txt
```

### 4. 配置（可选）

默认配置在 `config.py` 中，也可以通过环境变量覆盖：

```bash
export WHISPER_CPP_PATH="./whisper.cpp/main"
export MODEL_PATH="./whisper.cpp/models/ggml-small.bin"
export PORT=8000
export MAX_FILE_SIZE_MB=100
```

### 5. 启动服务

```bash
python server.py
```

服务将在 http://localhost:8000 启动。

访问 http://localhost:8000/docs 查看自动生成的 API 文档。

## 使用方法

### 方式 1: Python 客户端

```python
from client import TranscriptionClient

# 初始化客户端
client = TranscriptionClient("http://localhost:8000")

# 转录音频文件
result = client.transcribe("audio.mp3", language="zh")
print(result["text"])

# 异步版本
import asyncio

async def main():
    result = await client.transcribe_async("video.mp4", language="zh")
    print(result["text"])

asyncio.run(main())
```

### 方式 2: HTTP API

**转录音频：**
```bash
curl -X POST "http://localhost:8000/transcribe" \
  -F "file=@audio.mp3" \
  -F "language=zh"
```

**响应示例：**
```json
{
  "text": "这是转录的文本内容",
  "language": "zh",
  "duration": 125.6,
  "processing_time": 8.3
}
```

**健康检查：**
```bash
curl http://localhost:8000/health
```

**服务信息：**
```bash
curl http://localhost:8000/info
```

### 方式 3: 便捷函数

```python
from client import transcribe

text = transcribe("audio.mp3", language="zh")
print(text)
```

## API 参考

### POST /transcribe

转录音频/视频文件。

**参数：**
- `file` (必需): 音频或视频文件
- `language` (可选): 语言代码，如 "zh", "en"。不指定则自动检测
- `task` (可选): "transcribe" 或 "translate"，默认 "transcribe"

**响应：**
```json
{
  "text": "转录文本",
  "language": "zh",
  "duration": 125.6,
  "processing_time": 8.3
}
```

**支持的格式：**
- 音频: mp3, m4a, wav, flac, ogg, opus, aac
- 视频: mp4, avi, mov, mkv, webm（自动提取音频）

### GET /health

健康检查端点。

**响应：**
```json
{
  "status": "healthy",
  "whisper_ready": true,
  "model_loaded": true
}
```

### GET /info

获取服务信息。

**响应：**
```json
{
  "model": "small",
  "whisper_version": "1.5.4",
  "supported_languages": ["zh", "en", "ja", "ko", "es", "fr", "de", "auto"],
  "max_file_size_mb": 100
}
```

## 集成到其他项目

在 SiliconMomo 或其他项目中使用：

```python
# 在你的项目中
from server.client import TranscriptionClient

class VideoAnalyzer:
    def __init__(self):
        self.transcriber = TranscriptionClient("http://localhost:8000")

    async def analyze_video(self, video_path):
        # 提取视频文字
        result = await self.transcriber.transcribe_async(
            video_path,
            language="zh"
        )
        text = result["text"]

        # 进行进一步分析
        # ...
        return text
```

## 性能参考

基于 Intel i5-8250U (4核心) 的测试结果：

| 音频时长 | 处理时间 | 实时率 |
|---------|---------|--------|
| 30秒    | ~3秒    | 10x    |
| 1分钟   | ~6秒    | 10x    |
| 5分钟   | ~30秒   | 10x    |

*实时率 = 音频时长 / 处理时间，越高越好*

## 故障排查

### 1. whisper.cpp 编译失败

确保安装了 C++ 编译工具：
```bash
# macOS
xcode-select --install

# Ubuntu/Debian
sudo apt-get install build-essential
```

### 2. 模型下载失败

手动下载模型：
```bash
cd whisper.cpp/models
wget https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-small.bin
```

或使用国内镜像站。

### 3. ffmpeg 未找到

确保 ffmpeg 在 PATH 中：
```bash
which ffmpeg  # 应该输出路径
ffmpeg -version  # 应该显示版本信息
```

### 4. 转录超时

对于超长音频（>10分钟），可能需要增加超时时间：
```python
result = client.transcribe("long_audio.mp3", timeout=600)  # 10分钟
```

## 生产环境部署

### 使用 gunicorn + uvicorn workers

```bash
pip install gunicorn

gunicorn server:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --timeout 300
```

### 使用 Nginx 反向代理

```nginx
server {
    listen 80;
    server_name transcribe.example.com;

    client_max_body_size 100M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 300s;
    }
}
```

### 使用 systemd 服务

创建 `/etc/systemd/system/transcription.service`:

```ini
[Unit]
Description=Audio Transcription Service
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/path/to/server
Environment="PATH=/path/to/venv/bin"
ExecStart=/path/to/venv/bin/python server.py
Restart=always

[Install]
WantedBy=multi-user.target
```

启动服务：
```bash
sudo systemctl enable transcription
sudo systemctl start transcription
sudo systemctl status transcription
```

## 开发

### 运行测试

```bash
# 运行所有测试
pytest tests/ -v

# 运行特定测试
pytest tests/test_audio_converter.py -v

# 查看覆盖率
pytest --cov=. tests/
```

### 代码风格

```bash
# 格式化代码
black .

# 检查类型
mypy .
```

## 许可证

MIT License

## 致谢

- [whisper.cpp](https://github.com/ggerganov/whisper.cpp) - 高效的 Whisper 推理引擎
- [FFmpeg](https://ffmpeg.org/) - 强大的音视频处理工具
- [FastAPI](https://fastapi.tiangolo.com/) - 现代 Python Web 框架
