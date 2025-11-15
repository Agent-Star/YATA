# Frontend Systemd Service 配置文件说明

本目录包含 YATA Frontend 模块的 systemd 服务配置文件。

## 文件列表

### 用户级服务文件

- **`yata-frontend.service`**: Frontend 服务（用户级，生产模式）
- **`yata-frontend-dev.service`**: Frontend 服务（用户级，开发模式）

这两个文件使用 `%h` 等动态变量，**仅适用于用户级服务** (`systemctl --user`)。

## 服务说明

Frontend 是基于 Next.js 14 的 Web 应用，提供 AI 旅行规划的用户界面。提供两种运行模式：

### 生产模式 (`yata-frontend.service`)

- **启动命令**: `npm start`
- **前置要求**: 必须先运行 `npm run build`
- **特点**:
  - 代码经过优化和压缩
  - 性能优秀，资源占用低
  - 适合生产环境和长期运行
  - 无热重载，代码修改需要重新构建
- **适用场景**: 正式对外服务、生产环境

### 开发模式 (`yata-frontend-dev.service`)

- **启动命令**: `npm run dev`
- **前置要求**: 运行 `npm install`
- **特点**:
  - 支持热重载（Hot Module Replacement）
  - 代码未优化，包含调试信息
  - 启动快，无需构建
  - 资源占用较高
- **适用场景**: 开发调试、频繁修改代码、内部测试

### 通用配置

- **默认端口**: 3000（可通过环境变量 `PORT` 修改）
- **工作目录**: `frontend/`
- **Node 环境**: 生产模式使用 `production`，开发模式使用 `development`

## 如何选择？

| 场景 | 推荐方案 | 使用文件 |
|-----|---------|---------|
| 正式对外服务 | 生产模式 | `yata-frontend.service` |
| 长期稳定运行 | 生产模式 | `yata-frontend.service` |
| 内部测试环境 | 开发模式 | `yata-frontend-dev.service` |
| 频繁修改代码 | 开发模式 | `yata-frontend-dev.service` |
| 需要热重载 | 开发模式 | `yata-frontend-dev.service` |

## 快速开始

### 前置要求

1. 确保已安装 Node.js 和 npm：

```bash
node --version  # 建议 Node.js 18+
npm --version
```

2. 安装项目依赖：

```bash
cd frontend
npm install
```

3. **仅生产模式需要**：构建项目

```bash
npm run build
```

### 部署生产模式服务（推荐）

```bash
# 1. 创建用户级 systemd 配置目录
mkdir -p ~/.config/systemd/user/

# 2. 复制服务文件
cp backend/systemd-config/frontend/yata-frontend.service ~/.config/systemd/user/

# 3. 重新加载 systemd 配置
systemctl --user daemon-reload

# 4. 启用并启动服务
systemctl --user enable --now yata-frontend.service

# 5. 查看服务状态
systemctl --user status yata-frontend.service
```

### 部署开发模式服务

```bash
# 1. 创建用户级 systemd 配置目录
mkdir -p ~/.config/systemd/user/

# 2. 复制服务文件
cp backend/systemd-config/frontend/yata-frontend-dev.service ~/.config/systemd/user/

# 3. 重新加载 systemd 配置
systemctl --user daemon-reload

# 4. 启用并启动服务
systemctl --user enable --now yata-frontend-dev.service

# 5. 查看服务状态
systemctl --user status yata-frontend-dev.service
```

### 查看日志

```bash
# 生产模式日志
journalctl --user -u yata-frontend.service -f

# 开发模式日志
journalctl --user -u yata-frontend-dev.service -f

# 查看最近日志
journalctl --user -u yata-frontend.service -n 100
```

### 服务管理

```bash
# 停止服务
systemctl --user stop yata-frontend.service

# 重启服务
systemctl --user restart yata-frontend.service

# 禁用开机自启
systemctl --user disable yata-frontend.service

# 启用开机自启
systemctl --user enable yata-frontend.service
```

## 在两种模式之间切换

### 从开发模式切换到生产模式

```bash
# 1. 停止开发模式服务
systemctl --user stop yata-frontend-dev.service
systemctl --user disable yata-frontend-dev.service

# 2. 构建生产版本
cd frontend
npm run build

# 3. 启动生产模式服务
systemctl --user enable --now yata-frontend.service
```

### 从生产模式切换到开发模式

```bash
# 1. 停止生产模式服务
systemctl --user stop yata-frontend.service
systemctl --user disable yata-frontend.service

# 2. 启动开发模式服务
systemctl --user enable --now yata-frontend-dev.service
```

**注意**: 两个服务不能同时运行（都使用端口 3000）。

## 测试服务

服务启动后，可以通过以下方式测试：

### 访问 Web 界面

在浏览器中打开：

```
http://localhost:3000
```

您应该能看到 YATA 旅行规划助手的登录页面。

### 检查服务状态

```bash
# 检查端口是否监听
sudo lsof -i :3000

# 或使用
netstat -tulpn | grep 3000

# 使用 curl 测试
curl http://localhost:3000
```

## 更新代码流程

### 生产模式更新流程

当您修改了代码并需要更新生产服务时：

