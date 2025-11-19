# 流式输出 + Fallback 修复测试指南

## 修复总结

### 问题

1. ✅ **流式输出失败**：Backend 使用 Functional API，必须等函数执行完毕才能返回，无法实时流式输出
2. ✅ **Fallback 缺失**：直接调用 NLU 后，当 NLU 失败时无法自动切换到 research-assistant

### 解决方案

1. **直接流式转发**：在 `planner_routes.py` 中直接调用 NLU 并实时转发 tokens
2. **实现 Fallback**：捕获 NLU 异常，自动切换到 research-assistant
3. **保存历史**：使用 `save-history-helper` 保存完整对话历史

---

## 测试场景

### 场景 1: NLU 正常工作（主要路径）

**测试步骤：**

1. 启动 NLU 服务
2. 启动 backend 服务
3. 发送旅行规划请求：

   ```
   我想去日本旅游，帮我规划一下行程
   ```

**预期结果：**

- ✅ 立即开始逐 token 渲染
- ✅ 内容实时出现在前端
- ✅ 刷新页面后历史记录显示完整（用户消息 + AI 响应）
- ✅ 无延迟感

**检查日志：**

```
PlanStream: Calling NLU service
SaveHistoryHelper: Saved 2 new messages, total X messages
```

---

### 场景 2: NLU 服务不可用（Fallback 路径）

**测试步骤：**

1. **停止 NLU 服务**
2. 保持 backend 服务运行
3. 发送任意请求：

   ```
   什么是人工智能？
   ```

**预期结果：**

- ✅ 自动 fallback 到 research-assistant
- ✅ 仍然保持流式输出
- ✅ 返回正确的答案（来自 research-assistant）
- ✅ 历史记录正确保存

**检查日志：**

```
PlanStream: NLU failed (ServiceUnavailableError: ...), falling back to research-assistant
PlanStream: Calling research-assistant as fallback
```

---

### 场景 3: NLU 返回空内容（Fallback 路径）

**测试步骤：**

1. 启动 NLU 服务
2. 发送一个 NLU 无法处理的请求（可能返回空内容）
3. 观察是否自动 fallback

**预期结果：**

- ✅ 检测到空内容
- ✅ 自动 fallback 到 research-assistant
- ✅ 返回有效响应

**检查日志：**

```
PlanStream: NLU returned empty content
PlanStream: NLU failed (NLUServiceError: NLU returned empty content), falling back to research-assistant
```

---

### 场景 4: 多轮对话（历史记录验证）

**测试步骤：**

1. 发送第一个问题：`我想去日本`
2. 发送第二个问题：`需要准备多少钱？`
3. 刷新页面查看历史

**预期结果：**

- ✅ 所有用户消息都正确显示
- ✅ 所有 AI 响应都正确显示
- ✅ 对话顺序正确
- ✅ 时间戳正确

---

### 场景 5: Fallback 也失败（错误处理）

**测试步骤：**

1. 停止 NLU 服务
2. 停止或破坏 research-assistant（可能需要修改代码临时禁用）
3. 发送请求

**预期结果：**

- ✅ 返回友好的错误提示：`服务暂时不可用，请稍后重试`
- ✅ 不会崩溃
- ✅ 前端显示错误消息

**检查日志：**

```
PlanStream: Fallback to research-assistant also failed: ...
```

---

## 性能测试

### 延迟测试

**测试方法：**

1. 使用浏览器开发者工具 Network 面板
2. 发送请求
3. 观察第一个 token 到达的时间

**预期指标：**

- ✅ 第一个 token 应在 1-3 秒内到达（取决于 NLU 处理时间）
- ✅ 后续 tokens 应连续到达，无明显间隔
- ✅ 总体延迟与 NLU 生成速度一致

---

## 验证清单

### 代码验证

- [x] `save_history_helper` 函数已添加
- [x] `save-history-helper` agent 已注册
- [x] 异常类正确导入
- [x] NLU 流式调用已实现
- [x] Fallback 逻辑已实现
- [x] 历史保存逻辑已实现
- [x] 语法检查通过

### 功能验证

- [ ] NLU 正常路径测试通过
- [ ] Fallback 路径测试通过
- [ ] 历史记录正确保存
- [ ] 多轮对话正常
- [ ] 错误处理正确
- [ ] 性能符合预期
- [ ] **Message ID 格式正确（UUID）** ⭐ 新增
- [ ] **收藏功能正常工作** ⭐ 新增
- [ ] **Fallback 历史记录完整** ⭐ 新增

---

## 新增测试场景（v3.0）

### 场景 6: Message ID 格式验证 ⭐

