# 登录问题调试指南

## 当前问题

使用 `"account": "admin"` 登录失败，返回 401 错误。

## 已添加的调试日志

我已经在 `auth/manager.py` 中添加了详细的日志：

1. **尝试认证用户**: 显示正在尝试的账号
2. **通过 email 查找结果**: 显示是否找到
3. **通过 username 查找**: 显示查找过程
4. **密码验证**: 显示验证结果
5. **认证成功/失败**: 显示最终结果

## 启用 DEBUG 日志级别

### 方法 1: 临时修改 `.env` 文件

编辑 `.env` 文件，将日志级别改为 `DEBUG`:

```bash
LOG_LEVEL=DEBUG
```

然后重启服务。

### 方法 2: 在启动时覆盖

```bash
LOG_LEVEL=DEBUG python src/run_service.py
```

## 预期的 DEBUG 日志输出

成功登录时应该看到：

```
DEBUG: [auth.manager] 尝试认证用户: admin
DEBUG: [auth.manager] 通过 email 查找结果: 未找到
DEBUG: [auth.manager] 尝试通过 username 查找...
DEBUG: [auth.manager] 通过 username 查找用户 'admin': 找到
DEBUG: [auth.manager] 找到用户，开始验证密码...
INFO:  [auth.manager] 用户认证成功: admin (ID: xxx-xxx-xxx)
```

失败时会显示具体在哪一步失败。

## 常见问题排查

### 1. 用户不存在

如果看到 `用户不存在: admin`，说明数据库中没有这个用户。

**解决方案**：

```bash
# 检查数据库中的用户
psql -U yata -d yata_db -c "SELECT id, username, email FROM user;"
```

### 2. 通过 username 查找失败

如果看到 `通过 username 查找用户失败 'admin': ...`，说明查询出错。

**可能原因**：

- `user_db.session` 属性访问失败
- 数据库连接问题

### 3. 密码验证失败

如果看到 `密码验证失败: admin`，说明密码不匹配。

**解决方案**：

- 确认密码是否正确
- 检查数据库中的 `hashed_password` 字段

## 快速测试脚本

创建 `backend/test_login.py`:

```python
import asyncio
from auth.database import get_async_session, get_user_db
from auth.manager import UserManager
from fastapi.security import OAuth2PasswordRequestForm

async def test_login():
    async for session in get_async_session():
        async for user_db in get_user_db(session):
            manager = UserManager(user_db)
            
            # 测试登录
            credentials = OAuth2PasswordRequestForm(
                username="admin",
                password="12345678"
            )
            
            user = await manager.authenticate(credentials)
            
            if user:
                print(f"✅ 登录成功: {user.username} (ID: {user.id})")
                print(f"   Email: {user.email}")
                print(f"   Active: {user.is_active}")
            else:
                print("❌ 登录失败")
            
            break
        break

if __name__ == "__main__":
    asyncio.run(test_login())
```

运行：

```bash
cd backend
python test_login.py
```

## 手动验证数据库

```sql
-- 连接到数据库
psql -U yata -d yata_db

-- 查看所有用户
SELECT id, username, email, is_active, is_superuser FROM "user";

-- 查看特定用户
SELECT * FROM "user" WHERE username = 'admin';
```

## 下一步

1. **启用 DEBUG 日志**（方法 1 或 2）
2. **重启服务**
3. **再次尝试登录**
4. **查看完整的日志输出**
5. **将日志信息提供给我进行进一步诊断**
