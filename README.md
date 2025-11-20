# YATA - Yet Another Travel Agent

YATA 是一个端到端的 AI 旅行规划产品：前端提供聊天式旅行助手、灵感推荐与收藏管理；后端提供用户认证、SSE 规划流和数据接口；算法侧包含 NLU、多 Agent 规划器与 RAG 检索。本仓库是整个项目的 mono-repo，方便前后端与算法团队协同开发。

## Role Allocation

- 前端 - 刘俊琦
- 数据搜集 + RAG - 张曦文， 黄禄凯
- LLM + Evaluation - 黄兰婷， 郭萱
- 后端 - 王文翰

## Repository Structure

```txt
YATA/
├── frontend/        # Next.js + Semi UI 前端 (聊天、仪表盘、灵感、指南等模块)
├── backend/         # FastAPI 服务；负责认证、Planner API、SSE 流、收藏等
├── algorithms/      # 算法实验区 (NLU/LangGraph/RAG/Chroma 等子项目)
│   ├── NLU/         # 基于多 Agent 的 NLU & itinerary 生成服务
│   └── RAG_chroma/  # 检索增强、数据处理脚本
└── README.md        # 当前说明文档
```

每个子目录都包含更详细的 README，可按需深入了解。

## System Overview

| 层级 | 技术 | 说明 |
| ---- | ---- | ---- |
| 前端 | Next.js, Semi UI, React Context, i18next | 提供多页面体验（聊天、Saved Trips、Dashboard、Inspiration、Guides），通过 `planner/plan/stream` SSE 接收实时 AI 回复，并与认证/收藏接口交互。 |
| 后端 | FastAPI, FastAPI-Users, LangGraph, PostgreSQL/SQLite, Chroma | 提供用户体系、JWT 认证、Planner/收藏 API，以及与 LangGraph Agents、RAG、LLM 推理服务集成。 |
| 算法 | 多 Agent NLU、RAG Chroma、LLM 驱动能力 | 在 `algorithms` 中独立迭代，NLU 服务可直接通过 FastAPI 暴露 `/nlu`, `/nlu/simple`, `/nlu/stream` 等接口，供后端/前端联调。 |

典型请求链路：

1. 用户在前端登录（调用后端 `/auth/*`）。
2. 聊天界面将问题发送给后端 Planner API；后端与 LangGraph Agents、NLU 服务、RAG 知识库交互得到回答。
3. SSE 将回复流式推送到前端；用户可收藏、查看历史、切换场景；收藏数据存储在后端 DB。

## Key Features

- 🤖 **AI 旅行助手**：多轮对话、Quick Actions、语音输入、收藏、自动滚动。
- 🗂 **Saved Trips & Dashboard**：查看收藏、旅行统计卡片、任务概览。
- 💡 **Inspiration & Guides**：静态灵感/指南卡片，后续可与 RAG 真实数据对接。
- 🔐 **Auth**：基于 FastAPI-Users 的注册/登录、JWT、邮箱校验、密码重置。
- 🧠 **NLU & Planner**：多 Agent 意图识别、Clarifier/Verifier pipeline、RAG 检索增强、LangGraph Orchestration。

## Getting Started

> 以下为最小可运行方案；详细参数与脚本请参考 `frontend/README.md`, `backend/README.md`, `algorithms/NLU/README.md`。

### 1. Clone & Prerequisites

- Node.js >= 18
- Python >= 3.10
- [uv](https://github.com/astral-sh/uv) (用于后端/算法依赖)
- PostgreSQL / SQLite / Chroma (可选，开发可使用 SQLite + 内嵌 Chroma)

```bash
git clone <repo-url>
cd YATA
```

### 2. Backend Setup

```bash
cd backend
cp env.example .env        # 填写 OpenAI/Claude/Gemini 等模型 key、AUTH_JWT_SECRET 等
uv venv && source .venv/bin/activate
uv sync --frozen
python src/run_service.py  # 默认 8080 端口
```

> API 文档: `http://localhost:8080/docs`。如需 SSE/Planner，需要保证 `langgraph`、`agents` 配置正确且向量库可用。

### 3. (Optional) Algorithms Services

如果需要独立的 NLU/RAG 服务：

```bash
cd algorithms/NLU
uv venv && source .venv/bin/activate
uv sync
python fastapi_server.py   # 默认 8010
```

RAG/Chroma 数据处理脚本位于 `algorithms/RAG_chroma`，可在准备好目的地数据后运行构建索引。

### 4. Frontend Setup

```bash
cd frontend
cp .env.example .env.local   # 设置 NEXT_PUBLIC_API_BASE_URL 等
npm install
npm run dev                  # http://localhost:3000
```

前端将通过 `NEXT_PUBLIC_API_BASE_URL` 调用后端 API；未配置时默认同域（Next.js API Routes）。

### 5. Integration Notes

- SSE 入口：`/api/planner/plan/stream`（前端 `lib/services/aiPlanner.js`），需要后端返回 `text/event-stream`。
- 收藏接口：`/planner/favorites`，与 `Saved Trips` 页面联动。
- NLU 服务：后端可按需调用 `algorithms/NLU`，也可直接在前端调试。

## Development Tips

- **前端**：组件集中在 `components/` 与 `modules/`，状态管理位于 `store/` + `lib/hooks`。全局样式 `styles/globals.css`，i18n 文案在 `lib/i18n/resources.js`。
- **后端**：代理逻辑位于 `src/agents`，核心服务在 `src/service/service.py`，认证模块在 `src/auth`。`compose.yaml` 提供容器化示例，`docs/` 下有 Auth 快速开始。
- **算法**：`NLU_module/agents/adviser/*` 定义了 Advisor pipeline，`source/` 管理 prompt/模型配置。通过 `fastapi_server.py` 暴露 HTTP 接口。
- **测试**：前端可使用 `npm run lint/test`（如已配置）；后端单元测试在 `backend/tests`；NLU 部分可自建脚本在 `algorithms/NLU/docs` 中说明。

## Additional Documentation

- 前端: [`frontend/README.md`](frontend/README.md)
- 后端: [`backend/README.md`](backend/README.md)
- NLU 服务: [`algorithms/NLU/README.md`](algorithms/NLU/README.md)
- 用户认证: [`backend/docs/Authentication.md`](backend/docs/Authentication.md)
- Auth 快速开始: [`backend/docs/Quick_Start_Auth.md`](backend/docs/Quick_Start_Auth.md)

欢迎根据各子模块 README 获取更多实现细节，并在对应目录下提交 PR。
