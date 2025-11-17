# NLU 服务完全异步架构重构方案

> **基于前序分析**: 本方案基于 `service-freeze-analysis-and-fix-plan.md` 中的问题分析, 采用"长痛不如短痛"的策略, 直接进行完全异步架构重构.

## 核心策略

**放弃保守的同步端点方案**, 直接重构为完全异步架构, 从根本上解决事件循环阻塞问题, 并为未来的高并发场景打下坚实基础.

## Backend 集成分析 (基于 dev 分支)

### Backend 如何调用 NLU

通过分析 `backend/src/external_services/nlu_client.py` 和 `backend/src/agents/travel_planner.py`, 发现:

1. **Backend 使用完全异步调用**:

   ```python
   # backend/src/external_services/nlu_client.py:62-66
   self._client = httpx.AsyncClient(
       base_url=self.base_url,
       timeout=httpx.Timeout(self.timeout),  # 30 秒
   )
   ```

2. **Backend 传递 thread_id 作为 session_id**:

   ```python
   # backend/src/agents/travel_planner.py:73-82
   session_id = config.get("configurable", {}).get("thread_id")
   async with get_nlu_client() as nlu_client:
       nlu_response = await nlu_client.call_nlu(
           text=user_input,
           session_id=session_id,
       )
   ```

3. **Backend 期望的超时时间**:

   ```python
   # backend/src/core/settings.py:135-137
   NLU_SERVICE_URL: str = "http://localhost:8010"
   NLU_TIMEOUT: float = 30.0
   NLU_MAX_RETRIES: int = 1
   ```

### 关键洞察

- **Backend 已经是完全异步的**, 期望 NLU 能够快速响应 (30 秒内)
- **session_id 与 backend 的 thread_id 绑定**, 意味着 session 的生命周期应该与 backend 的 thread 一致
- **Backend 有 thread_manager.py** (backend/src/service/thread_manager.py), 管理 thread 的创建和清理

## 重构目标

### 阶段 1: 核心问题修复 (Critical, 2-3 天)

1. ✅ **修复 Verifier 无限循环** - 添加最大重试次数 (3 次)
2. ✅ **完全异步化 NLU 调用链** - 从 FastAPI 端点到 RAG 调用, 全部异步
3. ✅ **RAG 模型预加载** - 在 startup_event 中强制加载模型
4. ✅ **添加请求级别超时保护** - 使用 asyncio.timeout()

### 阶段 2: 性能与稳定性优化 (Medium, 1-2 天)

5. ✅ **Session 清理机制** - 与 backend thread 协调的过期清理
6. ✅ **异步日志记录** - 使用 aiofiles 替换同步文件 I/O
7. ✅ **连接池优化** - 复用 httpx.AsyncClient

---

## 详细实现方案

### 1. 修复 Verifier 无限循环

**文件**: `NLU_module/main.py`

**修改位置**: 第 108-136 行

**修改内容**:

```python
# 调用 Verifier 审查
task_type = response.get("intent_parsed", {}).get("task_type", "")
if self.with_verifier and task_type == "itinerary":
    explanation, is_safe = self.verifier.assess_cur_response(response)
    with open(self.log_path, "a+", encoding="utf-8") as f:
        f.write("\n&&&&&&&&&&&&&&&&&&&&&&& Safety Check &&&&&&&&&&&&&&&&&&&&&&&\n")
        f.write(f"Safety: {is_safe}\nExplanation: {explanation}\n")

    # 🔧 添加最大重试次数限制
    max_retries = 3
    retry_count = 0

    while not is_safe and retry_count < max_retries:
        retry_count += 1
        print(f"⚠️ Verifier 检测到问题 (尝试 {retry_count}/{max_retries}), 正在重新生成...")

        revision_prompt = f"""原始用户请求: {user_input}

请根据以下问题修正之前的计划:
{explanation}

请保持原始请求的意图 (task_type, 目的地, 天数, 预算等), 只修正检测到的问题."""

        # 重新生成时也传递历史对话
        conversation_history = []
        if self.history:
            for h in self.history:
                conv_turn = {
                    "user": h.get("user", ""),
                    "response": {
                        "intent_parsed": h.get("response", {}).get("intent_parsed", {})
                    },
                }
                conversation_history.append(conv_turn)

        response = self.adviser.generate_response(
            revision_prompt,
            conversation_history=conversation_history,
            use_rag=True,
            rag_top_k=25,
            debug=False,
        )
        explanation, is_safe = self.verifier.assess_cur_response(response)

        with open(self.log_path, "a+", encoding="utf-8") as f:
            f.write(
                f"\n----------------------- Regenerated Response (尝试 {retry_count}) -----------------------\n{json.dumps(response, ensure_ascii=False, indent=2)}\n"
            )
            f.write(f"Safety: {is_safe}\nExplanation: {explanation}\n")

    # 🔧 如果达到最大重试次数仍不安全, 记录警告但继续返回
    if not is_safe:
        print(f"⚠️ 警告: 经过 {max_retries} 次重试, Verifier 仍认为不安全, 但已达到最大重试次数")
        with open(self.log_path, "a+", encoding="utf-8") as f:
            f.write(f"\n⚠️ 警告: 达到最大重试次数, 返回当前结果\n")
else:
    print("Recommendation-type task detected: Skipping Verifier check.")
```