**测试步骤：**

1. 发送任意请求（NLU 或 Fallback 路径均可）
2. 打开浏览器开发者工具
3. 查看 Network 面板的 SSE 响应
4. 检查 `end` 事件中的 `messageId` 字段

**预期结果：**

- ✅ Message ID 格式为 UUID（例如：`550e8400-e29b-41d4-a716-446655440000`）
- ✅ 不是纯数字
- ✅ 符合标准 UUID v4 格式

**检查方法：**

```javascript
// 在浏览器控制台运行
const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
console.log(uuidRegex.test(messageId));  // 应该返回 true
```

---

### 场景 7: 收藏功能持久化测试 ⭐

**测试步骤：**

1. 发送请求并获得响应
2. 收藏该响应消息
3. 刷新页面
4. 检查收藏状态是否保持

**预期结果：**

- ✅ 收藏请求成功发送到后端（检查 Network 面板）
- ✅ 后端返回 200 OK
- ✅ 刷新页面后收藏图标仍然高亮
- ✅ 可以取消收藏

**检查日志：**

Backend 日志应显示：

```
POST /planner/favorites - 200 OK
```

---

### 场景 8: Fallback 历史记录完整性测试 ⭐

**测试步骤：**

1. **停止 NLU 服务**（触发 Fallback）
2. 发送请求：`什么是人工智能？`
3. 等待 research-assistant 响应完成
4. **刷新页面**
5. 检查历史记录

**预期结果：**

- ✅ 历史记录中显示用户输入：`什么是人工智能？`
- ✅ 历史记录中显示 AI 响应（完整内容）
- ✅ 时间戳正确
- ✅ 可以收藏该消息

**检查日志：**

```
PlanStream: NLU failed (...), falling back to research-assistant
PlanStream: Calling research-assistant as fallback
PlanStream: Fallback completed, saved XXX chars to history
SaveHistoryHelper: Saved 2 new messages, total Y messages
```

---

### 场景 9: 混合路径多轮对话 ⭐

**测试步骤：**

1. **启动 NLU 服务**
2. 发送第 1 个请求（旅行规划）：`我想去日本` - 走 NLU 路径
3. **停止 NLU 服务**
4. 发送第 2 个请求（一般问答）：`日本的人口是多少？` - 走 Fallback 路径
5. **启动 NLU 服务**
6. 发送第 3 个请求（旅行规划）：`需要准备多少钱？` - 走 NLU 路径
7. 刷新页面查看历史

**预期结果：**

- ✅ 所有 3 轮对话都正确显示
- ✅ 用户消息和 AI 响应都完整
- ✅ 顺序正确（按时间升序）
- ✅ 所有消息都可以收藏
- ✅ Message ID 都是 UUID 格式

---

## 启动命令

```bash
# 启动 NLU 服务（在 algorithms/NLU 目录）
cd /home/eden/HKU-MSC-CS/nlp/YATA/algorithms/NLU
# [运行 NLU 启动命令]

# 启动 Backend 服务
cd /home/eden/HKU-MSC-CS/nlp/YATA/backend
uv run fastapi dev src/service.py

# 访问前端
# [前端 URL]
```

---

## 常见问题排查

### 问题：流式输出仍然不工作

**排查步骤：**

1. 检查 NLU 服务是否正常运行
2. 查看 backend 日志，确认是否调用了 `nlu_client.call_nlu_stream`
3. 检查前端是否正确处理 SSE 事件
4. 使用 `curl` 测试 backend 的流式接口：

   ```bash
   curl -N -H "Authorization: Bearer <token>" \
        -H "Content-Type: application/json" \
        -d '{"prompt":"测试"}' \
        http://localhost:8000/planner/plan/stream
   ```

### 问题：Fallback 不工作

**排查步骤：**

1. 查看日志，确认是否捕获了异常
2. 检查异常类型是否正确（`ServiceUnavailableError` 或 `NLUServiceError`）
3. 确认 research-assistant 可用

### 问题：历史记录缺失

**排查步骤：**

1. 检查 `save-history-helper` 是否正确注册
2. 查看日志中的 `SaveHistoryHelper` 消息
3. 检查数据库连接是否正常

---

## 回滚方案

如果修复出现问题，可以：

1. **回退到上一个 commit**：

   ```bash
   git checkout <previous-commit-hash>
   ```

2. **使用原来的 travel_planner agent**：
   修改 `agents.py` 的 DEFAULT_AGENT 设置

---

**修复日期**：2025-11-18
**修复状态**：✅ 实施完成，待测试验证
**文档版本**：v2.0（包含 Fallback 支持）
