# Stream 重复输出历史消息 Bug 修复方案

## 问题描述

当调用 `POST /planner/plan/stream` 接口时, 通过 Apifox 等 API 测试工具观察到以下异常现象:

1. 首先按照预期逐 token 流式返回本次 AI 回答 ✅
2. 随后又完整返回本次回答的全部内容 (重复) ❌
3. 甚至还会返回上一轮或历史对话中的完整回答 ❌
4. 最后才收到 `[DONE]` 信号

而调用 `GET /planner/history` 接口时, 能够正确返回无重复、无遗漏、顺序正确的历史记录, 说明问题出在 stream 接口的实现上, 而非持久化存储层面.

## 问题根源分析

### 1. 代码位置

问题出在 `src/service/planner_routes.py` 文件的 `plan_stream` 函数中 (第 176-271 行), 具体是 `generate_events()` 异步生成器函数 (第 189-261 行).

### 2. 关键代码片段

```python
# Line 215-250
async for stream_event in agent.astream(
    user_input, config=config, stream_mode=["updates", "messages"], subgraphs=True
):
    if not isinstance(stream_event, tuple):
        continue

    # 解析事件
    if len(stream_event) == 3:
        _, stream_mode, event = stream_event
    else:
        stream_mode, event = stream_event

    # 处理 updates 事件
    if stream_mode == "updates":
        for node, updates in event.items():
            if node == "__interrupt__":
                continue

            updates = updates or {}
            update_messages = updates.get("messages", [])

            # 过滤掉工具消息
            for msg in update_messages:
                if isinstance(msg, AIMessage) and msg.content:
                    # 发送完整消息作为 token 事件
                    content = str(msg.content)
                    yield f"data: {json.dumps({'type': 'token', 'delta': content})}\n\n"

    # 处理 messages 事件 (token 流)
    if stream_mode == "messages":
        msg, metadata = event
        if isinstance(msg, AIMessageChunk):
            content = remove_tool_calls(msg.content)
            if content:
                yield f"data: {json.dumps({'type': 'token', 'delta': convert_message_content_to_string(content)})}\n\n"
```

### 3. 问题分析

#### 3.1 同时使用两种 stream_mode

当前代码同时监听了 `["updates", "messages"]` 两种流式输出模式:

- **`"messages"` 模式** (第 244-249 行):
  - 功能: 逐 token 流式输出 `AIMessageChunk`
  - 行为: ✅ 这是我们期望的行为, 能够实现逐字显示效果

- **`"updates"` 模式** (第 228-241 行):
  - 功能: 在节点执行完成后输出完整的状态更新
  - 行为: ❌ 这导致了重复输出问题

#### 3.2 "updates" 模式的问题

在第 234 行, 代码获取 `update_messages = updates.get("messages", [])`, 在 LangGraph 的实现中, 这个返回值可能包含:

1. **新增的消息** (理想情况, 但实际并非如此)
2. **完整的当前回复消息** (已经通过 `"messages"` 模式逐 token 输出过)
3. **甚至包含历史消息** (如果节点在状态更新中返回了历史消息)

第 238-241 行将这些消息的 **完整内容** (而非增量 token) 作为单个 `delta` 发送:

```python
for msg in update_messages:
    if isinstance(msg, AIMessage) and msg.content:
        # 问题: 将完整消息内容作为单个 token 发送
        content = str(msg.content)
        yield f"data: {json.dumps({'type': 'token', 'delta': content})}\n\n"
```

#### 3.3 为什么会出现历史消息?

查看 `src/agents/travel_planner.py` 的 `fallback_to_research_assistant` 函数 (第 133-163 行):

