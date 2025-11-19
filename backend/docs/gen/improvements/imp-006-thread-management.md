# IMP-006: Thread 管理功能扩展

## 元数据

- **ID**: IMP-006
- **分类**: 功能增强
- **优先级**: 🟢 低
- **状态**: 待处理
- **创建日期**: 2025-01-27
- **预计工作量**: 大
- **相关文档**: `phase2-implementation-summary.md`, `compliance-check.md`

---

## 问题描述

### 当前实现

#### 1. 单 Thread 模式

**文件**: `backend/src/auth/models.py`

```python
class User(SQLAlchemyBaseUserTable[uuid.UUID], Base):
    # Thread 管理: 用户的主对话 Thread ID
    main_thread_id: Mapped[Optional[str]] = mapped_column(
        String(length=100), index=True, nullable=True
    )
```

每个用户只有一个 `main_thread_id`，所有对话都在这个 thread 中。

#### 2. 当前支持的操作

- ✅ 获取或创建主 Thread
- ✅ 在主 Thread 中追加对话
- ❌ 创建新 Thread（会替换主 Thread）
- ❌ 列出所有 Thread
- ❌ 切换 Thread
- ❌ 删除 Thread

### 不足之处

1. **功能受限**：用户只能有一个对话历史
2. **场景受限**：无法支持"多个独立的旅行计划"等场景
3. **数据管理困难**：清空历史意味着丢失所有数据
4. **扩展性差**：未来难以支持对话分组、归档等功能

**用户场景示例**：

```
用户想规划三个旅行：
- 东京 3 日游
- 京都 5 日游
- 大阪 2 日游

当前系统：只能有一个对话，所有旅行计划混在一起
理想系统：每个旅行计划一个独立的 Thread
```

---

## 影响分析

### 功能影响

- ⚠️ **限制用户使用场景**：无法支持多个独立计划
- ⚠️ **数据组织混乱**：所有对话混在一起

### 用户体验影响

- ⚠️ **需要手动记录**：用户需要自己记住不同计划的内容
- ⚠️ **上下文混淆**：多个计划混在一起，AI 可能困惑

### 产品竞争力影响

- ⚠️ **功能弱于竞品**：大多数 AI 助手支持多对话
- 🟢 **但不影响 MVP**：当前功能足够验证核心价值

---

## 改进方案

### 方案 1: 多 Thread 支持（推荐）

**目标**：

- 用户可以创建多个 Thread（对话/项目）
- 每个 Thread 有独立的历史
- 支持切换、重命名、删除 Thread

**实施步骤**：

#### 1. 数据库设计

**方案 A: 新增 Thread 表**

```sql
CREATE TABLE conversation_thread (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    title VARCHAR(200) NOT NULL,
    description TEXT,
    langgraph_thread_id VARCHAR(100) UNIQUE NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_message_at TIMESTAMP WITH TIME ZONE,
    message_count INTEGER DEFAULT 0,
    metadata JSONB,
    FOREIGN KEY (user_id) REFERENCES user(id) ON DELETE CASCADE
);

CREATE INDEX idx_thread_user ON conversation_thread(user_id, updated_at DESC);
CREATE INDEX idx_thread_active ON conversation_thread(user_id, is_active);
```

**方案 B: 复用 User 表 + 关联表**

```sql
-- 保留 user.main_thread_id 作为当前活跃 Thread

CREATE TABLE user_thread (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    langgraph_thread_id VARCHAR(100) UNIQUE NOT NULL,
    title VARCHAR(200) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    FOREIGN KEY (user_id) REFERENCES user(id) ON DELETE CASCADE
);
```

**推荐方案 A**：更完整，支持更多元数据。

#### 2. Pydantic 模型

**文件**: `backend/src/schema/thread.py` (新建)

```python
"""对话 Thread 相关模型"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ThreadBase(BaseModel):
    """Thread 基础模型"""
    title: str = Field(description="对话标题", max_length=200)
    description: str | None = Field(default=None, description="对话描述")


class ThreadCreate(ThreadBase):
    """创建 Thread 请求"""
    pass


class ThreadUpdate(BaseModel):
    """更新 Thread 请求"""
    title: str | None = None
    description: str | None = None
    is_active: bool | None = None


class ThreadResponse(ThreadBase):
    """Thread 响应"""
    id: UUID
    langgraph_thread_id: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    last_message_at: datetime | None
    message_count: int
    
    class Config:
        from_attributes = True


class ThreadListResponse(BaseModel):
    """Thread 列表响应"""
    threads: list[ThreadResponse]
    total: int
    current_thread_id: UUID | None = Field(description="当前活跃的 Thread ID")
```

#### 3. Thread 管理服务

**文件**: `backend/src/service/thread_service.py` (新建)

