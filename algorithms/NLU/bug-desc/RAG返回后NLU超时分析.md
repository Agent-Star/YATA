# NLU 处理超时问题深入分析

## 问题现象

RAG 成功返回 50 条结果后，NLU 仍然在 28 秒超时限制内无法完成处理。

## 根本原因：串行 LLM 调用累积延迟 + Verifier 重试雪崩

### 完整的 LLM 调用链路

#### 阶段 1: Intent Parsing (`run_intent_parsing`)

- **调用 1**: `prompt_parse_intent` - 意图识别 (~1-2s)
- **调用 2**: `prompt_normalize_date` - 日期规范化 (~1-2s, 条件执行)
- **调用 3**: `prompt_clarify` - 缺失信息澄清 (~1-2s, 条件执行)
- **调用 4**: `prompt_query_rewrite` - 查询改写 (~1-2s)

**小计: 2-4 个 LLM 调用, 4-8 秒**

#### 阶段 2: RAG 检索

- **调用 5**: RAG API 调用 (~1-3s, 非 LLM 但也耗时)

**小计: 1-3 秒**

#### 阶段 3: 内容生成 (`generate_response` 后续)

- **调用 6**: `run_context_summary` - 上下文摘要 (~1-2s)
- **调用 7**: `run_plan_actions` - 计划步骤 (~1-2s)
- **调用 8**: `run_aggregate` - 最终聚合 (~1-2s)
- **调用 9**: `generate_itinerary` - **行程生成 (~5-10s, max_tokens=12000!)**

**小计: 4 个 LLM 调用, 8-16 秒**

#### 阶段 4: Verifier 审查

- **调用 10**: `assess_cur_response` - 逻辑审查 (~1-2s)

**小计: 1 个 LLM 调用, 1-2 秒**

---

### 时间估算

**最佳情况** (无日期规范化, 无 clarification, 无 Verifier 重试):

- Intent Parsing: 4s (2 个调用)
- RAG: 2s
- Content Generation: 10s (4 个调用, 含 itinerary 5s)
- Verifier: 1.5s
- **总计: ~17.5 秒** ✅ 未超时

**一般情况** (含日期规范化, 无 Verifier 重试):

- Intent Parsing: 6s (3 个调用)
- RAG: 2s
- Content Generation: 12s (4 个调用, 含 itinerary 7s)
- Verifier: 2s
- **总计: ~22 秒** ✅ 未超时但接近上限

**触发超时情况** (Verifier 检测到问题, 触发 1 次重试):

- 初次生成: 22s
- Verifier 重试: 再次调用 `generate_response` (20s) + Verifier (2s)
- **总计: 22 + 22 = 44 秒** ❌ **超时！**

**最坏情况** (Verifier 重试 3 次):

- 初次: 22s
- 重试 1: 22s
- 重试 2: 22s
- 重试 3: 22s
- **总计: 88 秒** ❌ **严重超时！**

---

## 关键瓶颈分析

### 1. `generate_itinerary` 是最大性能瓶颈 🔴

**位置**: `adviser_itinerary.py:80`

```python
markdown = await adviser.ask_text(itinerary_prompt, temperature=0.6, max_tokens=12000)
```

**问题**:

- `max_tokens=12000`: 生成 1800-2500 字中文 Markdown 长文
- 估计耗时: **5-10 秒**（占单次请求的 30-50%）
- Prompt 包含大量上下文（RAG 结果、票价信息、省钱攻略等）
- 在 Verifier 重试时会**反复执行**

### 2. 串行执行无并发 🔴

所有 LLM 调用都是严格串行的:

```python
# adviser_main.py:100-195
result = await run_intent_parsing(...)          # 等待 4-6s
rag_results = await call_rag_api(...)           # 等待 2s
result["context_summary"] = await run_context_summary(...)  # 等待 1-2s
result["plan_steps"] = await run_plan_actions(...)          # 等待 1-2s
result["final_aggregation"] = await run_aggregate(...)      # 等待 1-2s
result["detailed_itinerary"] = await generate_itinerary(...) # 等待 5-10s
```

**总等待时间 = 所有调用时间之和**

没有使用 `asyncio.gather()` 并发执行可并行的任务。

### 3. Verifier 重试的复合效应 🔴🔴🔴

**位置**: `NLU_module/main.py:112-143`

```python
while not is_safe and retry_count < self.max_retries:
    retry_count += 1
    response = await self.adviser.generate_response(...)  # 完整重新生成！
    explanation, is_safe = await self.verifier.assess_cur_response(response)
```

**问题**:

- 每次重试都会**重新执行 9 个 LLM 调用**
- 每次都会重新生成 **12000 tokens 的行程文本**
- 累积延迟呈**线性增长** (1 次重试 = 2 倍时间, 2 次重试 = 3 倍时间)
- Verifier 默认 `max_retries=3`, 最坏情况下会执行 4 次完整生成

### 4. 超时设置与实际需求的矛盾 🔴

**位置**: `fastapi_server.py:20`

```python
REQUEST_TIMEOUT = 28.0  # 留 2s buffer 给 backend 的 30s 超时
```

**矛盾点**:

- Backend 超时: 30s
- NLU 超时: 28s
- 实际需求:
  - 正常流程 (无重试): 17-22s ✅ (勉强够用)
  - 一次 Verifier 重试: 35-44s ❌ (必定超时)
  - 两次重试: 55-66s ❌ (远超限制)

**设计缺陷**: 超时时间没有考虑 Verifier 重试的情况。

---

## 为什么 "RAG 返回后仍然超时"？

从图片日志可以清楚看到时间线:

```
0s   - 开始处理 NLU 请求
1-6s - Intent Parsing (4 个 LLM 调用)
       • intent_parsed
       • 日期规范化
       • query_rewrite

7-9s - RAG 调用
       ✅ "RAG 调用成功: 获取到 50 条结果"  <-- RAG 在这里成功返回

10-12s - context_summary (LLM 调用 6)
13-15s - plan_steps (LLM 调用 7)
16-18s - final_aggregation (LLM 调用 8)

19-28s - generate_itinerary (LLM 调用 9) ⚠️ **耗时最长的步骤**
         • max_tokens=12000
         • 生成 1800-2500 字 Markdown
         • 包含详细的每日行程规划

29-30s - Verifier.assess_cur_response (LLM 调用 10)

>>> 如果 Verifier 返回 is_safe=False:
31-50s - 重新调用 generate_response (完整重复上述流程)
51-52s - 再次 Verifier

>>> 总计: ~52s ❌ 超过 28s 限制！
```

**关键点**:

1. RAG 只是整个流程的**第 2 阶段**（仅占总时间的 10-15%）
2. RAG 返回后，还有 **4 个 LLM 调用**要执行
3. 其中 `generate_itinerary` 是**最耗时的步骤**（5-10 秒）
4. 如果 Verifier 检测到问题，会触发**完整的重新生成**

---

## 触发条件

超时发生需要满足以下条件之一:

1. **Verifier 触发重试** (最常见)
   - Verifier 检测到逻辑问题：
     - 日期不一致 (开始日期晚于结束日期)
     - 行程天数与日期区间不符
     - 预算不合理 (负数或极端值)
     - 出发地与目的地相同
     - 其他逻辑矛盾
   - 触发 1-3 次重试
   - 累积时间超过 28 秒

2. **LLM API 响应慢** (偶发)
   - Azure OpenAI 服务端延迟
   - 网络抖动
   - 请求排队
   - 导致某些 LLM 调用耗时超过正常值 (2-3s 变成 5-6s)

3. **生成内容过长** (特定场景)
   - 用户请求较长行程 (7-10 天)
   - `generate_itinerary` 生成更长的 Markdown
   - 实际 tokens 接近 12000 上限
   - 耗时从 5-7s 增加到 10-15s

---

## 代码位置总结

### 超时设置

- `fastapi_server.py:20` - `REQUEST_TIMEOUT = 28.0`
- `fastapi_server.py:66,107` - `async with asyncio.timeout(REQUEST_TIMEOUT)`

### LLM 调用点

- `adviser_intent.py:19,44,53,59` - Intent Parsing 的 4 个调用
- `adviser_rag.py:31` - RAG API 调用
- `adviser_context.py` - context_summary 调用
- `adviser_plan_actions.py` - plan_steps 调用
- `adviser_aggregate.py` - final_aggregation 调用
- `adviser_itinerary.py:80` - **generate_itinerary (max_tokens=12000)** 🔴
- `verifier.py:15,69` - Verifier 的 2 个调用 (初次 + 每次重试)

### Verifier 重试逻辑

- `NLU_module/main.py:11` - `max_retries=3` 参数定义
- `NLU_module/main.py:112-143` - Verifier 重试循环

---

## 可能的解决方案 (供参考)

### 短期方案 (Quick Fix)

1. **增加超时时间**

   ```python
   # fastapi_server.py
   REQUEST_TIMEOUT = 60.0  # 从 28s 增加到 60s
   ```

   - 优点: 简单，立即生效
   - 缺点: 治标不治本，极端情况仍会超时

2. **减少 Verifier 重试次数**

   ```python
   # fastapi_server.py
   SESSIONS[sid] = NLU(log_folder="log", file_name=sid, with_verifier=True, max_retries=1)
   ```

   - 优点: 减少最坏情况的累积延迟
   - 缺点: 降低了行程质量保证

3. **禁用 Verifier** (不推荐)

   ```python
   SESSIONS[sid] = NLU(log_folder="log", file_name=sid, with_verifier=False)
   ```

   - 优点: 消除 Verifier 重试的延迟
   - 缺点: 可能生成不合理的行程

### 中期方案 (Optimization)

4. **减少 generate_itinerary 的 max_tokens**

   ```python
   # adviser_itinerary.py:80
   markdown = await adviser.ask_text(itinerary_prompt, temperature=0.6, max_tokens=6000)
   ```

   - 优点: 直接减少最大瓶颈的耗时
   - 缺点: 可能生成不够详细的行程

5. **并发执行独立的 LLM 调用**

   ```python
   # adviser_main.py:183-189
   context_task = run_context_summary(self.llm, user_input, doc_summaries)
   plan_task = run_plan_actions(self.llm, result["intent_parsed"])
   aggregate_task = run_aggregate(self.llm, [], result["intent_parsed"])

   context, plan, aggregate = await asyncio.gather(context_task, plan_task, aggregate_task)
   ```

   - 优点: 3 个独立调用并发执行，节省 4-6 秒
   - 缺点: 需要重构代码，增加复杂度

### 长期方案 (Architecture)

6. **流式响应 (Streaming)**
   - 使用 SSE (Server-Sent Events) 返回部分结果
   - 用户体验更好 (边生成边展示)
   - Backend 需要支持流式处理

7. **异步任务队列**
   - 将行程生成放入后台任务
   - 立即返回 202 Accepted
   - 前端轮询或 WebSocket 获取结果

8. **缓存机制**
   - 对相似的行程请求使用缓存
   - 减少重复的 LLM 调用
   - 需要设计合适的缓存键和失效策略

---

## 建议

**推荐组合方案**:

1. 短期: 增加超时到 60s + 减少 max_retries 到 1
2. 中期: 减少 max_tokens 到 8000 + 并发执行独立调用
3. 长期: 考虑流式响应或异步任务队列

这样可以在不影响功能的前提下，显著降低超时风险。
