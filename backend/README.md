# YATA 后端项目

这是 YATA (Yet Another Travel Agent) 项目的后端部分，基于 [JoshuaC215](https://github.com/JoshuaC215) 的 [Agent Service Toolkit](https://github.com/JoshuaC215/agent-service-toolkit) 构建。

## 项目架构

![架构](./media/agent_architecture.png)

该架构参考了 [JoshuaC215](https://github.com/JoshuaC215) 的 [Agent Service Toolkit](https://github.com/JoshuaC215/agent-service-toolkit)

架构图引用自 [Agent Service Toolkit](https://github.com/JoshuaC215/agent-service-toolkit) 项目的 [相关设计](https://github.com/JoshuaC215/agent-service-toolkit/blob/main/media/agent_architecture.png)

## 技术栈

- [FastAPI](https://fastapi.tiangolo.com/): 高性能的 Python 后端框架.
- [LangGraph](https://langchain-ai.github.io/langgraph/): 即开即用的 AI 代理框架, 可用于构建复杂的 `multi-agent` 系统.
- [ChromaDB](https://www.chromadb.io/): 高性能的开源向量数据库, 用于存储和管理 `向量` 数据, 以构建 `RAG` 知识库.
- [PostgreSQL](https://www.postgresql.org/): 高性能的开源关系型数据库, 用于存储和管理 `checkpoint` 以及其他必要数据.

## 关键文件 (项目结构)

- [src/agents/](./src/agents): 核心模块, 定义了功能不同的多个 agent
- [src/schema/](./src/schema): 通信协议层, 主要用于定义前后端交互时, 部分字段的复杂结构
- [src/core/](./src/core): LLM 定义与配置层
- [src/memory/](./src/memory): 用于后端与数据库的交互
- [src/service/service.py](./src/service/service.py): 面向前端与 agent 的后端服务
- [src/client/client.py](./src/client/client.py): 面向 agent 的客户端
- [src/streamlit_app.py](./src/streamlit_app.py): 提供聊天界面的 [Streamlit](https://streamlit.io/) 应用 (简易前端), 用于测试与调试

## 运行项目

todo

## 注意事项

- 目前仍处于初步开发阶段, [项目结构](#关键文件-项目结构) 后续可能会有变动
  - [项目架构](#项目架构) 也可能在现有基础上进行拓展
