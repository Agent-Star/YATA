"""认证测试的共享 fixtures"""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def test_user_data():
    """测试用户数据"""
    return {
        "email": "testuser@example.com",
        "password": "SecurePassword123!",
        "username": "testuser",
        "full_name": "Test User",
    }


@pytest.fixture
async def registered_user(test_client: TestClient, test_user_data):
    """创建并返回已注册的测试用户"""
    response = test_client.post("/auth/register", json=test_user_data)

    if response.status_code in [200, 201]:
        return test_user_data
    return None


@pytest.fixture
async def authenticated_user(test_client: TestClient, registered_user):
    """创建并返回已认证的测试用户（包含 token）"""
    if not registered_user:
        return None

    login_response = test_client.post(
        "/auth/jwt/login",
        data={
            "username": registered_user["email"],
            "password": registered_user["password"],
        },
    )

    if login_response.status_code == 200:
        token = login_response.json()["access_token"]
        return {
            **registered_user,
            "access_token": token,
            "token_type": "bearer",
        }
    return None
