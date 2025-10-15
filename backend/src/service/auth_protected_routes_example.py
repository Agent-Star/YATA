"""
用户认证保护的路由示例

本文件展示如何在 Agent 相关路由中集成用户认证。
这些路由示例使用 JWT token 进行用户身份验证。

使用方式：
1. 用户首先通过 POST /auth/register 注册账号
2. 然后通过 POST /auth/jwt/login 登录获取 JWT token
3. 在调用受保护的路由时，在 Header 中添加: Authorization: Bearer <jwt_token>
"""

from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends

from auth import User, current_active_user
from schema import ChatMessage, UserInput

# 创建受用户认证保护的路由器
protected_router = APIRouter(
    prefix="/protected",
    tags=["protected-agent-routes"],
    dependencies=[],  # 不使用全局 Bearer token 验证
)


@protected_router.post("/invoke")
async def protected_invoke(
    user_input: UserInput,
    current_user: Annotated[User, Depends(current_active_user)],
) -> ChatMessage:
    """
    受用户认证保护的 Agent 调用端点

    该端点要求用户已登录（提供有效的 JWT token）

    Args:
        user_input: 用户输入
        current_user: 当前登录用户（由 JWT token 自动注入）

    Returns:
        Agent 的响应消息

    Raises:
        HTTPException: 如果用户未登录或 token 无效
    """
    # 自动将 user_id 设置为当前登录用户的 ID
    if not user_input.user_id:
        user_input.user_id = str(current_user.id)

    # 这里可以添加额外的用户相关逻辑
    # 例如：检查用户的使用配额、记录用户行为等

    # TODO: 调用实际的 agent 逻辑
    # 这里仅作为示例，返回一个模拟响应
    return ChatMessage(
        type="ai",
        content=f"你好 {current_user.email}! 这是一个受保护的端点。你的消息是: {user_input.message}",
        run_id=str(uuid4()),
    )


@protected_router.get("/my-profile")
async def get_my_profile(
    current_user: Annotated[User, Depends(current_active_user)],
) -> dict:
    """
    获取当前用户的个人信息

    Args:
        current_user: 当前登录用户

    Returns:
        用户信息字典
    """
    return {
        "id": str(current_user.id),
        "email": current_user.email,
        "username": current_user.username,
        "full_name": current_user.full_name,
        "is_active": current_user.is_active,
        "is_verified": current_user.is_verified,
        "total_conversations": current_user.total_conversations,
        "created_at": current_user.created_at.isoformat(),
    }


@protected_router.get("/my-stats")
async def get_my_stats(
    current_user: Annotated[User, Depends(current_active_user)],
) -> dict:
    """
    获取当前用户的使用统计

    Args:
        current_user: 当前登录用户

    Returns:
        用户使用统计
    """
    return {
        "user_id": str(current_user.id),
        "total_conversations": current_user.total_conversations,
        "member_since": current_user.created_at.isoformat(),
        "account_status": "active" if current_user.is_active else "inactive",
    }


# === 可选：混合认证模式 ===
# 以下示例展示如何创建一个可选的用户认证端点
# 用户可以选择登录或不登录使用服务


async def optional_current_user(
    current_user: Annotated[User | None, Depends(current_active_user)] = None,
) -> User | None:
    """
    可选的用户认证依赖

    如果提供了有效的 JWT token，返回用户对象；否则返回 None
    """
    return current_user


@protected_router.post("/optional-auth/invoke")
async def optional_auth_invoke(
    user_input: UserInput,
    current_user: Annotated[User | None, Depends(optional_current_user)] = None,
) -> ChatMessage:
    """
    支持可选用户认证的 Agent 调用端点

    如果用户已登录，将自动关联用户 ID；
    如果用户未登录，仍可使用服务（匿名模式）

    Args:
        user_input: 用户输入
        current_user: 当前用户（可选）

    Returns:
        Agent 的响应消息
    """
    if current_user:
        # 用户已登录
        if not user_input.user_id:
            user_input.user_id = str(current_user.id)
        greeting = f"你好 {current_user.email}!"
    else:
        # 匿名用户
        greeting = "你好，访客!"

    # TODO: 调用实际的 agent 逻辑
    return ChatMessage(
        type="ai",
        content=f"{greeting} 你的消息是: {user_input.message}",
        run_id=str(uuid4()),
    )


# === 集成到主应用 ===
# 在 service.py 中添加以下代码来启用这些受保护的路由：
#
# from service.auth_protected_routes_example import protected_router
# app.include_router(protected_router)