---

### 2. 完全异步化 NLU 调用链

这是最核心的重构, 需要修改多个文件.

#### 2.1 异步化 RAG 调用

**文件**: `NLU_module/agents/adviser/adviser_rag.py`

**依赖**: 需要安装 `httpx` (已在 backend 中使用, 可复用)

**完整替换**:

```python
# adviser_rag.py
import os
from typing import Any

import httpx


async def call_rag_api(query: str, city: str = "", top_k: int = 25, debug: bool = False) -> list[dict[str, Any]]:
    """
    异步调用 RAG API

    Args:
        query: 查询文本
        city: 城市名称
        top_k: 返回结果数量
        debug: 是否打印调试信息

    Returns:
        RAG 检索结果列表
    """
    rag_url = os.getenv("RAG_API_URL", "http://127.0.0.1:8001/search")
    payload = {"query": query, "city": city or "", "top_k": int(top_k)}

    # 总是打印 RAG 调用信息
    print(f"🔍 正在调用 RAG API: {rag_url}")
    print(f"   Query: {query[:100]}{'...' if len(query) > 100 else ''}")
    print(f"   City: {city or '(未指定)'}, Top-K: {top_k}")

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(rag_url, json=payload, timeout=15.0)
            resp.raise_for_status()
            data = resp.json() if resp.content else {}
            results = data.get("results", [])
            if not results and "contexts" in data:
                results = [{"title": "RAG Context", "content": data["contexts"]}]

            # 总是打印结果数量
            if results:
                print(f"✅ RAG 调用成功: 获取到 {len(results)} 条结果")
                if debug:
                    for i, r in enumerate(results[:3], 1):
                        title = r.get("title", "无标题")
                        content_preview = r.get("content", "")[:100]
                        print(f"   [{i}] {title}: {content_preview}...")
            else:
                print("⚠️ RAG 调用成功但未返回结果 (可能数据库为空或查询无匹配)")
            return results

    except httpx.ConnectError as e:
        print(f"❌ RAG API 连接失败: 无法连接到 {rag_url}")
        print("   请确认 RAG 服务是否在运行 (默认端口 8001)")
        if debug:
            print(f"   错误详情: {e}")
        return []

    except httpx.TimeoutException as e:
        print("❌ RAG API 请求超时 (>15 秒)")
        if debug:
            print(f"   错误详情: {e}")
        return []

    except Exception as e:
        print(f"❌ RAG 调用失败: {type(e).__name__}: {e}")
        if debug:
            import traceback
            traceback.print_exc()
        return []
```

**类型标注说明**: 使用 `list[dict[str, Any]]` 而不是 `List[Dict[str, Any]]`, 符合 Python 3.10+ 的现代类型标注风格.

#### 2.2 异步化 LLM 调用

**文件**: `NLU_module/source/model_definition.py` (需要查看具体实现)

假设当前使用的是 OpenAI SDK, 需要将同步调用改为异步:

**修改前**:

```python
# 同步调用
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[...],
)
```

**修改后**:

```python
# 异步调用
response = await client.chat.completions.create(
    model="gpt-4o",
    messages=[...],
)
```

**注意**: 需要确保使用的是 `AsyncOpenAI` 客户端:

```python
from openai import AsyncOpenAI

client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
```

#### 2.3 异步化 Adviser

**文件**: `NLU_module/agents/adviser/adviser_main.py`

**修改策略**: 将所有方法改为 async, 并在调用 RAG 和 LLM 时使用 await.

**关键修改**:

