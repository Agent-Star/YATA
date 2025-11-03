# Cookie SameSite 跨站问题修复

**日期**: 2025-01-27  
**问题**: 登录成功但后续请求返回 401 Unauthorized  
**原因**: `SameSite=lax` 阻止跨站发送 Cookie  
**影响**: 前端从 localhost:3000 访问 EC2 服务器时无法保持登录状态  
**严重级别**: 🔴 严重

---

## 🐛 问题描述

### 错误现象

**场景**:

- 前端：`http://localhost:3000`
- 后端：`http://166.117.38.176:8080`（EC2）
- 这是**跨站请求**（不同域名/IP）

**表现**:

1. ✅ POST /auth/login → 200 OK（登录成功）
2. ✅ OPTIONS /planner/history → 200 OK（预检通过）
3. ❌ GET /planner/history → **401 Unauthorized**（认证失败）

**服务器日志**:

```
INFO:  146.235.17.47:24418 - "OPTIONS /auth/login HTTP/1.1" 200
INFO:  [auth.manager] 用户认证成功: admin (ID: 0254832b-9336-4d88-865f-51378f7e9e6b)
INFO:  146.235.17.47:24404 - "POST /auth/login HTTP/1.1" 200  ✅ 登录成功
INFO:  146.235.17.47:24418 - "OPTIONS /planner/history HTTP/1.1" 200
INFO:  146.235.17.47:24404 - "GET /planner/history HTTP/1.1" 401  ❌ 认证失败
```

---

## 🔍 问题根源

### SameSite Cookie 策略

**原始配置**（`backend/src/auth/auth.py` 第39行）:

```python
cookie_transport = CookieTransport(
    cookie_name="yata_auth",
    cookie_secure=not settings.is_dev(),
    cookie_samesite="lax",  # ❌ 问题所在！
)
```

### SameSite 的三种值

| 值 | 行为 | 适用场景 |
|---|------|---------|
| `Strict` | **仅同站**请求发送 Cookie | 最安全，但用户体验差 |
| `Lax` | **同站 + 顶级导航**发送 Cookie | 默认值，平衡安全和体验 |
| `None` | **所有请求**都发送 Cookie（需要 `Secure=True`） | 跨站场景（需 HTTPS） |

### 为什么 `SameSite=lax` 导致问题？

**请求类型对比**:

| 请求类型 | 示例 | SameSite=Lax 行为 |
|---------|------|------------------|
| **顶级导航** | 用户点击链接：`<a href="...">` | ✅ 发送 Cookie |
| **子资源请求** | `<img src="...">` | ❌ 不发送 Cookie |
| **AJAX/Fetch** | `fetch(...)` | ❌ 不发送 Cookie |
| **表单 POST** | `<form method="POST">` | ✅ 发送 Cookie |

**我们的场景**:

```javascript
// 前端：http://localhost:3000
// 后端：http://166.117.38.176:8080

// 登录（可能设置了 Cookie）
fetch('http://166.117.38.176:8080/auth/login', {
  method: 'POST',
  credentials: 'include',
  ...
})  // ✅ 某些情况下可能设置 Cookie

// 后续请求（无法发送 Cookie）
fetch('http://166.117.38.176:8080/planner/history', {
  method: 'GET',
  credentials: 'include',  // ❌ 浏览器拒绝发送 Cookie（SameSite=lax）
})  // → 401 Unauthorized
```

**为什么？**

1. `localhost:3000` 和 `166.117.38.176:8080` 是**不同的站点**
2. fetch 请求是**子资源请求**，不是顶级导航
3. `SameSite=lax` 阻止跨站的 fetch 请求发送 Cookie
4. 后端收不到 Cookie → 认证失败 → 401

---

## ✅ 解决方案

### 方案 1: 设置 `SameSite=None` ⭐ **已采用**

**修改**（`backend/src/auth/auth.py`）:

```python
cookie_transport = CookieTransport(
    cookie_name="yata_auth",
    cookie_max_age=settings.AUTH_JWT_LIFETIME_SECONDS,
    cookie_path="/",
    cookie_domain=None,
    cookie_secure=False,  # 开发/生产都使用 HTTP 时设为 False
    cookie_httponly=True,
    cookie_samesite="none",  # ✅ 允许跨站发送 Cookie
)
```

**优点**:

- ✅ 允许跨站请求发送 Cookie
- ✅ 适合开发环境（前后端不同域名/IP）

**缺点**:

- ⚠️ `SameSite=None` 通常需要 `Secure=True`（HTTPS）
- ⚠️ 某些现代浏览器（Chrome 80+）可能拒绝 `SameSite=None` + `Secure=False` 的 Cookie
- ⚠️ 安全性较低（允许所有跨站请求）

**适用场景**:

- 开发环境：前端 localhost，后端 EC2
- 测试环境：跨域测试
- **不推荐用于生产环境**（除非使用 HTTPS）

---

### 方案 2: 前端代理（推荐用于生产）

**原理**:

- 前端配置代理，将后端请求转发到同源路径
- 例如：`http://localhost:3000/api` → `http://166.117.38.176:8080`
- 浏览器认为请求是同源的，会发送 Cookie

**Next.js 配置示例**:

```javascript
// next.config.js
module.exports = {
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: 'http://166.117.38.176:8080/:path*',
      },
    ]
  },
}
```

**优点**:

- ✅ 完全解决跨域问题
- ✅ 可以使用 `SameSite=Lax`（安全）
- ✅ 生产环境推荐

**缺点**:

- ❌ 需要配置前端代理
- ❌ 本地开发需要额外配置

---

### 方案 3: 使用 Bearer Token

**原理**:

- 不使用 Cookie，改用 `Authorization: Bearer <token>` 头
- Token 存储在 localStorage 或 sessionStorage
- 每次请求手动添加到请求头

