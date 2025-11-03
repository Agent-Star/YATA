# 用户认证系统

YATA 后端集成了基于 [FastAPI-Users](https://fastapi-users.github.io/fastapi-users/) 的完整用户认证系统，支持用户注册、登录、密码管理等功能。

## 架构概览

认证系统包含以下核心组件：

1. **用户模型** (`src/auth/models.py`)：定义用户数据结构和 API Schema
2. **数据库适配器** (`src/auth/database.py`)：管理用户数据的存储（支持 SQLite 和 PostgreSQL）
3. **用户管理器** (`src/auth/manager.py`)：处理用户生命周期事件（注册、密码重置等）
4. **认证配置** (`src/auth/auth.py`)：配置 JWT 认证策略和用户依赖项

## 认证方式

YATA 支持两种认证方式：

### 1. Bearer Token 认证（向后兼容）

用于 API 密钥访问，适合服务间调用：

```bash
# 在 .env 中配置
AUTH_SECRET=your-api-secret-key

# 使用方式
curl -H "Authorization: Bearer your-api-secret-key" \
  http://localhost:8080/invoke
```

### 2. JWT 用户认证（推荐）

用于用户登录，支持完整的用户管理功能：

```bash
# 在 .env 中配置
AUTH_JWT_SECRET=your-jwt-secret-key
AUTH_JWT_LIFETIME_SECONDS=604800  # 7 天
```

## API 端点

### 用户注册

```bash
POST /auth/register
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "securepassword123",
  "username": "username",
  "full_name": "User Name"
}
```

响应：

```json
{
  "id": "uuid-string",
  "email": "user@example.com",
  "username": "username",
  "full_name": "User Name",
  "is_active": true,
  "is_superuser": false,
  "is_verified": false,
  "created_at": "2024-01-01T00:00:00Z",
  "total_conversations": 0
}
```

### 用户登录

```bash
POST /auth/jwt/login
Content-Type: application/x-www-form-urlencoded

username=user@example.com&password=securepassword123
```

响应：

```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "token_type": "bearer"
}
```

### 用户登出

```bash
POST /auth/jwt/logout
Authorization: Bearer <your-jwt-token>
```

### 获取当前用户信息

```bash
GET /users/me
Authorization: Bearer <your-jwt-token>
```

响应：

```json
{
  "id": "uuid-string",
  "email": "user@example.com",
  "username": "username",
  "full_name": "User Name",
  "is_active": true,
  "is_superuser": false,
  "is_verified": false,
  "created_at": "2024-01-01T00:00:00Z",
  "total_conversations": 0
}
```

### 更新用户信息

```bash
PATCH /users/me
Authorization: Bearer <your-jwt-token>
Content-Type: application/json

{
  "full_name": "New Name",
  "username": "new_username"
}
```

### 密码重置

#### 请求重置密码

```bash
POST /auth/forgot-password
Content-Type: application/json

{
  "email": "user@example.com"
}
```

#### 重置密码

```bash
POST /auth/reset-password
Content-Type: application/json

{
  "token": "reset-token-from-email",
  "password": "new-password-123"
}
```

### 邮箱验证

#### 请求验证邮箱

```bash
POST /auth/request-verify-token
Authorization: Bearer <your-jwt-token>
```

#### 验证邮箱

```bash
POST /auth/verify
Content-Type: application/json

{
  "token": "verification-token-from-email"
}
```

## 在端点中使用用户认证

### 必需认证

要求用户必须登录才能访问：

```python
from typing import Annotated
from fastapi import Depends, APIRouter
from auth import User, current_active_user

router = APIRouter()

@router.get("/protected-endpoint")
async def protected_endpoint(
    current_user: Annotated[User, Depends(current_active_user)]
):
    return {
        "message": f"Hello, {current_user.email}!",
        "user_id": str(current_user.id)
    }
```

### 可选认证

用户可以选择登录或匿名访问：

```python
from typing import Annotated, Optional
from fastapi import Depends, APIRouter
from auth import User, current_active_user

router = APIRouter()

@router.get("/optional-auth-endpoint")
async def optional_auth_endpoint(
    current_user: Annotated[Optional[User], Depends(current_active_user)] = None
):
    if current_user:
        return {"message": f"Hello, {current_user.email}!"}
    else:
        return {"message": "Hello, Guest!"}
```

### 超级用户权限

需要超级用户权限：

```python
from typing import Annotated
from fastapi import Depends, APIRouter
from auth import User, current_superuser

router = APIRouter()

@router.get("/admin-only")
async def admin_only(
    current_user: Annotated[User, Depends(current_superuser)]
):
    return {"message": "Admin access granted"}
```

## 示例：保护 Agent 端点

参考 `src/service/auth_protected_routes_example.py` 文件，该文件展示了如何为 Agent 调用添加用户认证：

```python
from typing import Annotated
from fastapi import APIRouter, Depends
from auth import User, current_active_user
from schema import UserInput, ChatMessage

protected_router = APIRouter()

@protected_router.post("/protected/invoke")
async def protected_invoke(
    user_input: UserInput,
    current_user: Annotated[User, Depends(current_active_user)]
) -> ChatMessage:
    # 自动关联用户 ID
    if not user_input.user_id:
        user_input.user_id = str(current_user.id)
    
    # 调用 Agent 逻辑...
    pass
```

## 数据库配置

### SQLite（默认）

适合开发和小规模部署：

```bash
DATABASE_TYPE=sqlite
SQLITE_DB_PATH=checkpoints.db
```

用户数据将存储在同一个 SQLite 数据库文件中。

### PostgreSQL（推荐用于生产）

适合生产环境和多用户场景：

```bash
DATABASE_TYPE=postgres
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your-password
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=agent_service
```

用户表将自动创建在指定的 PostgreSQL 数据库中。

## 安全最佳实践

1. **使用强密码作为 JWT Secret**

   ```bash
   # 生成安全的随机密钥（Linux/Mac）
   openssl rand -hex 32
   
   # 或使用 Python
   python -c "import secrets; print(secrets.token_hex(32))"
   ```

2. **设置合理的 Token 有效期**
   - 开发环境：7 天（默认）
   - 生产环境：考虑更短的有效期（如 1-2 天）并实现刷新令牌机制

3. **使用 HTTPS**
   - 生产环境务必使用 HTTPS 以保护 token 传输

4. **实现邮件发送**
   - 当前密码重置和邮箱验证的 token 仅记录在日志中
   - 生产环境需要实现实际的邮件发送逻辑（参见 `src/auth/manager.py`）

5. **配置 CORS**
   - 如果前端和后端分离部署，需要正确配置 CORS 策略

## 前端集成示例

### JavaScript/TypeScript

```typescript
// 注册
const register = async (email: string, password: string) => {
  const response = await fetch('http://localhost:8080/auth/register', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password })
  });
  return response.json();
};

// 登录
const login = async (email: string, password: string) => {
  const response = await fetch('http://localhost:8080/auth/jwt/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({ username: email, password })
  });
  const data = await response.json();
  // 保存 token
  localStorage.setItem('access_token', data.access_token);
  return data;
};

// 调用受保护的 API
const callProtectedAPI = async (message: string) => {
  const token = localStorage.getItem('access_token');
  const response = await fetch('http://localhost:8080/protected/invoke', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`
    },
    body: JSON.stringify({ message })
  });
  return response.json();
};
```

## 测试

运行认证相关测试：

```bash
# 安装测试依赖
uv sync --frozen

# 运行所有测试
pytest tests/auth/

# 运行特定测试
pytest tests/auth/test_auth.py::test_user_registration -v
```

## 故障排查

### 问题：用户注册返回 500 错误

**原因**：数据库未正确初始化

**解决**：

1. 检查数据库配置是否正确
2. 确保数据库服务正在运行（如 PostgreSQL）
3. 检查日志输出中的详细错误信息

### 问题：JWT token 无效

**原因**：token 过期或 JWT_SECRET 不匹配

**解决**：

1. 检查 `AUTH_JWT_LIFETIME_SECONDS` 配置
2. 确保前后端使用相同的 `AUTH_JWT_SECRET`
3. 重新登录获取新的 token

### 问题：密码重置邮件未发送

**原因**：邮件发送功能未实现

**解决**：

- 在 `src/auth/manager.py` 中的 `on_after_forgot_password` 方法中实现邮件发送逻辑
- 或查看日志中的重置 token 用于测试

## 相关文档

- [FastAPI-Users 官方文档](https://fastapi-users.github.io/fastapi-users/)
- [JWT 介绍](https://jwt.io/introduction)
- [YATA 项目架构](../README.md)