```python
async def fallback_to_research_assistant(
    state: TravelPlannerState,
    config: RunnableConfig,
) -> TravelPlannerState:
    # 延迟导入以避免循环导入
    from agents.agents import get_agent

    logger.info("TravelPlanner: Fallback triggered, calling Research-Assistant")

    # 获取 Research-Assistant Agent
    research_agent = get_agent("research-assistant")

    # 调用 Research-Assistant (非流式)
    result = await research_agent.ainvoke(state, config)

    # 返回 Research-Assistant 的输出
    return {
        "messages": result.get("messages", []),  # ← 可能包含多条消息
        "fallback_triggered": True,
    }
```

问题在于:

1. `state` 本身就包含了历史消息 (因为 `MessagesState` 会累积消息)
2. `result.get("messages", [])` 可能返回多条消息
3. 如果 `research_agent` 或其他子 Agent 在内部处理时引用了 `state` 中的历史消息, 这些消息就会被包含在 `updates` 中

#### 3.4 问题流程总结

1. 用户发送消息
2. `"messages"` 模式逐 token 输出 AI 回复 ✅
3. 节点完成后, `"updates"` 模式触发:
   - 输出完整的当前回复 (重复第 2 步的内容) ❌
   - 如果触发 fallback, 可能还会输出多条消息 ❌
   - 甚至可能包含历史消息 (如果 `update_messages` 中有) ❌
4. 发送 `[DONE]` 信号

## 修复方案

### 方案 1: 移除 "updates" stream_mode (推荐)

**思路**: 只保留 `stream_mode=["messages"]`, 移除对 `"updates"` 的处理, 因为:

1. `"messages"` 模式已经能够满足逐 token 流式输出的需求
2. 不需要在节点完成后再次输出完整消息
3. 这是最简单、最直接、最干净的解决方案

**实施步骤**:

1. 修改 `src/service/planner_routes.py` 第 215 行:

   ```python
   # 修改前
   async for stream_event in agent.astream(
       user_input, config=config, stream_mode=["updates", "messages"], subgraphs=True
   ):

   # 修改后
   async for stream_event in agent.astream(
       user_input, config=config, stream_mode=["messages"], subgraphs=True
   ):
   ```

2. 删除或注释掉第 228-241 行 (处理 `"updates"` 事件的代码块):

   ```python
   # 删除这段代码
   # if stream_mode == "updates":
   #     for node, updates in event.items():
   #         if node == "__interrupt__":
   #             continue
   #
   #         updates = updates or {}
   #         update_messages = updates.get("messages", [])
   #
   #         # 过滤掉工具消息
   #         for msg in update_messages:
   #             if isinstance(msg, AIMessage) and msg.content:
   #                 # 发送完整消息作为 token 事件
   #                 content = str(msg.content)
   #                 yield f"data: {json.dumps({'type': 'token', 'delta': content})}\n\n"
   ```

3. 保留第 244-249 行 (处理 `"messages"` 事件的代码块):

   ```python
   # 处理 messages 事件 (token 流)
   if stream_mode == "messages":
       msg, metadata = event
       if isinstance(msg, AIMessageChunk):
           content = remove_tool_calls(msg.content)
           if content:
               yield f"data: {json.dumps({'type': 'token', 'delta': convert_message_content_to_string(content)})}\n\n"
   ```

**优点**:

- ✅ 最简单直接, 代码改动最小
- ✅ 不需要复杂的去重逻辑
- ✅ 减少了潜在的 bug
- ✅ 性能更好 (只处理一种 stream_mode)

**缺点**:

- ⚠️ 如果某些节点不支持 `"messages"` 模式的逐 token 输出, 可能需要额外处理 (但目前看来不存在这个问题)

### 方案 2: 过滤 "updates" 中的重复内容

**思路**: 保留两种模式, 但在处理 `"updates"` 时进行去重:

1. 记录已经通过 `"messages"` 模式输出的内容或消息 ID
2. 在处理 `"updates"` 时, 只输出新增的、未通过 `"messages"` 输出的消息

**实施步骤**:

