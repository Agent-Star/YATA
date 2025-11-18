import asyncio
import json
import logging
import os
import sys
from collections import OrderedDict
from collections.abc import AsyncGenerator
from typing import Any, Dict, Optional
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from NLU_module.main import NLU
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# 内存会话缓存 (使用 OrderedDict 实现 LRU)
SESSIONS: OrderedDict[str, NLU] = OrderedDict()

# 会话管理配置
MAX_SESSIONS = 100  # 最大会话数, 超过后淘汰最旧的会话

# 请求超时时间 (秒), 留 2s buffer 给 backend 的 60s 超时
REQUEST_TIMEOUT = 58.0

app = FastAPI(title="YATA NLU API", description="智能旅行助手", version="1.0.0")

# 开启 CORS 支持
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

try:
    nlu = NLU(with_verifier=True)
    print("NLU 模块初始化成功 (Adviser + Verifier 已就绪)")
except Exception as e:
    print(f"初始化 NLU 失败: {e}", file=sys.stderr)
    nlu = None


class NLURequest(BaseModel):
    text: str
    session_id: Optional[str] = None


class NLUResponse(BaseModel):
    success: bool
    detail: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


@app.on_event("startup")
async def startup_event():
    print("YATA NLU API 服务已启动。")


def _get_or_create_session(session_id: str) -> NLU:
    """
    获取或创建会话 (实现 LRU 淘汰策略)

    Args:
        session_id: 会话 ID (backend 的 thread_id)

    Returns:
        NLU 实例
    """
    # 如果会话已存在, 移到末尾 (最近使用)
    if session_id in SESSIONS:
        SESSIONS.move_to_end(session_id)
        print(f"♻️  复用现有会话: {session_id}")
        return SESSIONS[session_id]

    # 如果达到最大会话数, 淘汰最旧的会话 (LRU)
    if len(SESSIONS) >= MAX_SESSIONS:
        oldest_sid, oldest_nlu = SESSIONS.popitem(last=False)
        print(f"🗑️  淘汰最旧会话 (LRU): {oldest_sid} (当前会话数: {len(SESSIONS)})")
        del oldest_nlu  # 释放内存

    # 创建新会话
    new_nlu = NLU(log_folder="log", file_name=session_id, with_verifier=True)
    SESSIONS[session_id] = new_nlu
    print(f"✨ 创建新会话: {session_id} (当前会话数: {len(SESSIONS)})")
    return new_nlu


def _delete_session(session_id: str) -> bool:
    """
    删除指定会话 (主动清理)

    Args:
        session_id: 会话 ID

    Returns:
        是否成功删除
    """
    if session_id in SESSIONS:
        nlu_instance = SESSIONS.pop(session_id)
        del nlu_instance
        print(f"🗑️  主动删除会话: {session_id} (剩余会话数: {len(SESSIONS)})")
        return True
    return False


@app.post("/nlu", response_model=NLUResponse)
async def nlu_api(request: NLURequest):
    if not nlu:
        raise HTTPException(status_code=500, detail="NLU 模块未初始化")

    try:
        if not request.text or not request.text.strip():
            raise HTTPException(status_code=400, detail="输入内容不能为空")

        print(f"收到输入: {request.text}")

        # 添加超时保护
        try:
            async with asyncio.timeout(REQUEST_TIMEOUT):
                result = await nlu.run(request.text)
        except TimeoutError:
            raise HTTPException(
                status_code=504,
                detail=f"NLU 处理超时 (>{REQUEST_TIMEOUT}s), 请稍后重试或简化请求",
            )

        if result is None:
            raise HTTPException(status_code=500, detail="Adviser 未返回结果")

        return NLUResponse(success=True, detail=result)

    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"[NLU ERROR]: {e}", file=sys.stderr)
        return NLUResponse(success=False, error=str(e))


