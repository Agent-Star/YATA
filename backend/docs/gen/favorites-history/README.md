# 收藏与历史删除功能规划文档

本目录包含 YATA 后端新增"收藏"和"历史记录删除"功能的完整实现规划。

---

## 📄 文档列表

### 1. `implementation-plan.md` (详细规划)

完整的实现规划文档, 包含:

- **数据库设计**: `Favorite` 表结构、字段说明、索引设计
- **API 设计**: 接口定义、请求/响应格式、错误码
- **代码实现**: 完整的代码示例和实现逻辑
- **实现步骤**: 分阶段的任务清单和时间估算
- **代码规范**: 类型标注、注释、错误处理等质量要求
- **测试方案**: 类型检查、手动测试、单元测试建议
- **注意事项**: 数据一致性、性能优化、扩展性考虑

**适用场景**: 首次阅读、深入理解、架构评审

---

### 2. `implementation-checklist.md` (快速检查清单)

简洁的任务检查清单, 包含:

- **收藏功能清单**: 6 个实现步骤的详细检查项
- **历史删除清单**: 1 个实现步骤的详细检查项
- **代码质量清单**: 类型标注、注释、错误处理、日志等检查项
- **测试清单**: Pyright 类型检查、手动测试用例

**适用场景**: 编码实现、进度跟踪、质量验证

---

## 🎯 使用指南

### 首次阅读

1. 先阅读 `implementation-plan.md` 的"功能概述"和"实现方案"部分
2. 理解数据库设计和 API 设计的核心思路
3. 浏览代码示例, 了解实现风格

### 开始实现

1. 参考 `implementation-checklist.md` 逐步实现功能
2. 每完成一个步骤, 在清单中打勾 ✅
3. 遇到疑问时, 回到 `implementation-plan.md` 查阅详细说明

### 代码审查

1. 使用 `implementation-checklist.md` 中的"代码质量检查清单"
2. 确保所有检查项都通过
3. 运行 Pyright 类型检查, 确保无错误

---

## 🔧 实现顺序建议

1. **阶段 1** (25 分钟): 实现历史删除功能
   - 简单、独立, 可先完成
   - 修改 `src/service/planner_routes.py`, 添加 `DELETE /planner/history` 路由

2. **阶段 2** (35 分钟): 数据库和 Schema
   - 修改 `src/auth/models.py`, 添加 `Favorite` 模型
   - 修改 `src/schema/schema.py`, 添加收藏相关 Schema

3. **阶段 3** (1.5 小时): 收藏功能路由
   - 修改 `src/service/planner_routes.py`, 实现 3 个接口

4. **阶段 4** (30 分钟): 测试和优化
   - 运行 Pyright 检查
   - 手动测试所有接口
   - 修复 bug 和类型错误

**总计**: 约 3.5 小时

---

## 📌 关键要点

### 收藏功能

- **数据存储**: 新增 `favorites` 表, 冗余存储消息内容
- **查询优化**: 使用单次查询 + set 成员检查标记 `isFavorited`
- **数据一致性**: 删除历史记录时同时删除收藏记录
- **幂等性**: DELETE 操作可重复调用

### 历史删除功能

- **实现方式**: 创建新 Thread ID, 旧数据仍保留
- **复用代码**: 使用 `thread_manager.create_new_thread_for_user()`
- **数据清理**: 同时删除用户的所有收藏记录

---

## 🚀 快速开始

```bash
# 1. 激活虚拟环境
source .venv/bin/activate  # Linux/Mac
# 或
./.venv/Scripts/activate  # Windows

# 2. 运行 Pyright 检查 (确保环境正常)
pyright src/auth/models.py

# 3. 开始实现 (参考 implementation-checklist.md)

# 4. 实现后再次运行 Pyright
pyright src/auth/models.py
pyright src/service/planner_routes.py
pyright src/schema/schema.py
```

---

## 📖 相关文档

- **接口规范**: `backend/docs/api/接口说明.md`
- **现有路由实现**: `backend/src/service/planner_routes.py`
- **数据模型**: `backend/src/auth/models.py`
- **Thread 管理**: `backend/src/service/thread_manager.py`

---

**文档创建时间**: 2025-11-11
**创建工具**: Claude Code
**版本**: v1.0
