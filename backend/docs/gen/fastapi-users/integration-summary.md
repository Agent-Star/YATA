# FastAPI-Users 集成总结

## 概述

本文档总结了将 FastAPI-Users 用户认证系统集成到 YATA 后端的完整过程。

## 集成内容

### 1. 依赖项添加

在 `pyproject.toml` 中添加了以下依赖：

```toml
"fastapi-users[sqlalchemy] ~=14.0.0"
"sqlalchemy[asyncio] ~=2.0.0"
```

### 2. 新增模块：`src/auth/`

创建了完整的认证模块，包含以下文件：

#### `models.py`

- 定义了 `User` 数据库模型（继承自 `SQLAlchemyBaseUserTableUUID`）
- 扩展字段：`username`, `full_name`, `created_at`, `updated_at`, `total_conversations`
- 定义了 Pydantic Schemas：`UserRead`, `UserCreate`, `UserUpdate`

#### `database.py`

- 实现了数据库适配器，支持 SQLite 和 PostgreSQL
- 提供异步数据库会话管理
- 自动创建用户表

#### `manager.py`

- 实现了 `UserManager`，处理用户生命周期事件
- 包含用户注册、密码重置、邮箱验证的回调钩子

#### `auth.py`

- 配置 JWT 认证策略
- 定义认证后端（Bearer Transport）
- 导出用户依赖项：`current_active_user`, `current_verified_user`, `current_superuser`

#### `__init__.py`

- 导出所有公共接口

### 3. 配置更新：`src/core/settings.py`

添加了 JWT 相关配置：

```python
AUTH_JWT_SECRET: SecretStr  # JWT 签名密钥
AUTH_JWT_LIFETIME_SECONDS: int = 604800  # Token 有效期（7天）
```

保留了向后兼容的 `AUTH_SECRET` 配置（用于 API 密钥访问）。

### 4. 服务集成：`src/service/service.py`

#### 认证路由

添加了以下路由前缀：

- `/auth/register` - 用户注册
- `/auth/jwt/login` - JWT 登录
- `/auth/jwt/logout` - JWT 登出
- `/auth/forgot-password` - 请求密码重置
- `/auth/reset-password` - 重置密码
- `/auth/request-verify-token` - 请求邮箱验证
- `/auth/verify` - 验证邮箱
- `/users/me` - 获取当前用户信息
- `/users/{id}` - 用户管理端点

#### 数据库初始化

在 `lifespan` 中添加了用户表初始化：

```python
await create_db_and_tables()
```

### 5. 示例代码：`src/service/auth_protected_routes_example.py`

创建了详细的示例文件，展示如何：

- 创建需要认证的端点
- 使用 `current_active_user` 依赖
- 实现可选认证（用户可登录或匿名访问）
- 获取当前登录用户信息

### 6. 测试代码：`tests/auth/`

创建了认证模块的测试：

- `test_auth.py` - 完整的认证功能测试
- `conftest.py` - 测试 fixtures

测试覆盖：

- 用户注册
- 用户登录
- Token 验证
- 受保护端点访问
- 无效 Token 处理
- 密码重置流程

### 7. 文档

#### `docs/Authentication.md`

完整的用户认证系统文档，包含：

- 架构概览
- 认证方式说明
- API 端点详解
- 在代码中使用认证的示例
- 数据库配置
- 安全最佳实践
- 前端集成示例
- 故障排查

#### `docs/Quick_Start_Auth.md`

快速开始指南，包含：

- 5 分钟快速体验
- 常见使用场景
- Postman 测试指南
- 数据库管理命令
- 故障排查

#### `env.example`

环境变量配置示例，新增：

- `AUTH_JWT_SECRET` - JWT 密钥配置说明
- `AUTH_JWT_LIFETIME_SECONDS` - Token 有效期配置

### 8. README 更新

更新了 `backend/README.md`，添加了：

- FastAPI-Users 技术栈说明
- `src/auth/` 模块介绍
- 用户认证系统功能列表
- 快速开始链接
- 安全提示

## 技术特性

### 已实现功能

✅ **用户管理**

- 用户注册（邮箱 + 密码）
- 用户登录（JWT Token）
- 用户信息查询和更新
- 密码重置流程
- 邮箱验证流程

