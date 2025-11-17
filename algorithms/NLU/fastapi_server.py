import asyncio
import os
import sys
from collections import OrderedDict
from typing import Any, Dict, Optional
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from NLU_module.main import NLU
from pydantic import BaseModel

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
