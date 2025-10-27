# 前端调用 Auth 接口指南

## 认证策略总结

### ✅ 当前实现：纯 Cookie 策略

后端采用 **HttpOnly Cookie** 方式存储 JWT token，前端**无需手动管理 token**。

```
┌─────────┐                           ┌─────────┐
│  前端   │  credentials: 'include'   │  后端   │
│         │ ────────────────────────> │         │
│         │  自动携带 Cookie          │         │
│         │ <──────────────────────── │         │
│         │  Set-Cookie: yata_auth    │         │
└─────────┘                           └─────────┘
```

---

## 前端调用方式

### 1. 注册接口

**端点**: `POST /auth/register`

**前端代码**:

```typescript
const response = await fetch(`${BASE_URL}/auth/register`, {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  credentials: 'include',  // ⚠️ 必须！允许浏览器接收 Cookie
  body: JSON.stringify({
    email: "user@example.com",
    username: "user",
    password: "12345678"
  }),
});

const data = await response.json();
// data = {
//   user: { id: "...", account: "user", displayName: "user" },
//   accessToken: null  // ⚠️ Cookie 模式，此字段为 null
// }
```

**响应处理**:

```typescript
if (response.ok) {
  // ✅ Cookie 已自动设置（浏览器处理）
  // ✅ 只需要保存 user 信息到状态管理
  setUser(data.user);
  
  // ❌ 不需要：localStorage.setItem('token', data.accessToken)
  // ❌ 不需要：设置 Authorization header
}
```

---

### 2. 登录接口

**端点**: `POST /auth/login`

**前端代码**:

```typescript
const response = await fetch(`${BASE_URL}/auth/login`, {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  credentials: 'include',  // ⚠️ 必须！
  body: JSON.stringify({
    account: "user@example.com",  // 或 "user"
    password: "12345678"
  }),
});

const data = await response.json();
// data = {
//   user: { id: "...", account: "user", displayName: "user" },
//   accessToken: null  // Cookie 模式
// }
```

**登录后的状态**:

- ✅ 浏览器自动存储 `yata_auth` Cookie
- ✅ Cookie 设置为 `HttpOnly`（JavaScript 无法访问，安全）
- ✅ 后续所有请求自动携带 Cookie（只要设置 `credentials: 'include'`）

---

### 3. 获取用户信息

**端点**: `GET /auth/profile`

**前端代码**:

```typescript
const response = await fetch(`${BASE_URL}/auth/profile`, {
  method: 'GET',
  credentials: 'include',  // ⚠️ 必须！自动携带 Cookie 进行认证
});

if (response.ok) {
  const data = await response.json();
  // data = { user: { id: "...", account: "...", displayName: "..." } }
  setUser(data.user);
} else if (response.status === 401) {
  // 未登录或 token 过期
  setUser(null);
}
```

**使用场景**:

- 页面刷新时恢复登录状态
- 应用启动时检查是否已登录
- Token 过期检测

---

### 4. 登出接口

**端点**: `POST /auth/logout`

**前端代码**:

```typescript
const response = await fetch(`${BASE_URL}/auth/logout`, {
  method: 'POST',
  credentials: 'include',  // ⚠️ 必须！携带要清除的 Cookie
});

if (response.ok) {
  // ✅ Cookie 已被后端清除
  // ✅ 清除本地用户状态
  setUser(null);
  router.push('/login');
}
```

---

### 5. 访问受保护接口（如行程规划）

**端点**: `POST /planner/plan/stream`

**前端代码**:

```typescript
const response = await fetch(`${BASE_URL}/planner/plan/stream`, {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  credentials: 'include',  // ⚠️ 必须！自动携带认证 Cookie
  body: JSON.stringify({
    prompt: "帮我规划三天的东京旅行",
    context: { language: "zh" }
  }),
});

// SSE 流式响应处理
const reader = response.body.getReader();
// ...
```

**关键点**:

