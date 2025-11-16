# 修复 web-search snippet 显示问题及消息隔断问题 - 规划文档

## 问题描述

在用户与 AI 对话过程中, 如果触发了 `research-assistant` 的 web-search 流程, 会出现以下两个问题:

1. **Snippet 显示不一致**: 在调用 `GET /planner/history` 时会返回包含 snippet 的对话记录 (role=assistant 的消息), 但在流式响应 (`POST /planner/plan/stream`) 过程中, 这些 snippet 不会被实时显示给用户.
2. **消息隔断问题**: 在 history 中应该分开显示的多条 assistant 消息 (例如"请稍等"和"很抱歉..."), 在 stream 过程中会连续输出, 没有明显的分隔.

### 问题示例

参考 `@backend/docs/bug-desc/history-dump.json`, 可以看到:

- 消息 ID `run--83b4ca64-3117-4248-90c9-a75fd4f0422c`: 内容为 "好的，没问题。我将使用网络搜索工具查询一些热门的温暖海滨城市，并了解它们未来7天的天气预报。请稍等。"
- 消息 ID `run--c9b733e3-9eb2-467b-a983-f015922d03ef`: 内容为 "很抱歉，我无法直接从搜索结果中提取到热门温暖海滨城市未来7天的天气预报。..."
- 消息 ID `a3e8047a-5765-4258-b9b7-b3b9540ecf19`: 内容为 snippet (搜索结果的摘要)

在流式输出时, 用户会看到 "请稍等" 后直接连续输出 "很抱歉", 中间没有明显分隔, 而且 snippet 消息完全不显示.

---

## 问题根本原因分析

### 1. LangGraph 消息流程

当 `research-assistant` 使用 web-search 工具时, LangGraph 会产生以下消息序列:

1. **AIMessage (with tool_calls)**: 模型决定调用工具, 包含 tool_calls 信息
2. **ToolMessage**: 工具执行结果 (这就是 snippet, 包含搜索结果的文本摘要)
3. **AIMessage**: 模型基于工具结果生成的最终回复

这是 LangGraph 标准的工具调用流程. 所有这些消息都会被保存在 Thread 的状态中.

### 2. 后端 Stream 处理逻辑 (`planner_routes.py` line 220-238)

```python
async for stream_event in agent.astream(
    user_input, config=config, stream_mode=["messages"], subgraphs=True
):
    if not isinstance(stream_event, tuple):
        continue

    # 解析事件
    if len(stream_event) == 3:
        _, stream_mode, event = stream_event
    else:
        stream_mode, event = stream_event

    # 处理 messages 事件 (token 流)
    if stream_mode == "messages":
        msg, _ = event
        if isinstance(msg, AIMessageChunk):
            content = remove_tool_calls(msg.content)
            if content:
                yield f"data: {json.dumps({'type': 'token', 'delta': convert_message_content_to_string(content)})}\n\n"
```

**关键问题**:

- 只处理 `AIMessageChunk` 类型的消息
- `ToolMessage` 被完全忽略, 不发送到前端
- 多条 AIMessage 的内容会被连续发送, 没有分隔标记

### 3. 后端 History 处理逻辑 (`planner_routes.py` line 148-151)

```python
messages: list[AnyMessage] = state.values.get("messages", [])
frontend_messages = [langchain_message_to_frontend(msg) for msg in messages]
```

**关键问题**:

- 会转换所有消息, 包括 `ToolMessage`
- `langchain_message_to_frontend` 函数 (line 75-119) 对于非 `HumanMessage` 和 `AIMessage` 的消息类型, 会默认设置 `role="assistant"`
- 因此 `ToolMessage` 也被转换为 `role="assistant"` 的消息并返回给前端

### 4. 前端 Stream 处理逻辑 (`frontend/lib/services/aiPlanner.js`)

前端在接收 SSE stream 时, 只处理以下事件类型:

- `token`: 追加到当前 assistant 消息的 content
- `metadata`: 更新当前 assistant 消息的 metadata
- `end`: 标记流结束
- `[DONE]`: 关闭流

前端只维护一个累积字符串 `accumulated`, 将所有 token 拼接起来, 没有消息分隔的概念.

### 5. 问题总结