```python
"""Thread 管理服务"""

from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.models import User
from schema.thread import ThreadCreate, ThreadResponse, ThreadUpdate


class ThreadService:
    """Thread 管理服务"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def create_thread(self, user: User, data: ThreadCreate) -> ThreadResponse:
        """创建新 Thread"""
        # 生成 LangGraph Thread ID
        langgraph_thread_id = str(uuid4())
        
        thread = ConversationThread(
            user_id=user.id,
            title=data.title,
            description=data.description,
            langgraph_thread_id=langgraph_thread_id,
        )
        
        self.session.add(thread)
        await self.session.commit()
        await self.session.refresh(thread)
        
        return ThreadResponse.model_validate(thread)
    
    async def list_threads(
        self,
        user: User,
        active_only: bool = True,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[ThreadResponse], int]:
        """列出用户的 Thread"""
        query = select(ConversationThread).where(ConversationThread.user_id == user.id)
        
        if active_only:
            query = query.where(ConversationThread.is_active == True)
        
        # 总数
        count_query = select(func.count()).select_from(query.subquery())
        total = await self.session.scalar(count_query)
        
        # 分页查询
        query = query.order_by(ConversationThread.updated_at.desc()).limit(limit).offset(offset)
        result = await self.session.execute(query)
        threads = result.scalars().all()
        
        return [ThreadResponse.model_validate(t) for t in threads], total or 0
    
    async def get_thread(self, thread_id: UUID, user: User) -> ThreadResponse | None:
        """获取单个 Thread"""
        query = select(ConversationThread).where(
            ConversationThread.id == thread_id,
            ConversationThread.user_id == user.id,
        )
        result = await self.session.execute(query)
        thread = result.scalar_one_or_none()
        
        if thread:
            return ThreadResponse.model_validate(thread)
        return None
    
    async def update_thread(self, thread_id: UUID, user: User, data: ThreadUpdate) -> ThreadResponse:
        """更新 Thread"""
        thread = await self._get_thread_or_raise(thread_id, user)
        
        if data.title is not None:
            thread.title = data.title
        if data.description is not None:
            thread.description = data.description
        if data.is_active is not None:
            thread.is_active = data.is_active
        
        thread.updated_at = datetime.utcnow()
        
        await self.session.commit()
        await self.session.refresh(thread)
        
        return ThreadResponse.model_validate(thread)
    
    async def delete_thread(self, thread_id: UUID, user: User) -> None:
        """删除 Thread（软删除）"""
        thread = await self._get_thread_or_raise(thread_id, user)
        thread.is_active = False
        thread.updated_at = datetime.utcnow()
        
        await self.session.commit()
    
    async def set_active_thread(self, thread_id: UUID, user: User) -> None:
        """设置当前活跃的 Thread"""
        thread = await self._get_thread_or_raise(thread_id, user)
        
        # 更新用户的 main_thread_id
        user.main_thread_id = thread.langgraph_thread_id
        await self.session.commit()
    
    async def _get_thread_or_raise(self, thread_id: UUID, user: User) -> ConversationThread:
        """获取 Thread 或抛出异常"""
        thread = await self.get_thread(thread_id, user)
        if not thread:
            raise NotFoundError("Thread")
        return thread
```

#### 4. Thread API 路由

**文件**: `backend/src/service/thread_routes.py` (新建)

