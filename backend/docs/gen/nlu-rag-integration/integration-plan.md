# NLU/RAG 服务整合规划总览

## 一、整合目标

将算法组开发的 NLU (自然语言理解) 和 RAG (检索增强生成) 微服务集成到现有的 YATA Backend 系统中，实现智能旅行规划功能，同时保持现有 Research-Assistant Agent 作为兜底方案。

## 二、核心需求

### 2.1 功能需求

1. **智能旅行规划**：
   - 用户输入旅行需求 (目的地、天数、预算等)
   - 系统自动识别意图 (行程规划 / 景点推荐)
   - 生成个性化的旅行方案

2. **多轮对话支持**：
   - 支持上下文理解
   - 支持信息补全和追问 (虽然目前有 BUG)

3. **兜底机制**：
   - NLU/RAG 服务不可用时，降级到 Research-Assistant
   - 确保系统始终能够响应用户请求

4. **会话管理**：
   - 维护用户的对话历史
   - 支持多用户并发使用

### 2.2 技术需求

1. **服务调用**：
   - 封装 NLU 和 RAG 服务的 HTTP 客户端
   - 处理网络异常、超时、重试

2. **架构兼容**：
   - 与现有 LangGraph Agent 架构兼容
   - 保持现有 API 接口不变 (或最小变动)
   - 遵循现有代码风格和类型标注规范

3. **性能要求**：
   - 支持流式响应 (SSE)
   - 异步调用，避免阻塞

4. **可观测性**：
   - 完整的日志记录
   - 错误追踪和监控

## 三、服务概览

### 3.1 NLU 服务

**服务地址**: `http://localhost:8010`

**核心接口**: `POST /nlu/simple`

**请求格式**:

```json
{
    "text": "规划一个4天的Paris行程，预算8000元，一个成人，下周去，从上海出发",
    "session_id": "optional-session-id"
}
```

**响应格式**:

```json
{
    "session_id": "550e8400-e29b-41d4-a716-446655440000",
    "type": "itinerary",  // 或 "recommendation"
    "status": "complete",  // 或 "incomplete"
    "reply": "# 4天巴黎行程规划\n\n## 第一天\n..."
}
```

**特点**:

- 支持意图识别 (行程规划 vs 景点推荐)
- 内部已集成 RAG 检索
- 返回 Markdown 格式的自然语言回复
- 支持会话管理 (通过 `session_id`)

**已知问题**:

- 追问功能在 FastAPI 调用中不完善
- 建议提供完整信息: 目的地、天数、预算、人数、出发时间、出发地点

### 3.2 RAG 服务

**服务地址**: `http://localhost:8001`

**核心接口**: `POST /search`

**请求格式**:

```json
{
    "query": "巴黎有哪些著名景点",
    "city": "Paris",
    "top_k": 5
}
```

**响应格式**:

```json
{
    "contexts": "...",
    "results": [
        {
            "id": "...",
            "city": "Paris",
            "title": "...",
            "content": "...",
            "score": 0.85
        }
    ]
}
```

**特点**:

- 基于 ChromaDB 和 BGE-M3 的向量检索
- 支持按城市过滤
- 可选的重排序功能

**整合说明**:

- NLU 内部已调用 RAG，backend 通常不需要直接调用
- 可保留 RAG 客户端用于未来扩展或独立使用

## 四、整合策略

### 4.1 整体架构

```txt
用户请求
  ↓
Frontend
  ↓
Backend API (FastAPI)
  ↓
Travel Planner Agent (新增)
  ├─ 优先方案: NLU Service (Port 8010)
  │     ├─ 内部调用: RAG Service (Port 8001)
  │     └─ 返回: 智能旅行规划
  │
  └─ 兜底方案: Research-Assistant Agent (现有)
        ├─ DuckDuckGo Web Search
        └─ 返回: 通用研究结果
```

### 4.2 核心设计原则