✅ **安全性**

- JWT Token 认证
- 密码哈希存储
- Token 过期管理
- 可配置的 Token 有效期

✅ **数据库支持**

- SQLite（开发环境）
- PostgreSQL（生产环境）
- 自动创建表结构
- 异步数据库操作

✅ **向后兼容**

- 保留了原有的 `AUTH_SECRET` Bearer Token 认证
- Agent 端点可继续使用 API 密钥访问
- 新的用户认证系统作为可选功能

✅ **灵活的认证策略**

- 必需认证（`current_active_user`）
- 可选认证（允许匿名访问）
- 超级用户权限检查（`current_superuser`）
- 邮箱验证用户（`current_verified_user`）

### 待实现功能

🔜 **邮件发送**

- 密码重置邮件
- 邮箱验证邮件
- 当前仅在日志中输出 token

🔜 **社交登录**

- Google OAuth
- GitHub OAuth
- 其他第三方登录

🔜 **用户权限系统**

- 基于角色的访问控制（RBAC）
- 细粒度权限管理

🔜 **使用配额管理**

- 用户调用次数限制
- Token 使用量统计

## 集成架构

```txt
Backend
├── src/
│   ├── auth/              # 🆕 用户认证模块
│   │   ├── models.py      # 用户数据模型
│   │   ├── database.py    # 数据库适配器
│   │   ├── manager.py     # 用户管理器
│   │   ├── auth.py        # 认证配置
│   │   └── __init__.py    # 模块导出
│   ├── service/
│   │   ├── service.py     # 🔄 集成认证路由
│   │   └── auth_protected_routes_example.py  # 🆕 示例路由
│   ├── core/
│   │   └── settings.py    # 🔄 添加 JWT 配置
│   └── ...
├── tests/
│   └── auth/              # 🆕 认证测试
│       ├── test_auth.py
│       └── conftest.py
├── docs/
│   ├── Authentication.md           # 🆕 完整文档
│   ├── Quick_Start_Auth.md         # 🆕 快速开始
│   └── gen/fastapi-users/
│       └── integration-summary.md  # 🆕 本文件
└── env.example            # 🔄 更新配置示例
```

## 使用示例

### 1. 用户注册和登录

```bash
# 注册
curl -X POST http://localhost:8080/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "secure123"}'

# 登录
curl -X POST http://localhost:8080/auth/jwt/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=user@example.com&password=secure123"

# 响应：{"access_token": "eyJ...", "token_type": "bearer"}
```

### 2. 在端点中使用认证

```python
from typing import Annotated
from fastapi import APIRouter, Depends
from auth import User, current_active_user

router = APIRouter()

@router.post("/my-endpoint")
async def protected_endpoint(
    current_user: Annotated[User, Depends(current_active_user)]
):
    return {
        "message": f"Hello, {current_user.email}!",
        "user_id": str(current_user.id)
    }
```

### 3. 前端集成

```javascript
// 登录
const login = async (email, password) => {
  const response = await fetch('http://localhost:8080/auth/jwt/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({ username: email, password })
  });
  const { access_token } = await response.json();
  localStorage.setItem('token', access_token);
};

// 调用受保护的 API
const callAPI = async (endpoint, data) => {
  const token = localStorage.getItem('token');
  return fetch(`http://localhost:8080${endpoint}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`
    },
    body: JSON.stringify(data)
  });
};
```

## 配置说明

### 开发环境配置

```bash
# .env
DATABASE_TYPE=sqlite
SQLITE_DB_PATH=checkpoints.db
AUTH_JWT_SECRET=dev-secret-key-change-in-production
AUTH_JWT_LIFETIME_SECONDS=604800  # 7 天
OPENAI_API_KEY=sk-your-key
```

### 生产环境配置

```bash
# .env
DATABASE_TYPE=postgres
POSTGRES_HOST=your-db-host
POSTGRES_USER=postgres
POSTGRES_PASSWORD=secure-password
POSTGRES_DB=yata_prod
AUTH_JWT_SECRET=<生成的强随机密钥>
AUTH_JWT_LIFETIME_SECONDS=86400  # 1 天
OPENAI_API_KEY=sk-your-key
```

生成安全的 JWT Secret：

```bash
openssl rand -hex 32
# 或
python -c "import secrets; print(secrets.token_hex(32))"
```

## 安全考虑

### 已实现的安全措施

1. ✅ **密码哈希**: 使用 bcrypt 自动哈希存储
2. ✅ **JWT 签名**: 使用 HS256 算法签名 Token
3. ✅ **Token 过期**: 可配置的 Token 有效期
4. ✅ **HTTPS Ready**: 支持在 HTTPS 环境下部署
5. ✅ **SQL 注入防护**: 使用 SQLAlchemy ORM

### 生产环境建议

1. 🔒 **使用强随机 JWT Secret**
   - 至少 32 字节的随机密钥
   - 不要使用默认值

2. 🔒 **启用 HTTPS**
   - Token 通过 HTTPS 传输
   - 配置 SSL 证书

3. 🔒 **使用 PostgreSQL**
   - 更好的并发性能
   - 更可靠的事务支持

4. 🔒 **实现邮件发送**
   - 真实的密码重置流程
   - 邮箱验证功能

5. 🔒 **配置 CORS**
   - 限制允许的来源
   - 正确配置 credentials

6. 🔒 **监控和日志**
   - 记录登录尝试
   - 监控异常行为

## 测试

运行认证测试：

```bash
# 安装依赖
uv sync --frozen

