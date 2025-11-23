# YATA's Algorithms

面向智能旅行助手的算法集合。包含 RAG 向量检索服务与 NLU 会话式理解/生成服务，支持检索增强、意图识别、行程规划与推荐等核心能力。

## 子项目

- RAG Chroma API
  - 基于 ChromaDB + BGE-M3（1024 维）的高效语义检索与 RAG
  - 支持城市过滤、可选重排序、持久化与增量更新
  - 提供简洁 RESTful API（/health, /search）
  - 详见: ./RAG_chroma/README.md

- YATA NLU 服务
  - 多 Agent 对话：意图识别、行程规划、推荐、追问/澄清与逻辑校验
  - 提供完整/简化/流式（SSE）接口与会话管理（LRU 清理机制）
  - 详见: ./NLU/README.md

## 快速开始

前置依赖（两项目通用）：
- Python 3.10+
- 推荐使用 `uv` 管理依赖与虚拟环境

安装与环境：
- macOS/Linux:
  - 安装 uv: `curl -LsSf https://astral.sh/uv/install.sh | sh`
  - 同步依赖: `uv sync`
  - 创建并激活虚拟环境: `uv venv && source .venv/bin/activate`
- Windows (PowerShell):
  - 安装 uv: `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`
  - 同步依赖: `uv sync`
  - 创建并激活虚拟环境: `uv venv && ./.venv/Scripts/activate`



更多细节与示例请查看各子项目 README：
- RAG Chroma API: `./RAG_chroma/README.md`
- YATA NLU: `./NLU/README.md`
