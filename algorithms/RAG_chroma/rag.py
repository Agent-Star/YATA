from __future__ import annotations

import json
from typing import Any, Dict, List

MAX_SNIPPET_LENGTH = 500


def _format_score(score: Any) -> float | None:
    """格式化相似度分数"""
    try:
        return round(float(score), 4)
    except (TypeError, ValueError):
        return None


def _truncate_snippet(text: str) -> str:
    """截断文本片段，保留最大长度"""
    snippet = text.strip().replace("\n", " ")
    if len(snippet) <= MAX_SNIPPET_LENGTH:
        return snippet
    return snippet[:MAX_SNIPPET_LENGTH].rstrip() + "..."


def build_prompt(question: str, contexts: List[Dict[str, Any]]) -> str:
    """构建 JSON 格式的 prompt，包含问题、上下文和必要信息（URL等）"""
    payload: Dict[str, Any] = {
        "question": question.strip(),
        "contexts": [],
    }

    for index, context in enumerate(contexts, start=1):
        snippet = _truncate_snippet(str(context.get("content", "")))
        created_at = context.get("created_at")
        # 格式化时间戳
        timestamp = None
        if created_at:
            if hasattr(created_at, "isoformat"):
                timestamp = created_at.isoformat()
            else:
                timestamp = str(created_at)

        payload["contexts"].append(
            {
                "id": index,
                "title": context.get("title") or "(untitled)",
                "city": context.get("city"),
                "url": context.get("url"),
                "score": _format_score(context.get("score")),
                "content": snippet,
                "source_file": context.get("source_file"),
                "chunk_index": context.get("chunk_index"),
                "timestamp": timestamp,
            }
        )

    return json.dumps(payload, ensure_ascii=False, indent=2)