```python
# adviser_main.py

class Adviser:
    def __init__(self, model_name="gpt4o"):
        self.llm = AdviserBase(model_name)
        self.memory: dict[str, Any] = {}
        self.clarifier = Clarifier()

    async def generate_response(  # 🔧 改为 async
        self,
        user_input: str,
        conversation_history: list | None = None,
        use_rag: bool = True,
        rag_top_k: int = 5,
        debug: bool = False,
        skip_clarifier: bool = False,
    ) -> dict[str, Any]:
        """
        异步生成响应

        Args:
            conversation_history: 历史对话列表, 格式为 [{"user": "用户输入", "response": {...}}, ...]
        """
        import time
        t0 = time.time()

        # 1) parse intent for current user input
        result = (
            await run_intent_parsing(self.llm, user_input, conversation_history, debug) or {}  # 🔧 加 await
        )
        intent_cur = result.get("intent_parsed", {})

        # 2️⃣ 合并历史上下文
        intent_merged = merge_partial(self.memory, intent_cur)
        if not skip_clarifier:
            clarify_result = self.clarifier.clarify(user_input, intent_merged)
            if not clarify_result["is_complete"]:
                self.memory = clarify_result["revised_intent"]
                return {
                    "need_more_info": True,
                    "follow_up": clarify_result["follow_up"],
                    "intent_parsed": clarify_result["revised_intent"],
                }

            # 信息完整, 更新 memory
            self.memory = clarify_result["revised_intent"]
            result["intent_parsed"] = self.memory
        else:
            # 跳过 Clarifier, 直接用上次记忆
            result["intent_parsed"] = self.memory

        task_type = result["intent_parsed"].get("task_type", "itinerary")

        # RAG
        if use_rag:
            city_list = result["intent_parsed"].get("dest_pref", [])
            city_raw = city_list[0] if city_list else ""
            rewrite_alias = result.get("query_rewrite", {}).get("city_alias", [])
            city_alias = rewrite_alias[0] if rewrite_alias else ""
            city_map = {
                "巴黎": "Paris",
                "伦敦": "London",
                # ... (保持不变)
            }
            city = city_alias or city_map.get(city_raw, city_raw)

            task_type = result["intent_parsed"].get("task_type", "itinerary")
            tags = result["intent_parsed"].get("tags", []) or []
            subtype = result["intent_parsed"].get("subtype", "")
            keywords = result.get("query_rewrite", {}).get("keywords", [])

            if task_type == "itinerary":
                query_text = f"{city} attractions restrants hotels travel guide"
            elif task_type == "recommendation":
                category = subtype or (tags[0] if tags else "attractions")
                query_text = f"{city} {category} recommendations"
            elif task_type == "qa":
                query_text = user_input.strip()
            else:
                query_text = (
                    " ".join(keywords).strip() or user_input.strip() or "travel guide"
                )

            if debug:
                print(
                    f"🧭 [RAG Query 构造] 类型={task_type}, Query={query_text}, 城市={city}"
                )

            rag_results = await call_rag_api(query_text, city, rag_top_k, debug)  # 🔧 加 await

            if debug:
                print(f"🔍 [RAG 精简查询] Query: {query_text}")
                print(f"✅ RAG 返回 {len(rag_results)} 条结果")

            doc_summaries = [f"{r['title']}: {r['content'][:200]}" for r in rag_results]
        else:
            doc_summaries, rag_results = ["No external context."], []

        result["context_summary"] = await run_context_summary(  # 🔧 加 await
            self.llm, user_input, doc_summaries
        )
        result["plan_steps"] = await run_plan_actions(self.llm, result["intent_parsed"])  # 🔧 加 await
        result["final_aggregation"] = await run_aggregate(  # 🔧 加 await
            self.llm, [], result["intent_parsed"]
        )

        # itinerary only if itinerary task
        if task_type == "itinerary":
            result["detailed_itinerary"] = await generate_itinerary(  # 🔧 加 await
                self.llm, result, rag_results, debug
            )
        elif task_type == "recommendation":
            subtype = result["intent_parsed"].get("subtype", "")
            result["recommendations"] = await generate_recommendations(  # 🔧 加 await
                self.llm, result, rag_results, debug=debug
            )
            result["final_output_type"] = f"recommendation_{subtype or 'general'}"

        result["latency_sec"] = round(time.time() - t0, 2)
        return result
```

**注意**: 所有被 `generate_response` 调用的函数也需要改为 async:

- `run_intent_parsing`
- `run_context_summary`
- `run_plan_actions`
- `run_aggregate`
- `generate_itinerary`
- `generate_recommendations`

这些函数的具体实现需要逐一检查并异步化.

#### 2.4 异步化 Verifier

**文件**: `NLU_module/agents/verifier.py`

**修改策略**: 将 `assess_cur_response` 方法改为 async.

```python
# verifier.py

class Verifier:
    def __init__(self):
        # ... (保持不变)
        pass

    async def assess_cur_response(self, response: dict) -> tuple[str, bool]:  # 🔧 改为 async
        """
        异步评估响应的安全性

        Returns:
            (explanation, is_safe): 评估说明和是否安全
        """
        # ... (LLM 调用改为 await)
        # 具体实现取决于当前的 LLM 调用方式
        pass
```

#### 2.5 异步化 NLU 主类

**文件**: `NLU_module/main.py`

**修改策略**: 将 `run` 方法改为 async.