1. 在 `generate_events()` 函数中维护一个已输出消息的集合:

   ```python
   async def generate_events() -> AsyncGenerator[str, None]:
       """生成 SSE 事件流"""
       try:
           # ... (前面的代码不变)

           # 维护已输出的消息 ID
           output_message_ids: set[str] = set()

           async for stream_event in agent.astream(...):
               # ...
   ```

2. 在处理 `"messages"` 时记录消息 ID:

   ```python
   if stream_mode == "messages":
       msg, metadata = event
       if isinstance(msg, AIMessageChunk):
           # 记录消息 ID
           msg_id = getattr(msg, "id", None) or str(id(msg))
           output_message_ids.add(msg_id)

           # ... (后续处理)
   ```

3. 在处理 `"updates"` 时进行去重:

   ```python
   if stream_mode == "updates":
       for node, updates in event.items():
           if node == "__interrupt__":
               continue

           updates = updates or {}
           update_messages = updates.get("messages", [])

           for msg in update_messages:
               if isinstance(msg, AIMessage) and msg.content:
                   # 检查是否已输出
                   msg_id = getattr(msg, "id", None) or str(id(msg))
                   if msg_id in output_message_ids:
                       continue  # 跳过已输出的消息

                   output_message_ids.add(msg_id)
                   content = str(msg.content)
                   yield f"data: {json.dumps({'type': 'token', 'delta': content})}\n\n"
   ```

**优点**:

- ✅ 保留了两种模式, 提供了更多灵活性
- ✅ 可以处理某些节点不支持 `"messages"` 模式的情况

**缺点**:

- ❌ 代码复杂度增加
- ❌ 需要额外的内存维护已输出消息集合
- ❌ 可能仍有边界情况未覆盖 (例如消息 ID 生成逻辑不一致)
- ❌ 如果 `"updates"` 中包含的是完整消息而 `"messages"` 是分块的, ID 可能不同

### 方案 3: 只在特定节点处理 "updates"

**思路**: 保留两种模式, 但只处理特定节点 (如 fallback 节点) 的 `"updates"`, 忽略其他节点.

**实施步骤**:

```python
# 处理 updates 事件
if stream_mode == "updates":
    for node, updates in event.items():
        # 只处理特定节点
        if node not in ["fallback_to_research_assistant"]:
            continue

        if node == "__interrupt__":
            continue

        # ... (后续处理)
```

**优点**:

- ✅ 可以针对特定节点进行特殊处理

**缺点**:

- ❌ 需要明确知道哪些节点需要处理
- ❌ 代码耦合度高, 不够灵活
- ❌ 仍然需要处理去重问题

## 推荐方案

**推荐采用方案 1: 移除 "updates" stream_mode**

理由:

1. **简单有效**: 代码改动最小, 逻辑最清晰
2. **符合需求**: `"messages"` 模式已经能够满足逐 token 流式输出的需求
3. **性能更好**: 减少了不必要的事件处理
4. **易于维护**: 不需要复杂的去重逻辑, 减少了潜在 bug
5. **经过验证**: LangGraph 官方文档中, 流式输出推荐使用 `stream_mode="messages"` (或 `stream_mode="messages-tuple"`)

## 实施细节

### 修改文件: `src/service/planner_routes.py`

#### 修改点 1: 调整 stream_mode

**位置**: 第 215 行

**修改前**:

```python
async for stream_event in agent.astream(
    user_input, config=config, stream_mode=["updates", "messages"], subgraphs=True
):
```

**修改后**:

```python
async for stream_event in agent.astream(
    user_input, config=config, stream_mode=["messages"], subgraphs=True
):
```

#### 修改点 2: 移除 "updates" 处理逻辑

**位置**: 第 228-241 行

**修改前**:

```python
# 处理 updates 事件
if stream_mode == "updates":
    for node, updates in event.items():
        if node == "__interrupt__":
            continue

        updates = updates or {}
        update_messages = updates.get("messages", [])

        # 过滤掉工具消息
        for msg in update_messages:
            if isinstance(msg, AIMessage) and msg.content:
                # 发送完整消息作为 token 事件
                content = str(msg.content)
                yield f"data: {json.dumps({'type': 'token', 'delta': content})}\n\n"

# 处理 messages 事件 (token 流)
if stream_mode == "messages":
    msg, metadata = event
    if isinstance(msg, AIMessageChunk):
        content = remove_tool_calls(msg.content)
        if content:
            yield f"data: {json.dumps({'type': 'token', 'delta': convert_message_content_to_string(content)})}\n\n"
```

**修改后**:

```python
# 处理 messages 事件 (token 流)
if stream_mode == "messages":
    msg, metadata = event
    if isinstance(msg, AIMessageChunk):
        content = remove_tool_calls(msg.content)
        if content:
            yield f"data: {json.dumps({'type': 'token', 'delta': convert_message_content_to_string(content)})}\n\n"
```

#### 修改点 3: 更新注释

建议在第 189 行附近添加注释说明为什么只使用 `"messages"` 模式:

```python
async def generate_events() -> AsyncGenerator[str, None]:
    """
    生成 SSE 事件流

    使用 stream_mode=["messages"] 实现逐 token 流式输出.
    不使用 "updates" 模式以避免重复输出完整消息.
    """
    try:
        # ...
```

### 完整的修改后代码

```python
@planner_router.post("/plan/stream")
async def plan_stream(
    request: PlanRequest,
    current_user: Annotated[User, Depends(current_active_user)],
    session: AsyncSession = Depends(get_async_session),
) -> StreamingResponse:
    """
    流式行程规划接口

    前端适配接口, 对应 POST /planner/plan/stream
    使用 SSE 返回增量响应
    """

    async def generate_events() -> AsyncGenerator[str, None]:
        """
        生成 SSE 事件流

        使用 stream_mode=["messages"] 实现逐 token 流式输出.
        不使用 "updates" 模式以避免重复输出完整消息.
        """
        try:
            # 获取用户的主 Thread ID
            thread_id = await get_or_create_main_thread(current_user, session)

            # 获取 agent
            agent: AgentGraph = get_agent(DEFAULT_AGENT)

            # 构建配置
            configurable: dict[str, Any] = {"thread_id": thread_id, "user_id": str(current_user.id)}
            if request.context and request.context.language:
                configurable["language"] = request.context.language
            if settings.DEFAULT_MODEL:
                configurable["model"] = settings.DEFAULT_MODEL

            config = RunnableConfig(configurable=configurable)

            # 构建输入 (带时间戳)
            input_message = create_timestamped_message(request.prompt, HumanMessage)
            user_input = {"messages": [input_message]}

            # 生成消息 ID (用于最终返回)
            message_id = f"msg-{id(input_message)}"

            # 流式调用 agent (只使用 messages 模式)
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
                    msg, metadata = event
                    if isinstance(msg, AIMessageChunk):
                        content = remove_tool_calls(msg.content)
                        if content:
                            yield f"data: {json.dumps({'type': 'token', 'delta': convert_message_content_to_string(content)})}\n\n"

            # 发送结束事件
            empty_dict = {}
            yield f"data: {json.dumps({'type': 'end', 'messageId': message_id, 'metadata': empty_dict})}\n\n"

            # 发送 [DONE] 标记
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
            "X-Accel-Buffering": "no",  # 禁用 Nginx 缓冲
        },
    )
```

## 测试计划

### 1. 单元测试

创建测试用例验证修复后的行为:

```python
# tests/test_planner_routes.py

async def test_plan_stream_no_duplicate_messages():
    """测试流式输出不会重复返回消息"""
    # TODO: 实现测试逻辑
    # 1. 调用 /planner/plan/stream
    # 2. 收集所有 SSE 事件
    # 3. 验证没有重复的完整消息
    # 4. 验证只有逐 token 的增量输出
    pass

async def test_plan_stream_no_history_messages():
    """测试流式输出不会返回历史消息"""
    # TODO: 实现测试逻辑
    # 1. 创建包含历史记录的 Thread
    # 2. 调用 /planner/plan/stream 发送新消息
    # 3. 验证输出中只包含新回复, 不包含历史消息
    pass
```

