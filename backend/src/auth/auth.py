"""FastAPI-Users 认证配置"""

from fastapi_users import FastAPIUsers
from fastapi_users.authentication import (
    AuthenticationBackend,
    BearerTransport,
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


# Bearer token 传输方式
bearer_transport = BearerTransport(tokenUrl="auth/jwt/login")

# JWT 认证后端
auth_backend = AuthenticationBackend(
    name="jwt",
    transport=bearer_transport,
    get_strategy=get_jwt_strategy,
)

# FastAPI Users 主实例
fastapi_users = FastAPIUsers[User, str](
    get_user_manager,
    [auth_backend],
)

# 当前活跃用户依赖
current_active_user = fastapi_users.current_user(active=True)

# 当前活跃且已验证的用户依赖
current_verified_user = fastapi_users.current_user(active=True, verified=True)

# 当前超级用户依赖
current_superuser = fastapi_users.current_user(active=True, superuser=True)
