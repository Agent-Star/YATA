# CORS 配置指南

**版本**: 2.0 (优化版)  
**日期**: 2025-01-27  
**原则**: 开发开放，生产严格

---

## 🎯 设计理念

### 核心原则

1. **开发模式**（`MODE=dev`）
   - ✅ **完全开放 CORS**
   - ✅ 允许任意 IP、端口、协议
   - ✅ 方便本地开发、API 测试、跨域调试
   - ⚠️ 仅用于开发/测试环境

2. **生产模式**（`MODE=production`）
   - ✅ **严格限制 CORS**
   - ✅ 只允许白名单中的来源
   - ✅ 保证生产环境安全
   - ✅ 防止未授权的跨域访问

---

## 📋 当前实现

### 配置代码

**文件**: `backend/src/service/service.py`

```python
# === CORS 中间件配置 ===

if settings.is_dev():
    # 开发模式：完全开放 CORS
    logger.info("开发模式：CORS 已完全开放（允许所有来源）")
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r".*",  # 匹配所有来源
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    # 生产模式：严格限制 CORS
    allowed_origins = [
        "http://166.117.38.176:3000",  # EC2 前端（已加速）
        "http://166.117.38.176:8080",  # EC2 后端（已加速）
        "http://13.213.30.181:3000",   # EC2 前端（原始）
        "http://13.213.30.181:8080",   # EC2 后端（原始）
        # "https://yata.example.com",  # 生产域名（如有）
    ]
    
    logger.info(f"生产模式：CORS 仅允许以下来源: {allowed_origins}")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
```

---

## 🔍 两种模式对比

### 开发模式（`MODE=dev`）

**配置**:

```python
allow_origin_regex=r".*"  # 匹配所有来源
allow_credentials=True
```

**允许的来源**（示例）:

- ✅ `http://localhost:3000`
- ✅ `http://127.0.0.1:8080`
- ✅ `http://192.168.1.100:4000`
- ✅ `http://154.92.130.90:20927` (Apifox 随机端口)
- ✅ `https://any-domain.com:any-port`
- ✅ **任意 IP、端口、协议**

**适用场景**:

- 本地前后端分离开发
- Postman/Apifox API 测试
- 跨域调试
- CI/CD 自动化测试
- 移动设备本地测试

**日志输出**:

```
INFO: [service.service] 开发模式：CORS 已完全开放（允许所有来源）
```

---

### 生产模式（`MODE=production`）

**配置**:

```python
allow_origins=[
    "http://166.117.38.176:3000",
    "http://13.213.30.181:3000",
    # ... 白名单
]
allow_credentials=True
```

**允许的来源**（示例）:

- ✅ `http://166.117.38.176:3000` (白名单中)
- ✅ `http://13.213.30.181:8080` (白名单中)
- ❌ `http://localhost:3000` (不在白名单)
- ❌ `http://154.92.130.90:20927` (不在白名单)
- ❌ `http://evil.com` (不在白名单)
- ❌ **任何未在白名单中的来源**

**适用场景**:

- 正式上线的生产环境
- 公网开放的 API 服务
- 需要严格安全控制的场景

**日志输出**:

```
INFO: [service.service] 生产模式：CORS 仅允许以下来源: ['http://166.117.38.176:3000', ...]
```

---

## 🚀 使用指南

### 本地开发

**`.env` 配置**:

```bash
MODE=dev
HOST=0.0.0.0
PORT=8080
```

**效果**:

- 任意来源可以访问 API ✅
- 支持 Cookie 认证 ✅
- Apifox/Postman 测试无障碍 ✅

**启动**:

```bash
python src/run_service.py
```

**日志验证**:

```
INFO: 开发模式：CORS 已完全开放（允许所有来源）
INFO: Uvicorn running on http://0.0.0.0:8080
```

---

### 生产部署

**`.env` 配置**:

```bash
MODE=production
HOST=0.0.0.0
PORT=8080
```

**更新白名单**（`service.py`）:

```python
allowed_origins = [
    "https://app.yata.com",      # 生产前端（HTTPS）
    "https://admin.yata.com",    # 管理后台
    # 添加所有需要访问的前端地址
]
```

**效果**:

- 只有白名单中的来源可以访问 ✅
- 未授权来源被拒绝 ✅
- 生产环境安全 ✅

**日志验证**:

```
INFO: 生产模式：CORS 仅允许以下来源: ['https://app.yata.com', ...]
```

---

## 🛡️ 安全考虑

### 开发模式的风险

**⚠️ 警告**: 开发模式会完全开放 CORS！

**风险**:

1. 任何网站都可以向你的后端发起请求
2. 如果后端暴露在公网，可能被恶意利用
3. CSRF 攻击风险增加

**缓解措施**:

1. ✅ **仅在开发环境使用** `MODE=dev`
2. ✅ **生产环境必须使用** `MODE=production`
3. ✅ 开发环境使用防火墙限制访问（如仅允许内网）
4. ✅ 不要在开发模式下处理敏感数据
5. ✅ 使用 `AUTH_SECRET` 保护关键接口

### 生产模式的最佳实践

**✅ 推荐配置**:

```python
# 1. 使用 HTTPS
allowed_origins = [
    "https://app.yata.com",  # ✅ HTTPS
]

# 2. 指定具体端口
allowed_origins = [
    "https://app.yata.com:443",  # ✅ 明确端口
]

# 3. 不要使用通配符
allowed_origins = [
    "https://app.yata.com",  # ✅ 明确域名
    # "https://*.yata.com",  # ❌ 通配符不被支持
]

# 4. 限制 IP 白名单
allowed_origins = [
    "http://166.117.38.176:3000",  # ✅ 特定 IP
]
```

---

## 🧪 测试验证

### 1. 验证当前模式

**检查启动日志**:

```bash
# 开发模式
INFO: 开发模式：CORS 已完全开放（允许所有来源）

# 生产模式
INFO: 生产模式：CORS 仅允许以下来源: [...]
```

**或运行测试脚本**:

```python
from core.settings import settings

if settings.is_dev():
    print("✅ 当前为开发模式")
else:
    print("⚠️ 当前为生产模式")
```

---

### 2. 测试 CORS 预检请求

**开发模式测试**:

```bash
# 测试任意来源
curl -i -X OPTIONS http://localhost:8080/auth/login \
  -H "Origin: http://random-domain.com:12345" \
  -H "Access-Control-Request-Method: POST"

# 预期：返回 200，允许该来源
```

**生产模式测试**:

```bash
# 测试白名单来源
curl -i -X OPTIONS http://production-server:8080/auth/login \
  -H "Origin: http://166.117.38.176:3000" \
  -H "Access-Control-Request-Method: POST"

# 预期：返回 200，允许该来源

# 测试非白名单来源
curl -i -X OPTIONS http://production-server:8080/auth/login \
  -H "Origin: http://evil.com" \
  -H "Access-Control-Request-Method: POST"

# 预期：返回 400 或 403，拒绝该来源
```

---

### 3. 浏览器开发者工具

**开发模式**:

```
Request Headers:
  Origin: http://localhost:3000

Response Headers:
  Access-Control-Allow-Origin: http://localhost:3000
  Access-Control-Allow-Credentials: true
  ✅ 允许所有来源
```

**生产模式（白名单）**:

```
Request Headers:
  Origin: http://166.117.38.176:3000

Response Headers:
  Access-Control-Allow-Origin: http://166.117.38.176:3000
  Access-Control-Allow-Credentials: true
  ✅ 仅允许白名单来源
```

**生产模式（非白名单）**:

```
Request Headers:
  Origin: http://evil.com

Response:
  ❌ CORS error: Origin not allowed
```

---

## 📝 配置检查清单

### 开发环境

- [ ] `.env` 中 `MODE=dev`
- [ ] 启动日志显示 "开发模式：CORS 已完全开放"
- [ ] 本地前端可以正常访问
- [ ] Apifox/Postman 测试正常
- [ ] Cookie 认证工作正常

### 生产环境

- [ ] `.env` 中 `MODE=production`
- [ ] 启动日志显示 "生产模式：CORS 仅允许以下来源"
- [ ] `allowed_origins` 已更新为生产地址
- [ ] 使用 HTTPS（推荐）
- [ ] Cookie `Secure` 属性已启用（HTTPS）
- [ ] 测试白名单来源可以访问
- [ ] 测试非白名单来源被拒绝

---

## 🔄 迁移指南

### 从旧配置迁移

**旧配置**（硬编码多个来源）:

```python
allowed_origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://154.92.130.90:3791",  # Apifox
    # ... 很多测试地址
]
allow_origin_regex=r"http://154\.92\.130\.90:\d+"
```

**新配置**（按环境分离）:

```python
if settings.is_dev():
    allow_origin_regex=r".*"  # 开发：允许所有
else:
    allowed_origins=[...]  # 生产：仅白名单
```

**优点**:

1. ✅ 配置更简洁
2. ✅ 开发更方便（无需手动添加测试地址）
3. ✅ 生产更安全（严格白名单）
4. ✅ 环境隔离清晰

---

## 📚 参考资源

- [FastAPI CORS 文档](https://fastapi.tiangolo.com/tutorial/cors/)
- [MDN CORS 指南](https://developer.mozilla.org/en-US/docs/Web/HTTP/CORS)
- [Starlette CORSMiddleware](https://www.starlette.io/middleware/#corsmiddleware)

---

## 🎉 总结

### 关键优势

| 方面 | 开发模式 | 生产模式 |
|------|---------|---------|
| **灵活性** | 🟢 极高（任意来源） | 🟡 受限（仅白名单） |
| **安全性** | 🔴 低（完全开放） | 🟢 高（严格限制） |
| **测试便利** | 🟢 极好（无需配置） | 🟡 需要维护白名单 |
| **生产就绪** | 🔴 否 | 🟢 是 |

### 最佳实践

1. **开发阶段**: 使用 `MODE=dev`，专注功能开发
2. **测试阶段**: 使用 `MODE=dev`，方便各种测试工具
3. **预发布**: 切换到 `MODE=production`，验证白名单
4. **生产上线**: 确保 `MODE=production` + HTTPS + 白名单

---

**文档版本**: 2.0  
**维护状态**: ✅ 活跃维护  
**最后更新**: 2025-01-27