### 2. 集成测试

使用 Apifox 或类似工具进行手动测试:

1. **测试场景 1: 首次对话**
   - 发送: "计划一次 3 天的东京之旅"
   - 预期: 逐 token 流式输出, 不重复, 最后收到 `[DONE]`

2. **测试场景 2: 多轮对话**
   - 第 1 轮: "计划一次 3 天的东京之旅"
   - 第 2 轮: "加上大阪的行程"
   - 预期: 第 2 轮输出不包含第 1 轮的内容

3. **测试场景 3: Fallback 场景**
   - 模拟 NLU 服务不可用, 触发 fallback 到 research-assistant
   - 预期: 逐 token 流式输出, 不重复

### 3. 性能测试

对比修复前后的性能:

- 响应时间
- 内存使用
- 网络传输量

预期修复后性能有所提升 (因为减少了不必要的事件处理).

## 验收标准

修复完成后, 应满足以下标准:

1. ✅ 调用 `/planner/plan/stream` 时, 只会逐 token 返回当前回复
2. ✅ 不会在 token 流结束后再次返回完整消息
3. ✅ 不会返回历史对话的消息
4. ✅ 正常接收到 `[DONE]` 信号
5. ✅ 前端能够正常渲染逐字显示效果
6. ✅ `GET /planner/history` 仍然能够正确返回历史记录
7. ✅ Fallback 场景下仍然能够正常工作

## 风险评估

### 低风险

- ✅ 代码改动量小, 只修改一个文件的几行代码
- ✅ 不涉及数据库 Schema 变更
- ✅ 不影响其他接口
- ✅ 向后兼容 (前端不需要修改)

### 潜在风险及缓解措施

1. **风险**: 某些特殊节点可能不支持 `"messages"` 模式
   - **缓解**: 当前所有使用的 Agent 都基于 LangGraph, 均支持 `"messages"` 模式
   - **验证**: 通过集成测试覆盖所有场景

2. **风险**: 修改可能影响流式输出的完整性
   - **缓解**: `"messages"` 模式本身就是为流式输出设计的, 是官方推荐的方式
   - **验证**: 通过测试验证输出的完整性

## 参考资料

1. LangGraph 官方文档 - Streaming: <https://langchain-ai.github.io/langgraph/concepts/streaming/>
2. LangGraph Stream Modes: <https://langchain-ai.github.io/langgraph/concepts/streaming/#stream-modes>
3. 前后端接口约定: `backend/docs/api/前后端-接口文档.md`
4. Stream 接口实现: `backend/src/service/planner_routes.py`
5. Travel Planner Agent 实现: `backend/src/agents/travel_planner.py`

## 附录: LangGraph Stream Modes 说明

根据 LangGraph 官方文档, 主要的 stream modes 包括:

1. **`"messages"`**: 流式输出 AIMessageChunk, 适用于逐 token 展示
   - 用途: 实时流式输出 AI 生成的文本
   - 输出: `(AIMessageChunk, metadata)` tuple

2. **`"updates"`**: 流式输出节点的状态更新
   - 用途: 获取节点执行后的完整状态变化
   - 输出: `{node_name: state_update}` dict

3. **`"values"`**: 流式输出完整的状态值
   - 用途: 获取每个节点执行后的完整状态
   - 输出: 完整的 state dict

在本场景中, 我们只需要 `"messages"` 模式来实现逐 token 流式输出, 不需要 `"updates"` 模式.

---

**文档创建时间**: 2025-11-16
**最后更新时间**: 2025-11-16
**作者**: Claude Code
**状态**: 待实施
