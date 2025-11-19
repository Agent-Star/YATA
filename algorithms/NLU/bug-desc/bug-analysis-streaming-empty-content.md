# Bug分析：NLU流式输出返回空内容导致Backend触发Fallback

**日期**：2025-11-18
**问题模块**：NLU (`algorithms/NLU`)
**影响范围**：recommendation 类型的请求无法正常流式输出
**严重程度**：高

---

## 问题现象

### Backend日志

```
⚠️ PlanStream: NLU returned empty content
⚠️ PlanStream: NLU failed (NLUServiceError: NLU returned empty content), falling back to research-assistant
```

### NLU日志

```
✅ RAG 调用成功: 获取到 1 条结果 (出现两次)
```

### 用户体验

- 用户发送 recommendation 类型的请求（如"推荐巴黎的美食"）
- NLU 成功解析意图并调用 RAG
- **但 Backend 判定为空内容，触发 fallback 到 research-assistant**
- 用户最终得到的是 research-assistant 的回复，而非 NLU+RAG 的专业推荐

---

## 根本原因分析

### 问题定位

**文件**：`algorithms/NLU/fastapi_server.py`
**函数**：`nlu_simple_stream()` (第 223-407 行)
**问题代码**：第 367-379 行

```python
# === 阶段 4: 行程生成 (流式) ===
if task_type == "itinerary":  # ⚠️ 只处理 itinerary 类型
    yield _sse_event({"type": "phase_start", "phase": "itinerary_generation"})

    async for token in generate_itinerary_stream(...):
        yield _sse_event({"type": "token", "delta": token})

    yield _sse_event({"type": "phase_end", "phase": "itinerary_generation"})

# === 完成 ===
yield _sse_event({"type": "end", "session_id": sid, "status": "complete"})
yield "data: [DONE]\n\n"
```

### 问题分析

1. **只处理 itinerary 类型**：
   - 流式输出只在 `task_type == "itinerary"` 时执行
   - 对于 `task_type == "recommendation"` 或其他类型，**直接跳过流式输出**
   - 直接发送 `end` 事件和 `[DONE]` 标记

2. **Backend 收不到 token 事件**：
   - Backend 的 `planner_routes.py:240-244` 只收集 `type == "token"` 的事件
   - 如果没有任何 token 事件，`full_content` 保持为空字符串
   - 触发第 257-259 行的空内容检查：

     ```python
     if not full_content:
         logger.warning("PlanStream: NLU returned empty content")
         raise NLUServiceError("NLU returned empty content")
     ```

3. **Fallback 被错误触发**：
   - Backend 认为 NLU 返回空内容
   - 触发 fallback 到 research-assistant
   - 用户得不到基于 RAG 的专业推荐

---

## 模块责任划分

### NLU 模块的问题 ✗

- **缺失功能**：recommendation 类型没有实现流式输出
- **不完整的实现**：只实现了 itinerary 的流式，忽略了其他类型
- **文件**：`fastapi_server.py`

### Backend 模块是否有问题？✓

- Backend 的逻辑是**正确的**：
  - 期望 NLU 流式返回 token 事件
  - 检查内容是否为空是合理的
  - Fallback 机制设计正确

### RAG 模块是否有问题？✓

- RAG 模块是**正确的**：
  - 成功返回了检索结果
  - NLU 日志显示 "RAG 调用成功: 获取到 1 条结果"

**结论**：问题完全出在 **NLU 模块**。

---

## 当前实现分析

### 1. itinerary 类型的流式实现

**文件**：`NLU_module/agents/adviser/adviser_itinerary.py`
**函数**：`generate_itinerary_stream()`

- 使用 LLM 的流式 API 生成行程
- 逐 token yield，实现真正的流式输出

### 2. recommendation 类型的实现

**文件**：`NLU_module/agents/adviser/adviser_recommendation.py`
**函数**：`generate_recommendations()`

- **问题**：这是一个普通的 async 函数，**不是生成器**
- 一次性生成完整的 JSON 结构推荐
- 然后调用 `adviser.ask_text()` 生成自然语言摘要
- **没有流式输出能力**

---

## 修复方案

### 方案 A：为 recommendation 创建流式生成函数 ⭐ 推荐

**优点**：

- 真正的流式输出，用户体验最好
- 与 itinerary 实现一致
- 充分利用 LLM 流式 API

**缺点**：

- 需要修改 `adviser_recommendation.py`
- 工作量稍大

**实施步骤**：

