from typing import Optional, List, Dict, Any
import numpy as np
from config import settings
from embedder import embed_texts, rerank
from db import vector_search



def _expand_query(query: str) -> str:
    """简单的查询扩展：为查询添加相关术语以提升召回率"""
    # 常见旅游相关词汇扩展
    tourism_keywords = {
        "attractions": ["places to visit", "landmarks", "sights", "must see"],
        "museums": ["galleries", "exhibitions", "collections"],
        "weather": ["climate", "temperature", "forecast"],
        "restaurants": ["dining", "food", "cuisine", "meals"],
        "hotels": ["accommodation", "lodging", "places to stay"],
        "shopping": ["markets", "stores", "boutiques"],
    }
    
    query_lower = query.lower()
    expanded_terms = []
    
    # 检查查询中的关键词并添加相关术语
    for key, synonyms in tourism_keywords.items():
        if key in query_lower:
            expanded_terms.extend(synonyms[:2])  # 添加前2个相关词
    
    if expanded_terms:
        return f"{query} {' '.join(expanded_terms)}"
    return query


def search(query: str, city: Optional[str] = None, top_k: Optional[int] = None) -> List[Dict[str, Any]]:
    if not query or not query.strip():
        return []
    
    # 查询扩展
    expanded_query = _expand_query(query) if settings.use_query_expansion else query
    
    # 初始检索：如果使用重排序，检索更多候选结果
    k = top_k or settings.top_k
    initial_k = settings.rerank_top_k if settings.use_reranking else k
    
    # 使用扩展后的查询进行检索
    q_emb: np.ndarray = embed_texts([expanded_query])[0]
    results = vector_search(q_emb.tolist(), top_k=initial_k, city=city)
    
    # 过滤低分结果
    filtered = [r for r in results if r.get("score", 0) >= settings.min_score]
    
    if not filtered:
        return []
    
    # 重排序
    if settings.use_reranking and len(filtered) > 1:
        # 使用原始查询（而非扩展后的）进行重排序，更精确
        documents = [r.get("content", "") for r in filtered]
        rerank_scores = rerank(query, documents)
        
        # 归一化重排序分数到 [0, 1] 范围
        # CrossEncoder 输出可能不在 [0,1] 范围，使用 min-max 归一化
        if rerank_scores:
            min_rerank = min(rerank_scores)
            max_rerank = max(rerank_scores)
            if max_rerank > min_rerank:
                normalized_rerank = [(s - min_rerank) / (max_rerank - min_rerank) 
                                     for s in rerank_scores]
            else:
                normalized_rerank = [1.0] * len(rerank_scores)
        else:
            normalized_rerank = []
        
        # 合并原始分数和重排序分数（加权平均）
        for result, rerank_score, norm_rerank in zip(filtered, rerank_scores, normalized_rerank):
            original_score = result.get("score", 0)
            # 使用归一化后的重排序分数
            combined_score = 0.3 * original_score + 0.7 * norm_rerank
            result["score"] = combined_score
            result["rerank_score"] = float(rerank_score)
            result["rerank_score_normalized"] = norm_rerank
        
        # 按新分数重新排序
        filtered.sort(key=lambda x: x.get("score", 0), reverse=True)
    
    # 返回 top_k 结果
    return filtered[:k]


