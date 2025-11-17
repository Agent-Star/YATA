# YATA NLU 服务

智能旅行助手 API，提供自然语言理解、意图识别和推荐/行程生成功能。

## 项目结构

核心目录说明：

- `NLU_module/`
  - `agents/adviser/` —— 多 Agent 智能体逻辑模块  
    - `adviser_intent.py`：意图识别  
    - `adviser_itinerary.py`：行程规划生成  
    - `adviser_recommendation.py`：景点/活动推荐
    - `adviser_rag.py`：RAG 检索增强模块  
    - `clarifier.py`：信息补全与追问逻辑  
    - `verifier.py`：逻辑验证与一致性检查  
  - `source/` —— 基础配置与模型封装  
    - `model_definition.py`：模型初始化定义  
    - `prompt.py`：Prompt 模板与系统指令  
    - `interaction_instructions.py`：交互协议定义  
    - `agent_personas.py`：多智能体角色设定  
    - `parse_utils.py`：通用解析工具函数  
  - `log/` —— 运行日志目录  
  - `initial.py`：系统初始化入口  
  - `main.py`：NLU 模块主入口
- `fastapi_server.py` —— FastAPI 主服务入口

## 功能特性

1. **意图识别**：自动识别用户请求类型（行程规划/景点推荐）
2. **智能生成**：生成个性化旅行推荐或详细行程规划
3. **逻辑审查**：使用 Verifier 对行程规划进行安全性和逻辑性检查
4. **会话管理**：支持多用户会话，每个会话维护独立的对话历史（需要使用seesion_id）
5. **多轮对话**：支持上下文理解和多轮追问（追问功能还未能在fastapi使用）

## 快速开始

### 安装依赖

先安装 `uv` 包管理器:

