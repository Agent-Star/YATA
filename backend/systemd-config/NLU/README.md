# NLU Systemd Service 配置文件说明

本目录包含 YATA NLU 模块的 systemd 服务配置文件。

## 文件列表

### 用户级服务文件

- **`yata-nlu.service`**: NLU 服务（用户级）

此文件使用 `%h` 等动态变量，**仅适用于用户级服务** (`systemctl --user`)。

## 服务说明

NLU 服务提供自然语言理解、意图识别和推荐/行程生成功能，基于 FastAPI 框架。

- **默认端口**: 8010（可通过环境变量 `NLU_API_PORT` 修改）
- **工作目录**: `algorithms/NLU/`
- **启动脚本**: `api/fastapi_server.py`
- **虚拟环境**: `.venv`

## 快速开始

### 前置要求

1. 确保已在 `algorithms/NLU/` 目录下安装好依赖并创建虚拟环境。
2. 确保虚拟环境 `.venv` 已创建并包含所有依赖。

### 部署用户级服务

```bash
# 1. 创建用户级 systemd 配置目录
mkdir -p ~/.config/systemd/user/

# 2. 复制服务文件
cp backend/systemd-config/NLU/yata-nlu.service ~/.config/systemd/user/

# 3. 重新加载 systemd 配置
systemctl --user daemon-reload

# 4. 启用并启动服务
systemctl --user enable --now yata-nlu.service

# 5. 查看服务状态
systemctl --user status yata-nlu.service
```

### 查看日志

```bash
# 查看实时日志
journalctl --user -u yata-nlu.service -f

# 查看最近日志
journalctl --user -u yata-nlu.service -n 100
```

### 服务管理

```bash
# 停止服务
systemctl --user stop yata-nlu.service

# 重启服务
systemctl --user restart yata-nlu.service

# 禁用开机自启
systemctl --user disable yata-nlu.service

# 启用开机自启
systemctl --user enable yata-nlu.service
```

## 测试服务

服务启动后，可以通过以下方式测试：

### 健康检查

```bash
curl http://localhost:8010/health
```

预期响应：

```json
{"status": "ok"}
```

### 简单查询测试

```bash
curl -X POST "http://localhost:8010/nlu/simple" \
     -H "Content-Type: application/json" \
     -d '{
       "text": "推荐Paris的顶级景点和必看地方，适合第一次去的游客"
     }'
```

## 常见问题

### Q: 服务启动失败，提示找不到文件？

**A**: 检查以下几点：

1. 确认 `algorithms/NLU/` 目录存在且路径正确
2. 确认虚拟环境 `.venv` 已创建
3. 确认 `api/fastapi_server.py` 文件存在
4. 查看详细日志：`journalctl --user -u yata-nlu.service -n 50`

### Q: 服务启动但无法访问？

**A**: 检查端口是否被占用：

```bash
# 检查端口 8010 是否被占用
sudo lsof -i :8010

# 或使用
netstat -tulpn | grep 8010
```

如果端口被占用，可以修改环境变量 `NLU_API_PORT` 来使用其他端口。

### Q: 如何让用户级服务在开机时自动启动（无需登录）？

**A**: 运行以下命令启用 linger：

```bash
sudo loginctl enable-linger $USER
```

### Q: 如何修改服务端口？

**A**: 编辑服务文件中的 `Environment="NLU_API_PORT=8010"` 行，将 `8010` 改为你想要的端口号，然后：

```bash
systemctl --user daemon-reload
systemctl --user restart yata-nlu.service
```

## 详细文档

更多关于 NLU 模块的详细信息，请参考：

- [NLU 模块 README](../../docs/cross-module-readmes/NLU-README.md)
- [Backend systemd 配置说明](../backend/README.md)

## 依赖关系

NLU 服务可能依赖于：

- **RAG 服务**（用于检索增强生成）- 默认端口 8001
- **API Keys** - 需要配置相关的 AI 模型 API 密钥（如 OpenAI、DeepSeek 等）

确保相关依赖服务已正确配置并运行。
