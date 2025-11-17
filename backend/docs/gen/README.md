# LLM Agent 生成的过程性文档

在该目录下, 存放所有 LLM Agent (Cursor, Claude Code, ...) 生成的过程性文档.

## 目录结构

### `fastapi-users/`

FastAPI-Users 用户认证系统集成的相关过程性文档:

- `integration-complete.md` - 集成完成总结，包含快速开始、功能清单、API 端点一览等
- `integration-summary.md` - 详细的技术实现和架构说明

### `travel-planner/`

Travel Planner Agent 流式返回优化的相关过程性文档:

- `README.md` - 文档概览和快速开始指南
- `streaming-chunks-history-fix.md` - 完整技术方案文档（问题分析、三种解决方案、实施计划）
- `implementation-example.md` - Functional API 实现示例（完整代码、对比分析、迁移步骤）

## 命名规范

所有过程性文档应遵循以下命名规范:

- 使用小写字母
- 多个单词之间用 `-` 连接
- 例如: `integration-complete.md`, `api-design.md`

## 文档分类

过程性文档应按照功能或模块进行分类存放:

- 每个主要功能或集成创建独立的子文件夹
- 相关文档集中在同一子文件夹中
- 保持目录结构清晰简洁
