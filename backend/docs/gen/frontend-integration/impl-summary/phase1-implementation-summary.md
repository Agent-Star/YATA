# 阶段 1 实施总结: 认证模块适配

## 实施内容

### 1. 混合认证方案实现

**文件**: `backend/src/auth/auth.py`

#### 1.1 Cookie Transport 配置

添加了基于 Cookie 的认证传输机制:

```python
from fastapi_users.authentication import CookieTransport

cookie_transport = CookieTransport(
    cookie_name="yata_auth",
    cookie_max_age=settings.AUTH_JWT_LIFETIME_SECONDS,
    cookie_path="/",
    cookie_secure=not settings.is_dev(),  # 生产环境启用 HTTPS
    cookie_httponly=True,                 # 防止 XSS 攻击
    cookie_samesite="lax",                # CSRF 防护
)
```

**安全特性**:

- `httponly=True`: JavaScript 无法访问 cookie, 防止 XSS 攻击
- `secure=True` (生产环境): 仅通过 HTTPS 传输
- `samesite="lax"`: 防止 CSRF 攻击, 同时允许正常的跨域导航

#### 1.2 双认证后端配置

实现了 Cookie 和 Bearer Token 的混合认证:

```python
# Cookie 认证后端 (用于浏览器用户)
cookie_auth_backend = AuthenticationBackend(
    name="cookie",
    transport=cookie_transport,
    get_strategy=get_jwt_strategy,
)

# Bearer 认证后端 (用于 API 调用, 向后兼容)
bearer_auth_backend = AuthenticationBackend(
    name="jwt",
    transport=bearer_transport,
    get_strategy=get_jwt_strategy,
)

# FastAPI-Users 实例支持两种认证方式
fastapi_users: FastAPIUsers[User, str] = FastAPIUsers(  # type: ignore[arg-type]
    get_user_manager,
    [cookie_auth_backend, bearer_auth_backend],
)
```

**优势**:

- 前端用户: 使用更安全的 HttpOnly Cookie
- API 用户: 继续使用 Bearer Token (向后兼容)
- 同一套 JWT 机制, 只是传输方式不同

---

### 2. CORS 跨域配置

**文件**: `backend/src/service/service.py`

为了支持前后端分离开发, 添加了 CORS 中间件:

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],  # 前端开发服务器
    allow_credentials=True,  # 允许携带 Cookie
    allow_methods=["*"],     # 允许所有 HTTP 方法
    allow_headers=["*"],     # 允许所有请求头
)
```

**配置说明**:

- `allow_origins`: 允许的前端源 (localhost:3000 for React, localhost:5173 for Vite)
- `allow_credentials=True`: **必须启用**, 否则浏览器不会发送/接收 Cookie
- 生产环境应该修改为实际的前端域名

---

### 3. 前端适配路由实现

**文件**: `backend/src/service/frontend_routes.py` (新建)

#### 3.1 数据模型定义

创建了前端期望的数据结构:

```python
class FrontendUserResponse(BaseModel):
    """前端用户响应格式"""
    userId: str          # 对应 User.id
    account: str         # 对应 User.email (登录凭证)
    displayName: str     # 对应 User.username (显示名称)

class FrontendAuthResponse(BaseModel):
    """前端认证响应格式"""
    user: FrontendUserResponse
    message: str

class FrontendLoginRequest(BaseModel):
    """前端登录请求格式"""
    account: str         # email 或 username
    password: str

class FrontendProfileResponse(BaseModel):
    """前端用户信息响应格式"""
    userId: str
    account: str
    displayName: str
```

#### 3.2 字段映射函数

实现了后端 -> 前端的字段映射:

```python
def user_to_frontend_format(user: User) -> FrontendUserResponse:
    """将后端 User 模型转换为前端期望的格式"""
    return FrontendUserResponse(
        userId=str(user.id),
        account=user.email,       # 前端的 account 对应后端的 email
        displayName=user.username or user.email.split("@")[0],
    )
