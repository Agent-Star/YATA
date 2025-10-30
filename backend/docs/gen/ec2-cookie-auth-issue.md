# EC2 部署 Cookie 认证问题排查

## 🐛 问题现象

- **本地环境**：Cookie 认证正常工作 ✅
- **EC2 环境**：
  - 登录成功，返回 Cookie ✅
  - 后续请求返回 401 Unauthorized ❌
  - 浏览器没有发送 Cookie ❌

---

## 🔍 根本原因

### 1. CORS 配置缺少 EC2 地址

**问题**：`allow_origins` 只包含 `localhost`，不包含 EC2 的 IP 地址

**后果**：浏览器拒绝发送 Cookie（跨域请求被阻止）

### 2. Cookie Secure 属性冲突

**当前配置**（`auth/auth.py` 第 37 行）：

```python
cookie_secure=not settings.is_dev(),
```

**行为**：

| 环境变量 `MODE` | `cookie_secure` | HTTP 可用？ | HTTPS 必需？ |
|----------------|-----------------|-------------|--------------|
| `dev` | `False` | ✅ 是 | ❌ 否 |
| `production` | `True` | ❌ **否** | ✅ **是** |

**问题**：

- 如果 EC2 使用 **HTTP**（`http://166.117.38.176:8080`）
- 但 `.env` 中 `MODE=production`
- 则 `cookie_secure=True`
- 浏览器会**拒绝发送** Cookie（Secure Cookie 必须通过 HTTPS）

---

## ✅ 解决方案

### 方案 1：临时快速修复（测试用）

**在 EC2 的 `.env` 文件中设置**：

```bash
MODE=dev
```

**然后重启服务**：

```bash
sudo systemctl restart yata-backend
# 或
python src/run_service.py
```

**优点**：立即生效，无需代码修改
**缺点**：不安全，仅用于测试

---

### 方案 2：强制禁用 Secure（调试用）

**修改 `backend/src/auth/auth.py`**：

```python
cookie_transport = CookieTransport(
    cookie_name="yata_auth",
    cookie_max_age=settings.AUTH_JWT_LIFETIME_SECONDS,
    cookie_path="/",
    cookie_domain=None,
    cookie_secure=False,  # ← 强制禁用（仅用于 HTTP 测试）
    cookie_httponly=True,
    cookie_samesite="lax",
)
```

**优点**：确保在 HTTP 下工作
**缺点**：不安全，Cookie 可能被拦截

---

### 方案 3：配置 HTTPS（生产环境推荐）⭐

#### 步骤 1: 安装 Nginx 和 Certbot

```bash
# 在 EC2 上执行
sudo dnf install nginx certbot python3-certbot-nginx -y
```

#### 步骤 2: 配置 Nginx 反向代理

创建 `/etc/nginx/conf.d/yata.conf`:

```nginx
server {
    listen 80;
    server_name your-domain.com;  # 替换为你的域名

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

#### 步骤 3: 获取 SSL 证书

```bash
sudo certbot --nginx -d your-domain.com
```

#### 步骤 4: 更新后端配置

**`.env` 文件**：

```bash
MODE=production
HOST=127.0.0.1  # Nginx 反向代理
PORT=8080
```

**`allow_origins` 添加 HTTPS 地址**：

```python
allowed_origins = [
    "https://your-domain.com",
    "http://localhost:3000",  # 本地开发
]
```

---

### 方案 4：条件性 Secure 配置（推荐）

**修改 `backend/src/auth/auth.py`**：

```python
# 判断是否使用 HTTPS
# 如果环境变量 USE_HTTPS=true，则启用 Secure
import os

use_https = os.getenv("USE_HTTPS", "false").lower() == "true"

cookie_transport = CookieTransport(
    cookie_name="yata_auth",
    cookie_max_age=settings.AUTH_JWT_LIFETIME_SECONDS,
    cookie_path="/",
    cookie_domain=None,
    cookie_secure=use_https,  # 根据环境变量决定
    cookie_httponly=True,
    cookie_samesite="lax",
)
```

**在 `.env` 中配置**：

```bash
# HTTP 环境（测试）
USE_HTTPS=false

