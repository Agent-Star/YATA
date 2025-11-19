# 快速开始：用户认证系统

本指南将帮助你快速上手 YATA 的用户认证功能。

## 5 分钟快速体验

### 1. 安装依赖

```bash
cd backend
uv sync --frozen
source .venv/bin/activate  # Linux/Mac
# 或 .venv\Scripts\activate  # Windows
```

### 2. 配置环境变量

创建 `.env` 文件（或复制 `env.example`）：

```bash
# 最小配置
OPENAI_API_KEY=sk-your-openai-api-key
DATABASE_TYPE=sqlite
AUTH_JWT_SECRET=my-super-secret-jwt-key-change-in-production
```

### 3. 启动服务

```bash
python src/run_service.py
```

服务将在 `http://localhost:8080` 启动。

### 4. 测试认证功能

#### 4.1 注册新用户

```bash
curl -X POST http://localhost:8080/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "SecurePassword123!",
    "username": "testuser"
  }'
```

响应示例：

```json
{
  "id": "a1b2c3d4-...",
  "email": "test@example.com",
  "username": "testuser",
  "is_active": true,
  "is_verified": false,
  "created_at": "2024-01-01T00:00:00Z",
  "total_conversations": 0
}
```

#### 4.2 用户登录

```bash
curl -X POST http://localhost:8080/auth/jwt/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=test@example.com&password=SecurePassword123!"
```

响应示例：

```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "token_type": "bearer"
}
```

**保存这个 access_token，后续请求需要用到！**

#### 4.3 获取用户信息

```bash
# 将 YOUR_TOKEN 替换为上一步获取的 access_token
curl -X GET http://localhost:8080/users/me \
  -H "Authorization: Bearer YOUR_TOKEN"
```

响应示例：

```json
{
  "id": "a1b2c3d4-...",
  "email": "test@example.com",
  "username": "testuser",
  "full_name": null,
  "is_active": true,
  "is_superuser": false,
  "is_verified": false,
  "created_at": "2024-01-01T00:00:00Z",
  "total_conversations": 0
}
```

#### 4.4 调用 Agent（使用用户认证）

参考 `src/service/auth_protected_routes_example.py` 中的示例路由。

## 常见使用场景

### 场景 1：Web 应用集成