1. 在 `adviser_recommendation.py` 中创建 `generate_recommendations_stream()` 函数
2. 使用 LLM 的流式 API 直接生成自然语言推荐（跳过 JSON 中间步骤）
3. 在 `fastapi_server.py` 中调用流式函数

### 方案 B：在 fastapi_server 中处理非流式输出

**优点**：

- 不需要修改 `adviser_recommendation.py`
- 实现简单快速

**缺点**：

- 不是真正的流式输出，只是模拟
- 用户体验不如方案 A

**实施步骤**：

1. 调用原有的 `generate_recommendations()`
2. 获取完整的 `natural_summary`
3. 手动分块并逐个 yield token 事件

---

## 推荐修复方案：方案 A（真正的流式输出）

### 修改 1：创建流式推荐生成函数

**文件**：`NLU_module/agents/adviser/adviser_recommendation.py`

添加新函数：

```python
async def generate_recommendations_stream(llm, intent_result, rag_results=None, debug=False):
    """
    流式生成推荐内容

    Args:
        llm: LLM 实例
        intent_result: 意图解析结果
        rag_results: RAG 检索结果
        debug: 调试模式

    Yields:
        str: 逐 token 生成的推荐内容
    """
    rag_results = rag_results or []
    intent = intent_result.get("intent_parsed", {})

    # ... 构建 prompt（复用现有逻辑）...

    # 使用流式 API 生成推荐
    async for token in llm.astream_text(prompt, temperature=0.7, max_tokens=6000):
        yield token
```

### 修改 2：支持所有类型的流式输出

**文件**：`fastapi_server.py`

```python
# === 阶段 4: 内容生成 (流式) ===
if task_type == "itinerary":
    yield _sse_event({"type": "phase_start", "phase": "itinerary_generation"})

    async for token in generate_itinerary_stream(...):
        yield _sse_event({"type": "token", "delta": token})

    yield _sse_event({"type": "phase_end", "phase": "itinerary_generation"})

elif task_type == "recommendation":
    yield _sse_event({"type": "phase_start", "phase": "recommendation_generation"})

    async for token in generate_recommendations_stream(...):
        yield _sse_event({"type": "token", "delta": token})

    yield _sse_event({"type": "phase_end", "phase": "recommendation_generation"})

else:
    # 其他类型（如闲聊、追问等）也应该有基本的文本输出
    # TODO: 根据实际需求决定如何处理
    pass

# === 完成 ===
yield _sse_event({"type": "end", "session_id": sid, "status": "complete"})
yield "data: [DONE]\n\n"
```

---

## 预期效果

### ✅ 修复后的行为

1. **recommendation 类型请求**：
   - NLU 流式输出推荐内容
   - Backend 实时转发 token 给前端
   - 用户看到逐字渲染
   - 历史记录完整保存

2. **itinerary 类型请求**：
   - 保持原有流式输出
   - 行为不变

3. **Backend 不再误触发 fallback**：
   - 所有类型都有 token 输出
   - `full_content` 不再为空
   - Fallback 只在真正失败时触发

---

## 测试计划

### 测试场景

1. **recommendation - 美食推荐**：
   - 输入："推荐巴黎的美食"
   - 预期：流式输出餐厅推荐

2. **recommendation - 景点推荐**：
   - 输入："巴黎有什么好玩的？"
   - 预期：流式输出景点推荐

3. **recommendation - 酒店推荐**：
   - 输入："巴黎的酒店推荐"
   - 预期：流式输出酒店推荐

4. **itinerary - 行程规划**：
   - 输入："我想去巴黎玩 3 天"
   - 预期：流式输出完整行程（保持原有行为）

5. **历史记录检查**：
   - 所有类型的对话都应该正确保存
   - 刷新页面后能看到完整历史

---

## 后续优化建议

1. **统一流式输出接口**：
   - 为所有 adviser 模块提供统一的流式接口
   - 减少重复代码

2. **添加流式输出测试**：
   - 单元测试验证流式生成器
   - 集成测试验证端到端流式

3. **性能监控**：
   - 记录流式输出的首 token 延迟
   - 监控总体生成时间

4. **错误处理增强**：
   - 流式生成中断时的处理
   - 部分内容已发送时的重试策略

---

## 相关文档

- Backend 修复文档：`backend/bug-desc/streaming-failure-root-cause.md`
- Backend Message ID 修复：`backend/bug-desc/message-id-and-fallback-history-fix.md`
- 测试指南：`backend/bug-desc/testing-guide.md`