# HTTPS 环境（生产）
USE_HTTPS=true
```

---

## 🧪 验证步骤

### 1. 检查浏览器 Cookie

**Chrome/Edge**：

1. 打开开发者工具（F12）
2. Application → Cookies → `http://166.117.38.176:8080`
3. 检查是否有 `yata_auth` Cookie
4. 查看 Cookie 的属性：
   - `Secure`: 应为空（HTTP）或 ✓（HTTPS）
   - `HttpOnly`: ✓
   - `SameSite`: Lax

### 2. 检查请求头

**在 `/auth/profile` 请求中**：

```
Headers:
Cookie: yata_auth=<JWT-token>
```

如果没有 `Cookie` 头，说明浏览器没有发送 Cookie。

### 3. 检查后端日志

```bash
# 查看认证日志
tail -f /var/log/yata-backend.log | grep auth
```

应该看到：

```
INFO: [auth.manager] 用户认证成功: admin (ID: xxx)
```

而不是：

```
INFO: 127.0.0.1:xxx - "GET /auth/profile HTTP/1.1" 401
```

---

## 📋 快速诊断命令

### 1. 检查当前模式

```bash
cd backend
python << EOF
from dotenv import load_dotenv
from core.settings import settings

load_dotenv()
print(f"MODE: {settings.MODE}")
print(f"is_dev: {settings.is_dev()}")
print(f"cookie_secure (推测): {not settings.is_dev()}")
EOF
```

### 2. 测试 CORS

```bash
curl -I -X OPTIONS http://166.117.38.176:8080/auth/login \
  -H "Origin: http://166.117.38.176:3000" \
  -H "Access-Control-Request-Method: POST"
```

**预期响应**：

```
Access-Control-Allow-Origin: http://166.117.38.176:3000
Access-Control-Allow-Credentials: true
```

### 3. 测试 Cookie

```bash
# 登录并保存 Cookie
curl -X POST http://166.117.38.176:8080/auth/login \
  -H "Content-Type: application/json" \
  -d '{"account": "admin", "password": "12345678"}' \
  -c cookies.txt -v

# 使用 Cookie 访问受保护接口
curl -X GET http://166.117.38.176:8080/auth/profile \
  -b cookies.txt -v
```

---

## 🎯 推荐的部署方案

### 开发/测试环境

```bash
# .env
MODE=dev
USE_HTTPS=false
```

**或**直接修改 `auth.py`：

```python
cookie_secure=False  # 临时禁用
```

### 生产环境

1. **配置域名**（如 `api.yata.com`）
2. **安装 SSL 证书**（Let's Encrypt）
3. **Nginx 反向代理**
4. **环境变量**：

   ```bash
   MODE=production
   USE_HTTPS=true
   ```

---

## ⚠️ 安全提示

### 不安全的配置（仅用于测试）

```python
cookie_secure=False  # ❌ Cookie 可能被拦截（中间人攻击）
```

### 安全的配置（生产环境）

```python
cookie_secure=True  # ✅ 必须通过 HTTPS
```

**生产环境必须使用 HTTPS**，否则：

- Cookie 可能被窃取
- 用户凭证可能泄露
- 违反安全最佳实践

---

## 📝 检查清单

- [ ] CORS `allow_origins` 包含 EC2 地址
- [ ] `.env` 中 `MODE=dev`（HTTP 测试）
- [ ] 或配置 `USE_HTTPS=false`
- [ ] 浏览器能看到 `yata_auth` Cookie
- [ ] Cookie 的 `Secure` 属性与协议匹配（HTTP=False, HTTPS=True）
- [ ] 后端日志显示认证成功
- [ ] `/auth/profile` 返回用户信息（200）

---

**修复日期**: 2025-01-27  
**问题类型**: Cookie 跨域 + Secure 属性冲突  
**影响范围**: HTTP 环境下的 Cookie 认证