| 场景 | 当前行为 | 预期行为 |
|------|----------|----------|
| **Stream 过程** | 只输出 AIMessageChunk, 忽略 ToolMessage, 多条 AI 消息连续输出 | 应该区分不同的消息, 或至少提供视觉上的分隔 |
| **History 返回** | 返回所有消息 (包括 ToolMessage 转换为 assistant), 消息之间有明确的 id 和顺序 | 保持一致性, 或过滤掉不需要的消息 |
| **用户体验** | History 中有 snippet, stream 中没有; 消息连续输出没有分隔 | 一致且清晰的消息展示 |

---

## 修复方案

### 方案 1: 简单修复 - 过滤 History 中的 ToolMessage (仅后端修改)

#### 目标

让 `GET /planner/history` 不返回 `ToolMessage`, 从而与 stream 行为保持一致.

#### 实现步骤

1. **修改 `planner_routes.py` 中的 `get_history` 函数** (line 125-173)

在转换消息为前端格式之前, 过滤掉 `ToolMessage`:

```python
from langchain_core.messages import ToolMessage

@planner_router.get("/history", response_model=HistoryResponse)
async def get_history(
    current_user: Annotated[User, Depends(current_active_user)],
    session: AsyncSession = Depends(get_async_session),
) -> HistoryResponse:
    """
    获取用户的历史对话记录

    前端适配接口, 对应 GET /planner/history
    根据登录用户自动查询其主 Thread 的对话历史
    """
    try:
        # 获取用户的主 Thread ID
        thread_id = await get_or_create_main_thread(current_user, session)

        # 获取 agent (使用默认 agent 或专门的 travel planner)
        agent: AgentGraph = get_agent(DEFAULT_AGENT)

        # 获取 Thread 状态
        config = RunnableConfig(configurable={"thread_id": thread_id})
        state = await agent.aget_state(config=config)

        # 提取消息历史
        messages: list[AnyMessage] = state.values.get("messages", [])

        # 过滤掉 ToolMessage (不展示 snippet)
        filtered_messages = [
            msg for msg in messages
            if not isinstance(msg, ToolMessage)
        ]

        # 转换为前端格式
        frontend_messages = [langchain_message_to_frontend(msg) for msg in filtered_messages]

        # 查询用户的所有收藏记录
        stmt = select(Favorite.message_id).where(Favorite.user_id == current_user.id)
        result = await session.execute(stmt)
        favorited_message_ids = {row[0] for row in result.fetchall()}

        # 标记 isFavorited
        for msg in frontend_messages:
            msg.isFavorited = msg.id in favorited_message_ids

        # 显式按时间升序排列
        frontend_messages.sort(key=lambda m: m.createdAt if m.createdAt else "")

        return HistoryResponse(messages=frontend_messages)

    except Exception as e:
        logger.error(f"获取历史记录失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "API_ERROR", "message": "获取历史记录失败"},
        )
```

#### 优点

- **实现简单**: 只需修改一个函数, 添加一行过滤逻辑
- **无需修改前端**: 前端代码完全不需要改动
- **风险低**: 不涉及 stream 处理逻辑, 不会影响实时响应

#### 缺点

- **治标不治本**: 只是隐藏了 ToolMessage, 没有解决消息隔断问题
- **用户体验一般**: snippet 信息完全丢失, 用户无法看到 AI 的搜索过程
- **不够优雅**: 消息连续输出的问题仍然存在

#### 适用场景

- 快速修复, 短期内需要保持前后端一致性
- 暂时不需要向用户展示工具调用的详细信息
- 作为临时方案, 为方案 2 的实现争取时间

---

### 方案 2: 完整修复 - 支持消息分隔和 Snippet 展示 (前后端协同修改)

#### 目标

1. 在 stream 过程中正确处理多条 AI 消息, 提供视觉上的分隔
2. 可选地展示 ToolMessage (snippet), 让用户了解 AI 的搜索过程
3. 保持 History 和 Stream 的一致性

#### 设计思路

##### 后端改动

1. **扩展 SSE 事件类型**, 新增 `message_complete` 事件, 表示一条完整消息结束:

```typescript
// 新增事件类型
type SSEEvent =
  | { type: "token", delta: string }
  | { type: "metadata", metadata: object }
  | { type: "message_complete", messageId: string, role: "assistant" | "tool" }  // 新增
  | { type: "end", messageId: string, metadata: object }
  | { type: "[DONE]" }
```

2. **修改 `plan_stream` 函数**, 在检测到消息边界时发送 `message_complete` 事件:

