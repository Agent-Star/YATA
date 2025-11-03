# IMP-005: 性能监控和日志优化

## 元数据

- **ID**: IMP-005
- **分类**: 可观测性
- **优先级**: 🟡 中
- **状态**: 待处理
- **创建日期**: 2025-01-27
- **预计工作量**: 中
- **相关文档**: 无

---

## 问题描述

### 当前实现

#### 1. 基础日志记录

**各文件中的日志**:

```python
import logging

logger = logging.getLogger(__name__)

# 简单的日志记录
logger.info("用户认证数据库表初始化完成")
logger.error(f"获取历史记录失败: {e}")
```

#### 2. 缺少结构化日志

当前日志格式简单，缺少关键信息：

- 无请求追踪 ID
- 无用户上下文
- 无性能指标
- 无结构化字段（难以解析和分析）

#### 3. 无性能监控

- 无接口响应时间监控
- 无 LLM 调用耗时统计
- 无数据库查询性能监控
- 无错误率统计

### 不足之处

1. **问题定位困难**：日志信息不完整，难以追踪请求链路
2. **性能瓶颈不明**：无法识别慢接口和性能问题
3. **运维困难**：缺少关键指标，难以监控系统健康状态
4. **用户体验无感知**：无法主动发现和解决性能问题

---

## 影响分析

### 功能影响

- ✅ 不影响核心功能

### 性能影响

- ⚠️ **无法定位性能瓶颈**：不知道哪些操作慢
- ⚠️ **无法优化**：缺少性能数据指导

### 运维影响

- 🔴 **故障排查困难**：日志信息不足
- ⚠️ **缺少告警**：无法及时发现问题
- ⚠️ **容量规划困难**：缺少关键指标

### 用户体验影响

- ⚠️ **响应缓慢无感知**：无法主动发现和优化

---

## 改进方案

### 方案 1: 结构化日志 + Prometheus 监控（推荐）

**优势**：

- ✅ 业界标准，生态完善
- ✅ 易于集成到现有监控系统
- ✅ 支持丰富的可视化（Grafana）

**实施步骤**：

#### 1. 配置结构化日志

**文件**: `backend/src/core/logging_config.py` (新建)

```python
"""日志配置"""

import logging
import sys
from datetime import datetime
from typing import Any

import structlog
from structlog.types import EventDict, Processor


def add_timestamp(logger: Any, name: str, event_dict: EventDict) -> EventDict:
    """添加时间戳"""
    event_dict["timestamp"] = datetime.utcnow().isoformat()
    return event_dict


def add_log_level(logger: Any, name: str, event_dict: EventDict) -> EventDict:
    """添加日志级别"""
    event_dict["level"] = name
    return event_dict


def setup_logging(is_dev: bool = True):
    """配置日志系统"""
    
    # 配置处理器链
    processors: list[Processor] = [
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        add_timestamp,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]
    
    if is_dev:
        # 开发环境：彩色输出，易读
        processors.append(structlog.dev.ConsoleRenderer())
    else:
        # 生产环境：JSON 格式，易于解析
        processors.append(structlog.processors.JSONRenderer())
    
    # 配置 structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # 配置标准库 logging
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter("%(message)s")
    )
    
    root_logger = logging.getLogger()
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.INFO)


# 获取日志器的辅助函数
def get_logger(name: str = None):
    """获取结构化日志器"""
    return structlog.get_logger(name)
```

**使用示例**:

```python
from core.logging_config import get_logger

logger = get_logger(__name__)

# 结构化日志
logger.info(
    "user_authenticated",
    user_id=str(user.id),
    email=user.email,
    ip_address=request.client.host,
    request_id=request.state.request_id,
)

# 包含上下文的错误日志
logger.error(
    "llm_call_failed",
    error=str(e),
    model=model_name,
    prompt_length=len(prompt),
    thread_id=thread_id,
    user_id=user_id,
)
```

#### 2. 添加性能监控中间件

**文件**: `backend/src/service/middleware.py` (新建)

```python
"""中间件"""

import time
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from core.logging_config import get_logger

logger = get_logger(__name__)


class PerformanceMonitoringMiddleware(BaseHTTPMiddleware):
    """性能监控中间件"""
    
    async def dispatch(self, request: Request, call_next: Callable):
        # 记录开始时间
        start_time = time.time()
        
        # 处理请求
        response = await call_next(request)
        
        # 计算耗时
        duration = time.time() - start_time
        
        # 记录性能日志
        logger.info(
            "request_completed",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=round(duration * 1000, 2),
            request_id=getattr(request.state, "request_id", None),
            user_id=getattr(request.state, "user_id", None),
        )
        
        # 添加响应头
        response.headers["X-Process-Time"] = str(duration)
        
        return response
```

**在 service.py 中使用**:

```python
from service.middleware import PerformanceMonitoringMiddleware

# 添加性能监控中间件
app.add_middleware(PerformanceMonitoringMiddleware)
```

#### 3. 集成 Prometheus 指标

**安装依赖**:

```bash
uv add prometheus-fastapi-instrumentator
```

**配置 Prometheus**:

```python
from prometheus_fastapi_instrumentator import Instrumentator

# 在 service.py 中
instrumentator = Instrumentator(
    should_group_status_codes=True,
    should_ignore_untemplated=True,
    should_respect_env_var=True,
    should_instrument_requests_inprogress=True,
    excluded_handlers=["/metrics", "/health"],
    env_var_name="ENABLE_METRICS",
    inprogress_name="fastapi_inprogress",
    inprogress_labels=True,
)

# 在 lifespan 中启用
@asynccontextmanager
async def lifespan(app: FastAPI):
    # ... 现有代码 ...
    
    # 启用 Prometheus 指标
    instrumentator.instrument(app).expose(app)
    
    yield
    
    # ... cleanup ...
```

**自定义指标**:

```python
from prometheus_client import Counter, Histogram

# 定义自定义指标
llm_requests_total = Counter(
    "llm_requests_total",
    "Total number of LLM requests",
    ["model", "status"]
)

llm_request_duration = Histogram(
    "llm_request_duration_seconds",
    "LLM request duration in seconds",
    ["model"]
)

# 在代码中使用
@llm_request_duration.labels(model=model_name).time()
async def call_llm():
    try:
        response = await model.ainvoke(...)
        llm_requests_total.labels(model=model_name, status="success").inc()
        return response
    except Exception as e:
        llm_requests_total.labels(model=model_name, status="error").inc()
        raise
```

#### 4. 添加健康检查端点

```python
@app.get("/health", tags=["System"])
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0",
    }


@app.get("/ready", tags=["System"])
async def readiness_check():
    """就绪检查（检查依赖服务）"""
    checks = {}
    
    # 检查数据库
    try:
        # 执行简单查询
        async with initialize_database() as saver:
            checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {str(e)}"
    
    # 检查 LLM
    try:
        get_model(settings.DEFAULT_MODEL)
        checks["llm"] = "ok"
    except Exception as e:
        checks["llm"] = f"error: {str(e)}"
    
    # 判断整体状态
    is_ready = all(v == "ok" for v in checks.values())
    status_code = 200 if is_ready else 503
    
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "ready" if is_ready else "not_ready",
            "checks": checks,
            "timestamp": datetime.utcnow().isoformat(),
        }
    )
```

---

### 方案 2: 使用 APM 工具（如 OpenTelemetry）

**优势**：

- ✅ 分布式追踪支持
- ✅ 自动埋点
- ✅ 更强大的分析能力

**劣势**：

- ❌ 配置复杂
- ❌ 需要额外的基础设施

**可选**：如果系统规模增长，可以考虑迁移到 OpenTelemetry。

---

## 实施建议

### 推荐方案

**方案 1（结构化日志 + Prometheus）** - 适合当前规模

### 实施步骤

1. **配置结构化日志**
   - 预计工作量：2 小时

2. **添加性能监控中间件**
   - 预计工作量：1 小时

3. **集成 Prometheus**
   - 预计工作量：2 小时

4. **添加健康检查**
   - 预计工作量：1 小时

5. **配置 Grafana 仪表板**（可选）
   - 预计工作量：2 小时

**总计**：约 6-8 小时

### 关键指标

**应用指标**:

- 请求速率（QPS）
- 响应时间（P50, P95, P99）
- 错误率
- 并发请求数

**业务指标**:

- 用户注册/登录速率
- LLM 调用次数和成功率
- 平均对话轮次
- Token 使用量

**资源指标**:

- CPU 使用率
- 内存使用量
- 数据库连接数

---

## Grafana 仪表板示例

```json
{
  "dashboard": {
    "title": "YATA Backend Metrics",
    "panels": [
      {
        "title": "Request Rate",
        "targets": [
          {
            "expr": "rate(http_requests_total[5m])"
          }
        ]
      },
      {
        "title": "Response Time (P95)",
        "targets": [
          {
            "expr": "histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))"
          }
        ]
      },
      {
        "title": "Error Rate",
        "targets": [
          {
            "expr": "rate(http_requests_total{status=~\"5..\"}[5m])"
          }
        ]
      }
    ]
  }
}
```

---

## 日志最佳实践

### 1. 统一日志格式

```python
# ✅ 好的日志
logger.info(
    "user_action",
    action="login",
    user_id=user_id,
    ip=request.client.host,
    duration_ms=duration,
)

# ❌ 不好的日志
logger.info(f"User {user_id} logged in from {ip}")
```

### 2. 日志级别规范

- **DEBUG**: 详细的调试信息
- **INFO**: 重要的业务事件（登录、注册、API 调用等）
- **WARNING**: 需要关注但不影响功能的问题
- **ERROR**: 错误但系统可以继续运行
- **CRITICAL**: 严重错误，可能导致系统崩溃

### 3. 避免记录敏感信息

```python
# ❌ 不要记录
logger.info("user_login", password=password)
logger.info("api_call", api_key=api_key)

# ✅ 应该记录
logger.info("user_login", user_id=user_id)
logger.info("api_call", api_key_prefix=api_key[:8])
```

---

## 相关资源

- [Structlog Documentation](https://www.structlog.org/)
- [Prometheus FastAPI Instrumentator](https://github.com/trallnag/prometheus-fastapi-instrumentator)
- [Grafana Dashboard Examples](https://grafana.com/grafana/dashboards/)
- [The Twelve-Factor App: Logs](https://12factor.net/logs)

---

## 更新日志

- 2025-01-27: 创建文档，提供结构化日志和 Prometheus 监控方案