# 运行所有认证测试
pytest tests/auth/ -v

# 运行特定测试
pytest tests/auth/test_auth.py::test_user_registration -v

# 查看测试覆盖率
pytest tests/auth/ --cov=src/auth --cov-report=html
```

## 迁移指南

### 从 API 密钥迁移到用户认证

1. **保持向后兼容**
   - 保留 `AUTH_SECRET` 配置
   - 现有 API 密钥访问仍然有效

2. **添加用户认证**
   - 新端点使用 JWT 认证
   - 用户可以注册账号

3. **逐步迁移**
   - 先在新功能中使用用户认证
   - 逐步将旧端点迁移到用户认证

### 前端改造建议

1. **添加登录界面**
   - 注册表单
   - 登录表单
   - 忘记密码流程

2. **Token 管理**
   - 存储 JWT Token（localStorage 或 sessionStorage）
   - 自动附加 Authorization Header
   - Token 过期处理和刷新

3. **用户状态管理**
   - 保存当前用户信息
   - 登录状态检查
   - 权限控制

## 常见问题

### Q: 如何生成强随机密钥？

```bash
openssl rand -hex 32
# 或使用 Python
python -c "import secrets; print(secrets.token_hex(32))"
```

### Q: 如何重置用户密码（开发环境）？

```python
# 使用 Python 脚本
from auth.database import async_engine
from auth.models import Base, User
from sqlalchemy.ext.asyncio import AsyncSession
import asyncio

async def reset_password():
    async with AsyncSession(async_engine) as session:
        user = await session.get(User, user_id)
        # 更新密码...
```

### Q: 如何创建超级用户？

```python
# 直接在数据库中更新
# SQLite
sqlite3 checkpoints.db "UPDATE users SET is_superuser=1 WHERE email='admin@example.com';"

# PostgreSQL
psql -U postgres -d agent_service -c "UPDATE users SET is_superuser=true WHERE email='admin@example.com';"
```

### Q: Token 过期后如何处理？

前端需要：

1. 检测 401 响应
2. 清除本地存储的 Token
3. 重定向到登录页面
4. 或实现 Token 刷新机制

## 相关资源

- [FastAPI-Users 官方文档](https://fastapi-users.github.io/fastapi-users/)
- [JWT 规范](https://jwt.io/)
- [SQLAlchemy 文档](https://docs.sqlalchemy.org/)
- [FastAPI 安全指南](https://fastapi.tiangolo.com/tutorial/security/)

## 更新日志

### 2024-10-12

- ✨ 初始集成 FastAPI-Users (v14.0.0)
- ✨ 实现 JWT 认证
- ✨ 支持 SQLite 和 PostgreSQL
- ✨ 添加完整文档和示例
- ✨ 创建测试套件
- ✨ 更新 README

## 贡献者

- Eden Wang (<edwardwang33773@gmail.com>)

## 许可证

MIT License - 详见项目根目录 LICENSE 文件