```python
@planner_router.post("/planner/plan/stream")
async def plan_stream(
    request: PlanRequest,
    current_user: Annotated[User, Depends(current_active_user)],
    session: AsyncSession = Depends(get_async_session),
) -> StreamingResponse:
    """流式行程规划接口"""

    async def generate_events() -> AsyncGenerator[str, None]:
        try:
            thread_id = await get_or_create_main_thread(current_user, session)
            agent: AgentGraph = get_agent(DEFAULT_AGENT)

            configurable: dict[str, Any] = {
                "thread_id": thread_id,
                "user_id": str(current_user.id)
            }
            if request.context and request.context.language:
                configurable["language"] = request.context.language
            if settings.DEFAULT_MODEL:
                configurable["model"] = settings.DEFAULT_MODEL

            config = RunnableConfig(configurable=configurable)
            input_message = create_timestamped_message(request.prompt, HumanMessage)
            user_input = {"messages": [input_message]}
            message_id = f"msg-{id(input_message)}"

            # 追踪当前正在流式输出的消息
            current_message_id = None
            current_message_type = None

            async for stream_event in agent.astream(
                user_input, config=config, stream_mode=["messages"], subgraphs=True
            ):
                if not isinstance(stream_event, tuple):
                    continue

                if len(stream_event) == 3:
                    _, stream_mode, event = stream_event
                else:
                    stream_mode, event = stream_event

                if stream_mode == "messages":
                    msg, metadata = event

                    # 检测新消息的开始
                    msg_id = getattr(msg, "id", None) or str(id(msg))

                    # 如果消息 ID 变化, 说明上一条消息已结束
                    if current_message_id and current_message_id != msg_id:
                        yield f"data: {json.dumps({'type': 'message_complete', 'messageId': current_message_id, 'role': current_message_type})}\n\n"

                    current_message_id = msg_id

                    # 处理 AIMessageChunk
                    if isinstance(msg, AIMessageChunk):
                        current_message_type = "assistant"
                        content = remove_tool_calls(msg.content)
                        if content:
                            yield f"data: {json.dumps({'type': 'token', 'delta': convert_message_content_to_string(content)})}\n\n"

                    # 处理 ToolMessage (可选: 发送 snippet)
                    elif isinstance(msg, ToolMessage):
                        current_message_type = "tool"
                        # 可选: 将 snippet 作为特殊消息发送
                        # 前端可以选择如何展示 (折叠/展开/隐藏)
                        snippet_content = convert_message_content_to_string(msg.content)
                        yield f"data: {json.dumps({'type': 'snippet', 'content': snippet_content, 'messageId': msg_id})}\n\n"

            # 最后一条消息结束
            if current_message_id:
                yield f"data: {json.dumps({'type': 'message_complete', 'messageId': current_message_id, 'role': current_message_type})}\n\n"

            # 发送结束事件
            empty_dict = {}
            yield f"data: {json.dumps({'type': 'end', 'messageId': message_id, 'metadata': empty_dict})}\n\n"
            yield "data: [DONE]\n\n"

        except Exception as e:
            logger.error(f"流式规划失败: {e}")
            yield f"data: {json.dumps({'type': 'error', 'content': '服务器异常'})}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        generate_events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
```

##### 前端改动

1. **修改 `aiPlanner.js` 的 `streamPlan` 函数**, 处理新的事件类型:

```javascript
const processEvent = (rawEvent) => {
  if (!rawEvent) return;

  const lines = rawEvent.split(/\r?\n/);
  const dataLine = lines.find((line) => line.startsWith('data:'));
  if (!dataLine) return;

  const data = dataLine.slice(5).trim();
  if (!data) return;

  if (data === '[DONE]') {
    finalize();
    return;
  }

  let parsed;
  try {
    parsed = JSON.parse(data);
  } catch {
    return;
  }

  switch (parsed.type) {
    case 'token':
      if (parsed.delta && onToken) {
        onToken(parsed.delta);
      }
      break;

    case 'snippet':  // 新增: 处理 snippet
      if (parsed.content && onSnippet) {
        onSnippet(parsed.content, parsed.messageId);
      }
      break;

    case 'message_complete':  // 新增: 处理消息完成
      if (onMessageComplete) {
        onMessageComplete(parsed.messageId, parsed.role);
      }
      break;

    case 'metadata':
      if (parsed.metadata) {
        finalMetadata = parsed.metadata;
        if (onMetadata) {
          onMetadata(parsed.metadata);
        }
      }
      break;

    case 'end':
      if (parsed.messageId) {
        finalMessageId = parsed.messageId;
      }
      if (parsed.metadata) {
        finalMetadata = parsed.metadata;
        if (onMetadata) {
          onMetadata(parsed.metadata);
        }
      }
      finalize();
      break;

    case 'error':
      fail(new Error(parsed.content || '获取行程规划流时发生错误。'));
      break;

    default:
      break;
  }
};
```