@app.post("/nlu/simple")
async def nlu_simple_api(request: NLURequest):
    if not nlu:
        raise HTTPException(status_code=500, detail="NLU 模块未初始化")

    # 使用 session_id（后端传过来的 thread_id）
    # 如果没有提供，自动生成一个（用于测试，生产环境建议后端总是提供）
    sid = request.session_id or str(uuid4())

    # 获取或创建会话 (自动实现 LRU 淘汰)
    session_nlu = _get_or_create_session(sid)

    try:
        print(f"[Session {sid}] 输入: {request.text}")

        # 添加超时保护
        try:
            async with asyncio.timeout(REQUEST_TIMEOUT):
                result = await session_nlu.run(request.text)
        except TimeoutError:
            raise HTTPException(
                status_code=504,
                detail=f"NLU 处理超时 (>{REQUEST_TIMEOUT}s), 请稍后重试或简化请求",
            )

        if not result:
            raise HTTPException(status_code=500, detail="Adviser 无输出")

        task_type = result.get("intent_parsed", {}).get("task_type", "unknown")

        itinerary_md = result.get("itinerary_markdown") or result.get(
            "detailed_itinerary", {}
        ).get("itinerary_markdown")

        recommend_md = result.get("recommendations", {}).get(
            "natural_summary"
        ) or result.get("recommendations", {}).get("summary")

        general_text = result.get("final_summary") or result.get("text_output")

        has_content = bool(itinerary_md or recommend_md or general_text)

        if has_content:
            reply = itinerary_md or recommend_md or general_text
            status = "complete"

        elif "follow_up" in result:
            reply = result["follow_up"]
            status = "incomplete"

        elif "clarification" in result:
            clar = result["clarification"]
            qs = clar.get("questions", [])
            sug = clar.get("suggestions", [])
            reply = "我还需要一些信息：\n" + "\n".join([f"· {q}" for q in qs])
            if sug:
                reply += "\n示例：" + "；".join(sug)
            status = "incomplete"

        else:
            reply = "暂无自然语言输出，请检查 Adviser 模块。"
            status = "complete"

        return {
            "session_id": sid,
            "type": task_type,
            "status": status,
            "reply": reply,
        }

    except Exception as e:
        print(f"[NLU SIMPLE ERROR]: {e}", file=sys.stderr)
        raise HTTPException(status_code=500, detail=str(e))


def _sse_event(data: dict) -> str:
    """生成 SSE 事件字符串"""
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