**前端代码**:

```javascript
// 登录后保存 token
const response = await fetch('/auth/jwt/login', { ... })
const data = await response.json()
localStorage.setItem('token', data.access_token)

// 后续请求携带 token
fetch('/planner/history', {
  headers: {
    'Authorization': `Bearer ${localStorage.getItem('token')}`
  }
})
```

**优点**:

- ✅ 完全避免 Cookie 相关问题
- ✅ 灵活控制 Token 存储和发送

**缺点**:

- ❌ Token 存储在 JavaScript 可访问的位置（XSS 风险）
- ❌ 需要手动管理 Token 生命周期
- ❌ 需要修改前端代码

---

## 🧪 测试验证

### 测试 1: 验证 Cookie 设置

**登录后检查 Cookie**:

```bash
# 浏览器 DevTools → Application → Cookies
# 查看是否有 yata_auth Cookie
```

**预期**:

```
Name: yata_auth
Value: <JWT token>
Path: /
SameSite: None
Secure: ❌ (HTTP)
HttpOnly: ✅
```

---

### 测试 2: 验证跨站请求

**前端代码**:

```javascript
// 登录
await fetch('http://166.117.38.176:8080/auth/login', {
  method: 'POST',
  credentials: 'include',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ account: 'admin', password: '12345678' })
})

// 访问 history
const res = await fetch('http://166.117.38.176:8080/planner/history', {
  credentials: 'include',
})

console.log(res.status)  // 预期：200 ✅
```

**预期**:

1. 登录成功，设置 Cookie ✅
2. history 请求发送 Cookie ✅
3. 返回 200 OK ✅

---

### 测试 3: 检查请求头

**浏览器 DevTools → Network → history 请求**:

**Request Headers**:

```
Cookie: yata_auth=<token>  ✅ Cookie 已发送
```

**Response Headers**:

```
Access-Control-Allow-Origin: http://localhost:3000
Access-Control-Allow-Credentials: true
```

---

## ⚠️ 潜在问题和解决方案

### 问题 1: 浏览器拒绝 `SameSite=None` + `Secure=False`

**现代浏览器策略**:

- Chrome 80+、Firefox 69+ 要求 `SameSite=None` 必须配合 `Secure=True`
- 否则 Cookie 会被拒绝

**解决方案**:

#### 选项 A: 使用 HTTPS

```python
cookie_secure=True,
cookie_samesite="none",
```

**要求**:

- 后端必须使用 HTTPS
- 需要 SSL 证书（可以使用自签名证书用于开发）

#### 选项 B: 浏览器标志（仅开发）

**Chrome**:

```
chrome://flags/#same-site-by-default-cookies → Disabled
chrome://flags/#cookies-without-same-site-must-be-secure → Disabled
```

**Firefox**:

```
about:config
network.cookie.sameSite.laxByDefault → false
network.cookie.sameSite.noneRequiresSecure → false
```

⚠️ **仅用于开发，不要在生产环境使用！**

#### 选项 C: 使用方案 2 或 3

如果浏览器完全拒绝，使用前端代理或 Bearer Token。

---

## 📊 不同场景的推荐配置

### 开发环境（前后端不同域名）

**当前方案**:

```python
cookie_secure=False
cookie_samesite="none"
```

**备用方案**（如果浏览器拒绝）:

- 使用前端代理
- 或使用 Bearer Token

---

### 生产环境（同域名）

**推荐**:

```python
cookie_secure=True  # HTTPS
cookie_samesite="lax"  # 安全
```

**要求**:

- 前后端部署在同一域名下（如 `app.yata.com` 和 `api.yata.com`）
- 使用 HTTPS

---

### 生产环境（不同域名）

**推荐**:

```python
cookie_secure=True
cookie_samesite="none"
```

**要求**:

- 必须使用 HTTPS
- CORS 配置正确
- 白名单包含前端域名

---

## 🎯 配置建议

### 动态配置（根据环境）

```python
# 未来可以优化为根据环境动态配置
cookie_transport = CookieTransport(
    cookie_name="yata_auth",
    cookie_max_age=settings.AUTH_JWT_LIFETIME_SECONDS,
    cookie_path="/",
    cookie_domain=None,
    cookie_secure=settings.COOKIE_SECURE,  # 从环境变量读取
    cookie_httponly=True,
    cookie_samesite=settings.COOKIE_SAMESITE,  # 从环境变量读取
)
```

**`.env` 配置**:

```bash
# 开发环境
COOKIE_SECURE=false
COOKIE_SAMESITE=none

# 生产环境
COOKIE_SECURE=true
COOKIE_SAMESITE=lax
```

---

## 📚 参考资源

- [MDN: SameSite cookies](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Set-Cookie/SameSite)
- [Chrome SameSite 更新](https://www.chromium.org/updates/same-site)
- [FastAPI-Users Cookie Transport](https://fastapi-users.github.io/fastapi-users/configuration/authentication/transports/cookie/)

---

## 🎉 总结

### 问题

登录成功，但后续请求返回 401 Unauthorized。

### 根本原因

`SameSite=lax` 阻止跨站的 fetch 请求发送 Cookie。

### 解决方案

将 `SameSite` 改为 `none`，允许跨站发送 Cookie。

### 注意事项

- ⚠️ 某些浏览器可能要求 `Secure=True`（需要 HTTPS）
- ⚠️ 如果浏览器拒绝，考虑使用前端代理或 Bearer Token
- ⚠️ 生产环境建议使用 HTTPS + `SameSite=none` 或同域部署 + `SameSite=lax`

---

**修复状态**: ✅ 已完成  
**测试状态**: ⏳ 待用户验证  
**文档状态**: ✅ 已记录  
**优先级**: 🔴 高（核心功能）
