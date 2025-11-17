# NLU 服务性能优化方案

## 概述

本方案基于 [RAG返回后NLU超时分析](./RAG返回后NLU超时分析.md) 中的发现，采纳以下两个核心解决方案：

1. **中期方案**: 并发执行独立的 LLM 调用（立即可实施）
2. **长期方案**: 流式响应架构（参考 backend/planner_routes.py 的 SSE 实现）

## 方案目标

### 性能指标

**当前状态**:

- 正常流程: 17-22 秒
- 一次 Verifier 重试: 44 秒 ❌ 超时

**优化目标**:

- 阶段 1 (并发调用): 11-16 秒 ✅ 节省 6 秒
- 阶段 2 (流式响应): 用户体验提升，避免长时间等待

### 架构目标

- 保持现有 async 基础设施
- 向后兼容现有 API
- 渐进式迁移，无需停机
- 为未来扩展留出空间

---

## 阶段 1: 并发执行独立的 LLM 调用

### 1.1 问题分析

**当前串行执行** (`adviser_main.py:183-189`):

```python
# 当前实现 - 串行等待
result["context_summary"] = await run_context_summary(...)  # 等待 1-2s
result["plan_steps"] = await run_plan_actions(...)          # 等待 1-2s
result["final_aggregation"] = await run_aggregate(...)      # 等待 1-2s
result["detailed_itinerary"] = await generate_itinerary(...)# 等待 5-10s

# 总计: 8-16 秒
```

**可并发的调用**:

以下 3 个 LLM 调用**相互独立**，可以并发执行：

- `run_context_summary()`
- `run_plan_actions()`
- `run_aggregate()`

**依赖关系**:

- `generate_itinerary()` 依赖于上述 3 个调用的结果，必须等待它们完成

### 1.2 实施方案

#### 修改文件: `NLU_module/agents/adviser/adviser_main.py`

**原代码** (约 183-189 行):

```python
# 串行执行
result["context_summary"] = await run_context_summary(
    self.llm, user_input, doc_summaries
)
result["plan_steps"] = await run_plan_actions(
    self.llm, result["intent_parsed"]
)
result["final_aggregation"] = await run_aggregate(
    self.llm, [], result["intent_parsed"]
)
```

**优化后代码**:

```python
# 并发执行独立的 LLM 调用
context_task = run_context_summary(self.llm, user_input, doc_summaries)
plan_task = run_plan_actions(self.llm, result["intent_parsed"])
aggregate_task = run_aggregate(self.llm, [], result["intent_parsed"])

# 使用 asyncio.gather 并发等待
context_summary, plan_steps, final_aggregation = await asyncio.gather(
    context_task,
    plan_task,
    aggregate_task,
)

# 将结果赋值到 result 字典
result["context_summary"] = context_summary
result["plan_steps"] = plan_steps
result["final_aggregation"] = final_aggregation
```

**需要导入**:

```python
import asyncio  # 在文件顶部添加
```

#### 预期效果

**串行执行时间**:

- context_summary: 1-2s
- plan_steps: 1-2s
- final_aggregation: 1-2s
- **总计: 3-6 秒**

**并发执行时间**:

- 3 个调用并发执行
- **总计: max(1-2s, 1-2s, 1-2s) = 1-2 秒**

**节省时间**: **4-6 秒** ✅

#### 错误处理

使用 `asyncio.gather` 的 `return_exceptions=True` 参数处理部分失败：

```python
results = await asyncio.gather(
    context_task,
    plan_task,
    aggregate_task,
    return_exceptions=True,  # 不会因为单个任务失败而全部失败
)

# 检查每个结果
context_summary, plan_steps, final_aggregation = results

if isinstance(context_summary, Exception):
    logger.error(f"context_summary 失败: {context_summary}")
    context_summary = ""  # 使用默认值

if isinstance(plan_steps, Exception):
    logger.error(f"plan_steps 失败: {plan_steps}")
    plan_steps = []

if isinstance(final_aggregation, Exception):
    logger.error(f"final_aggregation 失败: {final_aggregation}")
    final_aggregation = ""

result["context_summary"] = context_summary
result["plan_steps"] = plan_steps
result["final_aggregation"] = final_aggregation
```

### 1.3 其他潜在并发优化点

#### Intent Parsing 中的并发

**当前串行执行** (`adviser_intent.py:44-59`):

```python
# 意图识别
intent_parsed = await self.llm.ask_json(prompt_parse_intent, ...)

# 日期规范化 (条件执行)
if needs_date_normalization:
    normalized_dates = await self.llm.ask_json(prompt_normalize_date, ...)

# 查询改写
rewritten_query = await self.llm.ask_text(prompt_query_rewrite, ...)
```