```

**映射关系**:

| 前端字段 | 后端字段 | 说明 |
|---------|---------|------|
| `userId` | `User.id` | 用户唯一标识 |
| `account` | `User.email` | 登录账号 |
| `displayName` | `User.username` | 显示名称 |

#### 3.3 注册接口

**路由**: `POST /auth/register`

```python
@frontend_router.post("/register", response_model=FrontendAuthResponse)
async def register(
    request: Request,
    account: EmailStr = Form(...),
    password: str = Form(...),
    display_name: str | None = Form(None),
    user_manager: UserManagerDependency = Depends(get_user_manager),
) -> FrontendAuthResponse:
```

**功能**:

1. 验证用户是否已存在
2. 创建新用户 (email, username, hashed_password)
3. 自动登录并设置 HttpOnly Cookie
4. 返回用户信息

**请求示例**:

```bash
curl -X POST http://localhost:8080/auth/register \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "account=user@example.com&password=12345678&display_name=User"
```

**响应示例**:

```json
{
  "user": {
    "userId": "123e4567-e89b-12d3-a456-426614174000",
    "account": "user@example.com",
    "displayName": "User"
  },
  "message": "注册成功"
}
```

#### 3.4 登录接口

**路由**: `POST /auth/login`

```python
@frontend_router.post("/login", response_model=FrontendAuthResponse)
async def login(
    response: Response,
    request: FrontendLoginRequest,
    user_manager: UserManagerDependency = Depends(get_user_manager),
) -> FrontendAuthResponse:
```

**功能**:

1. 验证用户凭证 (支持 email 或 username 登录)
2. 生成 JWT token
3. 设置 HttpOnly Cookie
4. 返回用户信息

**Cookie 设置逻辑**:

```python
# 获取 cookie transport 配置
cookie_transport = cast(CookieTransport, cookie_auth_backend.transport)

# 生成 JWT token
strategy = cookie_auth_backend.get_strategy()
token = await strategy.write_token(user)

# 设置 HttpOnly Cookie
response.set_cookie(
    key=cookie_transport.cookie_name,
    value=token,
    max_age=cookie_transport.cookie_max_age,
    path=cookie_transport.cookie_path,
    domain=cookie_transport.cookie_domain,
    secure=cookie_transport.cookie_secure,
    httponly=cookie_transport.cookie_httponly,
    samesite=cast(Literal["lax", "strict", "none"], cookie_transport.cookie_samesite),
)
```

**请求示例**:

```bash
curl -X POST http://localhost:8080/auth/login \
  -H "Content-Type: application/json" \
  -d '{"account": "user@example.com", "password": "12345678"}'
```

**响应示例**:

```json
{
  "user": {
    "userId": "123e4567-e89b-12d3-a456-426614174000",
    "account": "user@example.com",
    "displayName": "User"
  },
  "message": "登录成功"
}
```

#### 3.5 登出接口

**路由**: `POST /auth/logout`

```python
@frontend_router.post("/logout")
async def logout(
    response: Response,
    current_user: Annotated[User, Depends(current_active_user)],
) -> dict[str, str]:
```

**功能**:

1. 验证用户已登录
2. 删除 HttpOnly Cookie
3. 返回成功消息

**Cookie 删除逻辑**:

```python
cookie_transport = cast(CookieTransport, cookie_auth_backend.transport)

response.delete_cookie(
    key=cookie_transport.cookie_name,
    path=cookie_transport.cookie_path,
    domain=cookie_transport.cookie_domain,
)
```

**请求示例**:

```bash
curl -X POST http://localhost:8080/auth/logout \
  -H "Cookie: yata_auth=<jwt-token>"
```

**响应示例**:

```json
{
  "message": "登出成功"
}
```

#### 3.6 用户信息接口

**路由**: `GET /auth/profile`

```python
@frontend_router.get("/profile", response_model=FrontendProfileResponse)
async def get_profile(
    current_user: Annotated[User, Depends(current_active_user)],
) -> FrontendProfileResponse:
```

**功能**:

1. 从 Cookie 中验证用户身份
2. 返回当前用户信息

**请求示例**:

```bash
curl -X GET http://localhost:8080/auth/profile \
  -H "Cookie: yata_auth=<jwt-token>"
```

**响应示例**:

```json
{
  "userId": "123e4567-e89b-12d3-a456-426614174000",
  "account": "user@example.com",
  "displayName": "User"
}
```

---

### 4. 路由集成

**文件**: `backend/src/service/service.py`

将前端路由注册到主应用:

```python
from service.frontend_routes import frontend_router