- linux / macos

  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```

- windows

  ```powershell
  powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
  ```

然后配置依赖:

```bash
uv sync
```

最后加载虚拟环境:

- linux / macos

  ```bash
  uv venv
  source .venv/bin/activate
  ```

- windows

  ```powershell
  uv venv
  ./.venv/Scripts/activate
  ```

### 启动服务器

```bash
python fastapi_server.py
```

服务器将在默认端口 **8010** 启动（可通过环境变量 `NLU_API_PORT` 修改）。

或者使用 uvicorn 启动：

```bash
uvicorn fastapi_server:app --host 0.0.0.0 --port 8010
```

### 验证服务

访问健康检查端点：

```bash
curl http://localhost:8010/health
```

预期响应：

```json
{"status": "ok"}
```

## API 接口文档

### 1. 基础 NLU 接口

**POST** `/nlu`

返回完整的 NLU 响应对象，包含所有中间处理结果。

**请求体**：

```json
{
    "text": "Plan a 4-day trip to Paris with museums and food experiences, budget 8000 yuan",
    "session_id": "optional-session-id"
}
```

**参数说明**：

- `text` (必填): 用户输入的自然语言文本
- `session_id` (可选): 会话 ID，用于维持对话上下文。不提供时会创建新会话

**响应格式**：

```json
{
    "success": true,
    "detail": {
        "intent_parsed": {
            "task_type": "itinerary",
            "destination": "Paris",
            "duration": 4,
            "budget": 8000
        },
        "itinerary_markdown": "# 4天巴黎行程...",
        "detailed_itinerary": {...},
        "recommendations": {...}
    },
    "error": null
}
```

**错误响应**：

```json
{
    "success": false,
    "detail": null,
    "error": "错误信息"
}
```

### 2. 简化版 NLU 接口（推荐）

**POST** `/nlu/simple`

返回格式化的自然语言回复，更适合前端展示。

**请求体**：

```json
{
    "text": "Plan a 4-day trip to Paris with museums and food experiences, budget 8000 yuan",
    "session_id": "optional-session-id"
}
```

**参数说明**：

- `text` (必填): 用户输入的自然语言文本(地点一定要是英文表示， rag调用需求)
- `session_id` (可选): 会话 ID。不提供时自动创建新会话并返回新的 `session_id`

**响应格式**：

```json
{
    "session_id": "550e8400-e29b-41d4-a716-446655440000",
    "type": "itinerary",
    "status": "complete",
    "reply": "# 4天巴黎行程规划\n\n## 第一天\n..."
}
```

**响应字段说明**：

- `session_id`: 会话 ID，后续请求使用此 ID 维持对话上下文
- `type`: 任务类型，`itinerary`（行程规划）或 `recommendation`（推荐）
- `status`: 状态，`complete`（完成）或 `incomplete`（需要补充信息）
- `reply`: 格式化的自然语言回复（Markdown 格式）

**状态说明**：

- `status: "complete"`: 任务完成，返回完整的行程规划或推荐内容
- `status: "incomplete"`: 需要更多信息，`reply` 字段包含追问内容

### 3. 流式 NLU 接口（推荐 - 实时体验）

**POST** `/nlu/simple/stream`

使用 SSE (Server-Sent Events) 逐 token 流式返回行程规划，用户可以边等待边看到生成过程。

**请求体**：

```json
{
    "text": "Plan a 4-day trip to Paris with museums and food experiences, budget 8000 yuan",
    "session_id": "optional-session-id"
}
```

**参数说明**：

- `text` (必填): 用户输入的自然语言文本 (地点建议使用英文)
- `session_id` (可选): 会话 ID。不提供时自动创建新会话

**响应格式** (SSE 事件流)：

流式接口返回一系列 SSE 事件，格式为 `data: {JSON}\n\n`。

**事件类型**：

1. **phase_start** - 阶段开始

```json
{"type": "phase_start", "phase": "intent_parsing"}
{"type": "phase_start", "phase": "rag_search"}
{"type": "phase_start", "phase": "content_generation"}
{"type": "phase_start", "phase": "itinerary_generation"}
```

2. **phase_end** - 阶段完成

```json
{"type": "phase_end", "phase": "intent_parsing"}
{"type": "phase_end", "phase": "rag_search", "result": {"count": 50}}
{"type": "phase_end", "phase": "content_generation"}
{"type": "phase_end", "phase": "itinerary_generation"}
```

3. **token** - 行程生成的文本片段 (逐 token 流式)

```json
{"type": "token", "delta": "#"}
{"type": "token", "delta": " 4"}
{"type": "token", "delta": "天"}
{"type": "token", "delta": "巴黎"}
{"type": "token", "delta": "行程"}
```

4. **end** - 处理完成

```json
{"type": "end", "session_id": "550e8400-e29b-41d4-a716-446655440000", "status": "complete"}
```

5. **error** - 错误

```json
{"type": "error", "message": "处理超时"}
```

6. **[DONE]** - 流式结束标记

```
data: [DONE]
```

**完整示例流程**：

```
data: {"type":"phase_start","phase":"intent_parsing"}
data: {"type":"phase_end","phase":"intent_parsing"}
data: {"type":"phase_start","phase":"rag_search"}
data: {"type":"phase_end","phase":"rag_search","result":{"count":50}}
data: {"type":"phase_start","phase":"content_generation"}
data: {"type":"phase_end","phase":"content_generation"}
data: {"type":"phase_start","phase":"itinerary_generation"}
data: {"type":"token","delta":"#"}
data: {"type":"token","delta":" "}
data: {"type":"token","delta":"4"}
data: {"type":"token","delta":"天"}
data: {"type":"token","delta":"巴黎"}
data: {"type":"token","delta":"行程"}
...
data: {"type":"phase_end","phase":"itinerary_generation"}
data: {"type":"end","session_id":"550e8400-e29b-41d4-a716-446655440000","status":"complete"}
data: [DONE]
```

**前端集成示例** (JavaScript):

```javascript
async function streamNLU(text, sessionId) {
    const response = await fetch('http://localhost:8010/nlu/simple/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text, session_id: sessionId })
    });

    const reader = response.body.getReader();
    const decoder = new TextDecoder();

    let buffer = '';

    while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';  // 保留未完成的行

        for (const line of lines) {
            if (line.startsWith('data: ')) {
                const data = line.slice(6);
                if (data === '[DONE]') return;

                const event = JSON.parse(data);

                switch (event.type) {
                    case 'phase_start':
                        console.log(`开始: ${event.phase}`);
                        break;
                    case 'token':
                        // 逐 token 显示行程内容
                        document.getElementById('itinerary').innerText += event.delta;
                        break;
                    case 'end':
                        console.log('完成:', event.session_id);
                        break;
                    case 'error':
                        console.error('错误:', event.message);
                        break;
                }
            }
        }
    }
}

