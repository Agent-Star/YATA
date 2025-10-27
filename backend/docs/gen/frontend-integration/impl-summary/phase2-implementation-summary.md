# 阶段 2 实施总结: 用户-Thread 关联机制

## 实施内容

### 1. 数据模型扩展

**文件**: `backend/src/auth/models.py`

在 `User` 模型中添加了 `main_thread_id` 字段:

```python
# Thread 管理: 用户的主对话 Thread ID
main_thread_id: Mapped[Optional[str]] = mapped_column(
    String(length=100), index=True, nullable=True
)
```

**作用**:

- 每个用户拥有一个主对话 Thread
- 用于实现"单 Thread + 清空"的历史管理模式
- 支持索引查询, 提升性能

---

### 2. Thread 管理工具

**文件**: `backend/src/service/thread_manager.py` (新建)

实现了以下核心功能:

#### 2.1 `get_or_create_main_thread(user, session)`

获取或创建用户的主 Thread ID:

- 如果用户已有 main_thread_id, 直接返回
- 否则创建新的 UUID 作为 thread_id 并保存到数据库

#### 2.2 `get_main_thread_id(user_id, session)`

根据用户 ID 查询主 Thread ID:

- 用于在不同上下文中获取用户的 Thread
- 返回 None 如果用户不存在或无主 Thread

#### 2.3 `create_new_thread_for_user(user, session)`

为用户创建新 Thread (支持"新建对话"功能):

- 生成新的 Thread ID
- 更新为用户的主 Thread
- 旧对话历史保留在原 Thread 中 (可选择性访问)

**设计说明**:

- 采用"单 Thread + 清空"模式, 符合决策点 4 的选择 C
- 未来可扩展为多 Thread 管理

---

### 3. 用户注册时自动创建 Thread

**文件**: `backend/src/auth/manager.py`

在 `UserManager.on_after_register()` 回调中添加逻辑:

```python
async def on_after_register(self, user: User, request: Optional[Request] = None):
    """用户注册后的回调"""
    logger.info(f"用户 {user.id} 已注册，邮箱: {user.email}")
    
    # 为新用户创建主 Thread ID
    if not user.main_thread_id:
        user.main_thread_id = str(uuid4())
        await self.user_db.update(user)
        logger.info(f"为用户 {user.id} 创建主 Thread: {user.main_thread_id}")
```

**作用**:

- 确保每个新注册用户都自动拥有一个主 Thread
- 无需手动初始化, 降低使用复杂度

---

## 技术决策

### 选择: 单 Thread + 清空模式

**理由**:

1. ✅ 符合前端当前设计 (单一对话流)
2. ✅ 实现简单, 易于维护
3. ✅ 为未来扩展预留空间 (可添加多 Thread 支持)

**工作流程**:

```
用户注册
  ↓
自动创建 main_thread_id
  ↓
用户发起对话 → 使用 main_thread_id
  ↓
历史记录累积在该 Thread 中
  ↓
[可选] 用户点击"新建对话"
  ↓
创建新 thread_id, 更新为 main_thread_id
  ↓
旧对话保留, 新对话在新 Thread 中
```

---

## 数据库迁移说明

### 新增字段

**表名**: `users`

| 字段名 | 类型 | 说明 | 索引 | 可空 |
|--------|------|------|------|------|
| `main_thread_id` | VARCHAR(100) | 用户主对话 Thread ID | ✅ | ✅ |

### 迁移步骤

**对于现有数据库**:

1. 添加新字段 (SQLite):

```sql
ALTER TABLE users ADD COLUMN main_thread_id VARCHAR(100);
CREATE INDEX ix_users_main_thread_id ON users(main_thread_id);
```

2. 为现有用户创建 Thread ID (可选):

```python
# 运行迁移脚本
async def migrate_existing_users():
    async with async_session_maker() as session:
        users = await session.execute(select(User))
        for user in users.scalars():
            if not user.main_thread_id:
                user.main_thread_id = str(uuid4())
        await session.commit()
```

**对于新部署**:

- 数据库表会在应用启动时自动创建 (`create_db_and_tables()`)
- 新字段会包含在初始 schema 中

---

## 集成测试要点

### 测试场景

1. **新用户注册**:
   - ✅ 验证 `main_thread_id` 已自动创建
   - ✅ 验证 thread_id 格式为有效的 UUID

2. **获取主 Thread**:
   - ✅ 已有 thread 的用户直接返回
   - ✅ 无 thread 的用户自动创建

3. **创建新 Thread**:
   - ✅ 旧 thread_id 被新 thread_id 替换
   - ✅ 旧对话历史仍可通过旧 thread_id 访问

### 示例测试代码

```python
async def test_new_user_has_main_thread():
    # 注册新用户
    user = await user_manager.create(UserCreate(
        email="test@example.com",
        password="password123"
    ))
    
    # 验证自动创建了 main_thread_id
    assert user.main_thread_id is not None
    assert len(user.main_thread_id) == 36  # UUID length
```

---

## 后续集成

阶段 2 完成后, 阶段 3 可以使用以下功能:

1. **获取用户对话历史**:

```python
from service.thread_manager import get_or_create_main_thread

# 在 /planner/history 中
thread_id = await get_or_create_main_thread(current_user, session)
history = await agent.aget_state(config={"thread_id": thread_id})
```

2. **流式对话接口**:

```python
# 在 /planner/plan/stream 中
thread_id = await get_or_create_main_thread(current_user, session)
# 使用 thread_id 进行对话
```

---

## 文件清单

### 新建文件

- `backend/src/service/thread_manager.py` - Thread 管理工具 (88 行)

### 修改文件

- `backend/src/auth/models.py` - 添加 main_thread_id 字段 (+4 行)
- `backend/src/auth/manager.py` - 注册时自动创建 Thread (+7 行)

### 总代码量

- 新增: ~100 行
- 修改: ~11 行

---

## 阶段状态

✅ **阶段 2 完成**

**完成时间**: 2025-10-27  
**下一阶段**: 阶段 3 - 行程规划接口实现

---

**文档版本**: v1.0  
**作者**: AI Assistant