```python
# main.py

class NLU:
    def __init__(self, log_folder="log", file_name="0", with_verifier=True):
        # ... (保持不变)
        pass

    async def run(self, contents: str, context: dict | None = None) -> dict[str, Any]:  # 🔧 改为 async
        """
        异步运行 NLU 处理

        Args:
            contents: 用户输入
            context: 上下文信息 (可选)

        Returns:
            处理结果
        """
        user_input = contents

        print("________________________________________")
        print(f"🧠 User Input: {user_input}")

        # 准备历史对话上下文
        conversation_history = []
        if self.history:
            for h in self.history:
                conv_turn = {
                    "user": h.get("user", ""),
                    "response": {
                        "intent_parsed": h.get("response", {}).get("intent_parsed", {})
                    },
                }
                conversation_history.append(conv_turn)

        # 第一次调用 Adviser
        if self.init:
            response = await self.adviser.generate_response(  # 🔧 加 await
                user_input,
                conversation_history=conversation_history,
                use_rag=True,
                rag_top_k=25,
                debug=True,
                skip_clarifier=False,
            )
            self.init = False
        else:
            # 非首次: 正常调用, 关掉 debug, 但传递历史对话
            response = await self.adviser.generate_response(  # 🔧 加 await
                user_input,
                conversation_history=conversation_history,
                use_rag=False,
                rag_top_k=25,
                debug=False,
                skip_clarifier=False,
            )

        # 保存 Adviser 输出 (文件 I/O 暂时保持同步, 后续优化)
        with open(self.log_path, "a+", encoding="utf-8") as f:
            f.write(
                f"\n----------------------- User -----------------------\n{user_input}\n"
            )
            f.write(
                f"----------------------- Adviser Response -----------------------\n{json.dumps(response, ensure_ascii=False, indent=2)}\n"
            )

        # ✅ 如果需要补充信息, 直接输出追问并返回 (不走 Verifier)
        if response.get("need_more_info"):
            follow_up = response.get("follow_up", "我还需要一些补充信息～")
            print("🤔 需要补充信息:\n")
            print(follow_up)
            # 记录历史
            self.history.append({"user": user_input, "response": response})
            with open(self.history_path, "a+", encoding="utf-8") as f:
                f.write(f"\n------------ User ------------\n{user_input}\n")
                f.write(
                    f"------------ Response ------------\n{json.dumps(response, ensure_ascii=False, indent=2)}\n"
                )
            print("\n****************************************")
            return response

        # 调用 Verifier 审查 (带重试限制)
        task_type = response.get("intent_parsed", {}).get("task_type", "")
        if self.with_verifier and task_type == "itinerary":
            explanation, is_safe = await self.verifier.assess_cur_response(response)  # 🔧 加 await
            with open(self.log_path, "a+", encoding="utf-8") as f:
                f.write(
                    "\n&&&&&&&&&&&&&&&&&&&&&&& Safety Check &&&&&&&&&&&&&&&&&&&&&&&\n"
                )
                f.write(f"Safety: {is_safe}\nExplanation: {explanation}\n")

            # 🔧 添加最大重试次数限制
            max_retries = 3
            retry_count = 0

            while not is_safe and retry_count < max_retries:
                retry_count += 1
                print(f"⚠️ Verifier 检测到问题 (尝试 {retry_count}/{max_retries}), 正在重新生成...")

                revision_prompt = f"""原始用户请求: {user_input}

请根据以下问题修正之前的计划:
{explanation}

请保持原始请求的意图 (task_type, 目的地, 天数, 预算等), 只修正检测到的问题."""

                # 重新生成时也传递历史对话
                conversation_history = []
                if self.history:
                    for h in self.history:
                        conv_turn = {
                            "user": h.get("user", ""),
                            "response": {
                                "intent_parsed": h.get("response", {}).get(
                                    "intent_parsed", {}
                                )
                            },
                        }
                        conversation_history.append(conv_turn)

                response = await self.adviser.generate_response(  # 🔧 加 await
                    revision_prompt,
                    conversation_history=conversation_history,
                    use_rag=True,
                    rag_top_k=25,
                    debug=False,
                )
                explanation, is_safe = await self.verifier.assess_cur_response(response)  # 🔧 加 await

                with open(self.log_path, "a+", encoding="utf-8") as f:
                    f.write(
                        f"\n----------------------- Regenerated Response (尝试 {retry_count}) -----------------------\n{json.dumps(response, ensure_ascii=False, indent=2)}\n"
                    )
                    f.write(f"Safety: {is_safe}\nExplanation: {explanation}\n")

            # 🔧 如果达到最大重试次数仍不安全, 记录警告但继续返回
            if not is_safe:
                print(f"⚠️ 警告: 经过 {max_retries} 次重试, Verifier 仍认为不安全, 但已达到最大重试次数")
                with open(self.log_path, "a+", encoding="utf-8") as f:
                    f.write(f"\n⚠️ 警告: 达到最大重试次数, 返回当前结果\n")
        else:
            print("Recommendation-type task detected: Skipping Verifier check.")

        # 更新历史记录
        self.history.append({"user": user_input, "response": response})
        with open(self.history_path, "a+", encoding="utf-8") as f:
            f.write(f"\n------------ User ------------\n{user_input}\n")
            f.write(
                f"------------ Response ------------\n{json.dumps(response, ensure_ascii=False, indent=2)}\n"
            )

        # ... (输出部分保持不变)

        print("\n****************************************")

        return response
```

#### 2.6 异步化 FastAPI 端点

**文件**: `fastapi_server.py`

**修改策略**: 保持 async 端点, 但调用异步的 `nlu.run()`.

```python
# fastapi_server.py

@app.post("/nlu", response_model=NLUResponse)
async def nlu_api(request: NLURequest):  # ✅ 保持 async
    if not nlu:
        raise HTTPException(status_code=500, detail="NLU 模块未初始化")

    try:
        if not request.text or not request.text.strip():
            raise HTTPException(status_code=400, detail="输入内容不能为空")

        print(f"收到输入: {request.text}")
        result = await nlu.run(request.text)  # 🔧 加 await

        if result is None:
            raise HTTPException(status_code=500, detail="Adviser 未返回结果")

        return NLUResponse(success=True, detail=result)

    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"[NLU ERROR]: {e}", file=sys.stderr)
        return NLUResponse(success=False, error=str(e))


@app.post("/nlu/simple")
async def nlu_simple_api(request: NLURequest):  # ✅ 保持 async
    if not nlu:
        raise HTTPException(status_code=500, detail="NLU 模块未初始化")

    sid = request.session_id or str(uuid4())

    if sid not in SESSIONS:
        SESSIONS[sid] = NLU(log_folder="log", file_name=sid, with_verifier=True)
        print(f"创建新会话: {sid} (thread_id)")

    session_nlu = SESSIONS[sid]

    try:
        print(f"[Session {sid}] 输入: {request.text}")
        result = await session_nlu.run(request.text)  # 🔧 加 await
        if not result:
            raise HTTPException(status_code=500, detail="Adviser 无输出")

        # ... (后续处理保持不变)

        return {
            "session_id": sid,
            "type": task_type,
            "status": status,
            "reply": reply,
        }

    except Exception as e:
        print(f"[NLU SIMPLE ERROR]: {e}", file=sys.stderr)
        raise HTTPException(status_code=500, detail=str(e))


@app.on_event("startup")
async def startup_event():  # ✅ 保持 async
    print("YATA NLU API 服务已启动。")
```

