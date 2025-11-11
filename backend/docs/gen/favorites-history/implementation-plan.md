# 收藏与历史记录删除功能实现规划

## 一、功能概述

本文档规划了 YATA 后端新增的两个核心功能:

1. **收藏功能 (Favorites)**: 允许用户收藏行程规划对话中的消息 (通常是 assistant 的回复), 并支持取消收藏。
2. **历史记录删除功能 (History Deletion)**: 允许用户清空云端保存的聊天历史记录。

这两个功能均需保持与现有代码架构和风格的完全一致。

---

## 二、收藏功能实现规划

### 2.1 功能需求

根据接口文档 `docs/api/接口说明.md`, 收藏功能需要实现以下接口:

1. **POST `/planner/favorites`** - 收藏指定消息
2. **DELETE `/planner/favorites/{messageId}`** - 取消收藏
3. **修改 GET `/planner/history`** - 在响应中添加 `isFavorited` 字段

### 2.2 数据库设计

#### 2.2.1 新增 Favorite 表

在 `src/auth/models.py` 中新增 `Favorite` 数据模型:

```python
from datetime import datetime
from uuid import UUID
from sqlalchemy import DateTime, ForeignKey, Index, String, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column


class Favorite(Base):
    """
    用户收藏记录表

    用于存储用户收藏的消息, 支持快速查询和标记.
    """

    __tablename__ = "favorites"

    # 主键
    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )

    # 用户关联 (外键)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # 消息标识
    message_id: Mapped[str] = mapped_column(
        String(length=100), nullable=False, index=True
    )

    # 消息内容 (冗余存储, 避免从 Thread 中反复查询)
    role: Mapped[str] = mapped_column(
        String(length=20), nullable=False, default="assistant"
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # 消息元数据 (JSON 格式, 可选)
    metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # 收藏时间
    saved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )

    # 复合唯一索引: 防止同一用户重复收藏同一消息
    __table_args__ = (
        Index("ix_favorites_user_message", "user_id", "message_id", unique=True),
    )
```

**设计要点**:

- 使用 UUID 作为主键, 与 `User` 表保持一致
- `user_id` 外键关联到 `users.id`, 级联删除 (用户删除时自动删除收藏)
- `message_id` 存储消息的唯一标识符 (从 LangChain message 中获取)
- `content` 和 `metadata` 冗余存储, 避免从 Thread checkpointer 中反复查询
- 复合唯一索引 `(user_id, message_id)` 确保用户不会重复收藏同一消息

### 2.3 Pydantic Schema 设计

在 `src/schema/schema.py` 或新建 `src/schema/favorites.py` 中定义:

#### 2.3.1 收藏相关 Schema

```python
from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field


class FavoriteCreate(BaseModel):
    """创建收藏请求"""

    messageId: str = Field(description="被收藏消息的唯一 ID")


class FavoriteRead(BaseModel):
    """收藏记录响应"""

    id: str = Field(description="收藏记录 ID")
    messageId: str = Field(description="消息 ID")
    role: str = Field(description="消息角色 (user/assistant)")
    content: str = Field(description="消息内容")
    metadata: dict[str, Any] | None = Field(default=None, description="消息元数据")
    savedAt: str = Field(description="收藏时间 (ISO 8601 UTC)")


class FavoriteResponse(BaseModel):
    """POST /planner/favorites 响应"""

    favorite: FavoriteRead
```

#### 2.3.2 修改 FrontendMessage

在 `src/service/planner_routes.py` 中的 `FrontendMessage` 添加新字段:

```python
class FrontendMessage(BaseModel):
    """前端消息格式"""

    id: str
    role: str | Literal["user", "assistant"]
    content: str
    metadata: dict[str, Any] | None = None
    createdAt: str | None = None
    isFavorited: bool = Field(default=False, description="是否已被当前用户收藏")  # 新增
```

### 2.4 路由实现

在 `src/service/planner_routes.py` 中实现以下路由:

#### 2.4.1 POST `/planner/favorites` - 收藏消息