2. **修改 `usePlanner.js` 的 `sendMessage` 函数**, 支持多条 assistant 消息:

```javascript
const sendMessage = useCallback(
  async (content) => {
    // ... (前面的代码保持不变)

    let currentAssistantMessageId = `assistant-${timestamp}`;
    let messageCounter = 0;

    dispatch({
      type: 'ADD_MESSAGE',
      payload: {
        id: currentAssistantMessageId,
        role: 'assistant',
        content: '',
        metadata: null,
        isStreaming: true,
        isFavorited: false,
        serverMessageId: null,
      },
    });

    let accumulated = '';
    let latestMetadata = null;

    try {
      const result = await streamPlan({
        prompt: trimmed,
        language: i18n.language,
        history: conversationHistory,

        onToken: (delta) => {
          if (!delta) return;
          accumulated += delta;
          dispatch({
            type: 'UPDATE_MESSAGE',
            payload: {
              id: currentAssistantMessageId,
              updates: { content: accumulated },
            },
          });
        },

        onMessageComplete: (messageId, role) => {
          // 消息完成, 标记当前消息为非流式
          dispatch({
            type: 'UPDATE_MESSAGE',
            payload: {
              id: currentAssistantMessageId,
              updates: {
                isStreaming: false,
                serverMessageId: messageId,
              },
            },
          });

          // 如果还会有新消息, 创建新的占位符
          messageCounter++;
          currentAssistantMessageId = `assistant-${timestamp}-${messageCounter}`;
          accumulated = '';

          dispatch({
            type: 'ADD_MESSAGE',
            payload: {
              id: currentAssistantMessageId,
              role: role === 'tool' ? 'tool' : 'assistant',
              content: '',
              metadata: null,
              isStreaming: true,
              isFavorited: false,
              serverMessageId: null,
            },
          });
        },

        onSnippet: (snippetContent, messageId) => {
          // 可选: 将 snippet 作为特殊消息插入
          // 或者以折叠形式展示
          dispatch({
            type: 'UPDATE_MESSAGE',
            payload: {
              id: currentAssistantMessageId,
              updates: {
                content: snippetContent,
                role: 'tool',  // 特殊标记
                isStreaming: false,
                serverMessageId: messageId,
              },
            },
          });

          // 准备下一条消息
          messageCounter++;
          currentAssistantMessageId = `assistant-${timestamp}-${messageCounter}`;
          accumulated = '';

          dispatch({
            type: 'ADD_MESSAGE',
            payload: {
              id: currentAssistantMessageId,
              role: 'assistant',
              content: '',
              metadata: null,
              isStreaming: true,
              isFavorited: false,
              serverMessageId: null,
            },
          });
        },

        onMetadata: (metadata) => {
          latestMetadata = metadata;
          dispatch({
            type: 'UPDATE_MESSAGE',
            payload: {
              id: currentAssistantMessageId,
              updates: { metadata },
            },
          });
        },
      });

      // 流结束, 清理最后一条消息
      const finalMetadata = result?.metadata ?? latestMetadata;
      dispatch({
        type: 'UPDATE_MESSAGE',
        payload: {
          id: currentAssistantMessageId,
          updates: {
            content: accumulated,
            metadata: finalMetadata || null,
            serverMessageId: result?.messageId || null,
            isStreaming: false,
          },
        },
      });
    } catch (error) {
      // ... (错误处理保持不变)
    } finally {
      dispatch({ type: 'SET_LOADING', payload: false });
    }
  },
  [dispatch, i18n, state.messages, t]
);
```

3. **修改 UI 组件**, 根据 `role` 区分展示 snippet:

可以在 `ChatHistory` 组件中添加特殊样式, 将 `role="tool"` 的消息以折叠或灰色文本的形式展示, 让用户知道这是 AI 的搜索过程.

#### 优点

- **用户体验优秀**: 消息分隔清晰, 可选地展示 snippet, 让用户了解 AI 的工作过程
- **前后端一致**: History 和 Stream 都能正确展示完整的对话流程
- **扩展性强**: 为未来支持更多工具类型 (如天气查询) 奠定基础

#### 缺点

