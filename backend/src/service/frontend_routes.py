"""
前端适配路由

提供与前端接口约定一致的路由别名和响应格式.
"""

import logging
from typing import Annotated, Literal, cast

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from fastapi_users.authentication import CookieTransport, Strategy
from pydantic import BaseModel, Field

from auth import User, UserCreate, cookie_auth_backend, current_active_user
from auth.manager import UserManager, get_user_manager

logger = logging.getLogger(__name__)


class FrontendUserResponse(BaseModel):
    """前端用户信息响应格式"""

    id: str
    account: str = Field(description="账号名 (对应后端 username 或 email)")
    displayName: str = Field(description="显示名称 (对应后端 full_name 或 username)")


class FrontendAuthResponse(BaseModel):
    """前端认证响应格式 (注册/登录)"""

    user: FrontendUserResponse
    accessToken: str | None = Field(default=None, description="可选, Cookie 认证时可为 None")


class FrontendLoginRequest(BaseModel):
    """前端登录请求格式"""

    account: str = Field(description="账号名 (邮箱或用户名)")
    password: str


class FrontendProfileResponse(BaseModel):
    """前端用户信息响应格式"""

    user: FrontendUserResponse


class ErrorResponse(BaseModel):
    """错误响应格式"""

    code: str
    message: str


# 创建路由器
frontend_router = APIRouter(prefix="/auth", tags=["frontend-auth"])


def user_to_frontend_format(user: User) -> FrontendUserResponse:
    """将后端 User 模型转换为前端期望的格式"""
    return FrontendUserResponse(
        id=str(user.id),
        account=user.username or user.email,
        displayName=user.full_name or user.username or user.email.split("@")[0],
    )


@frontend_router.post("/register", response_model=FrontendAuthResponse)
async def register(
    user_create: UserCreate,
    user_manager: UserManager = Depends(get_user_manager),
) -> FrontendAuthResponse:
    """
    注册新账号

    前端适配接口, 对应 POST /auth/register
    注册后自动登录并返回用户信息
    """
    try:
        # 创建用户
        user = await user_manager.create(user_create)

        # 转换为前端格式
        return FrontendAuthResponse(
            user=user_to_frontend_format(user),
            accessToken=None,  # Cookie 认证, 无需返回 token
        )
    except Exception as e:
        # 处理常见错误
        error_msg = str(e)
        if "already exists" in error_msg.lower() or "unique" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": "ACCOUNT_EXISTS", "message": "账号已存在"},
            )
        elif "invalid" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "INVALID_PAYLOAD", "message": "参数校验失败"},
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"code": "API_ERROR", "message": "服务器异常"},
            )


@frontend_router.post("/login", response_model=FrontendAuthResponse)
async def login(
    response: Response,
    credentials: FrontendLoginRequest,
    user_manager: UserManager = Depends(get_user_manager),
    strategy: Strategy = Depends(cookie_auth_backend.get_strategy),
) -> FrontendAuthResponse:
    """
    账号登录

    前端适配接口, 对应 POST /auth/login
    登录成功后设置 Cookie 并返回用户信息
    """
    try:
        # 验证用户凭据 (支持 email 或 username)
        user = await user_manager.authenticate(
            OAuth2PasswordRequestForm(username=credentials.account, password=credentials.password)
        )

        if user is None or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"code": "INVALID_CREDENTIALS", "message": "账号或密码错误"},
            )

        # 生成 JWT token
        token = await strategy.write_token(user)

        # 手动设置 Cookie
        cookie_transport = cast(CookieTransport, cookie_auth_backend.transport)
        samesite = cast(Literal["lax", "strict", "none"], cookie_transport.cookie_samesite)
        response.set_cookie(
            key=cookie_transport.cookie_name,
            value=token,
            max_age=cookie_transport.cookie_max_age,
            path=cookie_transport.cookie_path,
            domain=cookie_transport.cookie_domain,
            secure=cookie_transport.cookie_secure,
            httponly=cookie_transport.cookie_httponly,
            samesite=samesite,
        )

        # 返回前端期望的格式
        return FrontendAuthResponse(
            user=user_to_frontend_format(user),
            accessToken=None,  # Cookie 认证, token 已在 Cookie 中
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"登录失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "API_ERROR", "message": f"服务器异常: {str(e)}"},
        )


@frontend_router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(
    response: Response,
    current_user: Annotated[User, Depends(current_active_user)],
) -> dict:
    """
    注销登录

    前端适配接口, 对应 POST /auth/logout
    清除 Cookie 会话
    """
    # 清除 Cookie
    cookie_transport = cast(CookieTransport, cookie_auth_backend.transport)
    response.delete_cookie(
        key=cookie_transport.cookie_name,
        path=cookie_transport.cookie_path,
        domain=cookie_transport.cookie_domain,
    )
    return {}


@frontend_router.get("/profile", response_model=FrontendProfileResponse)
async def get_profile(
    current_user: Annotated[User, Depends(current_active_user)],
) -> FrontendProfileResponse:
    """
    获取当前登录用户信息

    前端适配接口, 对应 GET /auth/profile
    """
    return FrontendProfileResponse(user=user_to_frontend_format(current_user))
