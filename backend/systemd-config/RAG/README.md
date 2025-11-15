# RAG Systemd Service 配置文件说明

本目录包含 YATA RAG（检索增强生成）模块的 systemd 服务配置文件。

## 文件列表

### 用户级服务文件

- **`yata-rag.service`**: RAG 服务（用户级）

此文件使用 `%h` 等动态变量，**仅适用于用户级服务** (`systemctl --user`)。

## 服务说明

RAG 服务基于 ChromaDB 和 BGE-M3 提供向量检索服务，为 NLU 模块提供 RAG（检索增强生成）能力。

- **默认端口**: 8001（可通过环境变量 `RAG_API_PORT` 修改）
- **工作目录**: `algorithms/RAG_chroma/`
- **启动脚本**: `api_server.py`
- **虚拟环境**: `.venv`
- **数据存储**: `chroma_db/` 目录（ChromaDB 持久化存储）

## 快速开始

### 前置要求

1. 确保已在 `algorithms/RAG_chroma/` 目录下安装好依赖并创建虚拟环境。
2. 确保虚拟环境 `.venv` 已创建并包含所有依赖。
3. 初始化 ChromaDB 数据库（首次运行前）：

```bash
cd algorithms/RAG_chroma
source .venv/bin/activate
python ingest.py
```

### 部署用户级服务

```bash
# 1. 创建用户级 systemd 配置目录
mkdir -p ~/.config/systemd/user/

# 2. 复制服务文件
cp backend/systemd-config/RAG/yata-rag.service ~/.config/systemd/user/

# 3. 重新加载 systemd 配置
systemctl --user daemon-reload

# 4. 启用并启动服务
systemctl --user enable --now yata-rag.service

# 5. 查看服务状态
systemctl --user status yata-rag.service
```

### 查看日志

```bash
# 查看实时日志
journalctl --user -u yata-rag.service -f

# 查看最近日志
journalctl --user -u yata-rag.service -n 100
```

### 服务管理

```bash
# 停止服务
systemctl --user stop yata-rag.service

# 重启服务
systemctl --user restart yata-rag.service

# 禁用开机自启
systemctl --user disable yata-rag.service

# 启用开机自启
systemctl --user enable yata-rag.service
```

## 测试服务

服务启动后，可以通过以下方式测试：

### 健康检查

```bash
curl http://localhost:8001/health
```

预期响应：

```json
{"status": "ok"}
```

### 向量搜索测试

```bash
curl -X POST "http://localhost:8001/search" \
     -H "Content-Type: application/json" \
     -d '{
       "query": "巴黎有哪些著名景点",
       "city": "Paris",
       "top_k": 5
     }'
```

## 常见问题

### Q: 服务启动失败，提示找不到文件？

**A**: 检查以下几点：

1. 确认 `algorithms/RAG_chroma/` 目录存在且路径正确
2. 确认虚拟环境 `.venv` 已创建
3. 确认 `api_server.py` 文件存在
4. 确认 ChromaDB 数据库已初始化（`chroma_db/` 目录存在）
5. 查看详细日志：`journalctl --user -u yata-rag.service -n 50`

### Q: 服务启动但无法访问？

**A**: 检查端口是否被占用：

```bash
# 检查端口 8001 是否被占用
sudo lsof -i :8001

# 或使用
netstat -tulpn | grep 8001
```

如果端口被占用，可以修改环境变量 `RAG_API_PORT` 来使用其他端口。

### Q: 搜索返回空结果？

**A**: 可能是 ChromaDB 数据库未初始化或数据为空：

1. 停止服务：`systemctl --user stop yata-rag.service`
2. 运行数据导入：

   ```bash
   cd algorithms/RAG_chroma
   source .venv/bin/activate
   python ingest.py
   ```

3. 重启服务：`systemctl --user start yata-rag.service`

### Q: 如何让用户级服务在开机时自动启动（无需登录）？

**A**: 运行以下命令启用 linger：

```bash
sudo loginctl enable-linger $USER
```

### Q: 如何修改服务端口？

**A**: 编辑服务文件中的 `Environment="RAG_API_PORT=8001"` 行，将 `8001` 改为你想要的端口号，然后：

```bash
systemctl --user daemon-reload
systemctl --user restart yata-rag.service
```

## 数据管理

### 数据目录结构

```txt
algorithms/RAG_chroma/
├── data/           # 原始数据文件（JSON 格式）
├── chroma_db/      # ChromaDB 持久化存储
└── api_server.py   # API 服务入口
```

### 更新数据

如果需要更新向量数据库：

1. 将新的 JSON 数据文件放入 `data/` 目录
2. 停止服务：`systemctl --user stop yata-rag.service`
3. 重新导入数据：

   ```bash
   cd algorithms/RAG_chroma
   source .venv/bin/activate
   python ingest.py
   ```

4. 启动服务：`systemctl --user start yata-rag.service`

## 详细文档

更多关于 RAG 模块的详细信息，请参考：

- [RAG 模块 README](../../docs/cross-module-readmes/RAG-README.md)
- [Backend systemd 配置说明](../backend/README.md)

## 依赖关系

RAG 服务为以下模块提供支持：

- **NLU 服务** - 使用 RAG 进行检索增强生成

确保在启动 NLU 服务之前，RAG 服务已正确配置并运行。

## 性能优化

### 嵌入模型

RAG 服务使用 BGE-M3 嵌入模型（1024维）。首次启动时会自动下载模型，可能需要一些时间。

### 重排序

服务支持可选的重排序功能，可通过配置文件调整：

```bash
# 在 algorithms/RAG_chroma/ 目录下创建 .env 文件
USE_RERANKING=1
RERANK_TOP_K=20
```

修改配置后需要重启服务。