- ❌ 不需要手动添加 `Authorization: Bearer <token>` header
- ✅ Cookie 会自动携带（只要设置 `credentials: 'include'`）

---

## 关键配置项

### 前端必须设置

**每个请求都要加上**:

```typescript
credentials: 'include'
```

**原因**:

- 默认情况下，跨域请求不会发送 Cookie
- `credentials: 'include'` 告诉浏览器："跨域也要带上 Cookie"

---

### 后端已配置

**CORS 中间件** (`backend/src/service/service.py`):

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,  # ✅ 允许跨域携带 Cookie
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**Cookie 配置** (`backend/src/auth/auth.py`):

```python
cookie_transport = CookieTransport(
    cookie_name="yata_auth",
    cookie_max_age=604800,      # 7 天
    cookie_path="/",
    cookie_secure=False,        # 开发环境 False，生产环境 True
    cookie_httponly=True,       # ✅ 防止 XSS
    cookie_samesite="lax",      # ✅ 防止 CSRF
)
```

---

## 前端无需做的事情

### ❌ 不需要手动管理 Token

```typescript
// ❌ 错误做法（Token 模式）
localStorage.setItem('token', data.accessToken);
const token = localStorage.getItem('token');
fetch(url, {
  headers: {
    'Authorization': `Bearer ${token}`
  }
});

// ✅ 正确做法（Cookie 模式）
fetch(url, {
  credentials: 'include'  // 浏览器自动处理
});
```

### ❌ 不需要检查 Token 过期

```typescript
// ❌ 错误做法（Token 模式）
if (isTokenExpired(token)) {
  refreshToken();
}

// ✅ 正确做法（Cookie 模式）
// 后端会自动验证 Cookie 中的 JWT
// 如果过期，返回 401，前端只需处理 401 响应
const response = await fetch(url, { credentials: 'include' });
if (response.status === 401) {
  // 重定向到登录页
  router.push('/login');
}
```

### ❌ 不需要手动刷新 Token

```typescript
// ❌ 错误做法（Token 模式）
setInterval(() => {
  refreshToken();
}, 3600000);

// ✅ 正确做法（Cookie 模式）
// Cookie 会在过期前自动续期（如果后端实现）
// 或者用户重新登录即可
```

---

## 安全性保障

### 1. HttpOnly Cookie

```
Cookie: yata_auth=<jwt-token>; HttpOnly; SameSite=Lax
```

- ✅ JavaScript 无法读取（`document.cookie` 读不到）
- ✅ 防止 XSS 攻击窃取 token
- ✅ 浏览器自动管理，不怕用户误删

### 2. SameSite=Lax

- ✅ 防止 CSRF 攻击
- ✅ 允许正常的跨域导航（如从其他网站点链接进来）
- ❌ 阻止恶意网站的跨域请求

### 3. Secure Flag（生产环境）

- ✅ 仅通过 HTTPS 传输
- ✅ 防止中间人攻击

---

## 开发环境 vs 生产环境

### 开发环境配置

**后端** (`.env`):

```bash
MODE=dev  # 或不设置
```

**效果**:

- `cookie_secure=False` (允许 HTTP)
- 前端可以使用 `http://localhost:3000`

### 生产环境配置

**后端** (`.env`):

```bash
MODE=production
```

**CORS** (`service.py`):

```python
allow_origins=["https://your-frontend-domain.com"]
```

**效果**:

- `cookie_secure=True` (强制 HTTPS)
- 前端必须使用 `https://`

---

## 常见问题

### Q1: 为什么响应中 `accessToken` 是 `null`？

**A**: 因为当前使用 **Cookie 认证**，token 存储在 HttpOnly Cookie 中，不需要在响应体中返回。

```json
{
  "user": { "id": "...", "account": "...", "displayName": "..." },
  "accessToken": null  // ← 这是正常的
}
```

前端接口文档中说明：
> 如果使用 Cookie 会话，可忽略 `accessToken` 字段。

