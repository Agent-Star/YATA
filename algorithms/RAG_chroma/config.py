import os
from pathlib import Path
from dataclasses import dataclass


# 获取项目根目录
PROJECT_ROOT = Path(__file__).parent.absolute()


@dataclass
class Settings:
    # Chroma 配置
    chroma_persist_directory: str = os.getenv(
        "CHROMA_PERSIST_DIR", 
        str(PROJECT_ROOT / "chroma_db")
    )

    # embedding model
    model_name: str = os.getenv(
        "EMBEDDING_MODEL", "BAAI/bge-m3"
    )
    batch_size: int = int(os.getenv("EMBED_BATCH", "64"))
    normalize_embeddings: bool = os.getenv("EMBED_NORMALIZE", "1") == "1"
    # when JSON already contains embeddings, reuse them in ingest
    use_json_embeddings: bool = os.getenv("USE_JSON_EMBEDDINGS", "1") == "1"

    # chunking - 与 travel_rag_full_exporter.py 的策略1保持一致
    chunk_min_size: int = int(os.getenv("CHUNK_MIN_SIZE", "200"))  # 最小长度（字符数）
    chunk_max_size: int = int(os.getenv("CHUNK_MAX_SIZE", "500"))  # 最大长度（字符数）
    chunk_overlap: int = int(os.getenv("CHUNK_OVERLAP", "0"))      # 重叠长度（当前无重叠）

    # search
    top_k: int = int(os.getenv("TOP_K", "5"))
    min_score: float = float(os.getenv("MIN_SCORE", "0.15"))
    
    # query expansion
    use_query_expansion: bool = os.getenv("USE_QUERY_EXPANSION", "1") == "1"
    
    # reranking
    use_reranking: bool = os.getenv("USE_RERANKING", "1") == "1"
    rerank_top_k: int = int(os.getenv("RERANK_TOP_K", "20"))
    rerank_model_name: str = os.getenv(
        "RERANK_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2"
    )
    
    # hybrid search (optional)
    hybrid_search: bool = os.getenv("HYBRID_SEARCH", "0") == "1"
    hybrid_alpha: float = float(os.getenv("HYBRID_ALPHA", "0.7"))


settings = Settings()
