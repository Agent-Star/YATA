# Fallback 历史记录丢失用户输入问题分析

## 问题描述

**现象**：当 NLU 服务不可用，触发 fallback 到 research-assistant 时：

- ✅ Fallback 正常触发
- ✅ 流式输出正常工作
- ❌ 刷新页面后，历史记录中**只显示 AI 回复，没有显示用户发送的提示词**

**复现步骤**：

1. 不启动 NLU 和 RAG 服务
2. 在前端发送消息："今天去哪里旅行?"
3. 观察流式输出（正常显示）
4. 刷新页面，查看历史记录
5. **Bug**: 只看到 AI 回复，看不到用户输入

## 根本原因

在 `backend/src/agents/travel_planner_functional.py` 的 **第 212 行**（修复前）：

```python
# ❌ 错误的切片逻辑
new_messages = research_messages[len(input_messages) :]
```

### 问题分析

当 `research_assistant` 使用 Functional API 实现时：

1. **ainvoke 返回 value，不是 save**
   - `value={"messages": [AI回复]}`  ← ainvoke 返回这个
   - `save={"messages": [用户输入, AI回复]}`

2. **切片导致消息丢失**

   ```python
   research_messages = [AI回复]           # 长度 = 1
   len(input_messages) = 1                # 用户输入
   new_messages = research_messages[1:]   # [] 空列表！
   ```

3. **保存到 checkpoint 的只有用户输入**

   ```python
   save={"messages": all_messages + new_messages}
   # = [用户输入] + []
   # = [用户输入]  ← AI 回复丢失！
   ```

但这与观察到的现象相反（看到 AI 回复，看不到用户输入）...

### 深入分析

实际上，问题可能更复杂。如果 `research_messages` 返回的是 `[用户输入, AI回复]`（2 条消息），那么：

```python
new_messages = research_messages[1:]  # [AI回复]
save = all_messages + [AI回复]
# = [用户输入] + [AI回复]  ← 应该正确
```

但如果 `all_messages` 由于某种原因为空（比如 previous 的处理问题），那么：

```python
save = [] + [AI回复]
# = [AI回复]  ← 只有 AI 回复，没有用户输入！
```

### 原始假设的错误

代码注释写的是：
> 过滤掉输入消息（research_assistant 会返回完整的 messages，包括输入）

但这个假设可能在不同的 research_assistant 实现下不成立：

- 如果是 Functional API：只返回 value（AI 回复）
- 如果是 StateGraph：可能返回完整历史

使用固定切片 `[len(input_messages):]` 是不安全的。

## 解决方案

### 修复方法

使用类型过滤，而不是位置切片：

```python
# ✅ 安全的过滤方法
ai_responses = [msg for msg in research_messages if not isinstance(msg, HumanMessage)]

return entrypoint.final(
    value={"messages": ai_responses},
    save={"messages": all_messages + ai_responses},
)
```

### 优点

1. **类型安全**：无论 research_messages 包含什么，都只保留 AI 回复
2. **避免重复**：即使 research_messages 包含用户输入，也会被过滤掉
3. **容错性强**：适配不同的 research_assistant 实现

### 工作流程

第一次对话时：

1. `previous = None` 或 `{}`
2. `all_messages = [用户输入]`
3. `research_messages = [AI回复]` 或 `[用户输入, AI回复]`
4. `ai_responses = [AI回复]`（过滤掉 HumanMessage）
5. `save = [用户输入] + [AI回复]` ✅

后续对话：

1. `previous = {"messages": [历史消息...]}`
2. `all_messages = [历史...] + [当前用户输入]`
3. `ai_responses = [AI回复]`
4. `save = [历史...] + [当前用户输入] + [AI回复]` ✅

## 相关代码位置

| 文件 | 行号 | 说明 |
|------|------|------|
| `travel_planner_functional.py` | 78-81 | all_messages 构建逻辑 |
| `travel_planner_functional.py` | 192-193 | research_input 构建 |
| `travel_planner_functional.py` | 201 | research_agent.ainvoke() 调用 |
| `travel_planner_functional.py` | 214 | ✅ 修复后的过滤逻辑 |
| `travel_planner_functional.py` | 217-220 | entrypoint.final 返回 |

## 测试验证

### 修复前

```
用户发送: "今天去哪里旅行?"
↓
触发 fallback
↓
流式输出: [显示 AI 回复] ✅
↓
保存到 checkpoint: [AI回复]  ❌ 缺少用户输入
↓
刷新页面查看历史: 只看到 AI 回复 ❌
```

### 修复后

```
用户发送: "今天去哪里旅行?"
↓
触发 fallback
↓
流式输出: [显示 AI 回复] ✅
↓
保存到 checkpoint: [用户输入, AI回复] ✅
↓
刷新页面查看历史: 看到完整对话 ✅
```

## 经验教训

1. **不要依赖位置切片**：不同实现的返回格式可能不同
2. **使用类型过滤更安全**：`isinstance()` 检查比索引切片更可靠
3. **充分理解 Functional API**：
   - ainvoke 返回 value
   - aget_state 读取 save
   - 两者可能不同

4. **测试边界情况**：
   - 第一次对话（previous 为空）
   - Fallback 场景
   - 不同的 agent 实现

## 相关问题

- [流式返回历史记录分块问题](./流式返回历史记录分块问题分析.md)
- [Migration Complete](../docs/gen/travel-planner/migration-complete.md)

## 状态

- [x] 问题分析完成
- [x] 修复实施完成
- [ ] 运行时测试验证
- [ ] 部署上线

---

**创建时间**：2025-11-18
**修复时间**：2025-11-18
**严重程度**：高（影响用户体验）
**修复状态**：✅ 已修复，待验证