// 使用示例
streamNLU('规划一个4天的巴黎行程，预算8000元');
```

**cURL 测试示例**:

```bash
# 使用 -N 参数禁用缓冲
curl -N -X POST "http://localhost:8010/nlu/simple/stream" \
     -H "Content-Type: application/json" \
     -d '{
       "text": "Plan a 4-day trip to Paris, budget 8000 yuan"
     }'
```

**优势**：

- ✅ 实时反馈：用户边等待边看到生成进度
- ✅ 更好的体验：避免长时间"黑屏等待"
- ✅ 降低感知延迟：即使总时间相同，用户体验大幅提升
- ✅ 易于调试：可以看到每个处理阶段的进度

### 4. 删除会话

**DELETE** `/nlu/session/{session_id}`

主动删除指定会话，释放服务器内存。通常在对话完全结束时由 backend 调用。

**路径参数**：

- `session_id` (必填): 要删除的会话 ID

**响应格式**：

```json
{
    "success": true,
    "message": "会话 550e8400-e29b-41d4-a716-446655440000 已删除"
}
```

**会话不存在时**：

```json
{
    "success": false,
    "message": "会话 550e8400-e29b-41d4-a716-446655440000 不存在"
}
```

**使用说明**：

- 主动删除可以立即释放会话占用的内存资源
- 删除后该会话的所有对话历史将丢失
- 即使不主动删除，系统也会在达到 100 个会话上限时自动淘汰最旧的会话 (LRU 策略)

### 4. 健康检查

**GET** `/health`

检查服务运行状态。

**响应**：

```json
{
    "status": "ok"
}
```

## 使用示例

### Python 示例

"""
注意目前追问功能在fastapi调用中还不是很好用，需要把信息提供完整
行程类问题：目的地，天数，预算，人数，出发时间，出发地点
推荐类问题：目的地，推荐物品（景点，酒店，美食）

以及目前数据库方面，只有Paris比较齐全
"""

#### 使用简化版接口（推荐）

```python
import requests

BASE_URL = "http://localhost:8010"

# 第一次请求（创建新会话）
response = requests.post(f"{BASE_URL}/nlu/simple", json={
    "text": "推荐Paris的顶级景点和必看地方，适合第一次去的游客"
})
result = response.json()
session_id = result["session_id"]
print(f"会话 ID: {session_id}")
print(f"回复: {result['reply']}")

# 后续请求（使用同一会话，保持对话历史）
response = requests.post(f"{BASE_URL}/nlu/simple", json={
    "text": "那推荐什么Pairs的博物馆呢？",
    "session_id": session_id
})
print(response.json()["reply"])

# 行程规划示例
response = requests.post(f"{BASE_URL}/nlu/simple", json={
    "text": "规划一个4天的Pairs行程，包含博物馆和美食体验，预算8000元，一个成人，下周去, 从上海出发",
    "session_id": session_id  # 使用同一会话，系统会记住之前的对话
})
result = response.json()
if result["status"] == "complete":
    print("✅ 行程规划完成：")
    print(result["reply"])
else:
    print("❓ 需要更多信息：")
    print(result["reply"])

# 对话结束后，主动删除会话释放资源（可选）
delete_response = requests.delete(f"{BASE_URL}/nlu/session/{session_id}")
delete_result = delete_response.json()
if delete_result["success"]:
    print(f"✅ {delete_result['message']}")
```

#### 使用基础接口（获取完整响应）

```python
import requests

response = requests.post("http://localhost:8010/nlu", json={
    "text": "规划一个4天的Pairs行程，包含博物馆和美食体验，预算8000元，一个成人，下周去, 从上海出发"
})
result = response.json()

if result["success"]:
    detail = result["detail"]
    task_type = detail.get("intent_parsed", {}).get("task_type")
    print(f"任务类型: {task_type}")
    
    if task_type == "itinerary":
        itinerary = detail.get("itinerary_markdown")
        print(itinerary)
    elif task_type == "recommendation":
        recommendations = detail.get("recommendations", {})
        print(recommendations.get("natural_summary"))
else:
    print(f"错误: {result['error']}")