```python
@planner_router.post("/favorites", response_model=FavoriteResponse, status_code=status.HTTP_200_OK)
async def create_favorite(
    request: FavoriteCreate,
    current_user: Annotated[User, Depends(current_active_user)],
    session: AsyncSession = Depends(get_async_session),
) -> FavoriteResponse:
    """
    收藏指定消息

    从用户的历史记录中查找消息并创建收藏记录.
    若消息不存在或已收藏, 返回相应错误.
    """
    try:
        # 1. 获取用户的主 Thread ID
        thread_id = await get_or_create_main_thread(current_user, session)

        # 2. 从 Thread 历史中查找消息
        agent: AgentGraph = get_agent(DEFAULT_AGENT)
        config = RunnableConfig(configurable={"thread_id": thread_id})
        state = await agent.aget_state(config=config)
        messages: list[AnyMessage] = state.values.get("messages", [])

        # 3. 查找目标消息
        target_message = None
        for msg in messages:
            msg_id = getattr(msg, "id", None) or str(id(msg))
            if msg_id == request.messageId:
                target_message = msg
                break

        if not target_message:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "MESSAGE_NOT_FOUND", "message": "消息不存在"},
            )

        # 4. 检查是否已收藏 (基于唯一索引, 也可以提前查询)
        from sqlalchemy import select
        from auth.models import Favorite

        stmt = select(Favorite).where(
            Favorite.user_id == current_user.id,
            Favorite.message_id == request.messageId,
        )
        existing = await session.execute(stmt)
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": "ALREADY_FAVORITED", "message": "该消息已收藏"},
            )

        # 5. 提取消息内容和元数据
        role = "user" if isinstance(target_message, HumanMessage) else "assistant"
        content = str(target_message.content) if target_message.content else ""
        metadata = getattr(target_message, "response_metadata", None)

        # 6. 创建收藏记录
        from uuid import uuid4
        favorite = Favorite(
            id=uuid4(),
            user_id=current_user.id,
            message_id=request.messageId,
            role=role,
            content=content,
            metadata=metadata,
            saved_at=datetime.now(timezone.utc),
        )

        session.add(favorite)
        await session.commit()
        await session.refresh(favorite)

        # 7. 返回响应
        return FavoriteResponse(
            favorite=FavoriteRead(
                id=str(favorite.id),
                messageId=favorite.message_id,
                role=favorite.role,
                content=favorite.content,
                metadata=favorite.metadata,
                savedAt=favorite.saved_at.isoformat(),
            )
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"创建收藏失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "API_ERROR", "message": "创建收藏失败"},
        )
```

#### 2.4.2 DELETE `/planner/favorites/{messageId}` - 取消收藏

```python
@planner_router.delete("/favorites/{message_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_favorite(
    message_id: str,
    current_user: Annotated[User, Depends(current_active_user)],
    session: AsyncSession = Depends(get_async_session),
) -> None:
    """
    取消收藏指定消息

    幂等操作: 若消息未收藏, 也返回 204.
    """
    try:
        from sqlalchemy import delete
        from auth.models import Favorite

        # 删除收藏记录 (基于 user_id + message_id)
        stmt = delete(Favorite).where(
            Favorite.user_id == current_user.id,
            Favorite.message_id == message_id,
        )

        await session.execute(stmt)
        await session.commit()

        # 无论是否删除了记录, 都返回 204 (幂等)

    except Exception as e:
        logger.error(f"取消收藏失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "API_ERROR", "message": "取消收藏失败"},
        )
```

#### 2.4.3 修改 GET `/planner/history` - 添加 isFavorited 标记

修改现有的 `get_history` 函数, 在返回前查询收藏表并标记:

```python
@planner_router.get("/history", response_model=HistoryResponse)
async def get_history(
    current_user: Annotated[User, Depends(current_active_user)],
    session: AsyncSession = Depends(get_async_session),
) -> HistoryResponse:
    """
    获取用户的历史对话记录

    (修改版: 添加 isFavorited 标记)
    """
    try:
        # 1. 获取用户的主 Thread ID
        thread_id = await get_or_create_main_thread(current_user, session)

        # 2. 获取 Thread 状态
        agent: AgentGraph = get_agent(DEFAULT_AGENT)
        config = RunnableConfig(configurable={"thread_id": thread_id})
        state = await agent.aget_state(config=config)
        messages: list[AnyMessage] = state.values.get("messages", [])

        # 3. 转换为前端格式
        frontend_messages = [langchain_message_to_frontend(msg) for msg in messages]

        # 4. 查询用户的所有收藏记录
        from sqlalchemy import select
        from auth.models import Favorite

        stmt = select(Favorite.message_id).where(Favorite.user_id == current_user.id)
        result = await session.execute(stmt)
        favorited_message_ids = {row[0] for row in result.fetchall()}

        # 5. 标记 isFavorited
        for msg in frontend_messages:
            msg.isFavorited = msg.id in favorited_message_ids

        # 6. 按时间升序排列
        frontend_messages.sort(key=lambda m: m.createdAt if m.createdAt else "")

        return HistoryResponse(messages=frontend_messages)

    except Exception as e:
        logger.error(f"获取历史记录失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "API_ERROR", "message": "获取历史记录失败"},
        )
```

### 2.5 实现要点

1. **消息查找**: 从 LangGraph Thread 状态中查找消息, 需要遍历所有消息并匹配 `message_id`
2. **冗余存储**: 收藏时将消息内容和元数据存储到数据库, 避免后续查询 Thread (提高性能)
3. **唯一约束**: 使用复合唯一索引防止重复收藏, 创建时需要先检查或捕获唯一约束异常
4. **幂等性**: DELETE 操作需要保证幂等 (重复删除不报错)
5. **级联删除**: 用户删除时自动删除所有收藏记录 (外键 `ondelete="CASCADE"`)

---

## 三、历史记录删除功能实现规划

### 3.1 功能需求

根据接口文档, 历史删除功能需要实现:

- **DELETE `/planner/history`** - 删除用户的云端历史记录

### 3.2 实现方案

#### 3.2.1 核心思路

不直接删除 LangGraph checkpointer 中的 Thread 数据 (可能影响数据完整性), 而是采用 **"更换 Thread ID"** 的方式:

1. 为用户创建一个新的 `main_thread_id`
2. 更新 `User.main_thread_id` 字段
3. 旧的 Thread 数据仍保留在 checkpointer 中, 但用户无法访问

这种方式的优点:

- 实现简单, 复用现有的 `thread_manager` 工具
- 安全可靠, 不会误删除数据
- 支持未来可能的"历史恢复"功能

#### 3.2.2 代码实现

在 `src/service/planner_routes.py` 中添加路由:

```python
@planner_router.delete("/history", status_code=status.HTTP_204_NO_CONTENT)
async def delete_history(
    current_user: Annotated[User, Depends(current_active_user)],
    session: AsyncSession = Depends(get_async_session),
) -> None:
    """
    删除用户的历史对话记录

    实现方式: 为用户创建新的主 Thread ID, 旧的历史记录将无法访问.
    幂等操作: 重复调用不会报错.
    """
    try:
        # 调用 thread_manager 创建新 Thread
        new_thread_id = await create_new_thread_for_user(current_user, session)

        logger.info(f"用户 {current_user.id} 的历史记录已清空, 新 Thread ID: {new_thread_id}")

        # 返回 204 无内容

    except Exception as e:
        logger.error(f"删除历史记录失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "API_ERROR", "message": "删除历史记录失败"},
        )
```

### 3.3 实现要点

1. **复用现有工具**: 直接使用 `service/thread_manager.py` 中的 `create_new_thread_for_user` 函数
2. **数据保留**: 旧 Thread 数据不会被物理删除, 便于未来扩展 (如"恢复历史"功能)
3. **幂等性**: 重复调用只会创建新 Thread, 不会报错
4. **日志记录**: 记录操作日志, 便于审计和排查问题

---

## 四、实现步骤与时间估算

