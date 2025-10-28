# IMP-003: 生产环境配置管理

## 元数据

- **ID**: IMP-003
- **分类**: 部署
- **优先级**: 🔴 高
- **状态**: 待处理
- **创建日期**: 2025-01-27
- **预计工作量**: 小
- **相关文档**: `compliance-check.md`, `phase1-implementation-summary.md`

---

## 问题描述

### 当前实现

#### 1. CORS 配置硬编码

**文件**: `backend/src/service/service.py`

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],  # ❌ 硬编码
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

#### 2. Cookie Secure 配置基于 MODE

**文件**: `backend/src/auth/auth.py`

```python
cookie_transport = CookieTransport(
    cookie_name="yata_auth",
    cookie_secure=not settings.is_dev(),  # ✅ 基于环境判断，但不够灵活
    # ...
)
```

### 不足之处

1. **部署风险**：
   - ❌ 生产环境直接部署会使用开发环境的 CORS 配置
   - ❌ 任何域名都无法正常访问（除非是 localhost:3000/5173）

2. **安全隐患**：
   - ⚠️ 如果忘记修改代码，生产环境无法正常工作
   - ⚠️ 可能导致开发者临时使用 `allow_origins=["*"]`（极不安全）

3. **配置分散**：
   - 部署相关配置散落在代码中
   - 缺少统一的生产环境配置清单

---

## 影响分析

### 功能影响

- 🔴 **阻塞部署**：生产环境无法正常访问 API
- 🔴 **CORS 错误**：前端请求被浏览器拦截

### 安全影响

- 🔴 **配置错误风险**：可能误用不安全的配置
- ⚠️ **Cookie 安全**：`cookie_secure` 配置不够灵活

### 用户体验影响

- 🔴 **服务不可用**：如果配置错误，用户无法访问应用

### 开发维护影响

- ⚠️ **部署复杂**：需要修改代码才能部署
- ⚠️ **容易出错**：硬编码配置容易遗漏

---

## 改进方案

### 方案 1: 环境变量配置（推荐）

**优势**：

- ✅ 灵活性高，支持多环境部署
- ✅ 遵循 12-Factor App 原则
- ✅ 不需要修改代码

**实施步骤**：

#### 1. 扩展 Settings 配置

**文件**: `backend/src/core/settings.py`

```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # ... 现有配置 ...
    
    # === 部署配置 ===
    
    # CORS 配置
    CORS_ORIGINS: list[str] = Field(
        default=["http://localhost:3000", "http://localhost:5173"],
        description="允许的跨域源，多个用逗号分隔"
    )
    
    # Cookie 安全配置
    COOKIE_SECURE: bool | None = Field(
        default=None,
        description="Cookie Secure 标志，None 时根据 MODE 自动判断"
    )
    
    COOKIE_SAMESITE: str = Field(
        default="lax",
        description="Cookie SameSite 策略: lax, strict, none"
    )
    
    # 其他部署配置
    TRUSTED_HOSTS: list[str] = Field(
        default=["*"],
        description="允许的 Host 头，生产环境应明确指定"
    )

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        """支持从字符串解析 CORS origins"""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v
    
    def get_cookie_secure(self) -> bool:
        """获取 Cookie Secure 配置"""
        if self.COOKIE_SECURE is not None:
            return self.COOKIE_SECURE
        # 默认：生产环境启用，开发环境禁用
        return not self.is_dev()
```

#### 2. 更新 CORS 配置

**文件**: `backend/src/service/service.py`

```python
# 使用环境变量配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,  # ✅ 从配置读取
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

#### 3. 更新 Cookie 配置

**文件**: `backend/src/auth/auth.py`

```python
cookie_transport = CookieTransport(
    cookie_name="yata_auth",
    cookie_max_age=settings.AUTH_JWT_LIFETIME_SECONDS,
    cookie_path="/",
    cookie_domain=None,
    cookie_secure=settings.get_cookie_secure(),  # ✅ 使用方法获取
    cookie_httponly=True,
    cookie_samesite=settings.COOKIE_SAMESITE,  # ✅ 可配置
)
```

#### 4. 更新环境变量文件

**文件**: `backend/env.example`

```bash
# ==============================================
# 部署配置
# ==============================================

# 运行模式
MODE=dev  # dev, production

# CORS 允许的前端源（多个用逗号分隔）
# 开发环境
CORS_ORIGINS=http://localhost:3000,http://localhost:5173
# 生产环境示例
# CORS_ORIGINS=https://your-frontend-domain.com,https://www.your-frontend-domain.com

# Cookie 安全配置
# COOKIE_SECURE=true  # 强制启用 HTTPS（生产环境推荐）
# COOKIE_SAMESITE=lax  # lax (推荐), strict, none

# 受信任的 Host（生产环境应明确指定）
# TRUSTED_HOSTS=your-backend-domain.com,api.your-domain.com
```

---

### 方案 2: 配置文件管理

**优势**：

- ✅ 可以管理更复杂的配置
- ✅ 支持配置继承和覆盖

**劣势**：

- ❌ 增加部署复杂度
- ❌ 需要额外的配置加载逻辑

**不推荐**，环境变量足够满足需求。

---

## 实施建议

### 推荐方案

**方案 1 (环境变量配置)** - 简单高效

### 实施步骤

1. **修改配置类** (`settings.py`)
   - 添加 `CORS_ORIGINS`, `COOKIE_SECURE`, `COOKIE_SAMESITE` 等字段
   - 添加字段验证器和辅助方法
   - 预计工作量：30 分钟

2. **更新使用处** (`service.py`, `auth.py`)
   - 替换硬编码为配置读取
   - 预计工作量：15 分钟

3. **更新文档** (`env.example`, `README.md`)
   - 添加新的环境变量说明
   - 提供生产环境配置示例
   - 预计工作量：15 分钟

4. **测试验证**
   - 本地测试不同配置
   - 预计工作量：30 分钟

**总计**：约 1.5 小时

### 部署检查清单

创建部署检查清单文档：

**文件**: `backend/docs/deployment-checklist.md`

```markdown
# 生产环境部署检查清单