**潜在优化** (谨慎使用):

日期规范化和查询改写**可能独立**，可尝试并发：

```python
# 先执行意图识别
intent_parsed = await self.llm.ask_json(prompt_parse_intent, ...)

# 并发执行日期规范化和查询改写
tasks = []
if needs_date_normalization:
    tasks.append(self.llm.ask_json(prompt_normalize_date, ...))
else:
    tasks.append(None)  # 占位

tasks.append(self.llm.ask_text(prompt_query_rewrite, ...))

results = await asyncio.gather(*tasks, return_exceptions=True)
normalized_dates = results[0] if results[0] is not None else None
rewritten_query = results[1]
```

**注意**: 需要仔细验证查询改写是否依赖于日期规范化的结果。

---

## 阶段 2: 流式响应架构

### 2.1 设计目标

- 用户边等待边看到部分结果，避免"黑屏等待"
- 即使总时间不变，用户体验大幅提升
- 兼容 backend 的 SSE (Server-Sent Events) 实现

### 2.2 Backend 流式实现分析

**参考**: `backend/src/service/planner_routes.py` (dev 分支)

**核心模式**:

```python
@planner_router.post("/plan/stream")
async def plan_stream(...) -> StreamingResponse:
    async def generate_events() -> AsyncGenerator[str, None]:
        try:
            # 获取 agent 和 config
            agent: AgentGraph = get_agent(DEFAULT_AGENT)
            config = RunnableConfig(configurable={"thread_id": thread_id, ...})

            # 流式调用 agent.astream()
            async for stream_event in agent.astream(
                user_input,
                config=config,
                stream_mode=["messages"],  # 逐 token 流式
                subgraphs=True
            ):
                if stream_mode == "messages":
                    msg, _ = event
                    if isinstance(msg, AIMessageChunk):
                        content = remove_tool_calls(msg.content)
                        if content:
                            # 发送 SSE 事件
                            yield f"data: {json.dumps({'type': 'token', 'delta': convert_message_content_to_string(content)})}\n\n"

            # 发送结束事件
            yield f"data: {json.dumps({'type': 'end', 'messageId': message_id, 'metadata': {}})}\n\n"
            yield "data: [DONE]\n\n"

        except Exception as e:
            logger.error(f"流式规划失败: {e}")
            yield f"data: {json.dumps({'type': 'error', 'content': '服务器异常'})}\n\n"

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

**关键技术**:

1. **FastAPI StreamingResponse** - 返回异步生成器
2. **SSE 格式** - `data: {JSON}\n\n`
3. **AIMessageChunk** - LangChain 的流式消息类型
4. **stream_mode=["messages"]** - 逐 token 流式输出

### 2.3 NLU 流式实现方案

#### 方案 A: 渐进式流式输出（推荐）

**优点**: 分阶段流式，实现简单，向后兼容

**实现**: 在每个阶段完成时发送事件

```python
# fastapi_server.py - 新增流式端点

