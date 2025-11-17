# NLU 服务卡死问题深度分析与修复方案

## 问题概述

NLU 服务在 RAG 服务响应超时时会完全卡死, 即使连续按 Ctrl+C 也无法关闭服务, 最终需要使用 `lsof -ti :8010 | xargs kill -9` 强制终止.

## 根本原因分析

### 🔴 严重问题 1: Async/Sync 混用导致事件循环阻塞 (Critical)

**位置**: `fastapi_server.py:49-70`, `fastapi_server.py:73-139`

**问题描述**:
- FastAPI 端点声明为 `async def`, 但内部调用链条完全是同步的
- 调用链条: `async endpoint` → `sync nlu.run()` → `sync adviser.generate_response()` → `sync call_rag_api()` (使用 `requests.post()`)

**技术细节**:
```python
@app.post("/nlu/simple")
async def nlu_simple_api(request: NLURequest):  # ❌ 声明为 async
    ...
    result = session_nlu.run(request.text)  # ❌ 调用同步代码
    ...
```

在 `adviser_rag.py:17`:
```python
resp = requests.post(rag_url, json=payload, timeout=15)  # ❌ 同步阻塞 I/O
```

**导致的后果**:
1. 当 `requests.post()` 发起 HTTP 请求时, 会阻塞整个 asyncio 事件循环
2. uvicorn 的信号处理器 (SIGINT handler) 运行在同一个事件循环中
3. 事件循环被阻塞, 导致信号处理器无法被调度执行
4. 结果: Ctrl+C 完全无效, 服务无法优雅关闭

**为什么 15 秒超时后还是卡住**:
- 虽然 RAG 请求有 15 秒超时, 但如果 RAG 服务正在下载模型 (可能需要几分钟), timeout 会正确触发
- 但问题在于后续的 Verifier 循环可能会再次调用 RAG, 累积阻塞时间
- 更关键的是, 即使单次 15 秒, 在这期间服务也无法响应任何信号

---

### 🔴 严重问题 2: Verifier 的无限循环风险 (Critical)

**位置**: `NLU_module/main.py:108-136`

**问题描述**:
```python
while not is_safe:  # ❌ 没有最大重试次数限制
    print("⚠️ Verifier 检测到问题, 正在重新生成...")
    response = self.adviser.generate_response(
        revision_prompt,
        conversation_history=conversation_history,
        use_rag=True,  # ❌ 每次都调用 RAG
        rag_top_k=25,
        debug=False,
    )
    explanation, is_safe = self.verifier.assess_cur_response(response)
```

**导致的后果**:
1. 如果 Verifier 持续判定行程不安全, 会导致无限循环
2. 每次循环都会:
   - 调用 RAG API (可能超时 15 秒)
   - 调用 LLM 生成新行程 (可能耗时数秒)
   - 调用 Verifier LLM 验证 (可能耗时数秒)
3. 与问题 1 结合, 导致服务长时间阻塞, 完全无法关闭

**实际触发场景**:
- RAG 服务首次启动, 正在下载模型
- NLU 收到行程规划请求
- RAG 超时返回空结果
- Adviser 基于空结果生成行程
- Verifier 判定不安全 (因为缺少 RAG 信息)
- 进入重试循环, 再次调用 RAG, 再次超时...
- **无限循环, 服务卡死**

---

### 🔴 严重问题 3: RAG 服务的延迟模型加载 (Critical)

**位置**: `RAG_chroma/embedder.py:13-26`, `RAG_chroma/api_server.py:46-55`

**问题描述**:
```python
def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:  # ❌ 延迟加载, 首次调用时才下载
        print(f"正在加载 embedding 模型: {settings.model_name}...")
        print("(首次运行需要下载模型文件, 可能需要几分钟, 请耐心等待)")
        _model = SentenceTransformer(settings.model_name)  # 可能需要几分钟
```

虽然 `api_server.py` 的 startup_event 调用了 `get_embedding_dimension()`, 但对于 bge-m3 模型, 该函数会直接返回 1024, 不会真正加载模型:
```python
# embedder.py:43-46
def get_embedding_dimension() -> int:
    # BGE-M3 固定为 1024 维
    if "bge-m3" in settings.model_name.lower():
        return 1024  # ❌ 直接返回, 不加载模型
```

**导致的后果**:
1. RAG 服务启动后, 模型并未真正加载到内存
2. 第一次 `/search` 请求触发 `embed_texts()` 时, 才会真正加载模型
3. 如果模型文件不存在, 会从 HuggingFace 下载 (BAAI/bge-m3 约 2.2GB)
4. 下载过程可能需要数分钟, 远超 NLU 设置的 15 秒超时
5. NLU 收到超时错误, 但 RAG 服务还在下载模型, 后续请求同样会阻塞

---

