# SiliconMomo 快速测试指南

## 🚀 三步启动

### 1. 安装依赖
```bash
pip install -r requirements.txt
playwright install chromium
```

### 2. 启动Chrome（CDP模式）
```bash
# 方式1：使用脚本（推荐）
./start_chrome.sh

# 方式2：手动启动
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --remote-debugging-port=9222 \
  --user-data-dir="/tmp/chrome-debug"
```

### 3. 登录小红书
- 在启动的Chrome浏览器中，访问 `https://www.xiaohongshu.com`
- **手动登录**你的小红书账号
- 确保登录状态正常

### 4. 运行程序
```bash
python main.py
```

---

## ⚙️ 测试配置建议

### 快速测试（5分钟）
编辑 `config/settings.py`：
```python
RUN_DURATION = 300  # 5分钟
INSPIRATION_THRESHOLD = 2  # 降低阈值，更快触发
```

### 功能测试（30分钟）
```python
RUN_DURATION = 1800  # 30分钟
INSPIRATION_THRESHOLD = 2
```

### 完整测试（24小时）
```python
RUN_DURATION = 86400  # 24小时（默认）
INSPIRATION_THRESHOLD = 3  # 默认
```

---

## 📊 观察要点

### 控制台输出
- ✅ `👨‍✈️ [车间主任] 24小时运营启动` - 启动成功
- ✅ `🔄 [轮转] 切换关键词: 发疯文学` - 搜索正常
- ✅ `💾 [知识库] +1 新素材` - 记录素材正常
- ✅ `🎨 [创作流程] 开始创作+发帖流程` - 触发创作
- ✅ `📤 [发布员] 开始发布` - 发布流程

### 数据文件
- `data/inspiration.json` - 素材库（检查是否有新素材）
- `data/drafts.json` - 草稿库（检查是否有新草稿）
- `assets/images/` - 生成的图片

---

## 🐛 常见问题

### 连接失败
- 检查Chrome是否以CDP模式启动
- 检查端口9222是否被占用

### 未登录
- 在Chrome浏览器中手动登录小红书
- 重新运行程序

### LLM调用失败
- 检查 `ZHIPU_AI_KEY` 是否正确
- 检查网络连接

---

## 📚 详细文档

- 完整测试指南：`docs/测试运行指南.md`
- 开发规划：`docs/开发规划_转向迭代_v2.md`
- 完成总结：`docs/迭代开发完成总结.md`

---

**开始测试吧！** 🎉