---

### 3. RAG 模型预加载

**文件**: `RAG_chroma/api_server.py`

**修改位置**: 第 46-55 行

**修改内容**:

```python
@app.on_event("startup")
async def startup_event():
    """初始化数据库并预加载模型"""
    try:
        emb_dim = get_embedding_dimension()
        init_db(embedding_dim=emb_dim)
        print(f"✅ 数据库初始化完成, 维度: {emb_dim}")

        # 🔧 强制预加载模型 (warmup)
        print("🔥 正在预加载 embedding 模型...")
        from embedder import embed_texts
        _ = embed_texts(["warmup"])  # 触发模型加载
        print("✅ Embedding 模型预加载完成")

        # 🔧 预加载重排序模型 (如果启用)
        from config import settings
        if settings.use_reranking:
            print("🔥 正在预加载重排序模型...")
            from embedder import rerank
            _ = rerank("warmup", ["warmup"])
            print("✅ 重排序模型预加载完成")

        print(f"✅ RAG API 服务已启动")
    except Exception as e:
        print(f"❌ 初始化失败: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        # 🔧 如果初始化失败, 中断启动 (避免后续请求失败)
        raise
```

---

### 4. 添加请求级别超时保护

**文件**: `fastapi_server.py`

**修改策略**: 使用 `asyncio.timeout()` 为整个请求添加超时.

```python
import asyncio
from contextlib import asynccontextmanager

# 设置请求总超时时间 (略小于 backend 的 30 秒)
REQUEST_TIMEOUT = 28.0


@app.post("/nlu/simple")
async def nlu_simple_api(request: NLURequest):
    if not nlu:
        raise HTTPException(status_code=500, detail="NLU 模块未初始化")

    sid = request.session_id or str(uuid4())

    if sid not in SESSIONS:
        SESSIONS[sid] = NLU(log_folder="log", file_name=sid, with_verifier=True)
        print(f"创建新会话: {sid} (thread_id)")

    session_nlu = SESSIONS[sid]

    try:
        print(f"[Session {sid}] 输入: {request.text}")

        # 🔧 添加总超时保护
        async with asyncio.timeout(REQUEST_TIMEOUT):
            result = await session_nlu.run(request.text)

        if not result:
            raise HTTPException(status_code=500, detail="Adviser 无输出")

        # ... (后续处理保持不变)

        return {
            "session_id": sid,
            "type": task_type,
            "status": status,
            "reply": reply,
        }

    except asyncio.TimeoutError:
        print(f"[Session {sid}] ⚠️ 请求超时 (>{REQUEST_TIMEOUT}s)", file=sys.stderr)
        raise HTTPException(
            status_code=504,
            detail=f"请求处理超时 (>{REQUEST_TIMEOUT}s), 请稍后重试"
        )

    except Exception as e:
        print(f"[NLU SIMPLE ERROR]: {e}", file=sys.stderr)
        raise HTTPException(status_code=500, detail=str(e))
```

---

### 5. Session 清理机制 (与 Backend Thread 协调)

基于 backend 的 thread_id 管理, 我们有两种策略:

#### 策略 A: 被动清理 (推荐, 简单可靠)

**原理**: 不在 NLU 侧主动清理 session, 而是依赖 session 的过期时间. 当 backend 的 thread 被清理后, 对应的 session_id 不会再被使用, NLU 的 session 自然过期.

**实现**:

```python
# fastapi_server.py
import time
from threading import Lock
from collections import OrderedDict

# 🔧 使用 OrderedDict 维护 LRU 顺序
SESSIONS: OrderedDict[str, NLU] = OrderedDict()
SESSION_LAST_ACCESS: dict[str, float] = {}
SESSION_LOCK = Lock()

# 🔧 Session 配置
SESSION_TIMEOUT = 3600  # 1 小时过期
MAX_SESSIONS = 100  # 最大 session 数量


def cleanup_expired_sessions() -> None:
    """清理过期的 session"""
    with SESSION_LOCK:
        current_time = time.time()
        expired_sessions = [
            sid for sid, last_access in SESSION_LAST_ACCESS.items()
            if current_time - last_access > SESSION_TIMEOUT
        ]

        for sid in expired_sessions:
            print(f"🗑️ 清理过期会话: {sid} (最后访问: {int(current_time - SESSION_LAST_ACCESS[sid])}s 前)")
            del SESSIONS[sid]
            del SESSION_LAST_ACCESS[sid]

        # 🔧 如果 session 数量超过上限, 清理最旧的 session
        while len(SESSIONS) > MAX_SESSIONS:
            oldest_sid = next(iter(SESSIONS))
            print(f"🗑️ 清理最旧会话 (达到上限 {MAX_SESSIONS}): {oldest_sid}")
            del SESSIONS[oldest_sid]
            del SESSION_LAST_ACCESS[oldest_sid]


@app.post("/nlu/simple")
async def nlu_simple_api(request: NLURequest):
    if not nlu:
        raise HTTPException(status_code=500, detail="NLU 模块未初始化")

    # 🔧 定期清理过期 session (每 10 次请求清理一次)
    if len(SESSION_LAST_ACCESS) % 10 == 0:
        cleanup_expired_sessions()

    sid = request.session_id or str(uuid4())

    with SESSION_LOCK:
        if sid not in SESSIONS:
            SESSIONS[sid] = NLU(log_folder="log", file_name=sid, with_verifier=True)
            print(f"✨ 创建新会话: {sid} (thread_id)")

        # 🔧 更新最后访问时间
        SESSION_LAST_ACCESS[sid] = time.time()

        # 🔧 将 session 移到末尾 (LRU)
        SESSIONS.move_to_end(sid)

        session_nlu = SESSIONS[sid]

    # ... (后续处理保持不变)
```

