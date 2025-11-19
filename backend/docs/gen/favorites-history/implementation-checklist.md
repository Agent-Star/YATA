# 收藏与历史删除功能实现检查清单

快速参考文档, 用于实现过程中的进度跟踪和质量检查。

---

## 一、收藏功能实现检查清单

### ✅ 步骤 1: 数据库模型 (`src/auth/models.py`)

- [ ] 导入必要的模块: `ForeignKey`, `Index`, `Text`, `JSON`
- [ ] 创建 `Favorite` 类, 继承 `Base`
- [ ] 定义字段:
  - [ ] `id: Mapped[UUID]` (主键)
  - [ ] `user_id: Mapped[UUID]` (外键, `ondelete="CASCADE"`)
  - [ ] `message_id: Mapped[str]` (String 100)
  - [ ] `role: Mapped[str]` (String 20, default="assistant")
  - [ ] `content: Mapped[str]` (Text)
  - [ ] `metadata: Mapped[dict | None]` (JSON, nullable)
  - [ ] `saved_at: Mapped[datetime]` (DateTime, default=utcnow)
- [ ] 添加复合唯一索引: `Index("ix_favorites_user_message", "user_id", "message_id", unique=True)`
- [ ] 添加 docstring 注释

### ✅ 步骤 2: Pydantic Schema (`src/schema/schema.py`)

- [ ] 创建 `FavoriteCreate` (请求):
  - [ ] `messageId: str`
- [ ] 创建 `FavoriteRead` (响应):
  - [ ] `id: str`
  - [ ] `messageId: str`
  - [ ] `role: str`
  - [ ] `content: str`
  - [ ] `metadata: dict[str, Any] | None`
  - [ ] `savedAt: str`
- [ ] 创建 `FavoriteResponse`:
  - [ ] `favorite: FavoriteRead`

### ✅ 步骤 3: 修改 FrontendMessage (`src/service/planner_routes.py`)

- [ ] 添加字段: `isFavorited: bool = Field(default=False, description="是否已被当前用户收藏")`

### ✅ 步骤 4: POST /planner/favorites (`src/service/planner_routes.py`)

- [ ] 导入: `from auth.models import Favorite`
- [ ] 导入: `from uuid import uuid4`
- [ ] 创建路由函数 `create_favorite`:
  - [ ] 参数: `request: FavoriteCreate`, `current_user`, `session`
  - [ ] 返回类型: `FavoriteResponse`
  - [ ] 状态码: `status.HTTP_200_OK`
- [ ] 实现逻辑:
  1. [ ] 获取用户的 `main_thread_id`
  2. [ ] 从 Thread 状态中获取消息列表
  3. [ ] 遍历查找目标消息 (匹配 `message_id`)
  4. [ ] 若不存在, 抛出 404 错误 (`MESSAGE_NOT_FOUND`)
  5. [ ] 查询数据库检查是否已收藏
  6. [ ] 若已收藏, 抛出 409 错误 (`ALREADY_FAVORITED`)
  7. [ ] 提取消息的 `role`, `content`, `metadata`
  8. [ ] 创建 `Favorite` 对象
  9. [ ] `session.add()`, `await session.commit()`, `await session.refresh()`
  10. [ ] 返回 `FavoriteResponse`
- [ ] 异常处理: `try-except`, 捕获并返回 500 错误

### ✅ 步骤 5: DELETE /planner/favorites/{message_id} (`src/service/planner_routes.py`)

- [ ] 导入: `from sqlalchemy import delete`
- [ ] 创建路由函数 `delete_favorite`:
  - [ ] 参数: `message_id: str`, `current_user`, `session`
  - [ ] 返回类型: `None`
  - [ ] 状态码: `status.HTTP_204_NO_CONTENT`
- [ ] 实现逻辑:
  1. [ ] 构建 delete 语句: `delete(Favorite).where(...)`
  2. [ ] 执行: `await session.execute(stmt)`
  3. [ ] 提交: `await session.commit()`
  4. [ ] 无需检查删除结果 (幂等)
- [ ] 异常处理: 捕获并返回 500 错误

### ✅ 步骤 6: 修改 GET /planner/history (`src/service/planner_routes.py`)

- [ ] 在获取消息列表后, 添加收藏标记逻辑:
  1. [ ] 查询用户的所有收藏: `select(Favorite.message_id).where(Favorite.user_id == ...)`
  2. [ ] 提取为 set: `favorited_message_ids = {row[0] for row in result.fetchall()}`
  3. [ ] 遍历 `frontend_messages`, 设置 `msg.isFavorited = msg.id in favorited_message_ids`
- [ ] 确保返回的 `FrontendMessage` 包含 `isFavorited` 字段

---

## 二、历史删除功能实现检查清单

### ✅ 步骤 1: DELETE /planner/history (`src/service/planner_routes.py`)

