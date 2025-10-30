"""FastAPI-Users 认证配置"""

from fastapi_users import FastAPIUsers
from fastapi_users.authentication import (
    AuthenticationBackend,
    BearerTransport,
    CookieTransport,
    JWTStrategy,
)

from auth.manager import get_user_manager
from auth.models import User
from core.settings import settings


def get_jwt_strategy() -> JWTStrategy:
    """
    获取 JWT 认证策略

    Returns:
        配置好的 JWT 策略实例
    """
    return JWTStrategy(
        secret=settings.AUTH_JWT_SECRET.get_secret_value(),
        lifetime_seconds=settings.AUTH_JWT_LIFETIME_SECONDS,
        token_audience=["fastapi-users:auth"],
        algorithm="HS256",
    )


# Cookie 传输方式 (主要认证方式)
cookie_transport = CookieTransport(
    cookie_name="yata_auth",
    cookie_max_age=settings.AUTH_JWT_LIFETIME_SECONDS,
    cookie_path="/",
    cookie_domain=None,
    cookie_secure=False,  # 开发/生产都使用 HTTP 时设为 False
    cookie_httponly=True,
    cookie_samesite="lax",  # 已经开启前端代理, 使用 'lax'
)

# Bearer token 传输方式 (向后兼容, 用于 API 客户端)
bearer_transport = BearerTransport(tokenUrl="auth/jwt/login")

# Cookie 认证后端 (优先使用)
cookie_auth_backend = AuthenticationBackend(
    name="cookie",
    transport=cookie_transport,
    get_strategy=get_jwt_strategy,
)

# JWT Bearer 认证后端 (向后兼容)
bearer_auth_backend = AuthenticationBackend(
    name="jwt",
    transport=bearer_transport,
    get_strategy=get_jwt_strategy,
)

# FastAPI Users 主实例 (支持 Cookie 和 Bearer 两种认证方式)
# Note: User uses UUID as ID type internally, but FastAPI-Users serializes it as str in API
fastapi_users: FastAPIUsers[User, str] = FastAPIUsers(  # type: ignore[arg-type]
    get_user_manager,
    [cookie_auth_backend, bearer_auth_backend],
)

# 当前活跃用户依赖
current_active_user = fastapi_users.current_user(active=True)

# 当前活跃且已验证的用户依赖
current_verified_user = fastapi_users.current_user(active=True, verified=True)

# 当前超级用户依赖
current_superuser = fastapi_users.current_user(active=True, superuser=True)