#### 策略 B: 主动同步 (复杂, 需要 backend 支持)

**原理**: NLU 提供一个 `/sessions/cleanup` 接口, backend 在清理 thread 时主动通知 NLU.

**Backend 侧修改** (需要在 `thread_manager.py` 中添加):

```python
# backend/src/service/thread_manager.py
import httpx

async def cleanup_thread(thread_id: str):
    """清理线程时, 通知 NLU 清理对应的 session"""
    # ... (原有清理逻辑)

    # 通知 NLU 清理 session
    try:
        async with httpx.AsyncClient() as client:
            await client.delete(
                f"{settings.NLU_SERVICE_URL}/sessions/{thread_id}",
                timeout=5.0
            )
    except Exception as e:
        logger.warning(f"Failed to cleanup NLU session {thread_id}: {e}")
```

**NLU 侧修改** (需要在 `fastapi_server.py` 中添加):

```python
@app.delete("/sessions/{session_id}")
async def cleanup_session(session_id: str):
    """清理指定的 session"""
    with SESSION_LOCK:
        if session_id in SESSIONS:
            print(f"🗑️ 清理会话 (backend 通知): {session_id}")
            del SESSIONS[session_id]
            if session_id in SESSION_LAST_ACCESS:
                del SESSION_LAST_ACCESS[session_id]
            return {"status": "ok", "message": f"Session {session_id} cleaned up"}
        else:
            raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
```

**推荐**: 使用策略 A (被动清理), 因为:

1. 实现简单, 不需要修改 backend
2. 自动兜底, 即使 backend 没有通知也能清理
3. 通过 LRU 策略限制最大 session 数量, 防止内存泄漏

---

### 6. 异步日志记录

**文件**: `NLU_module/main.py`

**依赖**: 需要安装 `aiofiles`

```bash
uv add aiofiles
```

**修改策略**: 将所有 `open()` 改为 `aiofiles.open()`.

**示例**:

```python
import aiofiles

class NLU:
    # ...

    async def run(self, contents: str, context: dict | None = None) -> dict[str, Any]:
        # ...

        # 🔧 异步文件写入
        async with aiofiles.open(self.log_path, "a+", encoding="utf-8") as f:
            await f.write(
                f"\n----------------------- User -----------------------\n{user_input}\n"
            )
            await f.write(
                f"----------------------- Adviser Response -----------------------\n{json.dumps(response, ensure_ascii=False, indent=2)}\n"
            )

        # ...

        # ✅ 如果需要补充信息
        if response.get("need_more_info"):
            # ...
            self.history.append({"user": user_input, "response": response})
            async with aiofiles.open(self.history_path, "a+", encoding="utf-8") as f:
                await f.write(f"\n------------ User ------------\n{user_input}\n")
                await f.write(
                    f"------------ Response ------------\n{json.dumps(response, ensure_ascii=False, indent=2)}\n"
                )
            # ...

        # ... (其他所有文件写入都需要改为异步)
```

**注意**: 所有涉及文件 I/O 的地方都需要改为异步, 包括:

- `self.log_path` 的写入
- `self.history_path` 的写入
- Verifier 的日志写入

---

### 7. 连接池优化 (可选)

**文件**: `NLU_module/agents/adviser/adviser_rag.py`

**优化目标**: 复用 httpx.AsyncClient 实例, 避免每次请求都创建新的客户端.

**实现**:

```python
# adviser_rag.py
import os
from typing import Any

import httpx

# 🔧 全局共享的 HTTP 客户端 (复用连接池)
_http_client: httpx.AsyncClient | None = None


def _get_http_client() -> httpx.AsyncClient:
    """获取共享的 HTTP 客户端 (懒加载)"""
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(15.0),
            limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
        )
    return _http_client


async def call_rag_api(query: str, city: str = "", top_k: int = 25, debug: bool = False) -> list[dict[str, Any]]:
    """异步调用 RAG API (使用共享连接池)"""
    rag_url = os.getenv("RAG_API_URL", "http://127.0.0.1:8001/search")
    payload = {"query": query, "city": city or "", "top_k": int(top_k)}

    print(f"🔍 正在调用 RAG API: {rag_url}")
    print(f"   Query: {query[:100]}{'...' if len(query) > 100 else ''}")
    print(f"   City: {city or '(未指定)'}, Top-K: {top_k}")

    try:
        # 🔧 使用共享客户端 (不再使用 async with, 客户端保持打开)
        client = _get_http_client()
        resp = await client.post(rag_url, json=payload)
        resp.raise_for_status()
        # ... (后续处理保持不变)

    except Exception as e:
        # ... (错误处理保持不变)
        pass


# 🔧 在 fastapi_server.py 的 shutdown_event 中关闭客户端
@app.on_event("shutdown")
async def shutdown_event():
    """关闭共享资源"""
    from NLU_module.agents.adviser.adviser_rag import _http_client
    if _http_client:
        await _http_client.aclose()
        print("✅ HTTP 客户端已关闭")
```

