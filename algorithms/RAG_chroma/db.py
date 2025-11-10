import json
from typing import List, Optional, Sequence

import chromadb
from chromadb.config import Settings as ChromaSettings
from config import settings

type ClientAPI = chromadb.ClientAPI  # pyright: ignore[reportPrivateImportUsage]

_client: ClientAPI | None = None
_collection: chromadb.Collection | None = None


def _get_client() -> ClientAPI:
    """获取 Chroma 客户端（持久化到本地目录）"""
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(
            path=settings.chroma_persist_directory,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
    return _client


def _get_collection(embedding_dim: int = 1024) -> chromadb.Collection:
    """获取或创建 collection，确保维度匹配"""
    global _collection
    if _collection is None:
        client = _get_client()
        # 尝试获取现有 collection
        try:
            existing_collection = client.get_collection(name="documents")
            # 检查维度是否匹配：如果 collection 已有数据，检查第一条的维度
            count = existing_collection.count()
            if count > 0:
                # 获取一条数据检查维度
                sample = existing_collection.get(limit=1, include=["embeddings"])
                embeddings_list = sample.get("embeddings")
                # 检查 embeddings 是否存在且不为空
                if (
                    embeddings_list
                    and isinstance(embeddings_list, list)
                    and len(embeddings_list) > 0
                ):
                    first_embedding = embeddings_list[0]
                    if isinstance(first_embedding, list) and len(first_embedding) > 0:
                        existing_dim = len(first_embedding)
                        if existing_dim != embedding_dim:
                            # 维度不匹配，删除旧 collection 重新创建
                            print(
                                f"警告：现有 collection 维度为 {existing_dim}，需要维度 {embedding_dim}，将删除并重新创建"
                            )
                            try:
                                client.delete_collection(name="documents")
                            except Exception:
                                pass  # 如果删除失败，继续尝试创建
                            _collection = client.create_collection(
                                name="documents", metadata={"hnsw:space": "cosine"}
                            )
                        else:
                            _collection = existing_collection
                    else:
                        # embedding 格式异常，使用现有 collection
                        _collection = existing_collection
                else:
                    # 无法获取 embeddings，使用现有 collection
                    _collection = existing_collection
            else:
                # collection 存在但为空，可以直接使用
                _collection = existing_collection
        except Exception:
            # collection 不存在或其他错误，尝试创建新的
            try:
                _collection = client.create_collection(
                    name="documents",
                    metadata={"hnsw:space": "cosine"},  # 使用余弦相似度
                )
            except Exception as create_error:
                # 如果创建失败（可能是已存在），尝试获取
                if "already exists" in str(create_error).lower():
                    _collection = client.get_collection(name="documents")
                else:
                    raise create_error
    return _collection


def init_db(embedding_dim: int = 1024) -> None:
    """初始化 Chroma 数据库（创建 collection）"""
    # 确保 collection 存在且维度正确
    _get_collection(embedding_dim=embedding_dim)
    print(f"Chroma 数据库已初始化（维度: {embedding_dim}）")


def insert_documents(rows: Sequence[dict], embedding_dim: int = 1024) -> None:
    """批量插入文档到 Chroma"""
    if not rows:
        return

    collection = _get_collection(embedding_dim=embedding_dim)

    # 准备 Chroma 需要的数据格式
    ids = []
    embeddings = []
    documents = []  # 文本内容
    metadatas = []

    for idx, row in enumerate(rows):
        # 生成唯一 ID：使用 source_file 和 chunk_index 组合
        doc_id = f"{row.get('source_file', 'unknown')}_{row.get('chunk_index', idx)}"
        ids.append(doc_id)

        # embedding 已经是列表格式
        embedding = row.get("embedding")
        if embedding is None:
            continue
        if isinstance(embedding, list):
            embeddings.append(embedding)
        else:
            embeddings.append(list(embedding))

        # 文本内容
        documents.append(row.get("content", ""))

        # 元数据（Chroma 的 metadata 必须是字典，值必须是字符串、数字或布尔值）
        metadata = {
            "city": str(row.get("city", "")),
            "language": str(row.get("language", "")),
            "title": str(row.get("title", "")),
            "url": str(row.get("url", "")),
            "source_file": str(row.get("source_file", "")),
            "chunk_index": str(row.get("chunk_index", "")),
        }

        # 添加 timestamp 到 metadata（如果存在）
        timestamp = row.get("timestamp")
        if timestamp:
            metadata["timestamp"] = str(timestamp)

        author = row.get("author")
        if author not in (None, ""):
            metadata["author"] = str(author)

        day = row.get("day")
        if day not in (None, ""):
            metadata["day"] = str(day)

        # 如果有额外的 meta 字段，尝试合并
        if row.get("meta"):
            meta_dict = row.get("meta")
            if isinstance(meta_dict, dict):
                # 只保留可以序列化的值
                for k, v in meta_dict.items():
                    if isinstance(v, (str, int, float, bool)):
                        metadata[f"meta_{k}"] = str(v)
                    elif isinstance(v, dict):
                        # 嵌套字典转为 JSON 字符串
                        metadata[f"meta_{k}"] = json.dumps(v, ensure_ascii=False)

        metadatas.append(metadata)

    # 批量插入
    collection.add(
        ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas
    )


def delete_by_source(source_file: str, embedding_dim: int = 1024) -> None:
    """根据 source_file 删除文档"""
    collection = _get_collection(embedding_dim=embedding_dim)
    # Chroma 可以通过 metadata 过滤删除
    collection.delete(where={"source_file": source_file})


def get_stats(embedding_dim: int = 1024) -> dict:
    """获取数据库统计信息"""
    collection = _get_collection(embedding_dim=embedding_dim)
    count = collection.count()

    # 获取所有文档以提取城市列表
    results = collection.get(limit=10000)  # 根据需要调整
    cities = set()
    if res := results.get("metadatas"):
        for meta in res:
            if meta and "city" in meta:
                cities.add(meta["city"])

    return {"total": count, "cities": sorted(list(cities))}


def vector_search(
    query_vector: List[float],
    top_k: int,
    city: Optional[str] = None,
    embedding_dim: int = 1024,
) -> List[dict]:
    """向量搜索"""
    collection = _get_collection(embedding_dim=embedding_dim)

    # 构建 where 条件
    where = None
    if city:
        where = {"city": city}

    # 执行搜索
    results = collection.query(
        query_embeddings=[query_vector],
        n_results=top_k,
        # BUG: ignored `reportArgumentType`
        where=where,  # pyright: ignore[reportArgumentType]
        include=["documents", "metadatas", "distances"],
    )

    # 转换结果格式（匹配原来的 PostgreSQL 返回格式）
    output = []

    # results 的结构：
    # {
    #   "ids": [[id1, id2, ...]],
    #   "documents": [[doc1, doc2, ...]],
    #   "metadatas": [[meta1, meta2, ...]],
    #   "distances": [[dist1, dist2, ...]]
    # }

    if not results["ids"] or not results["ids"][0]:
        return []

    ids = results["ids"][0]
    docs = results["documents"][0] if results["documents"] else []
    metas = results["metadatas"][0] if results["metadatas"] else []
    distances = results["distances"][0] if results["distances"] else []

    for i, doc_id in enumerate(ids):
        # Chroma 使用距离（越小越相似），需要转换为相似度分数
        # cosine distance: 0 = 完全相同, 2 = 完全相反
        # 相似度 score = 1 - (distance / 2)，范围 [0, 1]
        distance = distances[i] if i < len(distances) else 1.0
        score = 1.0 - (distance / 2.0)  # 转换为相似度分数

        meta = metas[i] if i < len(metas) else {}
        doc_text = docs[i] if i < len(docs) else ""

        output.append(
            {
                "id": doc_id,
                "city": meta.get("city"),
                "language": meta.get("language"),
                "title": meta.get("title"),
                "url": meta.get("url"),
                "source_file": meta.get("source_file"),
                # BUG: ignored `reportArgumentType`
                "chunk_index": int(meta.get("chunk_index", 0))  # pyright: ignore[reportArgumentType]
                if meta.get("chunk_index")
                else None,
                "content": doc_text,
                "score": score,
                "created_at": meta.get("timestamp"),  # 从 metadata 中获取 timestamp
            }
        )

    return output
