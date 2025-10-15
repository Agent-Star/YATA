# YATA 前后端接口约定（中文）

本文档描述了新版前端与后端的接口约定。前端所有业务逻辑（账号注册 / 登录、智能行程规划、历史对话存储）均通过这些接口完成，前端只负责 UI 与网络请求。

- **基础地址**：`BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? ''`  
  若未配置该环境变量，前端会直接请求同域路径（例如通过 Next.js 代理 `/api`）。
- **请求格式**：除特殊说明外均为 `Content-Type: application/json`；请求默认携带 `credentials: include`，后端可使用 Cookie 会话或返回 Token。
- **错误约定**：失败时返回相应 HTTP 状态码，并携带统一 JSON 结构：

```json
{
  "code": "错误码",
  "message": "错误描述"
}
```

前端会读取 `code` 字段决定具体提示。

---

## 一、认证模块

### 1.1 POST `/auth/register`
- **用途**：注册新账号并立即登录。
- **请求体**

| 字段     | 类型   | 说明           | 必填 |
|----------|--------|----------------|------|
| account  | string | 账号名         | 是   |
| password | string | 密码（明文或前端加密后密文，由后端决定校验方式） | 是 |

**成功响应 200**

```json
{
  "user": {
    "id": "uuid",
    "account": "alice",
    "displayName": "Alice"
  },
  "accessToken": "可选，如果使用 JWT/自定义 Token"
}
```

> 如果使用 Cookie 会话，可忽略 `accessToken` 字段。前端会将响应中的 `user` 写入全局状态。

**错误码示例**

| HTTP | code             | 含义             |
|------|------------------|------------------|
| 409  | ACCOUNT_EXISTS   | 账号已存在       |
| 400  | INVALID_PAYLOAD  | 参数校验失败     |
| 500  | API_ERROR        | 服务器异常       |

---

### 1.2 POST `/auth/login`
- **用途**：账号登录。
- **请求体** 同注册。

**成功响应 200**：同 `/auth/register`。

**错误码示例**

| HTTP | code                 | 含义                     |
|------|----------------------|--------------------------|
| 401  | INVALID_CREDENTIALS  | 账号或密码错误           |
| 423  | ACCOUNT_LOCKED       | 账号被锁定（如实现）     |
| 400  | INVALID_PAYLOAD      | 参数校验失败             |

---

### 1.3 POST `/auth/logout`
- **用途**：注销当前登录态，清理服务器会话或 Token。
- **请求体**：无。
- **成功响应 204**：空响应体。

---

### 1.4 GET `/auth/profile`
- **用途**：在页面刷新或重新打开时获取当前登录用户信息。
- **成功响应 200**

```json
{
  "user": {
    "id": "uuid",
    "account": "alice",
    "displayName": "Alice"
  }
}
```

- **未登录响应 401**

```json
{
  "code": "UNAUTHENTICATED",
  "message": "登陆状态已失效"
}
```

---

## 二、智能行程规划模块

### 数据结构说明

#### 统一消息结构（前后端共享）

| 字段      | 类型   | 说明                                   |
|-----------|--------|----------------------------------------|
| id        | string | 消息唯一 ID（由后端生成，前端回显）    |
| role      | string | `user` 或 `assistant`                  |
| content   | string | 展示在聊天窗口的文字（支持 Markdown） |
| metadata  | object | 选填，自由扩展（如行程数组、提示等）   |
| createdAt | string | 选填，ISO 时间戳，前端目前不强制使用   |

历史记录接口与实时生成接口均使用该结构。

---

### 2.1 GET `/planner/history`
- **用途**：登录成功后拉取该账号的历史对话记录。
- **请求参数**：无，使用登录态识别用户。

**成功响应 200**

```json
{
  "messages": [
    {
      "id": "msg-1",
      "role": "user",
      "content": "计划一次 5 天的巴黎艺术之旅",
      "createdAt": "2024-05-01T08:00:00Z"
    },
    {
      "id": "msg-2",
      "role": "assistant",
      "content": "为你准备了以下行程……",
      "createdAt": "2024-05-01T08:00:02Z"
    }
  ]
}
```

若该用户尚无历史，可返回空数组或省略 `messages` 字段；前端会自动展示欢迎提示。

**错误码示例**

| HTTP | code             | 含义         |
|------|------------------|--------------|
| 401  | UNAUTHENTICATED  | 未登录       |
| 500  | API_ERROR        | 服务器异常   |

---

### 2.2 POST `/planner/plan/stream` （SSE 流式接口）
- **用途**：用户输入后，与后端建立一次 Server-Sent Events（SSE）流，实时接收助手回复的增量 token，并在结束时获取最终消息 ID / 元数据。后端应在流程中写入持久化历史。
- **请求头**
  - `Accept: text/event-stream`