1. **最小侵入性**：
   - 尽量不修改现有代码
   - 通过新增 Agent 和客户端模块实现功能

2. **渐进式集成**：
   - 第一阶段：实现基础调用和兜底机制
   - 第二阶段：优化会话管理和响应格式
   - 第三阶段：添加监控和性能优化

3. **保持兼容性**：
   - 与前端接口保持兼容
   - 保持现有 API 响应格式不变

4. **可测试性**：
   - 独立的客户端模块，便于单元测试
   - 清晰的错误处理和日志记录

### 4.3 关键技术决策

| 决策点 | 方案 | 理由 |
|--------|------|------|
| Agent 架构 | 创建新的 `travel_planner` Agent | 保持现有 Agent 不变，降低风险 |
| 会话管理 | 使用现有 `thread_id` 作为 NLU `session_id` | 简化设计，避免额外映射 |
| 响应格式 | 将 NLU 的 Markdown 回复包装为 AIMessage | 保持与现有流式响应格式一致 |
| 兜底触发条件 | NLU 服务不可达 / 错误 / 超时 | 确保系统可用性 |
| HTTP 客户端 | 使用 `httpx.AsyncClient` | 与 FastAPI 异步架构一致 |
| 默认 Agent | 保持 `research-assistant` 或切换到 `travel-planner` | 根据测试结果决定 |

## 五、实现计划

### 5.1 模块划分

```txt
backend/src/
├── external_services/          # 外部服务客户端 (新增)
│   ├── __init__.py
│   ├── nlu_client.py           # NLU 服务客户端
│   ├── rag_client.py           # RAG 服务客户端 (可选)
│   └── exceptions.py           # 自定义异常类
│
├── agents/
│   ├── travel_planner.py       # 旅行规划 Agent (新增)
│   ├── agents.py               # Agent 注册中心 (修改)
│   └── ...
│
├── core/
│   ├── settings.py             # 全局配置 (修改: 添加 NLU/RAG 配置)
│   └── ...
│
└── service/
    └── planner_routes.py       # 行程规划路由 (可能需要微调)
```

### 5.2 实现步骤

#### 阶段一：基础设施搭建 (预计 2-3 小时)

1. **配置管理** (`core/settings.py`)
   - 添加 NLU 服务配置 (`NLU_SERVICE_URL`, `NLU_TIMEOUT`)
   - 添加 RAG 服务配置 (`RAG_SERVICE_URL`, `RAG_TIMEOUT`)
   - 添加兜底开关 (`ENABLE_NLU_FALLBACK`)

2. **NLU 客户端** (`external_services/nlu_client.py`)
   - 封装 `POST /nlu/simple` 调用
   - 实现超时、重试、错误处理
   - 定义 Pydantic 模型 (请求/响应)

3. **RAG 客户端** (`external_services/rag_client.py`)
   - 封装 `POST /search` 调用
   - 实现错误处理
   - 定义 Pydantic 模型 (可选，用于未来扩展)

4. **异常类定义** (`external_services/exceptions.py`)
   - `NLUServiceError` - NLU 服务错误
   - `RAGServiceError` - RAG 服务错误
   - `ServiceUnavailableError` - 服务不可用

#### 阶段二：Travel Planner Agent 实现 (预计 3-4 小时)

1. **Agent 核心逻辑** (`agents/travel_planner.py`)
   - 定义 `AgentState` (继承 `MessagesState`)
   - 实现主节点：
     - `call_nlu_service` - 调用 NLU 服务
     - `fallback_to_research_assistant` - 兜底逻辑
   - 实现条件路由：
     - `should_fallback` - 判断是否需要兜底
   - 构建 StateGraph

2. **Agent 注册** (`agents/agents.py`)
   - 注册 `travel-planner` Agent
   - 决定是否更新 `DEFAULT_AGENT`

#### 阶段三：集成与测试 (预计 2-3 小时)