app.include_router(
    frontend_router,
    prefix="/auth",
    tags=["Frontend Auth"],
)
```

**结果**:

- `POST /auth/register`: 注册
- `POST /auth/login`: 登录
- `POST /auth/logout`: 登出
- `GET /auth/profile`: 获取用户信息

---

## 技术亮点

### 1. 安全性

- ✅ **HttpOnly Cookie**: JavaScript 无法访问, 防止 XSS
- ✅ **Secure Cookie**: 生产环境仅 HTTPS 传输
- ✅ **SameSite 保护**: 防止 CSRF 攻击
- ✅ **密码哈希**: FastAPI-Users 自动使用 bcrypt
- ✅ **JWT 时效**: 可配置的 token 过期时间

### 2. 向后兼容

- ✅ **双认证后端**: Cookie (新) + Bearer Token (旧)
- ✅ **现有 API 不受影响**: `/auth/jwt/login` 等端点保持可用
- ✅ **渐进式迁移**: 前端可逐步切换到新接口

### 3. 开发体验

- ✅ **CORS 配置**: 支持本地前后端分离开发
- ✅ **字段映射**: 后端结构与前端期望解耦
- ✅ **统一响应格式**: 前端接口一致性好

### 4. 灵活性

- ✅ **支持 email 或 username 登录**: 登录接口自动识别
- ✅ **可选 display_name**: 注册时可以不提供, 使用默认值
- ✅ **多前端源支持**: CORS 可配置多个前端地址

---

## 涉及文件

### 新建文件

- `backend/src/service/frontend_routes.py`: 前端适配路由

### 修改文件

- `backend/src/auth/auth.py`: 添加 Cookie 认证配置
- `backend/src/service/service.py`:
  - 添加 CORS 中间件
  - 注册前端路由

---

## 测试验证

### 1. 注册流程测试

```bash
# 1. 注册新用户
curl -X POST http://localhost:8080/auth/register \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "account=test@example.com&password=12345678&display_name=TestUser" \
  -c cookies.txt

# 2. 检查响应 (应返回 user 和 message)
# 3. 检查 cookies.txt (应包含 yata_auth cookie)
```

### 2. 登录流程测试

```bash
# 1. 使用已注册账号登录
curl -X POST http://localhost:8080/auth/login \
  -H "Content-Type: application/json" \
  -d '{"account": "test@example.com", "password": "12345678"}' \
  -c cookies.txt

# 2. 检查响应和 Cookie
```

### 3. 获取用户信息测试

```bash
# 使用登录后的 Cookie 获取用户信息
curl -X GET http://localhost:8080/auth/profile \
  -b cookies.txt
```

### 4. 登出测试

```bash
# 登出并清除 Cookie
curl -X POST http://localhost:8080/auth/logout \
  -b cookies.txt \
  -c cookies.txt

# 检查 cookies.txt (yata_auth 应被删除)
```

### 5. CORS 测试

在浏览器控制台测试跨域请求:

```javascript
// 前端代码 (运行在 localhost:3000)
fetch('http://localhost:8080/auth/profile', {
  method: 'GET',
  credentials: 'include',  // 发送 Cookie
})
.then(res => res.json())
.then(data => console.log(data));
```

---

## 后续阶段依赖

阶段 1 为后续阶段奠定了基础:

- **阶段 2** (用户-Thread 关联): 依赖阶段 1 的用户认证
- **阶段 3** (行程规划接口): 依赖阶段 1 的 `current_active_user` 依赖

所有后续接口都使用 `Depends(current_active_user)` 来验证用户身份, 确保只有登录用户才能访问。

---

## 已知问题与改进空间

### 1. CORS 配置

**当前**: 硬编码前端地址
**改进**: 从环境变量读取

```python
# settings.py
FRONTEND_ORIGINS: list[str] = Field(
    default=["http://localhost:3000"],
    description="允许的前端源地址"
)
```

### 2. 错误处理

**当前**: 基本的异常处理
**改进**: 统一错误码和国际化消息

```python
class ErrorCode(str, Enum):
    ACCOUNT_EXISTS = "ACCOUNT_EXISTS"
    INVALID_CREDENTIALS = "INVALID_CREDENTIALS"
    # ...
```

### 3. 登录方式

**当前**: 支持 email 登录
**未来**: 可扩展支持手机号、第三方登录等

---

## Linting Status

✅ 初始实现后有部分 linting errors (已在后续的 linting-fixes 阶段修复):

- Type error: `get_login_response` 参数问题 → 改为手动设置 Cookie
- Type error: `cookie_samesite` 类型问题 → 添加 `Literal` 类型转换
- Type error: `fastapi_users` 泛型参数 → 添加 `type: ignore[arg-type]`

所有错误已在 linting-fixes 阶段修复, 详见 `linting-fixes-summary.md`。

---

## 总结

阶段 1 成功实现了前后端认证接口的对接, 主要成果:

1. ✅ **混合认证方案**: Cookie + Bearer Token
2. ✅ **前端适配路由**: 4 个核心认证接口
3. ✅ **字段映射**: 后端与前端数据结构解耦
4. ✅ **CORS 支持**: 本地开发环境跨域访问
5. ✅ **安全加固**: HttpOnly Cookie + SameSite 保护

这为整个前后端集成项目打下了坚实的基础！