### ⚠️ 次要问题 4: 每个 Session 创建独立的 NLU 实例 (Medium)

**位置**: `fastapi_server.py:83-85`

**问题描述**:
```python
if sid not in SESSIONS:
    SESSIONS[sid] = NLU(log_folder="log", file_name=sid, with_verifier=True)
    print(f"创建新会话: {sid} (thread_id)")
```

每个 session 都会创建:
- 一个新的 Adviser 实例 (包含 LLM 客户端)
- 一个新的 Verifier 实例
- 一个新的 Clarifier 实例

**导致的后果**:
1. 多个 session 创建多个 LLM 客户端实例, 浪费连接资源
2. 内存占用随 session 数量线性增长
3. `SESSIONS` 字典没有过期清理机制, 可能导致内存泄漏
4. 虽然不直接导致卡死, 但会加剧资源压力, 降低服务稳定性

---

### ⚠️ 次要问题 5: 缺乏请求级别的超时保护 (Medium)

**位置**: 整个 NLU 调用链

**问题描述**:
- RAG 调用有 15 秒超时 (`adviser_rag.py:17`)
- 但 NLU 端点本身没有总体超时限制
- LLM API 调用依赖 OpenAI SDK 默认超时 (通常为 60-600 秒)
- Verifier 循环可能累积多次 LLM + RAG 调用

**导致的后果**:
- 单个请求可能耗时数分钟甚至更长
- 在 async/sync 混用的情况下, 长时间阻塞事件循环
- 影响服务的整体可用性

---

### ⚠️ 次要问题 6: 同步文件 I/O 在请求处理路径中 (Low)

**位置**: `NLU_module/main.py:74-80`, `88-93`, 多处

**问题描述**:
```python
with open(self.log_path, "a+", encoding="utf-8") as f:
    f.write(...)  # ❌ 同步文件 I/O
```

**导致的后果**:
- 在高并发下, 同步文件写入会增加请求延迟
- 与 async 端点结合, 会阻塞事件循环 (虽然影响较小)
- 建议使用异步日志库 (如 `aiofiles`) 或队列 + 后台线程

---

## 修复方案

### 方案 1: 将 FastAPI 端点改为同步 (推荐, 最小改动)

**优点**:
- 改动最小, 只需修改 `fastapi_server.py`
- 不需要重构 NLU 内部逻辑
- FastAPI 会自动在线程池中运行同步端点, 不阻塞主事件循环
- 可以正确响应 SIGINT 信号

**缺点**:
- 并发性能受限于线程池大小 (默认 40 个线程)
- 仍然存在其他问题 (Verifier 无限循环, RAG 模型加载等)

**实现步骤**:

1. 修改 `fastapi_server.py` 的端点定义:
   ```python
   # 将 async def 改为 def
   @app.post("/nlu", response_model=NLUResponse)
   def nlu_api(request: NLURequest):  # 去掉 async
       ...

   @app.post("/nlu/simple")
   def nlu_simple_api(request: NLURequest):  # 去掉 async
       ...
   ```

2. 修改 startup_event:
   ```python
   @app.on_event("startup")
   def startup_event():  # 去掉 async
       print("YATA NLU API 服务已启动。")
   ```

**预期效果**:
- 服务可以正确响应 Ctrl+C 信号
- 同步阻塞调用运行在线程池中, 不阻塞主事件循环
- 其他线程的请求不受影响

---

### 方案 2: 重构为完全异步架构 (最佳, 但改动较大)

**优点**:
- 最佳性能和可扩展性
- 完全非阻塞, 可以处理大量并发请求
- 符合 FastAPI async 的设计理念

**缺点**:
- 需要重构大量代码
- 需要替换所有同步 I/O 操作

**实现步骤**:

1. 替换 `requests` 为 `httpx.AsyncClient` (`adviser_rag.py`):
   ```python
   import httpx

   async def call_rag_api(query: str, city: str = "", top_k: int = 25, debug=False):
       rag_url = os.getenv("RAG_API_URL", "http://127.0.0.1:8001/search")
       payload = {"query": query, "city": city or "", "top_k": int(top_k)}

       try:
           async with httpx.AsyncClient() as client:
               resp = await client.post(rag_url, json=payload, timeout=15.0)
               resp.raise_for_status()
               ...
       except httpx.TimeoutException as e:
           ...
   ```

2. 将所有 LLM 调用改为异步 (需要根据具体的 LLM SDK):
   - 如果使用 OpenAI SDK, 使用 `await client.chat.completions.create(...)`
   - 如果使用其他 SDK, 查看是否有 async 版本

3. 将文件 I/O 改为异步 (`aiofiles`):
   ```python
   import aiofiles

   async with aiofiles.open(self.log_path, "a+", encoding="utf-8") as f:
       await f.write(...)
   ```