```python
"""Thread 管理路由"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from auth import User, current_active_user
from auth.database import get_async_session
from schema.thread import ThreadCreate, ThreadListResponse, ThreadResponse, ThreadUpdate
from service.thread_service import ThreadService


thread_router = APIRouter(prefix="/threads", tags=["Thread Management"])


def get_thread_service(session: AsyncSession = Depends(get_async_session)) -> ThreadService:
    """获取 Thread 服务"""
    return ThreadService(session)


@thread_router.post("/", response_model=ThreadResponse, status_code=201)
async def create_thread(
    data: ThreadCreate,
    current_user: Annotated[User, Depends(current_active_user)],
    service: ThreadService = Depends(get_thread_service),
) -> ThreadResponse:
    """创建新对话"""
    return await service.create_thread(current_user, data)


@thread_router.get("/", response_model=ThreadListResponse)
async def list_threads(
    current_user: Annotated[User, Depends(current_active_user)],
    active_only: bool = Query(default=True, description="只返回活跃的对话"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    service: ThreadService = Depends(get_thread_service),
) -> ThreadListResponse:
    """获取对话列表"""
    threads, total = await service.list_threads(current_user, active_only, limit, offset)
    
    # 获取当前活跃的 Thread
    current_thread_id = None
    if current_user.main_thread_id:
        # 查找对应的 Thread ID
        for thread in threads:
            if thread.langgraph_thread_id == current_user.main_thread_id:
                current_thread_id = thread.id
                break
    
    return ThreadListResponse(
        threads=threads,
        total=total,
        current_thread_id=current_thread_id,
    )


@thread_router.get("/{thread_id}", response_model=ThreadResponse)
async def get_thread(
    thread_id: UUID,
    current_user: Annotated[User, Depends(current_active_user)],
    service: ThreadService = Depends(get_thread_service),
) -> ThreadResponse:
    """获取对话详情"""
    thread = await service.get_thread(thread_id, current_user)
    if not thread:
        raise NotFoundError("Thread")
    return thread


@thread_router.patch("/{thread_id}", response_model=ThreadResponse)
async def update_thread(
    thread_id: UUID,
    data: ThreadUpdate,
    current_user: Annotated[User, Depends(current_active_user)],
    service: ThreadService = Depends(get_thread_service),
) -> ThreadResponse:
    """更新对话"""
    return await service.update_thread(thread_id, current_user, data)


@thread_router.delete("/{thread_id}", status_code=204)
async def delete_thread(
    thread_id: UUID,
    current_user: Annotated[User, Depends(current_active_user)],
    service: ThreadService = Depends(get_thread_service),
) -> None:
    """删除对话（软删除）"""
    await service.delete_thread(thread_id, current_user)


@thread_router.post("/{thread_id}/activate", status_code=204)
async def activate_thread(
    thread_id: UUID,
    current_user: Annotated[User, Depends(current_active_user)],
    service: ThreadService = Depends(get_thread_service),
) -> None:
    """切换到指定对话"""
    await service.set_active_thread(thread_id, current_user)
```

#### 5. 更新 Planner 路由

**修改**: `backend/src/service/planner_routes.py`

```python
# 添加可选的 thread_id 参数
@planner_router.post("/plan/stream")
async def plan_stream(
    request: PlanRequest,
    current_user: Annotated[User, Depends(current_active_user)],
    session: AsyncSession = Depends(get_async_session),
    thread_id: UUID | None = Query(default=None, description="指定 Thread ID，为空则使用主 Thread"),
) -> StreamingResponse:
    """流式行程规划接口"""
    
    async def generate_events() -> AsyncGenerator[str, None]:
        try:
            # 获取 Thread ID
            if thread_id:
                # 使用指定的 Thread
                service = ThreadService(session)
                thread = await service.get_thread(thread_id, current_user)
                if not thread:
                    raise NotFoundError("Thread")
                langgraph_thread_id = thread.langgraph_thread_id
            else:
                # 使用主 Thread
                langgraph_thread_id = await get_or_create_main_thread(current_user, session)
            
            # ... 后续逻辑使用 langgraph_thread_id ...
```

---

### 方案 2: Thread 分组和标签

**扩展方案 1**，增加分组和标签功能：

```sql
CREATE TABLE thread_tag (
    id UUID PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE
);

CREATE TABLE thread_tag_mapping (
    thread_id UUID,
    tag_id UUID,
    PRIMARY KEY (thread_id, tag_id)
);
```

---

## 实施建议

### 推荐方案

**方案 1（多 Thread 支持）** - 核心功能

### 实施步骤

1. **数据库迁移**
   - 创建 `conversation_thread` 表
   - 迁移现有 Thread 数据
   - 预计工作量：2 小时

2. **实现 Thread 服务**
   - 预计工作量：4 小时

3. **实现 Thread API**
   - 预计工作量：3 小时

4. **更新 Planner 路由**
   - 预计工作量：2 小时

5. **测试和文档**
   - 预计工作量：3 小时

**总计**：约 14 小时

### 注意事项

1. **数据迁移**：需要为现有用户创建默认 Thread
2. **向后兼容**：保留 `main_thread_id`，确保旧逻辑正常工作
3. **性能**：Thread 列表可能需要分页和缓存

---

## 前端集成

### 新增 API

```typescript
// 创建对话
POST /threads
{
  "title": "东京 3 日游",
  "description": "2025年春季东京旅行计划"
}

// 获取对话列表
GET /threads?active_only=true&limit=20

// 切换对话
POST /threads/{thread_id}/activate

// 删除对话
DELETE /threads/{thread_id}

// 在指定对话中聊天
POST /planner/plan/stream?thread_id={thread_id}
{
  "prompt": "第一天去哪里？",
  "context": {"language": "zh"}
}
```

### 前端 UI 建议

- 左侧栏显示对话列表
- 支持搜索和筛选对话
- 当前对话高亮显示
- 支持创建、重命名、删除对话

---

## 相关资源

- [LangGraph Thread Management](https://langchain-ai.github.io/langgraph/concepts/#threads)
- [ChatGPT Conversation Management](https://help.openai.com/en/articles/7925741-chatgpt-conversations)

---

## 更新日志

- 2025-01-27: 创建文档，提供多 Thread 支持方案