- [ ] 导入: `from service.thread_manager import create_new_thread_for_user`
- [ ] 导入: `from sqlalchemy import delete` (用于删除收藏)
- [ ] 导入: `from auth.models import Favorite`
- [ ] 创建路由函数 `delete_history`:
  - [ ] 参数: `current_user`, `session`
  - [ ] 返回类型: `None`
  - [ ] 状态码: `status.HTTP_204_NO_CONTENT`
- [ ] 实现逻辑:
  1. [ ] 删除用户的所有收藏记录:

     ```python
     stmt = delete(Favorite).where(Favorite.user_id == current_user.id)
     await session.execute(stmt)
     await session.commit()
     ```

  2. [ ] 创建新 Thread: `new_thread_id = await create_new_thread_for_user(current_user, session)`
  3. [ ] 记录日志: `logger.info(f"用户 {current_user.id} 的历史记录已清空")`
- [ ] 异常处理: 捕获并返回 500 错误

---

## 三、代码质量检查清单

### ✅ 类型标注

- [ ] 所有函数参数有类型标注
- [ ] 所有函数返回值有类型标注
- [ ] 使用 `Annotated[User, Depends(...)]` 进行依赖注入
- [ ] 避免使用 `Any`, 使用具体类型
- [ ] 使用 `Type | None` 表示可选类型

### ✅ 注释规范

- [ ] 所有函数有 docstring
- [ ] 注释使用英文标点
- [ ] 中文和英文之间有空格
- [ ] 关键逻辑有行内注释

### ✅ 错误处理

- [ ] 使用 `try-except` 捕获异常
- [ ] 业务异常使用明确的 HTTP 状态码和错误码
- [ ] 系统异常统一返回 500 和 `API_ERROR`
- [ ] 使用 `logger.error()` 记录错误

### ✅ 数据库操作

- [ ] 所有操作使用 `await`
- [ ] 使用 SQLAlchemy 2.0 风格查询
- [ ] 事务处理: `session.add()` → `session.commit()` → `session.refresh()`

### ✅ 日志记录

- [ ] 关键操作记录 `logger.info()`
- [ ] 错误信息记录 `logger.error()`

---

## 四、测试检查清单

### ✅ 类型检查 (Pyright)

```bash
# 激活虚拟环境
source .venv/bin/activate  # Linux/Mac
# 或
./.venv/Scripts/activate  # Windows

# 检查修改的文件
pyright src/auth/models.py
pyright src/service/planner_routes.py
pyright src/schema/schema.py
```

- [ ] `auth/models.py`: 无类型错误
- [ ] `service/planner_routes.py`: 无类型错误
- [ ] `schema/schema.py`: 无类型错误

### ✅ 手动测试

#### 收藏功能测试

- [ ] 登录获取 Cookie
- [ ] 调用 `GET /planner/history` 获取 `messageId`
- [ ] 调用 `POST /planner/favorites` 收藏消息
  - [ ] 响应 200, 返回 `favorite` 对象
  - [ ] `favorite.messageId` 与请求一致
- [ ] 再次调用 `GET /planner/history`, 验证 `isFavorited=true`
- [ ] 重复收藏同一消息, 验证返回 409 错误
- [ ] 调用 `DELETE /planner/favorites/{messageId}` 取消收藏
  - [ ] 响应 204
- [ ] 再次调用 `GET /planner/history`, 验证 `isFavorited=false`
- [ ] 重复取消收藏, 验证仍返回 204 (幂等)

#### 历史删除功能测试

- [ ] 调用 `GET /planner/history`, 确认有历史记录
- [ ] 调用 `DELETE /planner/history`, 响应 204
- [ ] 再次调用 `GET /planner/history`, 验证返回空数组
- [ ] 重复调用 `DELETE /planner/history`, 验证仍返回 204 (幂等)

#### 数据一致性测试

- [ ] 收藏消息后, 调用 `DELETE /planner/history`
- [ ] 验证收藏记录也被清空 (通过数据库查询或尝试获取收藏列表)

---

## 五、完成标志

当以下所有项目都完成时, 功能实现即告完成:

- [ ] ✅ 所有代码检查清单项完成
- [ ] ✅ 所有质量检查清单项通过
- [ ] ✅ Pyright 类型检查无错误
- [ ] ✅ 所有手动测试通过
- [ ] ✅ 代码风格与现有代码保持一致
- [ ] ✅ 文档和注释完整

---

**最后提醒**:

1. 实现前先运行 `pyright` 检查现有代码, 确保环境正常
2. 实现过程中频繁运行 `pyright`, 及时发现类型错误
3. 参考现有代码风格, 特别是 `planner_routes.py` 中的错误处理和日志记录方式
4. 完成后在本地测试环境充分验证, 确保功能正确且无 bug

Good luck! 🚀