1. **路由调整** (可选)
   - 如需要，在 `planner_routes.py` 中添加新路由
   - 或直接使用现有路由，切换底层 Agent

2. **端到端测试**
   - NLU 服务正常场景
   - NLU 服务异常场景 (兜底)
   - 流式响应功能
   - 会话管理功能

3. **日志和监控**
   - 添加关键路径的日志记录
   - 记录 NLU 调用成功/失败率

#### 阶段四：优化与文档 (预计 1-2 小时)

1. **性能优化**
   - 调整超时参数
   - 优化错误重试策略

2. **代码审查**
   - Pyright 类型检查
   - 代码风格检查

3. **文档更新**
   - 更新 API 文档
   - 编写集成完成总结

### 5.3 测试策略

1. **单元测试**
   - NLU Client 的 mock 测试
   - Agent 状态转换测试

2. **集成测试**
   - NLU 服务联调测试
   - 兜底机制触发测试

3. **端到端测试**
   - 前端发起请求 → Backend → NLU → 响应
   - 异常场景下的兜底流程

## 六、风险与应对

### 6.1 潜在风险

| 风险 | 影响 | 概率 | 应对措施 |
|------|------|------|----------|
| NLU 服务不稳定 | 用户体验下降 | 中 | 实现健壮的兜底机制 |
| NLU 追问功能 BUG | 多轮对话失败 | 高 | 提示用户提供完整信息，或直接兜底 |
| 会话管理复杂度 | 开发延期 | 中 | 简化设计，使用现有 thread_id |
| 响应格式不兼容 | 前端显示异常 | 低 | 仔细转换格式，充分测试 |
| 性能问题 (外部调用) | 响应变慢 | 中 | 设置合理超时，考虑缓存 |

### 6.2 回滚方案

- **阶段一**：如遇问题，删除新增文件即可
- **阶段二**：保持 `DEFAULT_AGENT = "research-assistant"`，不影响现有功能
- **阶段三**：通过配置开关快速禁用 NLU 集成

## 七、后续扩展

### 7.1 短期优化 (1-2 周)

1. **缓存机制**
   - 缓存常见查询的 NLU 响应
   - 减少外部服务调用

2. **监控看板**
   - NLU 调用成功率
   - 兜底触发频率
   - 平均响应时间

### 7.2 长期规划 (1-2 月)

1. **独立 RAG 调用**
   - 在某些场景下直接调用 RAG (不经过 NLU)
   - 例如：纯信息检索、FAQ 回答

2. **多 Agent 协作**
   - Travel Planner 负责行程规划
   - Research Assistant 负责通用查询
   - 根据意图自动路由

3. **行程编辑功能**
   - 基于 NLU 生成的行程进行局部修改
   - 支持"在第二天加入博物馆参观"等指令

## 八、成功标准

### 8.1 功能完整性

- [x] NLU 服务调用成功
- [x] 行程规划返回正确格式
- [x] 兜底机制正常工作
- [x] 会话管理无冲突
- [x] 流式响应正常

### 8.2 代码质量

- [x] 通过 Pyright standard 级别检查
- [x] 无明显的类型错误
- [x] 注释清晰，符合现有风格
- [x] 日志记录完整

### 8.3 性能指标

- [x] NLU 调用平均响应时间 < 5s
- [x] 兜底切换时间 < 1s
- [x] 端到端响应时间 < 10s

## 九、时间规划

| 阶段 | 预计时间 | 关键交付物 |
|------|----------|-----------|
| 阶段一：基础设施 | 2-3h | NLU/RAG 客户端 |
| 阶段二：Agent 实现 | 3-4h | Travel Planner Agent |
| 阶段三：集成测试 | 2-3h | 端到端联调成功 |
| 阶段四：优化文档 | 1-2h | 集成完成总结 |
| **总计** | **8-12h** | **NLU/RAG 完整集成** |

---

**文档版本**: v1.0
**编写日期**: 2025-11-14
**作者**: Claude Code
**状态**: 待审核
