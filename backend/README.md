# YATA 后端项目

这是 YATA (Yet Another Travel Agent) 项目的后端部分, 基于 [JoshuaC215](https://github.com/JoshuaC215) 的 [Agent Service Toolkit](https://github.com/JoshuaC215/agent-service-toolkit) 构建.

## 项目架构

![架构](./media/agent_architecture.png)

该架构参考了 [JoshuaC215](https://github.com/JoshuaC215) 的 [Agent Service Toolkit](https://github.com/JoshuaC215/agent-service-toolkit), 架构图引用自 [Agent Service Toolkit](https://github.com/JoshuaC215/agent-service-toolkit) 项目的 [相关设计](https://github.com/JoshuaC215/agent-service-toolkit/blob/main/media/agent_architecture.png).

## 技术栈

- [FastAPI](https://fastapi.tiangolo.com/): 高性能的 Python 后端框架.
- [FastAPI-Users](https://fastapi-users.github.io/fastapi-users/): 完整的用户认证系统，支持注册、登录、JWT 认证等功能.
- [LangGraph](https://langchain-ai.github.io/langgraph/): 即开即用的 AI 代理框架, 可用于构建复杂的 `multi-agent` 系统.
- [ChromaDB](https://www.chromadb.io/): 高性能的开源向量数据库, 用于存储和管理 `向量` 数据, 以构建 `RAG` 知识库.
- [PostgreSQL](https://www.postgresql.org/): 高性能的开源关系型数据库, 用于存储和管理 `checkpoint`、用户数据以及其他必要数据.

## 关键文件 (项目结构)

- [src/agents/](./src/agents): 核心模块, 定义了功能不同的多个 agent.
- [src/auth/](./src/auth): 用户认证模块, 基于 FastAPI-Users 实现完整的用户管理功能.
- [src/schema/](./src/schema): 通信协议层, 主要用于定义前后端交互时, 部分字段的复杂结构.
- [src/core/](./src/core): LLM 定义与配置层.
- [src/memory/](./src/memory): 用于后端与数据库的交互.
- [src/service/service.py](./src/service/service.py): 面向前端与 agent 的后端服务.
- [src/client/client.py](./src/client/client.py): 面向 agent 的客户端.
- [src/streamlit_app.py](./src/streamlit_app.py): 提供聊天界面的 [Streamlit](https://streamlit.io/) 应用 (简易前端), 用于测试与调试.

## 运行项目

1. 配置环境变量
   - 目前支持 `ChatGPT`, `Claude`, `Gemini`, `DeepSeek`, `Groq` 等模型, 也可以使用 `OpenRouter` 提供的中转服务.
   - [env.example](./env.example) 中提供了示例配置, 可以使用下述指令直接创建 `.env` 文件:

    ```bash
    cp env.example .env
    ```

   - 至少需要配置以下内容:
     - LLM API 密钥 (如 `OPENAI_API_KEY`)
     - JWT 认证密钥 (`AUTH_JWT_SECRET`, 生产环境请使用强随机密钥)

2. 安装 uv 包管理器
   - 已测试版本: `0.7.19`

    ```bash
    curl -LsSf https://astral.sh/uv/0.7.19/install.sh | sh
    ```

3. 配置虚拟环境与依赖

    ```bash
    uv venv
    uv sync --frozen
    source ./.venv/bin/activate
    ```

4. 启动后端服务

    ```bash
    python src/service/service.py
    ```

5. 启动简易前端界面 (可选)
  
    ```bash
    streamlit run src/streamlit_app.py
    ```

## 用户认证系统

后端已集成完整的用户认证系统，支持：

- ✅ 用户注册与登录
- ✅ JWT Token 认证
- ✅ 密码重置与邮箱验证
- ✅ 用户信息管理
- ✅ 支持 SQLite 和 PostgreSQL

### 快速开始

查看 [用户认证快速开始指南](./docs/Quick_Start_Auth.md) 了解如何：

- 注册和登录用户
- 获取和使用 JWT token
- 在前端集成认证功能

### 完整文档

- [用户认证系统完整文档](./docs/Authentication.md)
- [保护 Agent 端点的示例](./src/service/auth_protected_routes_example.py)

### API 文档

服务启动后，访问以下地址查看交互式 API 文档：

- Swagger UI: <http://localhost:8080/docs>
- ReDoc: <http://localhost:8080/redoc>

## 注意事项

- 目前仍处于初步开发阶段, [项目结构](#关键文件-项目结构) 后续可能会有变动.
  - [项目架构](#项目架构) 也可能在现有基础上进行拓展.
- **安全提示**: 生产环境部署时, 请务必:
  - 修改 `AUTH_JWT_SECRET` 为强随机密钥
  - 使用 PostgreSQL 而非 SQLite
  - 启用 HTTPS
  - 实现邮件发送功能 (密码重置和邮箱验证)