```bash
# 1. 停止服务
systemctl --user stop yata-frontend.service

# 2. 拉取最新代码（如果使用 Git）
cd frontend
git pull

# 3. 安装新依赖（如果 package.json 有变化）
npm install

# 4. 重新构建
npm run build

# 5. 启动服务
systemctl --user start yata-frontend.service

# 6. 验证服务状态
systemctl --user status yata-frontend.service
```

### 开发模式更新流程

开发模式支持热重载，大部分情况下无需重启：

```bash
# 1. 拉取最新代码
cd frontend
git pull

# 2. 如果 package.json 有变化，安装新依赖
npm install

# 3. 重启服务（仅在安装新依赖或环境变量改变时需要）
systemctl --user restart yata-frontend-dev.service
```

## 常见问题

### Q: 服务启动失败，提示找不到 npm？

**A**: 确保 npm 安装在系统路径中：

```bash
which npm
# 应该输出类似 /usr/bin/npm 的路径

# 如果 npm 在其他位置，修改服务文件中的 ExecStart 路径
```

### Q: 生产模式启动失败，提示 "Could not find a production build"？

**A**: 生产模式必须先运行 `npm run build`：

```bash
cd frontend
npm run build
systemctl --user restart yata-frontend.service
```

### Q: 端口 3000 被占用？

**A**: 检查端口占用情况：

```bash
sudo lsof -i :3000
```

可以修改服务文件中的 `Environment="PORT=3000"` 来使用其他端口，例如：

```ini
Environment="PORT=3001"
```

修改后记得重新加载配置：

```bash
systemctl --user daemon-reload
systemctl --user restart yata-frontend.service
```

### Q: 开发模式和生产模式可以同时运行吗？

**A**: 不可以，两个服务都默认使用端口 3000。如果需要同时运行，必须为其中一个修改端口。

### Q: 如何让用户级服务在开机时自动启动（无需登录）？

**A**: 运行以下命令启用 linger：

```bash
sudo loginctl enable-linger $USER
```

### Q: 服务运行但访问不了页面？

**A**: 检查以下几点：

1. 确认服务状态正常：`systemctl --user status yata-frontend.service`
2. 检查日志是否有错误：`journalctl --user -u yata-frontend.service -n 50`
3. 确认端口正在监听：`sudo lsof -i :3000`
4. 检查防火墙设置（如果有）
5. 尝试使用 `curl http://localhost:3000` 测试

### Q: 开发模式的热重载不工作？

**A**: 热重载依赖于文件系统监听，可能受以下因素影响：

1. 文件系统类型（某些网络文件系统不支持）
2. 文件监听数量限制

可以尝试增加文件监听限制：

```bash
# 临时增加
sudo sysctl fs.inotify.max_user_watches=524288

# 永久增加
echo "fs.inotify.max_user_watches=524288" | sudo tee -a /etc/sysctl.conf
sudo sysctl -p
```

### Q: 如何配置代理转发到后端 API？

**A**: Frontend 使用 Next.js 的 `rewrites` 功能代理 API 请求。配置位于 `frontend/next.config.js`：

```javascript
async rewrites() {
  return {
    afterFiles: [
      {
        source: '/api/:path*',
        destination: `${API_PROXY_TARGET}/:path*`,
      },
    ],
  };
}
```

可以通过环境变量 `API_PROXY_TARGET` 修改后端地址。在服务文件中添加：

```ini
Environment="API_PROXY_TARGET=http://localhost:8000"
```

## 性能优化建议

### 生产模式优化

1. **使用生产构建**: 确保运行 `npm run build` 而不是开发模式
2. **启用压缩**: Next.js 默认已启用 gzip/brotli 压缩
3. **CDN 部署**: 考虑将静态资源部署到 CDN
4. **内存限制**: 如果遇到内存问题，可以增加 Node.js 内存限制：

```ini
Environment="NODE_OPTIONS=--max-old-space-size=4096"
```

### 开发模式优化

1. **限制文件监听**: 排除 node_modules 等大目录
2. **使用 Turbopack**: Next.js 14 支持更快的开发服务器（实验性功能）

## 依赖关系

Frontend 服务依赖于：

- **Backend 服务** - 提供 API 接口（默认 `http://166.117.38.176:8080`）
- **Node.js 环境** - 建议 Node.js 18 或更高版本
- **网络连接** - 用于 API 代理和资源加载

确保 Backend 服务已正确配置并运行。

## 详细文档

更多关于 Frontend 模块的详细信息，请参考：

- [Frontend 模块 README](../../docs/cross-module-readmes/Frontend-README.md)
- [Backend systemd 配置说明](../backend/README.md)
- [Next.js 官方文档](https://nextjs.org/docs)

## 架构说明

Frontend 使用 Next.js 的以下特性：

- **页面路由**: `pages/` 目录下的文件自动成为路由
- **API Routes**: `pages/api/` 提供后端接口
- **SSR/SSG**: 支持服务端渲染和静态生成
- **React 18**: 使用最新的 React 特性
- **Semi UI**: 字节跳动的企业级组件库

### 关键目录

```txt
frontend/
├── pages/              # Next.js 页面
│   ├── api/            # API 路由
│   ├── index.js        # 首页
│   └── ...
├── components/         # React 组件
├── lib/                # 工具函数和服务
├── store/              # 状态管理
└── styles/             # 样式文件
```