**注意**: 这个优化是可选的, 如果不确定是否需要, 可以先跳过.

---

## 依赖管理

### 新增依赖

需要在 `pyproject.toml` 中添加以下依赖:

```toml
[project]
dependencies = [
    # ... (现有依赖)
    "httpx>=0.27.0",
    "aiofiles>=24.1.0",
]
```

### 安装依赖

```bash
uv sync
```

---

## 类型检查注意事项

### 1. 异步函数的返回类型

```python
from typing import Any

# ✅ 正确
async def generate_response(...) -> dict[str, Any]:
    ...

# ❌ 错误 (不需要 Coroutine)
async def generate_response(...) -> Coroutine[Any, Any, dict[str, Any]]:
    ...
```

### 2. 可选类型

```python
from typing import Optional

# ✅ 正确 (Python 3.10+)
def run(self, contents: str, context: dict | None = None) -> dict[str, Any]:
    ...

# ✅ 正确 (旧版本兼容)
def run(self, contents: str, context: Optional[dict] = None) -> dict[str, Any]:
    ...
```

### 3. List/Dict 类型

```python
# ✅ 正确 (Python 3.10+, 推荐)
async def call_rag_api(...) -> list[dict[str, Any]]:
    ...

# ✅ 正确 (旧版本兼容)
from typing import List, Dict
async def call_rag_api(...) -> List[Dict[str, Any]]:
    ...
```

### 4. Pyright 检查

在实现过程中, 随时运行 pyright 检查:

```bash
source .venv/bin/activate
pyright NLU_module/
pyright fastapi_server.py
```

确保没有类型错误 (除非是第三方库的已知问题).

---

## 实施步骤

### 第 1 天: 核心异步化

1. ✅ 安装依赖 (`httpx`, `aiofiles`)
2. ✅ 异步化 RAG 调用 (`adviser_rag.py`)
3. ✅ 修复 Verifier 无限循环 (`main.py`)
4. ✅ 运行 pyright 检查类型
5. ✅ 本地测试 RAG 调用是否正常

### 第 2 天: LLM 和 Adviser 异步化

6. ✅ 检查并异步化 LLM 调用 (`model_definition.py`, `adviser_base.py`)
7. ✅ 异步化 Adviser 的所有子模块:
   - `adviser_intent.py`
   - `adviser_itinerary.py`
   - `adviser_recommendation.py`
   - `clarifier.py`
8. ✅ 异步化 Adviser 主类 (`adviser_main.py`)
9. ✅ 运行 pyright 检查类型

### 第 3 天: NLU 主类和端点异步化

10. ✅ 异步化 Verifier (`verifier.py`)
11. ✅ 异步化 NLU 主类 (`main.py`)
12. ✅ 异步化 FastAPI 端点 (`fastapi_server.py`)
13. ✅ 添加请求超时保护
14. ✅ 运行 pyright 检查类型
15. ✅ 本地端到端测试

### 第 4 天: RAG 预加载和优化

16. ✅ RAG 模型预加载 (`RAG_chroma/api_server.py`)
17. ✅ 测试 RAG 服务启动时的模型加载
18. ✅ 添加 Session 清理机制 (`fastapi_server.py`)
19. ✅ 异步日志记录 (`main.py`, 使用 `aiofiles`)

### 第 5 天: 集成测试

20. ✅ 与 backend (dev 分支) 进行集成测试
21. ✅ 验证 session_id 与 thread_id 的绑定
22. ✅ 压力测试 (并发请求)
23. ✅ Ctrl+C 响应测试
24. ✅ 编写测试文档

---

## 测试方案

### 测试场景 1: Ctrl+C 响应测试

**目标**: 验证服务可以正确响应 Ctrl+C 信号.

**步骤**:

1. 启动 NLU 服务
2. 在另一个终端发送请求:

   ```bash
   curl -X POST "http://localhost:8010/nlu/simple" \
        -H "Content-Type: application/json" \
        -d '{"text": "规划一个4天的Paris行程, 包含博物馆和美食体验, 预算8000元, 一个成人, 下周去, 从上海出发"}'
   ```

3. 在服务处理请求时 (但未完成), 按 Ctrl+C
4. **预期**: 服务应该在 1-2 秒内优雅关闭, 显示 "Shutting down" 信息

### 测试场景 2: Verifier 重试限制测试

**目标**: 验证 Verifier 不会无限循环.

**步骤**:

1. (可选) 临时修改 Verifier, 使其总是返回 `is_safe=False`
2. 发送行程规划请求
3. 观察日志输出
4. **预期**: 系统最多重试 3 次后返回结果, 不会无限循环

### 测试场景 3: RAG 模型预加载测试

