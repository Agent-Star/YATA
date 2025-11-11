"""
RAG API 服务
"""

import os
import sys
from typing import Any, Dict, List, Optional

from db import init_db
from embedder import get_embedding_dimension
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from search import search

app = FastAPI(
    title="RAG Chroma API", description="RAG Chroma 向量搜索服务", version="0.1.0"
)

# 允许 CORS（方便 backend 调用）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class SearchRequest(BaseModel):
    """搜索请求"""

    query: str
    city: Optional[str] = None
    day: Optional[str] = None
    top_k: Optional[int] = None


class SearchResponse(BaseModel):
    """搜索响应"""

    contexts: str  # 格式化后的上下文字符串
    results: List[Dict[str, Any]]  # 原始搜索结果


@app.on_event("startup")
async def startup_event():
    """初始化数据库"""
    try:
        emb_dim = get_embedding_dimension()
        init_db(embedding_dim=emb_dim)
        print(f"✅ RAG API 服务已启动，数据库维度: {emb_dim}")
    except Exception as e:
        print(f"❌ 数据库初始化失败: {e}", file=sys.stderr)
        # 不中断启动，允许后续重试


def format_contexts(results: List[Dict[str, Any]]) -> str:
    """将搜索结果格式化为上下文字符串（类似 backend tools.py 的 format_contexts）"""
    if not results:
        return ""

    formatted = []
    for result in results:
        content = result.get("content", "").strip()
        city = result.get("city", "")
        title = result.get("title", "")
        url = result.get("url", "")

        # 构建格式化文本
        parts = []
        if title:
            parts.append(f"[{title}]")
        if city:
            parts.append(f"城市: {city}")
        if url:
            parts.append(f"链接: {url}")
        if content:
            parts.append(f"\n{content}")

        formatted.append("\n".join(parts))

    return "\n\n---\n\n".join(formatted)


@app.post("/search", response_model=SearchResponse)
async def search_api(request: SearchRequest):
    """
    向量搜索接口

    返回格式化的上下文字符串，供 backend 的 database_search 工具使用
    """
    try:
        if not request.query or not request.query.strip():
            raise HTTPException(status_code=400, detail="查询不能为空")

        # 执行搜索（支持 day 软优先，与 CLI 行为一致）
        results = search(query=request.query, city=request.city, day=request.day, top_k=request.top_k)

        # 格式化上下文
        contexts = format_contexts(results)

        return SearchResponse(contexts=contexts, results=results)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"搜索失败: {str(e)}")


@app.get("/health")
async def health():
    """健康检查"""
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    # 默认端口 8001，避免与 backend 的 8000 冲突
    port = int(os.getenv("RAG_API_PORT", "8001"))
    uvicorn.run(app, host="0.0.0.0", port=port)
