# 彩色日志配置指南

> **目的**: 为项目提供与 uvicorn 一致的彩色日志输出格式

---

## 📋 日志格式说明

### 统一的日志格式

```
INFO:  [service.service] 初始化用户认证数据库表...
^级别  ^tab×2  ^模块标识        ^日志内容

ERROR:  [auth.init] 超级管理员创建失败: admin (ID: xxx)
^级别   ^tab×2  ^模块标识      ^日志内容
```

**特点**:

- ✅ **彩色输出**: 不同日志级别使用不同颜色
  - `DEBUG`: 青色
  - `INFO`: 绿色
  - `WARNING`: 黄色
  - `ERROR`: 红色
  - `CRITICAL`: 紫色
- ✅ **统一缩进**: 使用 tab 分隔，确保对齐
- ✅ **模块标识**: 灰色的 `[module.name]` 标识日志来源
- ✅ **跨平台**: Windows/Linux/macOS 均支持

---

## 🚀 快速使用

### 1. 在应用代码中使用

**任何 Python 模块中**，只需使用标准的 `logging`：

```python
import logging

logger = logging.getLogger(__name__)

# 所有日志都会自动使用彩色格式
logger.info("用户认证数据库表初始化完成")
logger.warning("连接池已满，等待释放...")
logger.error("数据库连接失败", exc_info=True)
```

**输出效果**:

```
INFO:  [service.service] 用户认证数据库表初始化完成
WARNING: [service.service] 连接池已满，等待释放...
ERROR:  [service.service] 数据库连接失败
Traceback (most recent call last):
  ...
```

### 2. 已配置的模块

日志配置已在 `run_service.py` 中自动初始化，**无需额外配置**！

所有模块的日志都会自动使用统一格式：

- ✅ `service.service`
- ✅ `auth.init`
- ✅ `auth.manager`
- ✅ `agents.*`
- ✅ 所有其他模块

---

## 🎨 日志级别颜色参考

| 级别 | 颜色 | 使用场景 | 示例 |
|------|------|---------|------|
| `DEBUG` | 🔵 青色 | 调试信息 | `logger.debug("SQL: SELECT * FROM users")` |
| `INFO` | 🟢 绿色 | 常规信息 | `logger.info("服务启动成功")` |
| `WARNING` | 🟡 黄色 | 警告信息 | `logger.warning("连接池使用率达 80%")` |
| `ERROR` | 🔴 红色 | 错误信息 | `logger.error("数据库连接失败")` |
| `CRITICAL` | 🟣 紫色 | 严重错误 | `logger.critical("系统内存不足")` |

---

## ⚙️ 高级配置

### 自定义日志配置

如果需要在其他脚本中使用（非 `run_service.py`），可以手动初始化：

```python
from core.logging_config import setup_logging
import logging

# 初始化日志系统
setup_logging(
    level=logging.INFO,       # 日志级别
    use_colors=True,          # 启用彩色输出
    show_module=True,         # 显示模块名称
)

logger = logging.getLogger(__name__)
logger.info("自定义脚本启动")
```

### 禁用彩色输出

在某些环境（如 CI/CD 日志收集）可能需要禁用彩色输出：

```python
from core.logging_config import setup_logging
import logging

# 禁用颜色
setup_logging(level=logging.INFO, use_colors=False)
```

**或通过环境变量**（待实现）：

```bash
export NO_COLOR=1  # 遵循 NO_COLOR 标准
python src/run_service.py
```

### 隐藏模块名称

如果不需要显示模块标识：

```python
setup_logging(level=logging.INFO, show_module=False)

# 输出变为:
# INFO:  初始化用户认证数据库表...
#           （没有 [service.service]）
```

---

## 🔧 技术细节

### 1. 格式化器实现

**文件**: `backend/src/core/logging_config.py`

核心类 `ColoredFormatter` 负责：

- ANSI 颜色代码注入
- Tab 对齐计算
- 模块名称提取和格式化
- Windows 终端兼容性处理

### 2. Windows 兼容性

在 Windows 10+ 上，代码会自动启用虚拟终端处理：

