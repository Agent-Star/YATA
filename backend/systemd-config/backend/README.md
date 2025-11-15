# Backend Systemd Service 配置文件说明

本目录包含 YATA backend 项目的 systemd 服务配置文件。

## 文件列表

### 用户级服务文件

- **`yata-backend.service`**: 后端服务（用户级）
- **`yata-tiny-frontend.service`**: Streamlit 前端服务（用户级）

这两个文件使用 `%h` 等动态变量，**仅适用于用户级服务** (`systemctl --user`)。

### 系统级服务文件

- **`yata-backend-system.service`**: 后端服务（系统级）
- **`yata-tiny-frontend-system.service`**: Streamlit 前端服务（系统级）

这两个文件使用明确的用户名和路径，适用于系统级服务 (`sudo systemctl`)。

**使用前需要修改文件中的：**

- `User=ubuntu` → 改为实际用户名
- `/home/ubuntu/YATA/backend` → 改为实际项目路径

## 如何选择？

| 场景 | 推荐方案 | 使用文件 |
|-----|---------|---------|
| 个人开发环境 | 用户级服务 | `yata-backend.service` |
| Linux 桌面系统 | 用户级服务 | `yata-backend.service` |
| AWS EC2 个人项目 | 用户级服务 | `yata-backend.service` |
| 生产服务器（多用户） | 系统级服务 | `yata-backend-system.service` |
| 需要开机即启动（无需登录） | 系统级服务 | `yata-backend-system.service` |

## 快速开始

### 用户级服务（推荐）

```bash
# 1. 创建目录
mkdir -p ~/.config/systemd/user/

# 2. 复制服务文件
cp yata-backend.service ~/.config/systemd/user/
cp yata-tiny-frontend.service ~/.config/systemd/user/

# 3. 重新加载并启动
systemctl --user daemon-reload
systemctl --user enable --now yata-backend.service
systemctl --user enable --now yata-tiny-frontend.service

# 4. 查看状态
systemctl --user status yata-backend.service
```

### 系统级服务

```bash
# 1. 修改配置文件中的用户名和路径
nano yata-backend-system.service

# 2. 复制到系统目录
sudo cp yata-backend-system.service /etc/systemd/system/yata-backend.service
sudo cp yata-tiny-frontend-system.service /etc/systemd/system/yata-tiny-frontend.service

# 3. 重新加载并启动
sudo systemctl daemon-reload
sudo systemctl enable --now yata-backend.service
sudo systemctl enable --now yata-tiny-frontend.service

# 4. 查看状态
sudo systemctl status yata-backend.service
```

## 常见问题

### Q: 出现 "Invalid user/group name or numeric ID" 错误？

**A**: 你把用户级服务文件 (`yata-backend.service`) 当作系统级服务使用了。应该：

- 改用系统级服务文件 (`yata-backend-system.service`)
- 或改用用户级服务 (`systemctl --user`)

### Q: 服务启动失败，提示找不到文件？

**A**: 检查服务文件中的路径是否正确，确保：

- `WorkingDirectory` 指向正确的项目目录
- `ExecStart` 中的 Python 和脚本路径正确
- 虚拟环境已创建 (`.venv` 目录存在)

### Q: 如何让用户级服务在开机时自动启动（无需登录）？

**A**: 运行以下命令启用 linger：

```bash
sudo loginctl enable-linger $USER
```

## 详细文档

详细的配置说明请参考：

- [后端服务配置说明](../qa/封装后端服务-解决方案.md)
- [前端服务配置说明](../qa/封装简易前端服务-解决方案.md)
- [系统级服务配置说明](../qa/系统级服务配置说明.md)
