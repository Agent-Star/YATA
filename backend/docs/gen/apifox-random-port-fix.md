# Apifox 随机端口 CORS 问题修复

**日期**: 2025-01-27  
**问题**: Apifox 测试时每次请求的端口不同，导致 CORS 验证失败

---

## 🐛 问题现象

### 日志观察

```
INFO: 154.92.130.90:20927 - "POST /auth/login HTTP/1.1" 200
INFO: 154.92.130.90:58783 - "OPTIONS /auth/login HTTP/1.1" 405
INFO: 154.92.130.90:23211 - "OPTIONS /auth/login HTTP/1.1" 200
INFO: 154.92.130.90:27157 - "OPTIONS /auth/login HTTP/1.1" 200
INFO: 154.92.130.90:21855 - "POST /auth/login HTTP/1.1" 200
INFO: 154.92.130.90:64919 - "GET /auth/profile HTTP/1.1" 401
INFO: 154.92.130.90:52891 - "POST /auth/login HTTP/1.1" 200
INFO: 154.92.130.90:5313 - "GET /auth/profile HTTP/1.1" 401
```

### 核心问题

Apifox 作为客户端，每次 HTTP 请求都会使用**随机的临时端口**：

- 第一次：`:20927`
- 第二次：`:58783`
- 第三次：`:23211`
- ...

而 CORS `allow_origins` 需要精确匹配 `协议://IP:端口`，无法枚举所有可能的端口。

---

## ✅ 解决方案

### 使用 `allow_origin_regex` 正则匹配

**修改文件**: `backend/src/service/service.py`

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        # ... 其他固定端口
    ],
    allow_origin_regex=r"http://154\.92\.130\.90:\d+",  # ← 关键：匹配所有端口
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### 正则表达式说明

| 部分 | 说明 |
|------|------|
| `http://` | 协议（必须匹配） |
| `154\.92\.130\.90` | IP 地址（`.` 需要转义为 `\.`） |
| `:` | 端口分隔符 |
| `\d+` | 任意数字端口（1-65535） |

**匹配示例**：

- ✅ `http://154.92.130.90:20927`
- ✅ `http://154.92.130.90:58783`
- ✅ `http://154.92.130.90:3791`
- ❌ `https://154.92.130.90:3791` (协议不匹配)
- ❌ `http://154.92.130.91:3791` (IP 不匹配)

---

## 🎯 适用场景

这个解决方案适用于：

### ✅ 需要使用的情况

1. **API 测试工具**
   - Apifox
   - Postman
   - Insomnia
   - 其他桌面 API 客户端

2. **临时测试环境**
   - 开发者本地测试
   - CI/CD 自动化测试
   - 端口动态分配的容器环境

### ⚠️ 不推荐的情况

1. **生产环境的前端应用**
   - 前端应用通常有固定端口（如 3000, 80, 443）
   - 应该使用 `allow_origins` 明确列出
   - 更安全，防止意外的跨域请求

2. **公网开放的 API**
   - 正则匹配会允许该 IP 的所有端口
   - 可能引入安全风险
   - 应该限制特定端口或使用域名

---

## 🔐 安全考虑

### 当前配置的安全性

```python
allow_origin_regex=r"http://154\.92\.130\.90:\d+"
```

**风险评估**：

- ✅ 限制了特定 IP（`154.92.130.90`）
- ✅ 限制了协议（HTTP）
- ⚠️ 允许了所有端口（`:任意数字`）

**风险等级**: 🟡 中等（仅适用于可信的测试 IP）

### 生产环境建议

```python
# 生产环境：使用域名 + 固定端口
allow_origins=[
    "https://app.yata.com",      # 前端应用
    "https://admin.yata.com",    # 管理后台
]

# 开发/测试环境：可以使用正则
if settings.is_dev():
    allow_origin_regex=r"http://.*:\d+"  # 开发模式允许所有本地请求
```

---

## 📝 相关配置

### 完整的 CORS 配置示例

```python
# backend/src/service/service.py

allowed_origins = [
    # 本地开发
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8080",
    "http://127.0.0.1:8080",
    
    # EC2 生产环境
    "http://166.117.38.176:3000",  # 前端（已加速）
    "http://166.117.38.176:8080",  # 后端（已加速）
    "http://13.213.30.181:3000",   # 前端（原始）
    "http://13.213.30.181:8080",   # 后端（原始）
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=r"http://154\.92\.130\.90:\d+",  # Apifox 测试
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## 🧪 测试验证

### 1. Apifox 测试

**步骤**：

1. 在 Apifox 中发送 `POST /auth/login`
2. 检查响应头是否包含：

   ```
   Access-Control-Allow-Origin: http://154.92.130.90:<随机端口>
   Access-Control-Allow-Credentials: true
   ```

3. 登录后调用 `GET /auth/profile`
4. 应该返回 200 + 用户信息

### 2. 浏览器开发者工具

**检查 CORS 预检请求**：

```
Request:
  Method: OPTIONS
  Origin: http://154.92.130.90:12345

Response:
  Access-Control-Allow-Origin: http://154.92.130.90:12345
  Access-Control-Allow-Methods: GET, POST, PUT, DELETE, OPTIONS
  Access-Control-Allow-Headers: *
  Access-Control-Allow-Credentials: true
```

### 3. 命令行测试

```bash
# 模拟不同端口的请求
for port in 3000 4000 5000 8080; do
  echo "Testing port $port..."
  curl -i -X OPTIONS http://166.117.38.176:8080/auth/login \
    -H "Origin: http://154.92.130.90:$port" \
    -H "Access-Control-Request-Method: POST"
  echo ""
done
```

**预期**：所有端口都应该返回成功的 CORS 响应。

---

## 📚 扩展阅读

### FastAPI CORSMiddleware 文档

- [官方文档](https://fastapi.tiangolo.com/tutorial/cors/)
- [Starlette CORS](https://www.starlette.io/middleware/#corsmiddleware)

### 关键参数

| 参数 | 类型 | 说明 |
|------|------|------|
| `allow_origins` | `List[str]` | 允许的源列表（精确匹配） |
| `allow_origin_regex` | `str` | 允许的源正则表达式 |
| `allow_credentials` | `bool` | 是否允许携带 Cookie |
| `allow_methods` | `List[str]` | 允许的 HTTP 方法 |
| `allow_headers` | `List[str]` | 允许的请求头 |

### 正则表达式示例

```python
# 允许所有 localhost 的任意端口
allow_origin_regex=r"http://localhost:\d+"

# 允许特定域名的所有子域名
allow_origin_regex=r"https://.*\.example\.com"

# 允许 HTTP 和 HTTPS
allow_origin_regex=r"https?://api\.example\.com"

# 允许多个 IP 段
allow_origin_regex=r"http://(192\.168\.1\.\d+|10\.0\.0\.\d+):\d+"
```

---

## ✅ 检查清单

- [x] 添加 `allow_origin_regex` 匹配 Apifox IP
- [x] 测试不同端口的请求
- [x] 验证 Cookie 认证工作正常
- [x] 确认 CORS 预检请求（OPTIONS）成功
- [x] 文档已更新

---

**修复人员**: AI Assistant  
**验证人员**: User  
**状态**: ✅ 已修复并验证