```python
def _supports_color(self) -> bool:
    if sys.platform == "win32":
        import ctypes
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
        return True
    return hasattr(sys.stderr, "isatty") and sys.stderr.isatty()
```

### 3. uvicorn 集成

`get_uvicorn_log_config()` 返回 uvicorn 兼容的日志配置字典，确保 uvicorn 自身的日志（如启动消息）也使用统一格式。

### 4. 第三方库日志过滤

默认调整以下库的日志级别为 `WARNING`，减少噪音：

- `uvicorn.access`
- `httpx`
- `httpcore`
- `urllib3`
- `asyncio`

---

## 📝 最佳实践

### 1. 模块级 Logger

**推荐**：每个模块使用独立的 logger

```python
# ✅ 推荐
import logging
logger = logging.getLogger(__name__)

def my_function():
    logger.info("执行成功")  # 显示: [your.module] 执行成功
```

**不推荐**：使用根 logger

```python
# ❌ 不推荐
import logging
logging.info("执行成功")  # 显示: [root] 执行成功
```

### 2. 异常日志

使用 `exc_info=True` 自动记录异常堆栈：

```python
try:
    risky_operation()
except Exception as e:
    logger.error("操作失败", exc_info=True)  # 自动附加堆栈信息
```

### 3. 结构化日志（可选）

对于复杂场景，可以添加上下文信息：

```python
logger.info(
    "用户登录成功",
    extra={
        "user_id": user.id,
        "ip": request.client.host,
        "user_agent": request.headers.get("user-agent"),
    }
)
```

### 4. 性能敏感场景

避免在循环中频繁记录日志：

```python
# ❌ 不推荐
for item in large_list:
    logger.debug(f"处理 {item}")  # 可能产生大量日志

# ✅ 推荐
logger.debug(f"开始处理 {len(large_list)} 项数据")
for item in large_list:
    process(item)
logger.debug("处理完成")
```

---

## 🐛 故障排查

### 问题 1: 日志没有颜色

**原因**: 终端不支持 ANSI 转义码

**解决方案**:

1. Windows: 确保使用 Windows 10 1607+
2. 使用支持颜色的终端（如 Windows Terminal、iTerm2）
3. 手动禁用颜色：`setup_logging(use_colors=False)`

### 问题 2: 日志重复输出

**原因**: 多次调用 `setup_logging()` 或混用 `basicConfig()`

**解决方案**:

```python
# 确保只调用一次
if not logging.getLogger().handlers:
    setup_logging()
```

### 问题 3: 第三方库日志太多

**解决方案**: 在 `logging_config.py` 中调整对应库的级别

```python
# 在 setup_logging() 函数末尾添加
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
logging.getLogger("your_noisy_lib").setLevel(logging.ERROR)
```

---

## 🎯 示例对比

### 修改前（标准格式）

```
INFO:service.service:初始化用户认证数据库表...
INFO:auth.init:检查超级管理员账户: admin
ERROR:auth.manager:用户注册失败: Invalid email
```

**问题**:

- ❌ 没有颜色，难以区分级别
- ❌ 冒号分隔，不够清晰
- ❌ 模块名与内容挤在一起

### 修改后（彩色格式）

```
INFO:  [service.service] 初始化用户认证数据库表...
INFO:  [auth.init] 检查超级管理员账户: admin
ERROR:  [auth.manager] 用户注册失败: Invalid email
```

**优点**:

- ✅ 级别彩色醒目
- ✅ Tab 分隔清晰对齐
- ✅ 模块名灰色标识，易于识别

---

## 📚 参考资源

- [Python Logging 官方文档](https://docs.python.org/3/library/logging.html)
- [ANSI 颜色代码参考](https://en.wikipedia.org/wiki/ANSI_escape_code#Colors)
- [uvicorn 日志配置](https://www.uvicorn.org/settings/#logging)
- [NO_COLOR 标准](https://no-color.org/)

---

**文档版本**: 1.0  
**最后更新**: 2025-01-27  
**相关文件**:

- `backend/src/core/logging_config.py` - 日志配置模块
- `backend/src/run_service.py` - 应用入口（已配置）