---

### Q2: 为什么 `document.cookie` 看不到 `yata_auth`？

**A**: 因为 Cookie 设置了 `HttpOnly` 标志。

```javascript
console.log(document.cookie);
// 输出: "" 或其他非 HttpOnly 的 cookie

// 但实际上 yata_auth Cookie 存在，只是 JS 无法访问
// 可以在浏览器开发者工具 → Application → Cookies 中查看
```

这是**安全特性**，不是 bug！

---

### Q3: 跨域请求为什么收不到 Cookie？

**A**: 忘记设置 `credentials: 'include'`。

```typescript
// ❌ 错误
fetch(url, {
  method: 'POST',
  body: JSON.stringify(data)
});

// ✅ 正确
fetch(url, {
  method: 'POST',
  credentials: 'include',  // ← 必须加这个
  body: JSON.stringify(data)
});
```

---

### Q4: 如何判断用户是否已登录？

**A**: 调用 `GET /auth/profile`，根据响应判断。

```typescript
async function checkAuth() {
  try {
    const response = await fetch(`${BASE_URL}/auth/profile`, {
      credentials: 'include'
    });
    
    if (response.ok) {
      const data = await response.json();
      return data.user;  // 已登录
    } else {
      return null;  // 未登录
    }
  } catch (error) {
    return null;
  }
}

// 在应用启动时调用
const user = await checkAuth();
if (user) {
  setUser(user);
} else {
  router.push('/login');
}
```

---

### Q5: Token 过期了怎么办？

**A**: 后端会返回 `401 Unauthorized`，前端重定向到登录页即可。

```typescript
const response = await fetch(url, { credentials: 'include' });

if (response.status === 401) {
  // Token 过期或无效
  setUser(null);
  router.push('/login');
  return;
}

// 正常处理响应
const data = await response.json();
```

---

## 完整示例：React 登录流程

```typescript
import { useState } from 'react';

const BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || '';

function LoginPage() {
  const [account, setAccount] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    try {
      const response = await fetch(`${BASE_URL}/auth/login`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include',  // ⚠️ 关键！
        body: JSON.stringify({ account, password }),
      });

      if (response.ok) {
        const data = await response.json();
        // ✅ Cookie 已自动设置
        // ✅ 保存用户信息到全局状态（如 Context、Redux、Zustand 等）
        setUser(data.user);
        // 跳转到首页
        router.push('/');
      } else {
        const errorData = await response.json();
        setError(errorData.message || '登录失败');
      }
    } catch (err) {
      setError('网络错误');
    }
  };

  return (
    <form onSubmit={handleLogin}>
      <input
        type="text"
        value={account}
        onChange={(e) => setAccount(e.target.value)}
        placeholder="账号"
      />
      <input
        type="password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        placeholder="密码"
      />
      <button type="submit">登录</button>
      {error && <div className="error">{error}</div>}
    </form>
  );
}
```

---

## 总结

### 前端要做的（仅 3 件事）

1. ✅ **每个请求加上** `credentials: 'include'`
2. ✅ **保存用户信息**到全局状态（从响应的 `user` 字段）
3. ✅ **处理 401 响应**（重定向到登录页）

### 前端不要做的

1. ❌ 不要手动管理 token（localStorage/sessionStorage）
2. ❌ 不要手动添加 `Authorization` header
3. ❌ 不要关心 `accessToken` 字段（它是 null）
4. ❌ 不要尝试读取 Cookie（读不到，也不需要）

### 后端已做好的

1. ✅ 自动设置 HttpOnly Cookie
2. ✅ 自动验证 Cookie 中的 JWT
3. ✅ CORS 配置支持跨域携带 Cookie
4. ✅ 安全性保障（HttpOnly + SameSite + Secure）

---

**结论**: 是的，前端完全将认证视为 **Cookie 策略**，无需关心 Token 的存储、携带、刷新等细节，一切由浏览器和后端自动处理！🎉
