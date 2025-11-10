from __future__ import annotations

from typing import List

import numpy as np
from config import settings
from sentence_transformers import CrossEncoder, SentenceTransformer

_model: SentenceTransformer | None = None
_reranker: CrossEncoder | None = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        print(f"正在加载 embedding 模型: {settings.model_name}...")
        print("(首次运行需要下载模型文件，可能需要几分钟，请耐心等待)")
        _model = SentenceTransformer(settings.model_name)
        # 显示模型缓存路径
        import os

        cache_dir = os.getenv("HF_HOME") or os.path.expanduser("~/.cache/huggingface")
        print("模型加载完成！")
        hub_path = os.path.join(cache_dir, "hub")
        print(f"模型缓存位置: {hub_path}")
    return _model


def embed_texts(texts: List[str]) -> np.ndarray:
    model = _get_model()
    embeddings = model.encode(
        texts,
        batch_size=settings.batch_size,
        show_progress_bar=False,
        convert_to_numpy=True,
        normalize_embeddings=settings.normalize_embeddings,
    )
    # Ensure float32 for pgvector
    return embeddings.astype(np.float32)


def get_embedding_dimension() -> int:
    """返回当前 embedding 模型的向量维度"""
    # BGE-M3 固定为 1024 维
    if "bge-m3" in settings.model_name.lower():
        return 1024

    try:
        model = _get_model()
        if hasattr(model, "get_sentence_embedding_dimension") and (
            dim := model.get_sentence_embedding_dimension()
        ):
            return int(dim)
        # 兜底：用单条文本编码推断维度
        dim = int(embed_texts(["test"]).shape[1])
        return dim
    except Exception:
        # 如果加载失败，根据模型名称返回默认维度
        if "bge-m3" in settings.model_name.lower():
            return 1024
        elif "bge-base" in settings.model_name.lower():
            return 768
        elif "bge-small" in settings.model_name.lower():
            return 384
        else:
            return 384  # 默认


def _get_reranker() -> CrossEncoder:
    global _reranker
    if _reranker is None:
        print("正在加载重排序模型...")
        print("(首次运行需要下载模型文件，可能需要几分钟，请耐心等待)")
        _reranker = CrossEncoder(settings.rerank_model_name)
        print("重排序模型加载完成！")
    return _reranker


def rerank(query: str, documents: List[str]) -> List[float]:
    """使用交叉编码器对文档进行重排序"""
    if not documents:
        return []
    reranker = _get_reranker()
    pairs = [[query, doc] for doc in documents]
    scores = reranker.predict(pairs, show_progress_bar=False)
    return scores.tolist() if hasattr(scores, "tolist") else list(scores)