@app.post("/nlu/simple/stream")
async def nlu_simple_stream(request: NLURequest):
    """
    流式 NLU 接口 - 渐进式返回结果

    事件类型:
    - phase_start: 阶段开始 {"type": "phase_start", "phase": "intent_parsing"}
    - phase_end: 阶段完成 {"type": "phase_end", "phase": "intent_parsing", "result": {...}}
    - token: 行程生成的 token {"type": "token", "delta": "..."}
    - end: 处理完成 {"type": "end", "session_id": "..."}
    - error: 错误 {"type": "error", "message": "..."}
    """
    async def generate_events():
        session_id = request.session_id or str(uuid4())

        try:
            # 获取或创建会话
            if session_id not in SESSIONS:
                SESSIONS[session_id] = NLU(
                    log_folder="log",
                    file_name=session_id,
                    with_verifier=True
                )
                SESSIONS.move_to_end(session_id)
                logger.info(f"创建新会话: {session_id}")

            nlu = SESSIONS[session_id]
            SESSIONS.move_to_end(session_id)

            # === 阶段 1: Intent Parsing ===
            yield sse_event({"type": "phase_start", "phase": "intent_parsing"})

            intent_result = await nlu.adviser.run_intent_parsing(request.text)

            yield sse_event({
                "type": "phase_end",
                "phase": "intent_parsing",
                "result": intent_result
            })

            # === 阶段 2: RAG 检索 ===
            yield sse_event({"type": "phase_start", "phase": "rag_search"})

            rag_results = await nlu.adviser.call_rag_api(...)

            yield sse_event({
                "type": "phase_end",
                "phase": "rag_search",
                "result": {"count": len(rag_results)}
            })

            # === 阶段 3: 内容生成 (并发) ===
            yield sse_event({"type": "phase_start", "phase": "content_generation"})

            # 并发执行独立调用
            context_task = nlu.adviser.run_context_summary(...)
            plan_task = nlu.adviser.run_plan_actions(...)
            aggregate_task = nlu.adviser.run_aggregate(...)

            context, plan, aggregate = await asyncio.gather(
                context_task, plan_task, aggregate_task
            )

            yield sse_event({
                "type": "phase_end",
                "phase": "content_generation"
            })

            # === 阶段 4: 行程生成 (流式) ===
            yield sse_event({"type": "phase_start", "phase": "itinerary_generation"})

            # 这里需要修改 generate_itinerary 支持流式输出 (见下文)
            async for token in nlu.adviser.generate_itinerary_stream(...):
                yield sse_event({"type": "token", "delta": token})

            yield sse_event({"type": "phase_end", "phase": "itinerary_generation"})

            # === 阶段 5: Verifier 审查 ===
            if nlu.with_verifier:
                yield sse_event({"type": "phase_start", "phase": "verification"})

                # Verifier 检查
                # ...

                yield sse_event({"type": "phase_end", "phase": "verification"})

            # === 完成 ===
            yield sse_event({
                "type": "end",
                "session_id": session_id,
                "status": "complete"
            })
            yield "data: [DONE]\n\n"

        except Exception as e:
            logger.error(f"流式处理失败: {e}")
            yield sse_event({"type": "error", "message": str(e)})
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


def sse_event(data: dict) -> str:
    """生成 SSE 事件字符串"""
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
```

#### 方案 B: 完全流式输出（长期）

**优点**: 最佳用户体验，逐 token 流式

**实现**: 修改 `generate_itinerary` 支持流式输出

```python
# adviser_itinerary.py - 修改 generate_itinerary

async def generate_itinerary_stream(
    self,
    llm,
    intent_parsed,
    context_summary,
    plan_steps,
    final_aggregation
) -> AsyncGenerator[str, None]:
    """
    流式生成行程规划

    Yields:
        str: 每次生成的 token
    """
    # 构建 prompt
    itinerary_prompt = build_itinerary_prompt(
        intent_parsed,
        context_summary,
        plan_steps,
        final_aggregation
    )

    # 使用 LLM 的流式 API
    async for chunk in llm.ask_text_stream(
        itinerary_prompt,
        temperature=0.6,
        max_tokens=12000
    ):
        yield chunk
```

**需要修改 `model_definition.py`**:

```python
# source/model_definition.py

class LLMWrapper:
    async def ask_text_stream(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 2000
    ) -> AsyncGenerator[str, None]:
        """
        流式调用 LLM，逐 token 返回

        Yields:
            str: 每次生成的文本 chunk
        """
        messages = [{"role": "user", "content": prompt}]

        try:
            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,  # 启用流式输出
            )

            async for chunk in response:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        except Exception as e:
            logger.error(f"流式 LLM 调用失败: {e}")
            raise
```

### 2.4 前后端集成

**前端调用示例** (JavaScript):

```javascript
async function streamNLU(text, sessionId) {
    const response = await fetch('http://localhost:8010/nlu/simple/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text, session_id: sessionId })
    });

    const reader = response.body.getReader();
    const decoder = new TextDecoder();

    while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value);
        const lines = chunk.split('\n\n');

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
                        console.log('完成');
                        break;
                    case 'error':
                        console.error('错误:', event.message);
                        break;
                }
            }
        }
    }
}
```

---

## 阶段 3: 其他优化建议

### 3.1 减少 generate_itinerary 的 max_tokens

**当前**: `max_tokens=12000` (耗时 5-10 秒)

**优化**: 根据行程天数动态调整

```python
# adviser_itinerary.py

def calculate_max_tokens(duration: int) -> int:
    """
    根据行程天数计算合理的 max_tokens

    估算: 每天需要 800-1000 tokens (约 120-150 字中文)
    """
    base_tokens = 2000  # 基础部分 (标题、介绍、总结)
    tokens_per_day = 1000

    max_tokens = base_tokens + (duration * tokens_per_day)

    # 限制在合理范围内
    return min(max(max_tokens, 4000), 12000)