- **实现复杂**: 需要同时修改后端和前端
- **测试成本高**: 需要仔细测试消息边界检测逻辑, 避免出现重复或遗漏
- **兼容性风险**: 需要确保新旧版本的 API 兼容

#### 适用场景

- 长期方案, 提升整体用户体验
- 需要向用户透明展示 AI 的工作流程
- 有时间和资源进行充分测试

---

## 方案对比

| 维度 | 方案 1: 过滤 ToolMessage | 方案 2: 支持消息分隔 |
|------|-------------------------|---------------------|
| **实现难度** | 低 (1-2 小时) | 中高 (1-2 天) |
| **代码改动量** | 极小 (仅后端 1 处) | 较大 (后端 + 前端多处) |
| **用户体验** | 一般 (隐藏 snippet, 消息连续) | 优秀 (消息分隔, 可展示 snippet) |
| **一致性** | 部分一致 (snippet 消失) | 完全一致 |
| **风险** | 低 | 中 (需充分测试) |
| **可维护性** | 中 (治标不治本) | 高 (架构合理) |
| **是否需要前端改动** | 否 | 是 |
| **推荐度** | ⭐⭐⭐ (短期) | ⭐⭐⭐⭐⭐ (长期) |

---

## 推荐实施策略

### 短期 (本次迭代)

采用 **方案 1**, 快速修复 snippet 显示不一致的问题:

1. 修改 `get_history` 函数, 过滤 `ToolMessage`
2. 运行 pyright 检查, 确保无类型错误
3. 手动测试 `GET /planner/history`, 确认 snippet 不再出现
4. 部署到测试环境验证

### 中长期 (下次迭代)

规划实施 **方案 2**, 提升整体用户体验:

1. 先在 backend 实现 SSE 事件扩展和消息边界检测
2. 编写单元测试, 确保消息 ID 跟踪逻辑正确
3. 更新前端 API 层, 支持新事件类型
4. 修改 UI 组件, 实现消息分隔和 snippet 折叠展示
5. 进行端到端测试
6. 灰度发布, 收集用户反馈

---

## 相关文件清单

### 后端文件

- `backend/src/service/planner_routes.py`: 路由实现, 包含 `get_history` 和 `plan_stream`
- `backend/src/service/utils.py`: 消息转换工具函数
- `backend/src/agents/research_assistant.py`: Research Assistant agent 实现
- `backend/src/agents/travel_planner.py`: Travel Planner agent 实现

### 前端文件

- `frontend/lib/services/aiPlanner.js`: SSE stream 处理逻辑
- `frontend/lib/hooks/usePlanner.js`: 消息状态管理
- `frontend/modules/chat/ChatPanel.js`: 聊天面板组件
- `frontend/components/chat/ChatHistory.js`: 消息展示组件

### 文档文件

- `backend/docs/api/前后端-接口文档.md`: 前后端接口约定
- `backend/docs/bug-desc/history-dump.json`: 问题示例数据

---

## 附录: 技术细节

### LangGraph 消息类型

```python
from langchain_core.messages import (
    HumanMessage,      # 用户输入
    AIMessage,         # AI 回复
    AIMessageChunk,    # AI 流式回复片段
    ToolMessage,       # 工具返回结果
    SystemMessage,     # 系统提示
)
```

### SSE 事件格式

标准 SSE 格式:

```
data: {"type": "token", "delta": "Hello"}\n\n
data: {"type": "end", "messageId": "msg-123"}\n\n
data: [DONE]\n\n
```

每个事件以 `data:` 开头, JSON 格式, 以双换行符 `\n\n` 结束.

### 前后端消息结构

```typescript
interface FrontendMessage {
  id: string;                 // 消息唯一 ID
  role: "user" | "assistant" | "tool";  // 角色
  content: string;            // 消息内容
  metadata?: object;          // 元数据 (如行程数组)
  createdAt?: string;         // 创建时间
  isFavorited?: boolean;      // 是否收藏
  serverMessageId?: string;   // 服务器端消息 ID
  isStreaming?: boolean;      // 是否正在流式输出 (仅前端使用)
}
```

---

## 结论

本文档分析了 web-search snippet 显示不一致及消息隔断问题的根本原因, 并提出了两种修复方案:

- **方案 1** (短期): 简单过滤 ToolMessage, 快速修复一致性问题
- **方案 2** (长期): 完整支持消息分隔和 snippet 展示, 提升用户体验

建议先实施方案 1, 快速解决当前问题; 后续规划方案 2, 提供更优质的用户体验.
