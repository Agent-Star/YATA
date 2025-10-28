# Super Admin Auto-Initialization Implementation Summary

## 需求描述

在后端服务启动时，自动创建超级管理员账户（如果不存在），账户信息从环境变量读取。

## 实现方案

### 1. 环境变量配置

**文件**: `backend/src/core/settings.py`

添加了两个新的环境变量配置：

- `SUPER_ADMIN_USERNAME`: 超级管理员用户名（可选）
- `SUPER_ADMIN_PASSWORD`: 超级管理员密码（可选，SecretStr 类型）

```python
# 超级管理员配置
SUPER_ADMIN_USERNAME: str | None = None
SUPER_ADMIN_PASSWORD: SecretStr | None = None
```

### 2. 超级管理员初始化函数

**文件**: `backend/src/auth/init.py`

实现了 `initialize_super_admin()` 函数，主要逻辑：

1. **环境变量检查**: 如果未配置 `SUPER_ADMIN_USERNAME` 或 `SUPER_ADMIN_PASSWORD`，则跳过初始化
2. **用户存在性检查**:
   - 首先通过 email 查找（使用 `admin_username@admin.local` 格式）
   - 然后通过 username 查找（直接使用 `admin_username`）
3. **创建超级管理员**: 如果不存在，则创建新用户，设置属性：
   - `email`: `{admin_username}@admin.local`
   - `username`: `{admin_username}`
   - `password`: 从环境变量读取的明文密码（由 `UserManager.create()` 自动哈希）
   - `is_superuser`: `True`
   - `is_verified`: `True`
   - `is_active`: `True`

### 3. 密码加密机制

**重要**: FastAPI-Users 的 `UserManager.create()` 方法会自动处理密码哈希，因此：

- 环境变量中的 `SUPER_ADMIN_PASSWORD` 应该是**明文密码**
- `UserManager.create()` 会使用内置的密码哈希机制（默认使用 `passlib` 的 bcrypt）
- 存储到数据库的是 `hashed_password` 字段

**代码流程**:

```python
# 1. 从环境变量获取明文密码
password=admin_password.get_secret_value()

# 2. UserManager.create() 自动哈希密码
admin_user = await user_manager.create(
    UserCreate(
        password=password,  # 明文密码
        ...
    )
)

# 3. 存储到数据库的是 hashed_password
```

### 4. 服务启动集成

**文件**: `backend/src/service/service.py`

在 `lifespan()` 函数中，在创建数据库表之后、初始化 checkpointer 之前调用超级管理员初始化：

```python
from auth.init import initialize_super_admin

# ...

# Initialize user authentication database tables
await create_db_and_tables()

# Initialize super admin user if configured
if settings.SUPER_ADMIN_USERNAME and settings.SUPER_ADMIN_PASSWORD:
    await initialize_super_admin()
```

### 5. 环境变量示例更新

**文件**: `backend/env.example`

添加了超级管理员配置示例：

```bash
# 超级管理员配置
# 如果设置，服务启动时会自动创建超级管理员账户（如果不存在）
# SUPER_ADMIN_USERNAME=admin
# SUPER_ADMIN_PASSWORD=your-secure-password-here
```

## 技术要点

1. **依赖链正确性**: `get_async_session()` -> `get_user_db()` -> `get_user_manager()`
2. **异常处理**: 初始化失败不会阻止服务启动，只记录错误日志
3. **幂等性**: 多次启动不会重复创建，已存在则跳过
4. **安全性**:
   - 密码通过 `SecretStr` 类型保护
   - 密码自动哈希存储
   - 生产环境应使用强密码

## 使用方法

1. 在根目录的 `.env` 文件中添加：

   ```bash
   SUPER_ADMIN_USERNAME=admin
   SUPER_ADMIN_PASSWORD=your-secure-password
   ```

2. 启动服务，日志会显示：

   ```
   INFO: 检查超级管理员账户: admin
   INFO: 创建超级管理员: admin
   INFO: 超级管理员创建成功: admin (ID: ...)
   ```

3. 后续启动会跳过创建：

   ```
   INFO: 检查超级管理员账户: admin
   INFO: 超级管理员已存在 (username): admin
   ```

## 代码组织

为了提高模块化和可维护性，超级管理员初始化逻辑被抽离到独立的模块中：

- **`backend/src/auth/init.py`**: 用户初始化相关功能（包含 `initialize_super_admin()` 函数）
- **`backend/src/service/service.py`**: 在服务启动时调用初始化函数

这种设计的优势：

1. 职责分离：认证相关的初始化逻辑放在 `auth` 模块中
2. 可测试性：可以独立测试 `initialize_super_admin()` 函数
3. 可扩展性：未来可以在 `auth/init.py` 中添加其他初始化功能

## 涉及文件

- `backend/src/core/settings.py`: 环境变量配置
- `backend/src/auth/init.py`: 超级管理员初始化逻辑
- `backend/src/service/service.py`: 服务启动集成
- `backend/env.example`: 环境变量示例

## Linting Status

✅ 无 linting errors
