# adviser_rag.py
import os
from typing import Any

import httpx


async def call_rag_api(
    query: str, city: str = "", top_k: int = 25, debug: bool = False
) -> list[dict[str, Any]]:
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