@app.post("/nlu/simple/stream")
async def nlu_simple_stream(request: NLURequest):
    """
    流式 NLU 接口 - 逐 token 返回行程规划

    事件类型:
    - phase_start: 阶段开始 {"type": "phase_start", "phase": "intent_parsing"}
    - phase_end: 阶段完成 {"type": "phase_end", "phase": "intent_parsing"}
    - token: 行程生成的 token {"type": "token", "delta": "..."}
    - end: 处理完成 {"type": "end", "session_id": "...", "status": "complete"}
    - error: 错误 {"type": "error", "message": "..."}
    """
    if not nlu:
        raise HTTPException(status_code=500, detail="NLU 模块未初始化")

    # 使用 session_id（后端传过来的 thread_id）
    sid = request.session_id or str(uuid4())

    async def generate_events() -> AsyncGenerator[str, None]:
        """生成 SSE 事件流"""
        # 获取或创建会话
        session_nlu = _get_or_create_session(sid)

        try:
            logger.info(f"[Stream {sid}] 开始处理: {request.text[:50]}...")

            # === 阶段 1: Intent Parsing ===
            yield _sse_event({"type": "phase_start", "phase": "intent_parsing"})

            # 执行意图识别 (使用 session_nlu.adviser.generate_response 的部分逻辑)
            # 这里我们复用原有的串行逻辑，只在最后的行程生成部分使用流式
            from NLU_module.agents.adviser.adviser_intent import run_intent_parsing
            from NLU_module.agents.adviser.adviser_itinerary import (
                generate_itinerary_stream,
            )
            from NLU_module.agents.adviser.adviser_recommendation import (
                generate_recommendations_stream,
            )
            from NLU_module.agents.adviser.adviser_rag import call_rag_api

            result = (
                await run_intent_parsing(
                    session_nlu.adviser.llm,
                    request.text,
                    session_nlu.adviser.memory.get("history", []),
                    debug=False,
                )
                or {}
            )

            intent_cur = result.get("intent_parsed", {})

            # 合并历史上下文
            from NLU_module.agents.adviser.adviser_main import merge_partial

            intent_merged = merge_partial(session_nlu.adviser.memory, intent_cur)

            # 检查是否需要追问（简化版，暂不支持流式追问）
            if not result.get("intent_parsed", {}).get("dest_pref"):
                yield _sse_event(
                    {
                        "type": "end",
                        "session_id": sid,
                        "status": "incomplete",
                        "message": "需要更多信息：请提供目的地",
                    }
                )
                yield "data: [DONE]\n\n"
                return

            session_nlu.adviser.memory = intent_merged
            result["intent_parsed"] = intent_merged

            yield _sse_event({"type": "phase_end", "phase": "intent_parsing"})

            # === 阶段 2: RAG 检索 ===
            yield _sse_event({"type": "phase_start", "phase": "rag_search"})

            task_type = result["intent_parsed"].get("task_type", "itinerary")
            city_list = result["intent_parsed"].get("dest_pref", [])
            city_raw = city_list[0] if city_list else ""

            # 城市映射
            city_map = {
                "巴黎": "Paris",
                "伦敦": "London",
                "东京": "Tokyo",
                "上海": "Shanghai",
                "北京": "Beijing",
            }
            city = city_map.get(city_raw, city_raw)

            if task_type == "itinerary":
                query_text = f"{city} attractions restaurants hotels travel guide"
            else:
                query_text = f"{city} recommendations"

            rag_results = await call_rag_api(query_text, city, top_k=5, debug=False)

            yield _sse_event(
                {
                    "type": "phase_end",
                    "phase": "rag_search",
                    "result": {"count": len(rag_results)},
                }
            )

            # === 阶段 3: 内容生成 (并发调用) ===
            yield _sse_event({"type": "phase_start", "phase": "content_generation"})

            from NLU_module.agents.adviser.adviser_aggregate import run_aggregate
            from NLU_module.agents.adviser.adviser_context import run_context_summary
            from NLU_module.agents.adviser.adviser_plan_actions import run_plan_actions

            doc_summaries = [f"{r['title']}: {r['content'][:200]}" for r in rag_results]

            # 并发执行
            context_task = run_context_summary(
                session_nlu.adviser.llm, request.text, doc_summaries
            )
            plan_task = run_plan_actions(
                session_nlu.adviser.llm, result["intent_parsed"]
            )
            aggregate_task = run_aggregate(
                session_nlu.adviser.llm, [], result["intent_parsed"]
            )

            results_concurrent = await asyncio.gather(
                context_task, plan_task, aggregate_task, return_exceptions=True
            )

            context_summary, plan_steps, final_aggregation = results_concurrent

            # 错误处理
            if isinstance(context_summary, Exception):
                context_summary = ""
            if isinstance(plan_steps, Exception):
                plan_steps = []
            if isinstance(final_aggregation, Exception):
                final_aggregation = ""

            result["context_summary"] = context_summary
            result["plan_steps"] = plan_steps
            result["final_aggregation"] = final_aggregation

            yield _sse_event({"type": "phase_end", "phase": "content_generation"})

            # === 阶段 4: 内容生成 (流式) ===
            if task_type == "itinerary":
                yield _sse_event(
                    {"type": "phase_start", "phase": "itinerary_generation"}
                )

                # 使用流式生成
                async for token in generate_itinerary_stream(
                    session_nlu.adviser.llm, result, rag_results, debug=False
                ):
                    yield _sse_event({"type": "token", "delta": token})

                yield _sse_event({"type": "phase_end", "phase": "itinerary_generation"})

            elif task_type == "recommendation":
                yield _sse_event(
                    {"type": "phase_start", "phase": "recommendation_generation"}
                )

                # 使用流式生成推荐
                async for token in generate_recommendations_stream(
                    session_nlu.adviser.llm, result, rag_results, debug=False
                ):
                    yield _sse_event({"type": "token", "delta": token})

                yield _sse_event({"type": "phase_end", "phase": "recommendation_generation"})

            # === 完成 ===
            yield _sse_event({"type": "end", "session_id": sid, "status": "complete"})
            yield "data: [DONE]\n\n"

            logger.info(f"[Stream {sid}] 处理完成")

        except asyncio.TimeoutError:
            logger.error(f"[Stream {sid}] 处理超时")
            yield _sse_event(
                {"type": "error", "message": f"处理超时 (>{REQUEST_TIMEOUT}s)"}
            )
            yield "data: [DONE]\n\n"

        except Exception as e:
            logger.error(f"[Stream {sid}] 处理失败: {e}")
            yield _sse_event({"type": "error", "message": str(e)})
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


@app.delete("/nlu/session/{session_id}")
async def delete_session(session_id: str):
    """
    主动删除会话 (backend 在对话结束时调用)

    Args:
        session_id: 会话 ID (thread_id)

    Returns:
        删除结果
    """
    success = _delete_session(session_id)
    if success:
        return {"success": True, "message": f"会话 {session_id} 已删除"}
    else:
        return {"success": False, "message": f"会话 {session_id} 不存在"}


@app.get("/health")
async def health():
    """健康检查"""
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("NLU_API_PORT", "8010"))
    uvicorn.run(app, host="0.0.0.0", port=8010)
