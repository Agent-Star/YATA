import os
import sys
from typing import Any, Dict, Optional
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from NLU_module.main import NLU
from pydantic import BaseModel

# 内存会话缓存
SESSIONS = {}

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


@app.post("/nlu", response_model=NLUResponse)
async def nlu_api(request: NLURequest):
    if not nlu:
        raise HTTPException(status_code=500, detail="NLU 模块未初始化")

    try:
        if not request.text or not request.text.strip():
            raise HTTPException(status_code=400, detail="输入内容不能为空")

        print(f"收到输入: {request.text}")
        result = nlu.run(request.text)

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

    # 如果会话不存在，创建新的 NLU 实例，使用 session_id 作为日志文件夹名
    if sid not in SESSIONS:
        SESSIONS[sid] = NLU(log_folder="log", file_name=sid, with_verifier=True)
        print(f"创建新会话: {sid} (thread_id)")

    session_nlu = SESSIONS[sid]

    try:
        print(f"[Session {sid}] 输入: {request.text}")
        result = session_nlu.run(request.text)
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


@app.get("/health")
async def health():
    """健康检查"""
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("NLU_API_PORT", "8010"))
    uvicorn.run(app, host="0.0.0.0", port=8010)