### 4.1 收藏功能实现步骤

| 步骤 | 任务 | 预计时间 |
|------|------|----------|
| 1 | 在 `auth/models.py` 中添加 `Favorite` 数据模型 | 20 分钟 |
| 2 | 在 `schema/schema.py` 或新文件中定义 Pydantic Schema | 15 分钟 |
| 3 | 修改 `planner_routes.py` 中的 `FrontendMessage`, 添加 `isFavorited` 字段 | 5 分钟 |
| 4 | 实现 `POST /planner/favorites` 路由 | 40 分钟 |
| 5 | 实现 `DELETE /planner/favorites/{messageId}` 路由 | 20 分钟 |
| 6 | 修改 `GET /planner/history` 路由, 添加收藏标记逻辑 | 30 分钟 |
| 7 | 运行 Pyright 类型检查, 修复类型错误 | 20 分钟 |
| 8 | 测试接口功能 (手动或单元测试) | 30 分钟 |
| **总计** | | **约 3 小时** |

### 4.2 历史删除功能实现步骤

| 步骤 | 任务 | 预计时间 |
|------|------|----------|
| 1 | 实现 `DELETE /planner/history` 路由 | 15 分钟 |
| 2 | 测试接口功能 | 10 分钟 |
| **总计** | | **约 25 分钟** |

### 4.3 总体实现顺序建议

1. **第一阶段**: 实现历史删除功能 (简单, 可先完成)
2. **第二阶段**: 实现收藏功能的数据库模型和 Schema
3. **第三阶段**: 实现收藏功能的路由和业务逻辑
4. **第四阶段**: 运行类型检查和测试, 确保代码质量

---

## 五、代码风格与质量要求

### 5.1 类型标注

- 所有函数参数和返回值必须有完整的类型标注
- 使用 `Annotated[Type, Depends(...)]` 进行依赖注入
- 避免使用 `Any`, 尽量使用具体类型
- 使用 `Type | None` 表示可选类型 (Python 3.10+ 语法)
- **Pyright standard level**: 确保代码通过 `pyright` 检查, 无类型错误

### 5.2 注释规范

- 函数和类必须有 docstring (三引号注释)
- 注释可以是中英文混合, 但必须使用英文标点
- 中文和英文之间用一个空格隔开
- 示例:

  ```python
  def create_favorite(message_id: str) -> Favorite:
      """
      创建收藏记录

      根据 message_id 从历史记录中查找消息并创建收藏.
      若消息不存在, 抛出 HTTPException.
      """
      pass
  ```

### 5.3 错误处理

- 使用 `try-except` 捕获异常
- 区分业务异常 (如"消息不存在") 和系统异常 (如"数据库连接失败")
- 业务异常使用明确的 HTTP 状态码和错误码:

  ```python
  raise HTTPException(
      status_code=status.HTTP_404_NOT_FOUND,
      detail={"code": "MESSAGE_NOT_FOUND", "message": "消息不存在"},
  )
  ```

- 系统异常统一返回 500 和 `API_ERROR` 错误码
- 使用 `logger.error()` 记录异常信息

### 5.4 数据库操作

- 所有数据库操作必须使用异步方法 (`await`)
- 使用 `session.add()` 添加记录, `session.commit()` 提交事务
- 使用 `session.refresh()` 刷新对象 (获取自动生成的字段)
- 使用 SQLAlchemy 2.0 风格的查询 (`select()`, `delete()`)

### 5.5 日志记录

- 使用 `logger = logging.getLogger(__name__)` 创建 logger
- 记录关键操作和错误信息
- 示例:

  ```python
  logger.info(f"用户 {user.id} 收藏了消息 {message_id}")
  logger.error(f"创建收藏失败: {e}")
  ```

---

## 六、测试建议

### 6.1 类型检查

在虚拟环境中运行 Pyright 检查新增代码:

```bash
source .venv/bin/activate  # Linux/Mac
# 或
./.venv/Scripts/activate  # Windows

# 检查特定文件
pyright src/auth/models.py
pyright src/service/planner_routes.py
```