**目标**: 验证 RAG 服务启动时预加载模型, 首次请求不触发下载.

**步骤**:

1. 删除 HuggingFace 缓存中的 bge-m3 模型:

   ```bash
   rm -rf ~/.cache/huggingface/hub/models--BAAI--bge-m3
   ```

2. 启动 RAG 服务
3. 观察启动日志, 应该显示 "正在预加载 embedding 模型..."
4. 发送首次搜索请求
5. **预期**: 首次请求应该在 15 秒内返回, 不会因模型下载而超时

### 测试场景 4: 异步性能测试

**目标**: 验证异步架构的并发性能.

**步骤**:

1. 使用 `wrk` 或 `ab` 进行压力测试:

   ```bash
   # 使用 wrk (需要先安装)
   wrk -t10 -c100 -d30s --timeout 35s \
       -s post_nlu.lua \
       http://localhost:8010/nlu/simple

   # post_nlu.lua 内容:
   # wrk.method = "POST"
   # wrk.headers["Content-Type"] = "application/json"
   # wrk.body = '{"text": "推荐Paris的顶级景点"}'
   ```

2. **预期**: 服务应该稳定处理所有请求, QPS 应该明显高于同步版本

### 测试场景 5: Session 清理测试

**目标**: 验证 session 过期清理机制.

**步骤**:

1. 创建多个 session (发送不同 session_id 的请求)
2. 等待超过 SESSION_TIMEOUT (1 小时, 可以临时改为 60 秒测试)
3. 观察日志, 应该显示 "清理过期会话: ..."
4. 发送超过 MAX_SESSIONS (100) 个 session
5. **预期**: 最旧的 session 应该被自动清理

### 测试场景 6: Backend 集成测试

**目标**: 验证与 backend 的完整集成.

**步骤**:

1. 切换到 dev 分支, 启动 backend
2. 启动 NLU 服务
3. 启动 RAG 服务
4. 通过 backend 的 `/chat` 接口发送旅行规划请求
5. **预期**: backend 应该正确调用 NLU, 并返回行程规划结果

### 测试场景 7: 请求超时测试

**目标**: 验证请求级别的超时保护.

**步骤**:

1. 临时修改某个 LLM 调用, 使其耗时超过 28 秒 (如 `await asyncio.sleep(30)`)
2. 发送请求
3. **预期**: 请求应该在 28 秒后返回 504 错误, 不会无限等待

---

## 回滚方案

如果重构过程中遇到严重问题, 可以分阶段回滚:

### 回滚点 1: 异步化 RAG 调用之前

- 保留: 同步 RAG 调用
- 回滚: `adviser_rag.py`

### 回滚点 2: 异步化 Adviser 之前

- 保留: 同步 Adviser
- 回滚: `adviser_main.py`, `adviser_*.py`

### 回滚点 3: 异步化 NLU 主类之前

- 保留: 同步 NLU.run()
- 回滚: `main.py`

### 完全回滚

- 使用 git 回到重构前的 commit:

  ```bash
  git checkout <commit-hash>
  ```

---

## 性能预期

### 同步架构 (重构前)

- **并发能力**: 受限于线程池大小 (~40 个线程)
- **响应时间**: 单个请求 10-30 秒
- **QPS**: ~2-5 (取决于请求复杂度)
- **Ctrl+C 响应**: 无法响应 (阻塞事件循环)

### 异步架构 (重构后)

- **并发能力**: 可处理数百个并发请求 (受限于 LLM API 限流)
- **响应时间**: 单个请求 10-30 秒 (与同步版本相同)
- **QPS**: ~10-20 (取决于 LLM API 性能)
- **Ctrl+C 响应**: 1-2 秒内优雅关闭

---

## 总结

### 核心改动

1. ✅ **完全异步化**: 从 FastAPI 端点到 RAG/LLM 调用, 全部使用 async/await
2. ✅ **Verifier 重试限制**: 最多重试 3 次, 防止无限循环
3. ✅ **RAG 模型预加载**: 服务启动时预加载模型, 避免首次请求超时
4. ✅ **请求超时保护**: 使用 asyncio.timeout() 限制总请求时间 (28 秒)
5. ✅ **Session 清理机制**: 基于 LRU 和过期时间的自动清理
6. ✅ **异步日志记录**: 使用 aiofiles 避免阻塞 I/O

### 预期效果

- **根本解决卡死问题**: 服务可以正确响应 Ctrl+C
- **提升并发性能**: QPS 提升 2-4 倍
- **提升稳定性**: 自动清理过期 session, 防止内存泄漏
- **更好的可维护性**: 与 backend 的异步架构保持一致

### 风险与缓解

- **风险**: 异步重构涉及大量代码改动, 可能引入新的 bug
- **缓解**: 分阶段实施, 每个阶段都进行 pyright 检查和测试
- **风险**: 第三方库 (如 LLM SDK) 可能不支持异步
- **缓解**: 使用 `asyncio.to_thread()` 包装同步调用 (作为兜底方案)

### 后续优化方向

1. **缓存优化**: 对 LLM 响应进行缓存, 减少重复调用
2. **批处理优化**: 对多个相似请求进行批处理, 提升吞吐量
3. **监控与告警**: 添加 Prometheus 指标, 监控性能和错误率
4. **A/B 测试**: 对比同步和异步版本的性能差异
