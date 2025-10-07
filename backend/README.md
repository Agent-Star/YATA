# YATA 后端项目

这是 YATA (Yet Another Travel Agent) 项目的后端部分, 基于 [JoshuaC215](https://github.com/JoshuaC215) 的 [Agent Service Toolkit](https://github.com/JoshuaC215/agent-service-toolkit) 构建.

## 项目架构

![架构](./media/agent_architecture.png)

该架构参考了 [JoshuaC215](https://github.com/JoshuaC215) 的 [Agent Service Toolkit](https://github.com/JoshuaC215/agent-service-toolkit), 架构图引用自 [Agent Service Toolkit](https://github.com/JoshuaC215/agent-service-toolkit) 项目的 [相关设计](https://github.com/JoshuaC215/agent-service-toolkit/blob/main/media/agent_architecture.png).

## 技术栈

- [FastAPI](https://fastapi.tiangolo.com/): 高性能的 Python 后端框架.
- [LangGraph](https://langchain-ai.github.io/langgraph/): 即开即用的 AI 代理框架, 可用于构建复杂的 `multi-agent` 系统.
- [ChromaDB](https://www.chromadb.io/): 高性能的开源向量数据库, 用于存储和管理 `向量` 数据, 以构建 `RAG` 知识库.
- [PostgreSQL](https://www.postgresql.org/): 高性能的开源关系型数据库, 用于存储和管理 `checkpoint` 以及其他必要数据.

## 关键文件 (项目结构)

- [src/agents/](./src/agents): 核心模块, 定义了功能不同的多个 agent.
- [src/schema/](./src/schema): 通信协议层, 主要用于定义前后端交互时, 部分字段的复杂结构.
- [src/core/](./src/core): LLM 定义与配置层.
- [src/memory/](./src/memory): 用于后端与数据库的交互.
- [src/service/service.py](./src/service/service.py): 面向前端与 agent 的后端服务.
- [src/client/client.py](./src/client/client.py): 面向 agent 的客户端.
- [src/streamlit_app.py](./src/streamlit_app.py): 提供聊天界面的 [Streamlit](https://streamlit.io/) 应用 (简易前端), 用于测试与调试.

## 运行项目

1. 配置 API KEY
   - 目前支持 `ChatGPT`, `Claude`, `Gemini`, `DeepSeek`, `Groq` 等模型, 也可以使用 `OpenRouter` 提供的中转服务.
   - [.env.example](./.env.example) 中提供了示例配置, 可以使用下述指令直接创建 `.env` 文件:

    ```bash
    cp .env.example .env
    ```

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

## 注意事项

- 目前仍处于初步开发阶段, [项目结构](#关键文件-项目结构) 后续可能会有变动.
  - [项目架构](#项目架构) 也可能在现有基础上进行拓展.
