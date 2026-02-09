# 项目指南：SiliconMomo - 小红书自动化运营系统

欢迎来到 SiliconMomo 项目！这是一个强大且智能的自动化运营系统，旨在帮助您高效管理小红书账号。无论您是技术新手还是经验丰富的开发者，本指南都将带您了解项目的核心功能、如何运行、以及各部分如何协同工作。

## 目录
1.  [项目概述](#1-项目概述)
2.  [核心功能](#2-核心功能)
3.  [环境搭建与安装](#3-环境搭建与安装)
    *   [3.1. 依赖安装](#31-依赖安装)
    *   [3.2. 浏览器配置](#32-浏览器配置)
    *   [3.3. FFmpeg 安装](#33-ffmpeg-安装)
    *   [3.4. AI 服务配置](#34-ai-服务配置)
    *   [3.5. 配置文件设置](#35-配置文件设置)
4.  [如何运行](#4-如何运行)
    *   [4.1. 启动 Chrome 浏览器](#41-启动-chrome-浏览器)
    *   [4.2. 运行主应用程序](#42-运行主应用程序)
    *   [4.3. 运行内容创作模块](#43-运行内容创作模块)
    *   [4.4. 运行音频转录服务器](#44-运行音频转录服务器)
5.  [核心组件详解](#5-核心组件详解)
    *   [5.1. 核心自动化 (`core/`)](#51-核心自动化-core)
    *   [5.2. 行为模块 (`actions/`)](#52-行为模块-actions)
    *   [5.3. 服务器模块 (`server/`)](#53-服务器模块-server)
6.  [整体工作流程](#6-整体工作流程)
7.  [给新手的建议](#7-给新手的建议)

---

## 1. 项目概述

SiliconMomo 是一个专为小红书平台设计的自动化内容生产和运营系统。它模拟人类行为，通过浏览、学习、创作、发布等一系列操作，实现账号的智能化增长。项目主要分为两个核心部分：

*   **核心自动化应用**：负责模拟浏览器行为，执行内容抓取、分析、创作和发布等任务。
*   **音频转录微服务**：一个独立的 FastAPI 服务，提供高效的音频到文本转录功能，支持核心应用或其他外部服务使用。

本项目旨在通过数据驱动和智能决策，优化内容策略，提升运营效率。

## 2. 核心功能

*   **AI 驱动的内容创作**：结合大语言模型 (LLM) 和 AI 绘画工具，自动生成图文内容草稿。
*   **小红书智能互动**：模拟用户浏览、点赞、收藏、评论等行为，学习热门趋势和内容灵感。
*   **数据驱动的内容策略**：通过趋势分析和内容规划，优化发布时间、主题和关键词。
*   **半自动化发布**：自动填写发布内容，但在最终发布前提供人工审核确认，确保内容质量和安全。
*   **智能错误恢复**：内置恢复机制，应对浏览器异常或网络波动，提高系统稳定性。
*   **独立音频转录服务**：利用 `whisper.cpp` 提供高性能的音频转文本 API。

## 3. 环境搭建与安装

在运行项目之前，您需要配置好相应的环境。

### 3.1. 依赖安装

项目使用 Python 编写，并依赖特定的库。

1.  **主应用程序依赖**:
    ```bash
    pip install -r requirements.txt
    ```
    主要依赖包括 `playwright` (用于浏览器自动化) 和 `zai` (用于大语言模型接口)。

2.  **音频转录服务器依赖**:
    ```bash
    pip install -r server/requirements.txt
    ```
    主要依赖包括 `fastapi` (构建 API 服务) 和 `uvicorn` (ASGI 服务器)，以及 `ffmpeg-python` (处理音频)。

### 3.2. 浏览器配置

本项目依赖于 Chrome 浏览器进行自动化操作。

1.  **安装 Playwright 浏览器驱动**:
    ```bash
    playwright install
    ```
    这会安装 Playwright 驱动所需的所有浏览器（包括 Chromium）。

2.  **启动带有远程调试的 Chrome**:
    主应用程序需要连接到一个开启了远程调试端口的 Chrome 浏览器实例。您可以使用项目提供的脚本来启动：
    ```bash
    ./cmmand.sh
    # 或者
    ./start_chrome.sh
    ```
    这两个脚本都会以 `--remote-debugging-port=9222` 参数启动 Chrome，并使用一个独立的 `user-data-dir` (`$HOME/chrome_debug_profile`)，避免与您日常使用的 Chrome 配置文件冲突。**请确保在运行主应用程序之前，此 Chrome 实例已经启动并保持运行。**

### 3.3. FFmpeg 安装

音频转录服务器需要 FFmpeg 来处理音频文件。

*   **macOS**:
    ```bash
    brew install ffmpeg
    ```
*   **Linux (Debian/Ubuntu)**:
    ```bash
    sudo apt update
    sudo apt install ffmpeg
    ```
*   **Windows**: 请访问 [FFmpeg 官网](https://ffmpeg.org/download.html) 下载并按照说明安装，确保 `ffmpeg` 命令可以在命令行中运行。

### 3.4. AI 服务配置

项目使用 **智谱 AI** 作为大语言模型服务。

1.  **获取 API Key**: 访问 [智谱 AI 开放平台](https://open.bigmodel.cn/) 注册账号并获取您的 API Key。
2.  **配置 Key**: 在 `config/settings.example.py` 文件中找到 `ZHIPU_AI_KEY` 变量，将其替换为您的真实 Key。建议将 `config/settings.example.py` 复制一份并重命名为 `config/settings.py` 进行修改，以避免版本控制冲突。

### 3.5. 配置文件设置

项目通过 `config/settings.py` 管理大部分配置。

1.  **复制配置文件**: 将 `config/settings.example.py` 复制一份并重命名为 `config/settings.py`。
    ```bash
    cp config/settings.example.py config/settings.py
    ```
2.  **修改配置**: 打开 `config/settings.py`，您可以根据自己的需求调整以下参数：
    *   `CDP_URL`: Chrome 远程调试地址，通常不需要修改。
    *   `BASE_URL`: 小红书的基础 URL。
    *   `ZHIPU_AI_KEY`: 您的智谱 AI API Key。
    *   `SEARCH_KEYWORDS`, `TARGET_TOPICS`: 调整搜索关键词和目标内容领域，以适应您的账号定位。
    *   `PUBLISH_HOURS`, `DAILY_PUBLISH_LIMIT`: 设置自动发帖的时间和数量上限。
    *   `PROB_TRIGGER_THINKING`, `PROB_POST_COMMENT` 等：调整拟人化互动概率，使模拟行为更符合预期。
    *   `JIMENG_GENERATE_URL`: AI 绘画工具的生成接口地址，通常不需要修改。
    *   `PUBLISH_SELECTORS`, `SELECTORS`: Playwright 选择器，除非小红书 DOM 结构大改，否则无需调整。

## 4. 如何运行

项目提供了多个入口点，用于不同的功能。

### 4.1. 启动 Chrome 浏览器

在运行任何自动化脚本之前，请确保按照 [3.2. 浏览器配置](#32-浏览器配置) 中的说明启动了 Chrome 浏览器。

```bash
./cmmand.sh &
# 或者
./start_chrome.sh &
```
添加 `&` 符号可以在后台运行脚本，这样您可以继续在终端中输入其他命令。

### 4.2. 运行主应用程序

这是整个自动化运营系统的核心入口。它将启动 `Supervisor` 来管理所有自动化任务。

```bash
python main.py
```
运行此命令后，系统将进入持续运营模式，自动执行浏览、学习、分析、创作（如果素材充足）等任务。

### 4.3. 运行内容创作模块

如果您只想手动触发一次内容创作流程，可以使用 `run_creation.py`。

```bash
python run_creation.py
```
此脚本会协调 `WriterAgent` (LLM 生成文本) 和 `ArtistAgent` (AI 绘画生成图片) 来创建一个内容草稿。

### 4.4. 运行音频转录服务器

这是一个独立的微服务，可以在后台运行，为需要音频转录的模块提供服务。

1.  **进入 `server` 目录**:
    ```bash
    cd server
    ```
2.  **启动服务器**:
    ```bash
    uvicorn server:app --host 0.0.0.0 --port 8000
    # 或者在后台运行
    uvicorn server:app --host 0.0.0.0 --port 8000 &
    ```
    服务器将在 `http://localhost:8000` 上监听请求。您可以通过访问 `http://localhost:8000/docs` 查看 API 文档。
    **注意**：此服务器需要 `whisper.cpp` 编译后的可执行文件。项目结构中 `server/whisper.cpp` 已经包含了一个 `whisper.cpp` 的子模块，您可能需要根据其文档进行编译。

## 5. 核心组件详解

### 5.1. 核心自动化 (`core/`)

这个目录包含了项目大部分的智能和自动化逻辑。

*   **`supervisor.py`**: **系统的“大脑”**。它是一个中央调度器，运行主循环，负责协调各种代理 (Agent) 的工作，如决定何时浏览、何时创作、何时分析数据。
*   **`browser_manager.py`**: 管理与 Chrome 浏览器的连接和基本操作，如页面导航、等待元素等。
*   **`dom_helper.py`**: 提供一系列工具函数，用于更高级的 DOM 元素查找和交互，例如点击特定按钮、填写表单等。
*   **`llm_client.py`**: 封装了与大语言模型 (智谱 AI) 的交互逻辑，用于文本生成、分析和评论。
*   **`knowledge_base.py`**: （待详细分析）可能用于存储和管理从小红书抓取到的内容灵感、用户数据等。
*   **`content_cleaner.py`**: 用于处理和清洗从网页抓取到的内容，确保数据质量。
*   **`content_strategy.py`**: 根据预设策略和当前数据，制定内容创作和发布的计划。
*   **`artist.py`**: 封装了与 AI 绘画工具（如 Jimeng）的交互，根据文本描述生成图片。
*   **`writer.py`**: 负责利用 LLM 生成图文内容的文字部分。
*   **`publisher.py`**: 处理将创作好的内容发布到小红书的自动化流程。
*   **`human_motion.py` & `smart_interact.py`**: 实现了模拟人类鼠标移动、点击、滚动等行为，使自动化操作更加自然，减少被平台检测的风险。
*   **`recovery.py`**: 负责处理自动化过程中可能出现的错误和异常，尝试恢复系统到正常状态。
*   **`analytics.py`**: （待详细分析）可能用于收集和分析运营数据。
*   **`product_manager.py`**: （待详细分析）可能用于管理产品信息或推广内容。
*   **`title_optimizer.py`**: （待详细分析）可能用于优化内容标题。
*   **`trend_tracker.py`**: 负责追踪小红书或其他平台的热门趋势，为内容创作提供灵感。
*   **`video_downloader.py`**: （待详细分析）可能用于下载视频内容。
*   **`viral_analyzer.py`**: （待详细分析）可能用于分析内容的传播性。
*   **`xhs_api_client.py`**: （待详细分析）可能用于与小红书非官方 API 交互。

### 5.2. 行为模块 (`actions/`)

这个目录定义了系统可以执行的具体操作。

*   **`interaction.py`**: 包含模拟用户在小红书上进行各种互动（如浏览帖子、点赞、收藏、评论）的逻辑。
*   **`publisher.py`**: 包含将草稿发布到小红书的详细步骤。

### 5.3. 服务器模块 (`server/`)

这个独立的 Python 包提供了一个音频转录微服务。

*   **`server.py`**: FastAPI 应用程序的入口，定义了 `/transcribe` API 端点，接收音频文件并返回转录文本。
*   **`transcriber.py`**: 核心转录逻辑，负责将音频文件处理后，调用 `whisper.cpp` 可执行文件进行转录。
*   **`utils/audio_converter.py`**: 辅助工具，用于将各种音频格式转换为 `whisper.cpp` 支持的 WAV 格式。
*   **`utils/file_manager.py`**: 辅助工具，用于管理服务器接收和处理的临时文件。
*   **`whisper.cpp/`**: 包含 `whisper.cpp` 的源代码。您需要根据其文档自行编译以生成可执行文件。

## 6. 整体工作流程

SiliconMomo 的核心工作流程由 `core/supervisor.py` 驱动，大致遵循以下循环：

1.  **感知 (Perception)**:
    *   通过 `ActionExecutor` (在 `main.py` 中初始化) 模拟浏览器访问小红书，根据 `config/settings.py` 中的 `SEARCH_KEYWORDS` 和 `TARGET_TOPICS` 搜索相关内容。
    *   浏览帖子，收集灵感和数据到 `knowledge_base.py`。
    *   `trend_tracker.py` 持续监控热门趋势。

2.  **分析与策略 (Analysis & Strategy)**:
    *   `content_strategy.py` 根据收集到的数据和预设规则，判断何时进行创作、创作什么主题。
    *   `analytics.py` 和 `viral_analyzer.py` 提供数据支持，优化决策。
    *   `title_optimizer.py` 辅助生成更具吸引力的标题。

3.  **创作 (Creation)**:
    *   当满足 `INSPIRATION_THRESHOLD` (足够多的灵感素材) 时，`Supervisor` 会触发创作流程。
    *   `writer.py` 利用 `llm_client.py` (智谱 AI) 根据灵感素材生成内容文案。
    *   `artist.py` 调用外部 AI 绘画服务 (如 Jimeng) 根据文案生成配图。
    *   生成的图文草稿存储在 `data/drafts.json`。

4.  **发布 (Publishing)**:
    *   `Supervisor` 根据 `PUBLISH_HOURS` 调度发布任务。
    *   `publisher.py` 自动化登录小红书创作者平台，上传图片，填写标题和正文。
    *   **关键安全步骤**：在最终点击“发布”按钮前，系统会暂停，等待人工审核和确认。这确保了发布内容的质量和合规性。

5.  **互动与学习 (Interaction & Learning)**:
    *   在浏览过程中，系统会根据 `PROB_LIKE`, `PROB_COLLECT`, `PROB_COMMENT` 等拟人化概率，执行点赞、收藏、评论等互动行为。
    *   这些互动不仅增加了账号活跃度，也为后续的内容策略提供反馈。
    *   `recovery.py` 在整个过程中监控并处理异常。

## 7. 给新手的建议

*   **从 `main.py` 开始**：这是项目的核心入口，运行它可以看到整个系统的运作。
*   **理解配置文件 `config/settings.py`**：这是您定制系统行为的关键。尝试修改搜索关键词、发布时间等，观察效果。
*   **注意浏览器状态**：确保 Chrome 浏览器以正确的方式启动 (`./cmmand.sh`)，并且在系统运行时不要关闭它。
*   **逐步调试**：如果遇到问题，可以尝试在 `main.py` 或 `run_creation.py` 中设置断点，单步调试来理解流程。
*   **查阅 `Playwright` 文档**：如果想修改或增加浏览器自动化逻辑，熟悉 `Playwright` 是非常有帮助的。
*   **查看日志**：`logs/` 目录会记录系统的运行日志，是排查问题的重要依据。
*   **安全第一**：由于本项目涉及自动化操作社交媒体平台，请务必遵守平台的使用条款，并谨慎使用自动发布功能。人工审核是必不可少的环节。
*   **探索 `core/` 目录**：`core/supervisor.py` 和 `core/publisher.py` 是理解项目核心逻辑的重要文件。

希望这份指南能帮助您快速上手 SiliconMomo 项目！祝您使用愉快！