4. 重构 NLU 类的所有方法为 async:
   ```python
   async def run(self, contents, context=None):
       ...
       response = await self.adviser.generate_response(...)
       ...
   ```

**预期效果**:
- 完全非阻塞架构
- 高并发性能
- 服务可以正确响应信号

---

### 方案 3: 使用 asyncio.to_thread() 包装同步调用 (折中方案)

**优点**:
- 改动较小, 主要在 `fastapi_server.py`
- 不阻塞事件循环
- 保持异步端点的优势

**缺点**:
- 仍然依赖线程池
- 内部调用链仍是同步的

**实现步骤**:

1. 使用 `asyncio.to_thread()` 包装同步调用:
   ```python
   import asyncio

   @app.post("/nlu/simple")
   async def nlu_simple_api(request: NLURequest):
       if not nlu:
           raise HTTPException(status_code=500, detail="NLU 模块未初始化")

       sid = request.session_id or str(uuid4())

       if sid not in SESSIONS:
           # 在线程池中创建 NLU 实例 (可能涉及文件 I/O)
           SESSIONS[sid] = await asyncio.to_thread(
               NLU, log_folder="log", file_name=sid, with_verifier=True
           )
           print(f"创建新会话: {sid} (thread_id)")

       session_nlu = SESSIONS[sid]

       try:
           print(f"[Session {sid}] 输入: {request.text}")
           # 在线程池中运行同步的 run() 方法
           result = await asyncio.to_thread(session_nlu.run, request.text)
           ...
   ```

**预期效果**:
- 同步调用运行在线程池中, 不阻塞事件循环
- 服务可以正确响应信号
- 代码改动较小

---

### 必须修复: Verifier 无限循环问题

**无论选择哪个方案, 都必须修复此问题**

**实现步骤**:

修改 `NLU_module/main.py:108-136`:
```python
# 调用 Verifier 审查
task_type = response.get("intent_parsed", {}).get("task_type", "")
if self.with_verifier and task_type == "itinerary":
    explanation, is_safe = self.verifier.assess_cur_response(response)
    with open(self.log_path, "a+", encoding="utf-8") as f:
        f.write("\n&&&&&&&&&&&&&&&&&&&&&&& Safety Check &&&&&&&&&&&&&&&&&&&&&&&\n")
        f.write(f"Safety: {is_safe}\nExplanation: {explanation}\n")

    # 如果不安全, 重新生成 (最多重试 3 次)
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

    # 如果达到最大重试次数仍不安全, 记录警告但继续返回
    if not is_safe:
        print(f"⚠️ 警告: 经过 {max_retries} 次重试, Verifier 仍认为不安全, 但已达到最大重试次数")
        with open(self.log_path, "a+", encoding="utf-8") as f:
            f.write(f"\n⚠️ 警告: 达到最大重试次数, 返回当前结果\n")
else:
    print("Recommendation-type task detected: Skipping Verifier check.")
```

---

### 必须修复: RAG 模型预加载

**实现步骤**:

修改 `RAG_chroma/api_server.py:46-55`:
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

        print(f"✅ RAG API 服务已启动")
    except Exception as e:
        print(f"❌ 初始化失败: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        # 如果初始化失败, 中断启动 (避免后续请求失败)
        raise
```

同时优化 `embedder.py:42-66`:
```python
def get_embedding_dimension() -> int:
    """返回当前 embedding 模型的向量维度"""
    # 对于已知模型, 可以直接返回维度 (避免加载模型)
    if "bge-m3" in settings.model_name.lower():
        return 1024
    elif "bge-base" in settings.model_name.lower():
        return 768
    elif "bge-small" in settings.model_name.lower():
        return 384

    # 对于未知模型, 需要加载模型推断维度
    try:
        model = _get_model()
        if hasattr(model, "get_sentence_embedding_dimension"):
            return int(model.get_sentence_embedding_dimension())
        # 兜底: 用单条文本编码推断维度
        dim = int(embed_texts(["test"]).shape[1])
        return dim
    except Exception as e:
        print(f"⚠️ 无法推断模型维度: {e}")
        return 384  # 默认维度
```

---

### 可选优化: Session 清理机制

**实现步骤**:

在 `fastapi_server.py` 中添加 session 过期清理:
```python
import time
from threading import Lock

# 内存会话缓存, 带过期时间
SESSIONS = {}
SESSION_LAST_ACCESS = {}  # session_id -> last_access_timestamp
SESSION_LOCK = Lock()
SESSION_TIMEOUT = 3600  # 1 小时过期

def cleanup_expired_sessions():
    """清理过期的 session"""
    with SESSION_LOCK:
        current_time = time.time()
        expired_sessions = [
            sid for sid, last_access in SESSION_LAST_ACCESS.items()
            if current_time - last_access > SESSION_TIMEOUT
        ]
        for sid in expired_sessions:
            print(f"清理过期会话: {sid}")
            del SESSIONS[sid]
            del SESSION_LAST_ACCESS[sid]

@app.post("/nlu/simple")
def nlu_simple_api(request: NLURequest):  # 使用同步端点
    # 清理过期 session
    cleanup_expired_sessions()

    sid = request.session_id or str(uuid4())

    with SESSION_LOCK:
        if sid not in SESSIONS:
            SESSIONS[sid] = NLU(log_folder="log", file_name=sid, with_verifier=True)
            print(f"创建新会话: {sid} (thread_id)")

        # 更新最后访问时间
        SESSION_LAST_ACCESS[sid] = time.time()
        session_nlu = SESSIONS[sid]

    ...
```

---

## 推荐修复顺序 (按优先级)

### 阶段 1: 立即修复 (Critical, 解决无法关闭问题)

1. **修复 Verifier 无限循环** (最高优先级)
   - 文件: `NLU_module/main.py`
   - 预计时间: 15 分钟
   - 影响: 防止无限循环导致的卡死

2. **将 FastAPI 端点改为同步** (方案 1)
   - 文件: `fastapi_server.py`
   - 预计时间: 10 分钟
   - 影响: 解决无法响应 Ctrl+C 的核心问题

3. **RAG 模型预加载**
   - 文件: `RAG_chroma/api_server.py`, `RAG_chroma/embedder.py`
   - 预计时间: 15 分钟
   - 影响: 避免首次请求触发长时间模型下载

### 阶段 2: 性能优化 (Medium)

4. **添加请求级别超时**
   - 文件: `fastapi_server.py`
   - 预计时间: 20 分钟
   - 影响: 防止单个请求长时间阻塞

5. **Session 清理机制**
   - 文件: `fastapi_server.py`
   - 预计时间: 30 分钟
   - 影响: 防止内存泄漏

### 阶段 3: 架构优化 (可选, 长期)

6. **重构为完全异步架构** (方案 2)
   - 文件: 多个文件
   - 预计时间: 2-3 天
   - 影响: 最佳性能和可扩展性

---

## 验证测试

### 测试场景 1: Ctrl+C 响应测试

1. 启动 NLU 服务
2. 在另一个终端发送请求 (让 RAG 超时):
   ```bash
   # 先关闭 RAG 服务模拟超时
   curl -X POST "http://localhost:8010/nlu/simple" \
        -H "Content-Type: application/json" \
        -d '{"text": "规划一个4天的Pairs行程"}'
   ```
3. 在服务处理请求时, 按 Ctrl+C
4. **预期**: 服务应该在 1-2 秒内优雅关闭, 显示 "Shutting down" 信息

### 测试场景 2: Verifier 重试限制测试

1. 修改 Verifier 使其总是返回 `is_safe=False` (模拟极端情况)
2. 发送行程规划请求
3. **预期**: 系统最多重试 3 次后返回结果, 不会无限循环

### 测试场景 3: RAG 模型预加载测试

1. 删除 HuggingFace 缓存中的 bge-m3 模型:
   ```bash
   rm -rf ~/.cache/huggingface/hub/models--BAAI--bge-m3
   ```
2. 启动 RAG 服务
3. **预期**: 服务启动时下载并加载模型, 首次搜索请求不会触发下载

### 测试场景 4: 并发请求测试

1. 使用多个并发请求测试服务稳定性:
   ```bash
   # 使用 wrk 或 ab 进行压力测试
   ab -n 100 -c 10 -p request.json -T "application/json" http://localhost:8010/nlu/simple
   ```
2. **预期**: 服务应该稳定处理所有请求, 不崩溃, 不卡死

---

## Type Checking 注意事项

在实现修复时, 注意 pyright 的类型检查:

1. **async/await 类型标注**:
   ```python
   from typing import Dict, Any

   async def call_rag_api(...) -> list[dict[str, Any]]:
       ...
   ```

2. **Optional 类型**:
   ```python
   from typing import Optional

   def run(self, contents: str, context: Optional[dict] = None) -> dict[str, Any]:
       ...
   ```

3. **避免使用 `# type: ignore`**, 除非确实无法解决的第三方库问题

---

## 总结

**根本原因**: Async/Sync 混用 + 无限循环 + 延迟模型加载的三重组合导致服务卡死且无法关闭.

**推荐修复路径**:
1. 立即修复: 方案 1 (改为同步端点) + Verifier 重试限制 + RAG 预加载
2. 中期优化: 添加超时保护 + Session 清理
3. 长期架构: 方案 2 (完全异步化)

**预期效果**: 修复后, 服务应该可以正确响应 Ctrl+C, 不会出现无限循环, 首次请求也不会因模型下载而超时.