# 在 generate_itinerary 中使用
max_tokens = calculate_max_tokens(intent_parsed.get("duration", 3))
markdown = await adviser.ask_text(
    itinerary_prompt,
    temperature=0.6,
    max_tokens=max_tokens  # 动态调整
)
```

**预期效果**:

- 3 天行程: 5000 tokens → 耗时 3-5 秒 (节省 2-5 秒)
- 7 天行程: 9000 tokens → 耗时 4-8 秒 (节省 1-2 秒)

### 3.2 调整 Verifier 重试策略

**当前**: `max_retries=3` (最坏情况 88 秒)

**优化 1: 减少重试次数**

```python
# fastapi_server.py
SESSIONS[sid] = NLU(
    log_folder="log",
    file_name=sid,
    with_verifier=True,
    max_retries=1  # 从 3 降低到 1
)
```

**优化 2: 增量重试**

不重新生成整个行程，只修复检测到的问题：

```python
# NLU_module/main.py

async def incremental_fix(response, issue):
    """
    增量修复 Verifier 检测到的问题

    而不是完整重新生成
    """
    # 只调用 LLM 修复特定问题
    fix_prompt = f"""
    检测到行程中的问题: {issue}

    请修复以下行程中的问题 (只输出修复后的部分):
    {response}
    """

    fixed_part = await self.adviser.llm.ask_text(fix_prompt, max_tokens=2000)

    # 合并修复
    return merge_fix(response, fixed_part)
```

### 3.3 增加超时时间 (Quick Fix)

**当前**: `REQUEST_TIMEOUT = 28.0`

**优化**: 考虑 Verifier 重试的情况

```python
# fastapi_server.py

# 方案 1: 固定增加到 60s
REQUEST_TIMEOUT = 60.0

# 方案 2: 根据是否启用 Verifier 动态调整
REQUEST_TIMEOUT = 60.0 if WITH_VERIFIER else 30.0
```

**注意**: 需要同步修改 backend 的超时设置

---

## 实施计划

### Phase 1: 并发调用优化 (立即实施)

**时间**: 1-2 天

**任务**:

1. ✅ 修改 `adviser_main.py` - 并发执行 3 个独立调用
2. ✅ 添加错误处理和日志
3. ✅ 本地测试验证性能提升
4. ✅ 部署到开发环境

**预期效果**: 节省 4-6 秒

### Phase 2: 渐进式流式输出 (1 周)

**时间**: 1 周

**任务**:

1. ✅ 实现 `/nlu/simple/stream` 端点 (方案 A)
2. ✅ 分阶段发送 SSE 事件
3. ✅ 前端适配流式接口
4. ✅ 测试和优化

**预期效果**: 用户体验大幅提升

### Phase 3: 完全流式输出 (2-3 周)

**时间**: 2-3 周

**任务**:

1. ✅ 实现 `LLMWrapper.ask_text_stream()`
2. ✅ 修改 `generate_itinerary` 支持流式
3. ✅ 完整的逐 token 流式输出
4. ✅ 性能测试和调优

**预期效果**: 最佳用户体验

### Phase 4: 其他优化 (持续)

**任务**:

1. ✅ 动态调整 max_tokens
2. ✅ 优化 Verifier 重试策略
3. ✅ 调整超时设置
4. ✅ 监控和日志优化

---

## 测试策略

### 单元测试

```python
# tests/test_concurrent_calls.py

import asyncio
import pytest
from NLU_module.agents.adviser.adviser_main import Adviser

@pytest.mark.asyncio
async def test_concurrent_generation():
    """测试并发调用是否正常工作"""
    adviser = Adviser(llm=...)

    intent_parsed = {...}
    user_input = "..."
    doc_summaries = [...]

    # 并发执行
    context_task = adviser.run_context_summary(adviser.llm, user_input, doc_summaries)
    plan_task = adviser.run_plan_actions(adviser.llm, intent_parsed)
    aggregate_task = adviser.run_aggregate(adviser.llm, [], intent_parsed)

    results = await asyncio.gather(
        context_task,
        plan_task,
        aggregate_task,
        return_exceptions=True,
    )

    # 验证结果
    assert all(not isinstance(r, Exception) for r in results)
    assert len(results) == 3


@pytest.mark.asyncio
async def test_streaming_output():
    """测试流式输出"""
    adviser = Adviser(llm=...)

    tokens = []
    async for token in adviser.generate_itinerary_stream(...):
        tokens.append(token)

    # 验证流式输出
    assert len(tokens) > 0
    full_text = ''.join(tokens)
    assert len(full_text) > 100
```

### 性能测试

```python
# tests/test_performance.py

import time
import pytest

