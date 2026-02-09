# 🚀 自动发布功能说明

## 功能介绍

新增自动发布功能，可以在内容填充完成后自动点击发布按钮，无需手动操作。

## 使用方法

### 1. 查看当前模式

```bash
Momo> auto
```

**输出示例：**
```
当前模式: ✅ 自动发布 (自动点击发布按钮)
```

### 2. 切换发布模式

```bash
# 切换到自动发布模式
Momo> auto on

# 切换到手动发布模式
Momo> auto off
```

### 3. 发布草稿

```bash
Momo> publish 1
```

**自动发布模式：**
- 填充内容后自动点击发布按钮
- 自动处理确认弹窗
- 检测发布成功状态

**手动发布模式：**
- 填充内容后等待 60 秒
- 需要手动点击发布按钮

## 工作流程

### 自动发布模式

```
1. 填充标题和内容
2. 🚀 自动点击发布按钮
3. ⏳ 等待发布完成
4. 🔍 检查确认弹窗（自动点击）
5. ✅ 检测发布成功
```

### 手动发布模式

```
1. 填充标题和内容
2. ⏸️  等待 60 秒
3. 👤 手动点击发布按钮
```

## 技术实现

### 多重选择器策略

```python
publish_selectors = [
    "button.publish-btn",           # CSS 类名
    "button:has-text('发布')",      # 按钮文字
    ".publish-btn",                  # 通用选择器
    "button[class*='publish']",      # 类名模糊匹配
]
```

### JavaScript 兜底

如果所有选择器都失败，使用 JavaScript 方式查找和点击按钮：

```javascript
// 查找所有按钮，检查文字或类名包含"发布"
for (let btn of document.querySelectorAll('button')) {
    if (btn.textContent.includes('发布') ||
        btn.className.includes('publish')) {
        btn.click();
    }
}
```

### 确认弹窗处理

自动检测并点击确认弹窗：

```python
confirm_selectors = [
    "button:has-text('确认发布')",
    "button:has-text('确定')",
    "button:has-text('发布')",
]
```

### 发布成功检测

多种方式检测发布是否成功：

```python
# 1. 检查成功提示元素
".publish-success"
":text('发布成功')"
":text('笔记已发布')"

# 2. 检查 URL 跳转
if "/explore/" in page.url:
    # 可能已跳转到笔记详情页
```

## 配置选项

### 代码中使用

```python
from actions.publisher import XiaohongshuPoster

# 自动发布模式（默认）
poster = XiaohongshuPoster(auto_publish=True)

# 手动发布模式
poster = XiaohongshuPoster(auto_publish=False)
```

### 草稿发布器中

```python
from tests.publish_draft import DraftPublisher

# 自动发布模式（默认）
publisher = DraftPublisher(auto_publish=True)

# 手动发布模式
publisher = DraftPublisher(auto_publish=False)
```

## 注意事项

### ⚠️ 风险提示

1. **自动发布可能导致风控**
   - 建议先使用手动模式测试
   - 确认内容无误后再切换到自动模式

2. **确认弹窗可能有变化**
   - 如果小红书更新 UI，可能需要更新选择器

3. **建议保留手动模式**
   - 重要内容建议手动检查后发布

### ✅ 最佳实践

1. **首次使用建议手动模式**
   ```bash
   Momo> auto off
   Momo> publish 1
   ```

2. **确认内容无误后再用自动模式**
   ```bash
   Momo> preview 1
   Momo> auto on
   Momo> publish 1
   ```

3. **定期检查发布结果**
   - 查看小红书创作者中心
   - 确认笔记已成功发布

## 故障排查

### 问题1：找不到发布按钮

**解决方案：**
- 检查是否已正确登录
- 查看截图 `debug_publish_button.png`
- 尝试使用手动模式

### 问题2：点击后无反应

**解决方案：**
- 检查按钮是否被遮挡
- 等待页面完全加载
- 尝试刷新页面后重试

### 问题3：未检测到发布成功

**解决方案：**
- 检查是否需要确认弹窗
- 手动检查笔记是否已发布
- 查看浏览器控制台错误信息

## 更新日志

| 版本 | 日期 | 更新内容 |
|------|------|---------|
| v1.2.0 | 2025-01-15 | 新增自动发布功能 |
| v1.1.0 | 2025-01-15 | 新增内容清洗功能 |

---

**更新日期：** 2025-01-15
**版本：** v1.2.0
**作者：** SiliconMomo Team