- **请求体**

| 字段       | 类型   | 说明                                   | 必填 |
|------------|--------|----------------------------------------|------|
| prompt     | string | 用户最新输入内容                       | 是   |
| context    | object | 额外上下文                             | 否   |
| ↳ language | string | 当前 UI 语言（如 `zh` / `en`）          | 否   |
| ↳ history  | array  | 既有消息列表（含本次用户提问），使用统一消息结构 | 否   |

示例：

```json
{
  "prompt": "安排一个 3 天的东京美食之旅",
  "context": {
    "language": "zh",
    "history": [
      { "id": "msg-100", "role": "user", "content": "上次行程..." },
      { "id": "msg-101", "role": "assistant", "content": "上次回复..." },
      { "id": "msg-102", "role": "user", "content": "安排一个 3 天的东京美食之旅" }
    ]
  }
}
```

#### SSE 数据格式
后端需按照标准 SSE 格式返回，每条事件以空行 `\n\n` 结尾，常用类型如下：

| 事件类型 (`type`) | 说明 | 示例载荷 |
|-------------------|------|---------|
| `token`    | 增量内容片段（前端会逐字显示） | `data: {"type":"token","delta":"第一天：..."}` |
| `metadata` | 可选的结构化结果，将覆盖当前消息的 `metadata` | `data: {"type":"metadata","metadata":{"itinerary":[...]}}` |
| `end`      | 流结束。可携带最终 `messageId` 及最终元数据 | `data: {"type":"end","messageId":"msg-103","metadata":{...}}` |
| `[DONE]`   | 结束标记（字符串），用于兼容 OpenAI 风格流式协议 | `data: [DONE]` |

前端处理逻辑：
1. `token`：追加到当前助手消息的 `content` 字段，实现逐字显示。
2. `metadata`：更新当前助手消息的 `metadata`。
3. `end`：记录后端生成的 `messageId`（便于后续引用），若同时包含 `metadata` 也会覆盖到消息中。
4. `[DONE]`：关闭流。

流关闭后，后端需确保最新的提问与回答已经写入持久化历史（与 `/planner/history` 返回保持一致）。

**错误码示例**

| HTTP | code                  | 含义                               |
|------|-----------------------|------------------------------------|
| 400  | INVALID_PAYLOAD       | 缺少 `prompt` 或 `history` 格式错误 |
| 401  | UNAUTHENTICATED       | 用户未登录                         |
| 503  | SERVICE_UNAVAILABLE   | 智能服务不可用或超时               |
| 500  | API_ERROR             | 其它服务器异常                     |

---

## 三、业务流程说明

1. **注册 / 登录**：前端调用 `/auth/register` 或 `/auth/login`，成功后写入用户信息并跳转到智能行程页面。
2. **载入历史对话**：`ChatPanel` 挂载时调用 `/planner/history`，若返回空列表，则前端显示默认欢迎语；若返回列表，直接渲染。
3. **发送问题**：用户提交内容时，前端会：
   - 立即在界面显示用户消息；
   - 调用 `/planner/plan/stream` 建立 SSE 流，携带当前语言和完整历史；
   - 随着流返回的 `token` 实时更新助手消息，最终得到完整回复并显示结构化结果；
   - 后端负责持久化最新问答，确保历史接口能返回。
4. **退出登录**：前端调用 `/auth/logout`，清空本地状态。重新登录后再次加载该账号的历史对话。
5. 前端是靠 SSE 流里约定好的“终止信号”来判断一次回答已经结束的。现在的实现里有两种方式（后端可以任选其一或同时发送）：

   - **type: "end" 事件**：当服务器推送形如
     data: {"type":"end","messageId":"msg-123","metadata":{...}}
     时，前端会把这次回答视为完成：记录最终 messageId、合并元数据，并关闭连接。
   - **[DONE] 文本**：如果最后发送 data: [DONE]，前端也会立即收尾。

   因此，只要后端保证每轮回答最终会发出 type: "end" 或 [DONE]，前端就能准确地判断这次流式输出结束，随后把累积的文本视为完整回答。

---

## 四、后端实现注意事项

- **会话隔离**：历史对话按照账号（或用户 ID）隔离存储，互不干扰。
- **排序要求**：`/planner/history` 返回的 `messages` 建议按时间升序排列，以便前端按顺序渲染。
- **安全控制**：如需防护 CSRF，请结合 Cookie `SameSite`、CSRF Token 等策略。前端默认带上 `credentials`。
- **多语言支持**：如果需要根据语言生成不同内容，可读取 `context.language`。

如有新增接口或字段，请在此文档扩展说明，以保持前后端同步。
