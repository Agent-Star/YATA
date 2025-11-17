# Travel Planner 流式返回优化

## 文档概览

本目录包含 Travel Planner 流式返回历史记录分块问题的分析和解决方案文档。

### 问题描述

**现象**：虽然流式返回的实时渲染效果很好，但刷新前端页面返回历史记录后，之前 NLU 返回的内容被分成了许多小块（每个块只有 1-2 个字符）。

**根本原因**：Backend 的 travel_planner 返回了多个 AIMessageChunk，LangGraph 将它们全部保存到 checkpoint。

## 文档列表

### 1. [streaming-chunks-history-fix.md](./streaming-chunks-history-fix.md)

**完整的技术方案文档**

包含内容：
- 问题背景和技术调研
- 三种解决方案的详细分析（方案 A/B/C）
- 推荐实施方案（短期 + 长期）
- 技术细节和测试计划
- 部署计划和风险评估

**推荐方案**：
- **短期**：方案 C - 后处理合并（1-2 小时快速修复）
- **长期**：方案 A - 完全重构为 Functional API（1-2 天彻底解决）

### 2. [implementation-example.md](./implementation-example.md)

**Functional API 实现示例**

包含内容：
- 完整的代码实现（travel_planner_functional.py）
- 与旧实现的详细对比
- 关键改进点说明
- 测试对比和性能对比
- 迁移步骤和常见问题

**关键改进**：
```python
# 旧实现 (StateGraph)
return {"messages": chunks}  # ❌ 所有 chunks 都被保存

# 新实现 (Functional API)
return entrypoint.final(
    value={"messages": chunks},         # ✅ 流式输出
    save={"messages": [final_message]}  # ✅ 只保存完整消息
)
```

## 快速开始

### 1. 理解问题

阅读 `../bug-desc/流式返回历史记录分块问题分析.md` 了解问题根源。

### 2. 选择方案

- **需要快速修复**：参考 streaming-chunks-history-fix.md 中的方案 C
- **需要彻底解决**：参考 implementation-example.md 实施 Functional API

### 3. 实施

按照 implementation-example.md 中的迁移步骤操作。

## 技术要点

### LangGraph Functional API 核心概念

**entrypoint.final**：区分返回值和保存值

```python
@entrypoint()
async def my_agent(inputs, *, previous, config):
    return entrypoint.final(
        value=...,  # 返回给调用者（用于流式输出）
        save=...    # 保存到 checkpoint（用于历史记录）
    )
```

### 流式输出机制

在 `stream_mode=["messages"]` 时：
1. LangGraph 逐个 yield `value` 中的 AIMessageChunk
2. 流式输出完成后，将 `save` 中的值保存到 checkpoint
3. 历史记录读取时只看到 `save` 中的完整消息

### 现有参考实现

- `backend/src/agents/chatbot.py` - 已使用 Functional API
- `backend/src/agents/agents.py:28` - AgentGraph 类型定义支持 Pregel

## 预期效果

实施长期方案（Functional API）后：

| 指标 | 改进 |
|------|------|
| Checkpoint 大小 | -80% (只保存完整消息) |
| 历史记录加载时间 | -75% (无需合并 chunks) |
| 代码复杂度 | -18% (单个函数) |
| 用户体验 | ✅ 流式输出 + ✅ 正确历史记录 |

## 相关资源

- [LangGraph Functional API 官方文档](https://docs.langchain.com/oss/python/langgraph/use-functional-api)
- [LangGraph entrypoint.final 参考](https://reference.langchain.com/python/langgraph/func/)
- [问题分析文档](../bug-desc/流式返回历史记录分块问题分析.md)

## 状态

- [x] 问题分析完成
- [x] 技术调研完成
- [x] 方案设计完成
- [x] 实现示例完成
- [ ] 短期修复实施（方案 C）
- [ ] 长期重构实施（方案 A）
- [ ] 测试验证
- [ ] 部署上线

## 下一步行动

1. 复审技术方案，确认可行性
2. 实施方案 C（快速修复，1-2 小时）
3. 实施方案 A（长期重构，1-2 天）
4. 充分测试和验证
5. 灰度发布和监控
6. 全量上线

---

**创建时间**：2025-11-18
**负责人**：Backend Team
**优先级**：高（影响用户体验）