```javascript
// 前端代码示例
class AuthAPI {
  baseURL = 'http://localhost:8080';
  
  async register(email, password) {
    const response = await fetch(`${this.baseURL}/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password })
    });
    return response.json();
  }
  
  async login(email, password) {
    const response = await fetch(`${this.baseURL}/auth/jwt/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams({ username: email, password })
    });
    const data = await response.json();
    localStorage.setItem('token', data.access_token);
    return data;
  }
  
  async getCurrentUser() {
    const token = localStorage.getItem('token');
    const response = await fetch(`${this.baseURL}/users/me`, {
      headers: { 'Authorization': `Bearer ${token}` }
    });
    return response.json();
  }
}
```

### 场景 2：移动应用集成

```python
# Python 客户端示例
import requests

class YATAClient:
    def __init__(self, base_url="http://localhost:8080"):
        self.base_url = base_url
        self.token = None
    
    def register(self, email, password):
        response = requests.post(
            f"{self.base_url}/auth/register",
            json={"email": email, "password": password}
        )
        return response.json()
    
    def login(self, email, password):
        response = requests.post(
            f"{self.base_url}/auth/jwt/login",
            data={"username": email, "password": password}
        )
        data = response.json()
        self.token = data["access_token"]
        return data
    
    def get_current_user(self):
        headers = {"Authorization": f"Bearer {self.token}"}
        response = requests.get(
            f"{self.base_url}/users/me",
            headers=headers
        )
        return response.json()

# 使用示例
client = YATAClient()
client.login("test@example.com", "SecurePassword123!")
user = client.get_current_user()
print(f"Logged in as: {user['email']}")
```

### 场景 3：API 密钥访问（无需用户登录）

如果你不需要用户系统，仍可使用传统的 API 密钥方式：

```bash
# 在 .env 中设置
AUTH_SECRET=your-api-secret-key

# 使用方式
curl -X POST http://localhost:8080/invoke \
  -H "Authorization: Bearer your-api-secret-key" \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello, Agent!"}'
```

## 查看 API 文档

启动服务后，访问以下 URL 查看完整的 API 文档：

- **Swagger UI**: <http://localhost:8080/docs>
- **ReDoc**: <http://localhost:8080/redoc>

在文档界面中，你可以：

- 查看所有可用的 API 端点
- 测试 API 调用
- 查看请求/响应格式

### 在 Swagger UI 中使用认证

1. 点击页面右上角的 "Authorize" 按钮
2. 在弹出的对话框中，输入你的 JWT token：`Bearer YOUR_TOKEN`
3. 点击 "Authorize"，现在所有请求都会自动带上认证信息

## 使用 Postman 测试

### 1. 导入 Collection

创建一个新的 Postman Collection，包含以下请求：

#### 注册用户

- **Method**: POST
- **URL**: `http://localhost:8080/auth/register`
- **Headers**: `Content-Type: application/json`
- **Body** (raw JSON):

  ```json
  {
    "email": "{{userEmail}}",
    "password": "{{userPassword}}",
    "username": "{{username}}"
  }
  ```

#### 登录

- **Method**: POST
- **URL**: `http://localhost:8080/auth/jwt/login`
- **Headers**: `Content-Type: application/x-www-form-urlencoded`
- **Body** (x-www-form-urlencoded):
  - `username`: `{{userEmail}}`
  - `password`: `{{userPassword}}`
- **Tests** (自动保存 token):

  ```javascript
  const response = pm.response.json();
  pm.environment.set("accessToken", response.access_token);
  ```

#### 获取用户信息

- **Method**: GET
- **URL**: `http://localhost:8080/users/me`
- **Headers**: `Authorization: Bearer {{accessToken}}`

### 2. 设置环境变量

在 Postman 中创建环境变量：

- `userEmail`: `test@example.com`
- `userPassword`: `SecurePassword123!`
- `username`: `testuser`
- `accessToken`: (将由登录请求自动填充)

## 数据库管理

### SQLite

用户数据存储在 `checkpoints.db` 文件中：

```bash
# 查看用户表
sqlite3 checkpoints.db "SELECT * FROM users;"

# 删除所有用户（重置测试环境）
sqlite3 checkpoints.db "DELETE FROM users;"
```

### PostgreSQL

```bash
# 连接到数据库
psql -U postgres -d agent_service

# 查看用户
SELECT id, email, username, is_active, created_at FROM users;

# 删除测试用户
DELETE FROM users WHERE email = 'test@example.com';
```

## 故障排查

### 问题：服务启动失败

检查日志输出，常见原因：

1. 数据库连接失败（检查 PostgreSQL 是否运行）
2. 端口 8080 已被占用（修改 `PORT` 环境变量）
3. LLM API 密钥无效（检查 `.env` 中的 API 密钥）

### 问题：注册时返回 500 错误

**可能原因**：数据库表未创建

**解决方案**：

```bash
# 删除旧的数据库文件
rm checkpoints.db

# 重启服务，将自动创建新表
python src/run_service.py
```

### 问题：登录后 token 无效

**可能原因**：JWT secret 不一致

**解决方案**：

1. 确保 `.env` 中的 `AUTH_JWT_SECRET` 没有改变
2. 如果改变了，需要重新登录获取新 token

## 下一步

- 📖 查看完整的 [认证系统文档](./Authentication.md)
- 🔧 学习如何[保护你的 Agent 端点](./Authentication.md#在端点中使用用户认证)
- 🧪 运行[认证测试](../tests/auth/)
- 🚀 部署到生产环境（记得修改 `AUTH_JWT_SECRET`！）

## 需要帮助？

- 查看 [FastAPI-Users 官方文档](https://fastapi-users.github.io/fastapi-users/)
- 提交 Issue 到项目仓库
- 查看项目 [README](../README.md)