### 6.2 手动测试

使用 `curl` 或 Postman 测试接口:

#### 测试收藏功能

```bash
# 1. 登录获取 Cookie
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"account": "test", "password": "test123"}' \
  -c cookies.txt

# 2. 获取历史记录 (找到一个 messageId)
curl -X GET http://localhost:8000/planner/history \
  -b cookies.txt

# 3. 收藏消息
curl -X POST http://localhost:8000/planner/favorites \
  -H "Content-Type: application/json" \
  -d '{"messageId": "msg-123"}' \
  -b cookies.txt

# 4. 再次获取历史 (验证 isFavorited 字段)
curl -X GET http://localhost:8000/planner/history \
  -b cookies.txt

# 5. 取消收藏
curl -X DELETE http://localhost:8000/planner/favorites/msg-123 \
  -b cookies.txt
```

#### 测试历史删除

```bash
# 删除历史记录
curl -X DELETE http://localhost:8000/planner/history \
  -b cookies.txt

# 验证历史已清空
curl -X GET http://localhost:8000/planner/history \
  -b cookies.txt
```

### 6.3 单元测试建议

在 `tests/` 目录下创建测试文件 (可选):

- `test_favorites.py`: 测试收藏功能的创建、查询、删除
- `test_history_deletion.py`: 测试历史删除功能

---

## 七、注意事项与最佳实践

### 7.1 数据一致性

- **收藏记录的失效问题**: 如果用户删除了历史记录 (清空 Thread), 收藏表中的记录会引用不存在的 `message_id`。
  - **解决方案**: 在 `DELETE /planner/history` 中同时删除用户的所有收藏记录:

    ```python
    from sqlalchemy import delete
    from auth.models import Favorite

    stmt = delete(Favorite).where(Favorite.user_id == current_user.id)
    await session.execute(stmt)
    await session.commit()
    ```

### 7.2 性能优化

- **收藏标记查询优化**: 在 `GET /planner/history` 中使用单次查询获取所有收藏记录, 而不是逐条查询
- **索引优化**: 确保 `favorites` 表的 `(user_id, message_id)` 索引生效, 提高查询速度

### 7.3 扩展性考虑

- **收藏列表接口**: 未来可能需要单独的 `GET /planner/favorites` 接口, 只返回收藏的消息
- **历史恢复功能**: 保留旧 Thread 数据, 便于未来实现"撤销删除"功能
- **多 Thread 支持**: 当前实现为"单 Thread"模式, 未来可扩展为"多对话"模式

---

## 八、完整文件清单

实现完成后, 以下文件会被修改或新增:

| 文件路径 | 修改类型 | 说明 |
|---------|----------|------|
| `src/auth/models.py` | 修改 | 新增 `Favorite` 数据模型 |
| `src/schema/schema.py` | 修改 | 新增收藏相关 Schema (或新建 `favorites.py`) |
| `src/service/planner_routes.py` | 修改 | 新增收藏和历史删除路由, 修改 `FrontendMessage` 和 `get_history` |
| `src/service/thread_manager.py` | 无需修改 | 直接复用 `create_new_thread_for_user` 函数 |

---

## 九、总结

本规划文档详细描述了收藏和历史删除功能的实现方案, 包括:

1. ✅ **数据库设计**: 新增 `Favorite` 表, 复用 `User` 和 Thread 管理机制
2. ✅ **API 设计**: 三个新接口 + 一个修改接口, 遵循 RESTful 风格
3. ✅ **实现细节**: 完整的代码示例和错误处理逻辑
4. ✅ **代码规范**: 类型标注、注释、错误处理、日志记录等要求
5. ✅ **测试方案**: 类型检查、手动测试、单元测试建议

实现时请严格遵循现有代码风格, 确保类型安全和功能完整性。如有疑问, 请参考现有代码 (特别是 `planner_routes.py` 和 `auth/models.py`) 的实现方式。

---

**文档生成时间**: 2025-11-11
**作者**: Claude Code
**版本**: v1.0