```

### cURL 示例

#### 创建新会话并发送请求

```bash
curl -X POST "http://localhost:8002/nlu/simple" \
     -H "Content-Type: application/json" \
     -d '{
       "text": "推荐巴黎的顶级景点"
     }'
```

#### 使用已有会话继续对话

```bash
curl -X POST "http://localhost:8002/nlu/simple" \
     -H "Content-Type: application/json" \
     -d '{
       "text": "那博物馆呢？",
       "session_id": "your-session-id-here"
     }'
```

#### 行程规划请求

```bash
curl -X POST "http://localhost:8002/nlu/simple" \
     -H "Content-Type: application/json" \
     -d '{
       "text": "规划一个4天的Pairs行程，包含博物馆和美食体验，预算8000元，一个成人，下周去, 从上海出发"
     }'
```

## 任务类型说明

### 行程规划 (itinerary)

用户请求生成详细的旅行行程，包含：目的地，天数，预算，人数，出发时间，出发地点

**示例输入**：

- 规划一个4天的Pairs行程，包含博物馆和美食体验，预算8000元，一个成人，下周去, 从上海出发

**响应特点**：

- 返回详细的每日行程安排（Markdown 格式）
- 会经过 Verifier 逻辑审查，确保行程合理性
- 如果信息不足，会返回追问问题

### 景点推荐 (recommendation)

用户请求推荐景点、餐厅、活动等，不要求详细行程。

**示例输入**：

- "推荐巴黎的顶级景点"
- "北京有什么好吃的餐厅？"
- "京都值得去的地方有哪些？"

**响应特点**：

- 返回推荐列表和自然语言摘要
- 不经过 Verifier 审查
- 基于 RAG 检索相关旅行信息

## 会话管理

### 会话生命周期

1. **创建会话**：首次请求时不提供 `session_id`，系统自动创建新会话
2. **使用会话**：后续请求使用返回的 `session_id` 维持对话上下文
3. **删除会话**：
   - **主动删除**: Backend 调用 `DELETE /nlu/session/{session_id}` 主动删除会话
   - **被动清理 (LRU)**: 当会话数达到 100 个上限时，自动淘汰最旧的会话

### 会话特点

- 每个会话维护独立的 NLU 实例和对话历史
- 支持多用户同时使用，会话之间互不影响
- 会话日志保存在 `NLU_module/log/{session_id}/` 目录下
- 采用 LRU (Least Recently Used) 策略自动清理长时间未使用的会话
- Backend 应在对话完全结束时调用删除接口，及时释放资源

### 会话清理策略

**被动清理 (LRU)**:

- 会话数上限: 100 个
- 当创建新会话时，如果已达上限，自动删除最久未使用的会话
- 每次请求时，会话会被标记为"最近使用"

**主动清理**:

- Backend 在对话结束时调用 `DELETE /nlu/session/{session_id}`
- 立即释放会话占用的内存和资源
- 推荐在以下场景主动删除：
  - 用户明确表示对话结束
  - 对话超时或用户离线
  - 任务完成且不需要后续追问

## 架构说明

### 核心模块

 **NLU 模块** (`NLU_module/main.py`)

- Adviser: 主要对话生成模块（GPT-3.5/DeepSeek）
- Verifier: 逻辑审查模块（GPT-4o）
- RAG: 向量检索模块

### 处理流程

```txt
用户输入
  ↓
意图识别 (Adviser)
  ↓
RAG 检索 (向量搜索)
  ↓
内容生成 (Adviser)
  ↓
逻辑审查 (Verifier, 仅行程规划)
  ↓
格式化输出
  ↓
返回响应
```

## 错误处理

### 常见错误

1. **输入为空**
   - 状态码: 400
   - 错误信息: "输入内容不能为空"

2. **NLU 模块未初始化**
   - 状态码: 500
   - 错误信息: "NLU 模块未初始化"

3. **Adviser 无输出**
   - 状态码: 500
   - 错误信息: "Adviser 无输出"

### 错误响应格式

```json
{
    "success": false,
    "detail": null,
    "error": "具体错误信息"
}
```

## 日志和调试

### 日志位置

- 会话日志: `NLU_module/log/0/log.txt`
- 历史记录: `NLU_module/log/0/history.txt`
