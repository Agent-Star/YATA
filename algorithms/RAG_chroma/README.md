# RAG Chroma API

基于 ChromaDB 和 BGE-M3 的向量检索服务，提供高效的 RAG（检索增强生成）能力。

## 项目结构

核心代码文件：

- `api_server.py` - FastAPI 服务
- `cli.py` - 命令行工具
- `config.py` - 配置管理
- `db.py` - ChromaDB 操作
- `embedder.py` - 嵌入模型封装
- `ingest.py` - 数据导入脚本
- `search.py` - 搜索核心逻辑
- `rag.py` - Prompt 构建
- `travel_rag_full_exporter.py` - 数据导出工具

## 功能特性

- **向量检索**：基于 BGE-M3 模型（1024维）的语义搜索
- **多城市支持**：支持按城市过滤检索结果
- **智能重排序**：可选的重排序功能提升结果准确性
- **ChromaDB 持久化**：数据持久化存储，支持增量更新
- **RESTful API**：提供简洁的 HTTP 接口，便于集成

## 快速开始

### 安装依赖

先安装 `uv` 包管理器:

- linux / macos

  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```

- windows

  ```powershell
  powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
  ```

然后配置依赖:

```bash
uv sync
```

最后加载虚拟环境:

- linux / macos

  ```bash
  uv venv
  source .venv/bin/activate
  ```

- windows

  ```powershell
  uv venv
  ./.venv/Scripts/activate
  ```

### 初始化数据库

将数据文件（JSON 格式）放入 `data/` 目录，然后运行：

```bash
python ingest.py
```

### 启动 API 服务

```bash
python api_server.py
```

服务默认运行在 `http://localhost:8001`

### 使用命令行工具

```bash
# 使用默认 question.json
python cli.py

# 指定输入文件
python cli.py --input question.json --city Paris --top_k 5
```

## API 接口

### 1. 健康检查

**GET** `/health`

检查服务状态。

**响应示例：**

```json
{
  "status": "ok"
}
```

---

### 2. 向量搜索

**POST** `/search`

执行向量检索，返回相关文档上下文。

**请求体：**

| 字段   | 类型    | 说明               | 必填 |
|--------|---------|--------------------|------|
| query  | string  | 搜索查询           | 是   |
| city   | string  | 城市过滤（可选）   | 否   |
| top_k  | integer | 返回结果数量（可选）| 否   |

**请求示例：**

```json
{
  "query": "巴黎有哪些著名景点",
  "city": "Paris",
  "top_k": 5
}
```

**响应示例：**

```json
{
  "contexts": "...",
  "results": [
    {
      "id": "...",
      "city": "Paris",
      "title": "...",
      "url": "...",
      "content": "...",
      "score": 0.85,
      "source_file": "...",
      "chunk_index": 0
    }
  ]
}
```

**错误响应：**

| HTTP | 说明           |
|------|----------------|
| 400  | 查询不能为空   |
| 500  | 搜索失败       |

---

## 使用示例

### Python 示例

```python
import requests

# 搜索
response = requests.post(
    "http://localhost:8001/search",
    json={
        "query": "推荐巴黎景点",
        "city": "Paris",
        "top_k": 3
    }
)
data = response.json()
print(data["contexts"])
```

### cURL 示例

```bash
curl -X POST "http://localhost:8001/search" \
  -H "Content-Type: application/json" \
  -d '{"query": "推荐巴黎旅游景点", "top_k": 3}'
```

## 项目结构 (文件树)

```txt
.
├── api_server.py          # FastAPI 服务
├── cli.py                 # 命令行工具
├── ingest.py              # 数据导入脚本
├── search.py              # 搜索核心逻辑
├── embedder.py            # 嵌入模型封装
├── db.py                  # ChromaDB 操作
├── config.py              # 配置管理
├── rag.py                 # Prompt 构建
├── data/                  # 数据目录
└── chroma_db/             # ChromaDB 存储目录
```

## 配置

通过环境变量配置：

```bash
# ChromaDB 存储路径
CHROMA_PERSIST_DIR=./chroma_db

# 嵌入模型
EMBEDDING_MODEL=BAAI/bge-m3

# 搜索参数
TOP_K=5
MIN_SCORE=0.15

# 重排序
USE_RERANKING=1
RERANK_TOP_K=20

# API 端口
RAG_API_PORT=8001
```
