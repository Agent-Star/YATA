import argparse
import json
import sys
from pathlib import Path
from typing import Optional

from db import init_db
from embedder import get_embedding_dimension
from rag import build_prompt
from search import search


def main():
    parser = argparse.ArgumentParser(
        description="RAG CLI: read question JSON, output prompt"
    )
    parser.add_argument(
        "--input",
        "-i",
        type=str,
        default=None,
        help="Path to input JSON (default: question.json in current directory)",
    )
    parser.add_argument("--city", type=str, default=None, help="Optional city filter")
    parser.add_argument("--top_k", type=int, default=None, help="Override top_k")
    args = parser.parse_args()

    # load question JSON
    if args.input is None:
        # 默认读取同目录下的 question.json
        input_file = Path(__file__).parent / "question.json"
        if not input_file.exists():
            print(f"错误：未找到 question.json 文件: {input_file}", file=sys.stderr)
            sys.exit(1)
        with open(input_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    elif args.input == "-":
        # 从标准输入读取
        data = json.loads(sys.stdin.read())
    else:
        # 从指定文件读取
        with open(args.input, "r", encoding="utf-8") as f:
            data = json.load(f)

    question: str = data.get("question") or data.get("query") or ""
    if not question:
        print("Missing 'question' in input JSON", file=sys.stderr)
        sys.exit(1)

    # prefer explicit city arg over payload city
    city: Optional[str] = args.city or data.get("city")
    # prefer explicit top_k arg over payload top_k
    top_k: Optional[int] = args.top_k or data.get("top_k")

    # 使用当前模型的向量维度初始化数据库表结构
    try:
        emb_dim = get_embedding_dimension()
    except Exception:
        emb_dim = 1024  # bge-m3 兜底
    init_db(embedding_dim=emb_dim)

    # 执行检索
    results = search(question, city=city, top_k=top_k)
    prompt = build_prompt(question, results)
    print(prompt)


if __name__ == "__main__":
    main()