## 环境变量配置

- [ ] `MODE=production`
- [ ] `CORS_ORIGINS` 设置为实际的前端域名
- [ ] `AUTH_JWT_SECRET` 使用强随机密钥
- [ ] `DATABASE_TYPE` 设置为 `postgres`（推荐）
- [ ] 数据库连接信息正确配置
- [ ] LLM API Keys 正确配置

## 安全配置

- [ ] `COOKIE_SECURE=true`（如果使用 HTTPS）
- [ ] `COOKIE_SAMESITE=lax` 或 `strict`
- [ ] 数据库密码使用强密码
- [ ] API 密钥安全存储（不要提交到 Git）

## 服务配置

- [ ] 配置反向代理（Nginx/Caddy）
- [ ] 启用 HTTPS
- [ ] 配置防火墙规则
- [ ] 设置日志记录

## 验证测试

- [ ] 前端可以正常访问 API
- [ ] 用户注册/登录功能正常
- [ ] CORS 配置正确（无跨域错误）
- [ ] Cookie 正常设置和发送
```

### 注意事项

1. **向后兼容**：保持默认值与当前行为一致
2. **文档更新**：确保所有文档反映新的配置方式
3. **测试覆盖**：测试不同的环境变量组合

### 回滚方案

如果新配置出现问题，可以快速回退到硬编码版本（保留一个备份分支）。

---

## 配置示例

### 开发环境 (.env.dev)

```bash
MODE=dev
CORS_ORIGINS=http://localhost:3000,http://localhost:5173,http://127.0.0.1:3000
COOKIE_SECURE=false
DATABASE_TYPE=sqlite
SQLITE_DB_PATH=./checkpoints.db
```

### 生产环境 (.env.prod)

```bash
MODE=production

# CORS 配置（仅允许实际的前端域名）
CORS_ORIGINS=https://yata.example.com

# Cookie 安全配置
COOKIE_SECURE=true
COOKIE_SAMESITE=lax

# 数据库配置
DATABASE_TYPE=postgres
POSTGRES_HOST=db.example.com
POSTGRES_PORT=5432
POSTGRES_DB=yata_prod
POSTGRES_USER=yata_user
POSTGRES_PASSWORD=<strong-password>

# JWT 配置
AUTH_JWT_SECRET=<strong-random-secret-key>
AUTH_JWT_LIFETIME_SECONDS=604800

# LLM 配置
DEFAULT_MODEL=gpt-4o
OPENAI_API_KEY=sk-xxx
```

### Staging 环境 (.env.staging)

```bash
MODE=production

# CORS 配置
CORS_ORIGINS=https://staging.yata.example.com

# Cookie 安全配置
COOKIE_SECURE=true
COOKIE_SAMESITE=lax

# 数据库配置（使用独立的 staging 数据库）
DATABASE_TYPE=postgres
POSTGRES_HOST=db-staging.example.com
POSTGRES_PORT=5432
POSTGRES_DB=yata_staging
POSTGRES_USER=yata_staging_user
POSTGRES_PASSWORD=<staging-password>

# JWT 配置
AUTH_JWT_SECRET=<staging-secret-key>
```

---

## 测试计划

### 单元测试

```python
def test_cors_origins_from_string():
    """测试从字符串解析 CORS origins"""
    os.environ["CORS_ORIGINS"] = "http://a.com,http://b.com"
    settings = Settings()
    assert len(settings.CORS_ORIGINS) == 2
    assert "http://a.com" in settings.CORS_ORIGINS


def test_cookie_secure_auto_detection():
    """测试 Cookie Secure 自动检测"""
    # 开发环境
    os.environ["MODE"] = "dev"
    os.environ.pop("COOKIE_SECURE", None)
    settings = Settings()
    assert settings.get_cookie_secure() == False
    
    # 生产环境
    os.environ["MODE"] = "production"
    settings = Settings()
    assert settings.get_cookie_secure() == True
    
    # 显式配置
    os.environ["COOKIE_SECURE"] = "false"
    settings = Settings()
    assert settings.get_cookie_secure() == False
```

### 集成测试

```bash
# 1. 设置生产环境配置
export MODE=production
export CORS_ORIGINS=https://example.com

# 2. 启动服务
uvicorn src.run_service:app

# 3. 验证 CORS
curl -H "Origin: https://example.com" \
     -H "Access-Control-Request-Method: POST" \
     -X OPTIONS \
     http://localhost:8080/auth/login

# 期望：返回 Access-Control-Allow-Origin: https://example.com

# 4. 验证非法域名被拒绝
curl -H "Origin: https://evil.com" \
     -H "Access-Control-Request-Method: POST" \
     -X OPTIONS \
     http://localhost:8080/auth/login

# 期望：无 Access-Control-Allow-Origin 头
```

---

## 相关资源

- [12-Factor App: Config](https://12factor.net/config)
- [FastAPI CORS Configuration](https://fastapi.tiangolo.com/tutorial/cors/)
- [Pydantic Settings Management](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
- [MDN: Cookie Security](https://developer.mozilla.org/en-US/docs/Web/HTTP/Cookies)

---

## 更新日志

- 2025-01-27: 创建文档，提供环境变量配置方案