@pytest.mark.asyncio
async def test_performance_improvement():
    """验证并发调用的性能提升"""

    # 串行执行
    start = time.time()
    await sequential_execution()
    sequential_time = time.time() - start

    # 并发执行
    start = time.time()
    await concurrent_execution()
    concurrent_time = time.time() - start

    # 验证性能提升
    improvement = sequential_time - concurrent_time
    assert improvement > 3, f"Expected >3s improvement, got {improvement:.2f}s"

    print(f"性能提升: {improvement:.2f} 秒")
```

### 集成测试

```bash
# 测试流式接口
curl -N -X POST "http://localhost:8010/nlu/simple/stream" \
     -H "Content-Type: application/json" \
     -d '{
       "text": "规划一个4天的巴黎行程，预算8000元"
     }'
```

---

## 监控和日志

### 性能监控

```python
# 在关键路径添加性能监控

import time
from functools import wraps

def monitor_performance(phase_name: str):
    """性能监控装饰器"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start = time.time()
            try:
                result = await func(*args, **kwargs)
                elapsed = time.time() - start
                logger.info(f"[PERF] {phase_name}: {elapsed:.2f}s")
                return result
            except Exception as e:
                elapsed = time.time() - start
                logger.error(f"[PERF] {phase_name} FAILED after {elapsed:.2f}s: {e}")
                raise
        return wrapper
    return decorator


# 使用示例
@monitor_performance("context_summary")
async def run_context_summary(llm, user_input, doc_summaries):
    # ...
```

### 日志增强

```python
# 在 fastapi_server.py 添加请求级别的日志

@app.post("/nlu/simple/stream")
async def nlu_simple_stream(request: NLURequest):
    request_id = str(uuid4())[:8]
    logger.info(f"[{request_id}] 开始处理流式请求: {request.text[:50]}...")

    start_time = time.time()

    async def generate_events():
        try:
            # ... 处理逻辑 ...

            elapsed = time.time() - start_time
            logger.info(f"[{request_id}] 完成处理，总耗时: {elapsed:.2f}s")

        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"[{request_id}] 处理失败，耗时: {elapsed:.2f}s, 错误: {e}")

    return StreamingResponse(generate_events(), ...)
```

---

## 风险和缓解

### 风险 1: 并发调用导致 API 限流

**风险**: 并发请求可能触发 Azure OpenAI 的速率限制

**缓解**:

- 监控 429 错误
- 实现指数退避重试
- 调整并发数量

```python
# 添加重试逻辑
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10)
)
async def call_llm_with_retry(llm, prompt, **kwargs):
    return await llm.ask_text(prompt, **kwargs)
```

### 风险 2: 流式输出中断

**风险**: 客户端断开连接导致流式输出中断

**缓解**:

- 捕获 `asyncio.CancelledError`
- 清理资源
- 日志记录

```python
async def generate_events():
    try:
        # ... 流式输出 ...
    except asyncio.CancelledError:
        logger.warning(f"客户端断开连接，停止流式输出")
        # 清理资源
        raise
```

### 风险 3: 向后兼容性

**风险**: 新接口可能破坏现有集成

**缓解**:

- 保留原有 `/nlu/simple` 接口
- 新增 `/nlu/simple/stream` 接口
- 前端渐进式迁移

---

## 总结

### 预期性能提升

| 优化项 | 节省时间 | 实施难度 | 优先级 |
|--------|----------|----------|--------|
| 并发执行 3 个 LLM 调用 | 4-6 秒 | 低 | 🔴 高 |
| 动态调整 max_tokens | 1-5 秒 | 低 | 🟡 中 |
| 减少 Verifier 重试 | 20-40 秒 | 低 | 🔴 高 |
| 增加超时时间 | - | 低 | 🔴 高 |
| 渐进式流式输出 | 用户体验 | 中 | 🟡 中 |
| 完全流式输出 | 用户体验 | 高 | 🟢 低 |

### 最终效果

**阶段 1 完成后** (并发调用 + Quick Fix):

- 正常流程: **11-16 秒** (原 17-22 秒)
- 一次 Verifier 重试: **22-32 秒** (原 44 秒) ✅ 不超时
- 超时限制: **60 秒**

**阶段 2 完成后** (流式输出):

- 用户在 **2-3 秒内** 看到第一个结果
- 边等待边看到行程逐步生成
- 总体用户体验提升 **80%+**

### 下一步行动

1. **立即**: 实施阶段 1 (并发调用优化)
2. **本周**: 增加超时时间 + 减少 Verifier 重试
3. **下周**: 启动阶段 2 (渐进式流式输出)
4. **本月**: 完成性能测试和监控
