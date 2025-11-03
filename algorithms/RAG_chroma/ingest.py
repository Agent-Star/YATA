"""
数据导入脚本：将 data/*.json 文件中的数据导入到 Chroma 数据库
"""
import json
from pathlib import Path
from typing import Dict, Any, List

from config import settings
from db import init_db, insert_documents, delete_by_source
from embedder import embed_texts, get_embedding_dimension



def _select_url(urls: Dict[str, Any]) -> str:
    """从 urls 字典中优先选择合适的 URL"""
    if not isinstance(urls, dict):
        return ""
    # 优先选择 wikipedia, official, official_site
    for preferred in ("wikipedia", "official", "official_site"):
        value = urls.get(preferred)
        if isinstance(value, str) and value:
            return value
    # 否则返回第一个非空字符串值
    for value in urls.values():
        if isinstance(value, str) and value:
            return value
    return ""


def load_rows_from_file(path: Path) -> List[Dict[str, Any]]:
    """从单个 JSON 文件加载数据并转换为数据库行格式"""
    with path.open("r", encoding="utf-8") as fh:
        payload = json.load(fh)

    city = payload.get("city_name") or payload.get("city")
    language = payload.get("lang") or payload.get("language")
    timestamp = payload.get("timestamp")  # 从 JSON 文件根级别提取 timestamp
    urls = payload.get("urls") or {}
    default_url = _select_url(urls)
    knowledge = payload.get("knowledge") or {}
    chunks = knowledge.get("text_chunks") if isinstance(knowledge, dict) else None

    rows: List[Dict[str, Any]] = []
    if not isinstance(chunks, list):
        return rows

    # 收集需要计算 embedding 的文本
    texts_to_embed: List[str] = []
    embed_indices: List[int] = []
    for idx, chunk in enumerate(chunks):
        if not isinstance(chunk, dict):
            continue
        if chunk.get("embedding") is None:
            text = chunk.get("text") or chunk.get("content") or ""
            if text:
                texts_to_embed.append(text)
                embed_indices.append(idx)

    # 批量计算缺失的 embeddings
    computed_embeddings: List[Any] = []
    if texts_to_embed:
        computed_embeddings = embed_texts(texts_to_embed).tolist()

    computed_map = {i: emb for i, emb in zip(embed_indices, computed_embeddings)}

    # 构建数据库行，同时检查 embedding 维度
    expected_dim = None  # 期望的维度（从第一个 embedding 推断）
    skipped_count = 0
    
    for idx, chunk in enumerate(chunks):
        if not isinstance(chunk, dict):
            continue
        text = (chunk.get("text") or chunk.get("content") or "").strip()
        if not text:
            continue

        # 优先使用 JSON 中的 embedding，否则使用计算得到的
        embedding = chunk.get("embedding")
        if embedding is None:
            embedding = computed_map.get(idx)
        if embedding is None:
            continue
        
        # 检查 embedding 维度
        if not isinstance(embedding, list):
            embedding = list(embedding)
        
        emb_dim = len(embedding)
        
        # 如果这是第一个 embedding，设置期望维度
        if expected_dim is None:
            expected_dim = emb_dim
        # 如果维度不匹配，跳过这条数据
        elif emb_dim != expected_dim:
            skipped_count += 1
            continue

        # 优先使用 JSON 根级别的 urls.wikipedia，否则使用 chunk 中的 URL
        chunk_url = chunk.get("url") or chunk.get("source_url")
        final_url = default_url if default_url else chunk_url
        
        rows.append(
            {
                "city": city,
                "language": language,
                "title": chunk.get("title") or payload.get("city_name"),
                "url": final_url,  # 优先使用 JSON 根级别的 urls.wikipedia (通过 _select_url 提取)
                "source_file": path.name,
                "chunk_index": idx,
                "content": text,
                "embedding": embedding,
                "timestamp": timestamp,  # 添加 timestamp 字段
                "meta": {"urls": urls} if isinstance(urls, dict) else None,
            }
        )
    
    # 如果跳过了一些数据，给出提示
    if skipped_count > 0:
        print(f"  跳过 {skipped_count} 条维度不匹配的记录（期望维度: {expected_dim if expected_dim else '未知'}）")

    return rows


def main() -> None:
    """主函数：初始化数据库并导入所有 JSON 文件"""
    print("初始化 Chroma 数据库...")
    try:
        emb_dim = get_embedding_dimension()
    except Exception:
        emb_dim = 1024
    init_db(embedding_dim=emb_dim)

    data_dir = Path("data")
    if not data_dir.exists():
        print(f"错误：数据目录不存在: {data_dir}")
        return

    json_files = sorted(data_dir.glob("*.json"))
    if not json_files:
        print(f"错误：在 {data_dir} 中未找到 JSON 文件")
        return

    print(f"找到 {len(json_files)} 个 JSON 文件")
    total_rows = 0
    skipped_files = []  # 记录跳过的文件

    for path in json_files:
        print(f"\n处理文件: {path.name}")
        try:
            rows = load_rows_from_file(path)
            if not rows:
                print(f"  跳过：文件中没有有效数据")
                skipped_files.append((path.name, "文件中没有有效数据"))
                continue
            
            # 检查第一条数据的维度，如果与期望维度不匹配，跳过整个文件
            if rows:
                first_embedding = rows[0].get("embedding")
                if first_embedding and isinstance(first_embedding, list):
                    file_emb_dim = len(first_embedding)
                    if file_emb_dim != emb_dim:
                        print(f"  跳过：文件 embedding 维度为 {file_emb_dim}，期望维度为 {emb_dim}")
                        skipped_files.append((path.name, f"维度不匹配 ({file_emb_dim}维，期望{emb_dim}维)"))
                        continue

            # 删除该文件的旧数据（如果存在）
            delete_by_source(path.name, embedding_dim=emb_dim)
            # 插入新数据（传递 embedding 维度）
            insert_documents(rows, embedding_dim=emb_dim)
            print(f"  ✓ 已导入 {len(rows)} 条记录")
            total_rows += len(rows)
        except Exception as e:
            print(f"  ✗ 错误：{e}")
            skipped_files.append((path.name, f"导入错误: {str(e)}"))
            import traceback
            traceback.print_exc()
            continue

    # 输出导入结果统计
    print(f"\n{'='*60}")
    print(f"导入完成！总共导入 {total_rows} 条记录")
    print(f"成功导入文件数: {len(json_files) - len(skipped_files)}")
    
    if skipped_files:
        print(f"\n跳过的文件 ({len(skipped_files)} 个):")
        for filename, reason in skipped_files:
            print(f"  - {filename} ({reason})")
    else:
        print("\n所有文件都已成功导入！")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()

