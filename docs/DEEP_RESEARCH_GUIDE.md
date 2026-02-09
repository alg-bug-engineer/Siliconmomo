# 深度调研模式指南：使用 `run_research.py`

本指南将详细介绍如何设置和运行 SiliconMomo 的深度调研模式。通过 `run_research.py`，您可以针对特定关键词在小红书上进行深入的数据收集、处理和分析，并生成详细的研究报告。

## 目录
1.  [概述](#1-概述)
2.  [前置环境搭建](#2-前置环境搭建)
    *   [2.1. Python 环境与依赖](#21-python-环境与依赖)
    *   [2.2. Chrome 浏览器设置](#22-chrome-浏览器设置)
    *   [2.3. FFmpeg 安装](#23-ffmpeg-安装)
3.  [服务配置](#3-服务配置)
    *   [3.1. 音频转录 (ASR) 服务器设置](#31-音频转录-asr-服务器设置)
    *   [3.2. AI 大模型服务配置](#32-ai-大模型服务配置)
4.  [深度调研模式特定配置](#4-深度调研模式特定配置)
    *   [4.1. 配置文件修改](#41-配置文件修改)
5.  [运行深度调研模式](#5-运行深度调研模式)
    *   [5.1. 启动 Chrome 浏览器](#51-启动-chrome-浏览器)
    *   [5.2. 启动 ASR 服务器](#52-启动-asr-服务器)
    *   [5.3. 执行 `run_research.py`](#53-执行-run_research.py)
6.  [输出结果](#6-输出结果)
7.  [注意事项](#7-注意事项)

---

## 1. 概述

深度调研模式是 SiliconMomo 项目提供的一项强大功能，它允许用户针对指定的小红书关键词进行以下操作：

*   **智能搜索与浏览**：模拟人类行为，搜索关键词并浏览相关帖子。
*   **内容全面抓取**：自动下载帖子中的图片、文字描述、视频以及所有可见评论（最多100条）。
*   **多媒体内容处理**：
    *   **视频 ASR 转录**：将下载的视频发送到本地 ASR（自动语音识别）服务器进行文本转录。
    *   **图片 OCR 识别**：预留 OCR 功能，未来可对图片进行文字识别。
*   **LLM 深度分析**：将抓取和处理后的所有数据（帖子URL、标题、正文、图片URL、视频URL、ASR转录文本、评论等）提交给大语言模型进行综合分析。
*   **生成结构化报告**：LLM 输出一份详细的深度研究报告和一份统计表格，报告包含趋势分析、内容偏好、用户情绪、内容策略建议等，并附带帖子溯源信息（URL）。
*   **数据本地存储**：所有抓取到的原始数据和生成的报告都会保存在本地指定目录。

## 2. 前置环境搭建

在使用深度调研模式之前，请确保您的系统已具备以下环境。

### 2.1. Python 环境与依赖

项目使用 Python 编写。

1.  **安装 Python**：确保您的系统安装了 Python 3.8 或更高版本。
2.  **安装项目依赖**：
    ```bash
    pip install -r requirements.txt
    pip install -r server/requirements.txt
    ```
    `requirements.txt` 包含主应用的依赖（如 Playwright、zai），`server/requirements.txt` 包含 ASR 服务器的依赖（如 FastAPI、uvicorn、httpx）。

### 2.2. Chrome 浏览器设置

深度调研模式需要通过 Chrome 浏览器进行自动化操作。

1.  **安装 Playwright 浏览器驱动**：
    ```bash
    playwright install
    ```
    这会安装 Playwright 驱动所需的所有浏览器（包括 Chromium）。

2.  **启动带有远程调试的 Chrome 实例**：
    您需要一个开启了远程调试端口的 Chrome 浏览器实例。请在**运行 `run_research.py` 之前**，在单独的终端中执行以下脚本来启动 Chrome：
    ```bash
    ./cmmand.sh &
    # 或者
    ./start_chrome.sh &
    ```
    这两个脚本都会以 `--remote-debugging-port=9222` 参数启动 Chrome，并使用独立的 `user-data-dir` (`$HOME/chrome_debug_profile`)，避免与您日常使用的 Chrome 配置冲突。请确保此 Chrome 实例保持运行。

### 2.3. FFmpeg 安装

音频转录服务器需要 FFmpeg 来处理视频文件，将其转换为 `whisper.cpp` 可处理的格式。

*   **macOS**:
    ```bash
    brew install ffmpeg
    ```
*   **Linux (Debian/Ubuntu)**:
    ```bash
    sudo apt update
    sudo apt install ffmpeg
    ```
*   **Windows**: 请访问 [FFmpeg 官网](https://ffmpeg.org/download.html) (https://ffmpeg.org/download.html) 下载并按照说明安装，确保 `ffmpeg` 命令可以在命令行中运行。

## 3. 服务配置

### 3.1. 音频转录 (ASR) 服务器设置

深度调研模式依赖于一个本地运行的 ASR 服务器来转录视频内容。

1.  **编译 `whisper.cpp`**：
    项目中的 `server/whisper.cpp` 是一个 Git 子模块，包含了 `whisper.cpp` 的源代码。您需要根据 `whisper.cpp` 官方文档或其 `README` 文件中的说明，在 `server/whisper.cpp` 目录下编译它，以生成可执行文件。通常，编译步骤可能包括：
    ```bash
    cd server/whisper.cpp
    # 根据你的系统和需求，可能需要安装依赖，然后执行：
    make # 或 cmake . && make
    # 编译成功后，确保 'whisper' 可执行文件在 server/whisper.cpp 目录下或系统的 PATH 中
    ```
    **注意**：`server/transcriber.py` 默认会尝试在 `server/whisper.cpp/main` 找到编译后的可执行文件，或者在 `server/whisper`。如果你的可执行文件路径不同，可能需要调整 `server/transcriber.py` 中的 `WHISPER_CPP_PATH` 变量。

2.  **启动 ASR 服务器**：
    在**运行 `run_research.py` 之前**，请在**另一个独立的终端中**启动 ASR 服务器：
    ```bash
    cd server
    uvicorn server:app --host 0.0.0.0 --port 8000 &
    ```
    服务器将在 `http://localhost:8000` 上监听请求。您可以访问 `http://localhost:8000/docs` 查看其 API 文档。

### 3.2. AI 大模型服务配置

深度调研模式使用大语言模型进行内容分析和报告生成。

1.  **获取智谱 AI Key**：
    访问 [智谱 AI 开放平台](https://open.bigmodel.cn/) (https://open.bigmodel.cn/) 注册账号并获取您的 API Key。

2.  **配置 AI Key 和 ASR 服务器 URL**：
    打开您的项目配置文件 `config/settings.py` (如果尚未创建，请复制 `config/settings.example.py` 为 `config/settings.py`)，并修改以下变量：
    ```python
    # config/settings.py

    # === 🧠 大模型配置 ===
    ZHIPU_AI_KEY = "your-zhipu-ai-key-here"  # <<<<<< 替换为你的智谱 AI Key
    LLM_MODEL = "glm-4.6"         # 默认的LLM模型
    ASR_SERVER_URL = "http://localhost:8000/transcribe" # <<<<<< 确认ASR服务器地址
    ```
    **注意**：`DEEP_RESEARCH_LLM_MODEL` 可以在深度调研模式中指定不同的模型 (例如 "kimi")，如果您的 `LLMClient` 实现了对其他模型的支持。目前默认仍会通过 `ZhipuAiClient` 发送请求。

## 4. 深度调研模式特定配置

您需要在配置文件中启用并调整深度调研模式的参数。

### 4.1. 配置文件修改

打开 `config/settings.py` (如果尚未创建，请复制 `config/settings.example.py` 为 `config/settings.py`)，并修改以下变量：

```python
# config/settings.py

# === 深度研究配置 ===
DEEP_RESEARCH_ENABLED = True # <<<<<< 必须设置为 True 以启用深度调研模式
DEEP_RESEARCH_POST_LIMIT = 20 # 深度研究模式下阅读的帖子数量 (默认20篇)
DEEP_RESEARCH_LLM_MODEL = "kimi" # 深度研究使用的LLM模型 (例如: kimi, gpt-4)。目前会通过 Zhipu AI 客户端发送请求，Kimi 兼容性待验证。
DEEP_RESEARCH_COMMENT_LIMIT = 100 # 每个帖子下载的评论数量上限 (默认100条)
DEEP_RESEARCH_OUTPUT_DIR = DATA_DIR / "deep_research_reports" # 深度研究报告输出目录
DEEP_RESEARCH_OUTPUT_DIR.mkdir(exist_ok=True) # 确保目录存在
```

## 5. 运行深度调研模式

在确保所有前置环境和服务都已设置并运行后，您可以启动深度调研模式。

### 5.1. 启动 Chrome 浏览器

如 [2.2 节](#22-chrome-浏览器设置) 所述，在独立的终端中运行：
```bash
./cmmand.sh &
```

### 5.2. 启动 ASR 服务器

如 [3.1 节](#31-音频转录-asr-服务器设置) 所述，在独立的终端中运行（进入 `server` 目录）：
```bash
cd server
uvicorn server:app --host 0.0.0.0 --port 8000 &
```

### 5.3. 执行 `run_research.py`

在项目根目录下执行 `run_research.py` 脚本，并提供一个您希望调研的关键词。

**示例：**
```bash
python run_research.py "2月龄宝宝推荐奶粉"
```
系统将开始根据关键词进行搜索、抓取、处理和分析，并生成报告。

## 6. 输出结果

深度调研模式运行完成后，所有的输出结果都将保存在 `DEEP_RESEARCH_OUTPUT_DIR` 指定的目录下（默认是 `data/deep_research_reports`）。

在该目录下，您会找到：

*   **原始数据 JSON 文件**：`research_data_您的关键词.json`，包含每个帖子的 URL、标题、正文、图片URL、视频URL、视频本地路径、ASR转录结果、评论等详细信息。
*   **深度研究报告 Markdown 文件**：`research_report_您的关键词.md`，这是由大语言模型生成的结构化报告，包含趋势分析、内容偏好、用户情绪、内容策略建议，以及一个 Markdown 格式的统计表格，所有内容都带有帖子溯源信息（URL）。
*   **下载的视频文件**：如果帖子包含视频，视频文件会保存在 `DEEP_RESEARCH_OUTPUT_DIR/videos` 子目录中。

## 7. 注意事项

*   **网络连接**：确保您的网络连接稳定，以便顺利抓取内容和调用 AI 服务。
*   **API Key 安全**：请勿将您的智谱 AI Key 直接提交到版本控制。建议使用环境变量或 `.env` 文件进行管理。
*   **小红书反爬机制**：频繁或异常的自动化行为可能会触发小红书的反爬机制，导致 IP 被封禁或账号受限。请谨慎使用，并遵守平台的使用条款。
*   **LLM 成本**：使用大语言模型会产生费用，请注意您的 API 余额。
*   **OCR (图片文字识别)**：目前图片 OCR 功能仅为占位符，尚未实现。如果需要，您需要在 `ResearchAgent` 中集成图片 OCR 服务。

希望这份详细指南能帮助您顺利使用深度调研模式！如有疑问，请查阅相关代码或联系开发人员。