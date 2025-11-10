# AWS EC2 系统级服务快速修复指南

## 问题

在 AWS EC2 上使用系统级服务时遇到错误：

```txt
Invalid user/group name or numeric ID
yata-backend.service: Unit configuration has fatal error, unit will not be started.
```

## 原因

`yata-backend.service` 文件中使用了 `User=%i` 和 `%h` 等变量，这些只在用户级服务中有效。系统级服务需要明确指定用户名和路径。

## 解决方案

### 方案一：使用系统级服务文件（适合生产环境）

#### 步骤 1: 检查你的用户名和项目路径

```bash
# 查看当前用户名
whoami

# 查看项目路径
cd ~/YATA/backend && pwd
```

通常结果是：

- **Ubuntu EC2**: 用户名 `ubuntu`, 路径 `/home/ubuntu/YATA/backend`
- **Amazon Linux EC2**: 用户名 `ec2-user`, 路径 `/home/ec2-user/YATA/backend`

#### 步骤 2: 删除旧的错误服务

```bash
# 停止并删除错误的服务
sudo systemctl stop yata-backend.service
sudo systemctl disable yata-backend.service
sudo rm /etc/systemd/system/yata-backend.service

# 重新加载
sudo systemctl daemon-reload
sudo systemctl reset-failed
```

#### 步骤 3: 部署正确的服务文件

**对于 Ubuntu EC2 (默认配置)：**

```bash
# 直接复制（无需修改，默认配置就是 ubuntu 用户）
sudo cp ~/YATA/backend/services/yata-backend-system.service /etc/systemd/system/yata-backend.service

# 重新加载并启动
sudo systemctl daemon-reload
sudo systemctl enable yata-backend.service
sudo systemctl start yata-backend.service

# 检查状态
sudo systemctl status yata-backend.service
```

**对于 Amazon Linux EC2：**

```bash
# 需要先修改配置文件
cd ~/YATA/backend/services

# 创建临时副本并修改
cp yata-backend-system.service yata-backend-system-ec2.service

# 修改用户名为 ec2-user（使用 sed）
sed -i 's/User=ubuntu/User=ec2-user/g' yata-backend-system-ec2.service
sed -i 's|/home/ubuntu/|/home/ec2-user/|g' yata-backend-system-ec2.service

# 复制到系统目录
sudo cp yata-backend-system-ec2.service /etc/systemd/system/yata-backend.service

# 重新加载并启动
sudo systemctl daemon-reload
sudo systemctl enable yata-backend.service
sudo systemctl start yata-backend.service

# 检查状态
sudo systemctl status yata-backend.service
```

**对于其他用户名或路径：**

```bash
# 手动编辑配置文件
nano ~/YATA/backend/services/yata-backend-system.service

# 修改以下行：
# User=ubuntu          → 改为你的用户名
# WorkingDirectory=... → 改为你的项目路径
# Environment="PATH=...→ 改为你的项目路径
# ExecStart=...        → 改为你的项目路径

# 保存后复制
sudo cp ~/YATA/backend/services/yata-backend-system.service /etc/systemd/system/yata-backend.service

# 重新加载并启动
sudo systemctl daemon-reload
sudo systemctl enable yata-backend.service
sudo systemctl start yata-backend.service
```

#### 步骤 4: 验证服务正常运行

```bash
# 查看服务状态
sudo systemctl status yata-backend.service

# 查看最新日志
sudo journalctl -u yata-backend.service -n 50 --no-pager

# 实时查看日志
sudo journalctl -u yata-backend.service -f
```

### 方案二：改用用户级服务（更简单，推荐）

用户级服务不需要修改配置文件，更简单且更安全。

```bash
# 1. 删除旧的系统级服务
sudo systemctl stop yata-backend.service 2>/dev/null
sudo systemctl disable yata-backend.service 2>/dev/null
sudo rm /etc/systemd/system/yata-backend.service 2>/dev/null
sudo systemctl daemon-reload

# 2. 创建用户级服务目录
mkdir -p ~/.config/systemd/user/

# 3. 复制用户级服务文件
cp ~/YATA/backend/services/yata-backend.service ~/.config/systemd/user/

# 4. 启用 linger（允许用户服务在未登录时运行）
sudo loginctl enable-linger $USER

# 5. 重新加载并启动
systemctl --user daemon-reload
systemctl --user enable yata-backend.service
systemctl --user start yata-backend.service

# 6. 查看状态
systemctl --user status yata-backend.service
```

## 同时配置前端服务

如果你也需要配置 Streamlit 前端服务，使用相同的方法：

### 系统级（Ubuntu EC2）

```bash
sudo cp ~/YATA/backend/services/yata-tiny-frontend-system.service /etc/systemd/system/yata-tiny-frontend.service
sudo systemctl daemon-reload
sudo systemctl enable --now yata-tiny-frontend.service
sudo systemctl status yata-tiny-frontend.service
```

### 用户级

```bash
cp ~/YATA/backend/services/yata-tiny-frontend.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now yata-tiny-frontend.service
systemctl --user status yata-tiny-frontend.service
```

## 一键部署脚本

### Ubuntu EC2 系统级服务一键部署

保存以下内容为 `deploy-system-service.sh`：

```bash
#!/bin/bash

echo "正在部署 YATA 系统级服务..."

# 停止并清理旧服务
echo "清理旧服务..."
sudo systemctl stop yata-backend.service 2>/dev/null
sudo systemctl stop yata-tiny-frontend.service 2>/dev/null
sudo systemctl disable yata-backend.service 2>/dev/null
sudo systemctl disable yata-tiny-frontend.service 2>/dev/null
sudo rm /etc/systemd/system/yata-backend.service 2>/dev/null
sudo rm /etc/systemd/system/yata-tiny-frontend.service 2>/dev/null

# 部署新服务
echo "部署新服务..."
sudo cp ~/YATA/backend/services/yata-backend-system.service /etc/systemd/system/yata-backend.service
sudo cp ~/YATA/backend/services/yata-tiny-frontend-system.service /etc/systemd/system/yata-tiny-frontend.service

# 启动服务
echo "启动服务..."
sudo systemctl daemon-reload
sudo systemctl enable yata-backend.service
sudo systemctl enable yata-tiny-frontend.service
sudo systemctl start yata-backend.service
sudo systemctl start yata-tiny-frontend.service

# 检查状态
echo ""
echo "===== 后端服务状态 ====="
sudo systemctl status yata-backend.service --no-pager

echo ""
echo "===== 前端服务状态 ====="
sudo systemctl status yata-tiny-frontend.service --no-pager

echo ""
echo "部署完成！"
echo "后端地址: http://localhost:8000"
echo "前端地址: http://localhost:8501"
echo ""
echo "查看日志:"
echo "  sudo journalctl -u yata-backend.service -f"
echo "  sudo journalctl -u yata-tiny-frontend.service -f"
```

运行：

```bash
chmod +x deploy-system-service.sh
./deploy-system-service.sh
```

### 用户级服务一键部署

保存以下内容为 `deploy-user-service.sh`：

```bash
#!/bin/bash

echo "正在部署 YATA 用户级服务..."

# 停止旧的系统级服务（如果存在）
echo "清理旧的系统级服务..."
sudo systemctl stop yata-backend.service 2>/dev/null
sudo systemctl stop yata-tiny-frontend.service 2>/dev/null
sudo systemctl disable yata-backend.service 2>/dev/null
sudo systemctl disable yata-tiny-frontend.service 2>/dev/null
sudo rm /etc/systemd/system/yata-backend.service 2>/dev/null
sudo rm /etc/systemd/system/yata-tiny-frontend.service 2>/dev/null

# 创建用户级服务目录
echo "创建用户级服务目录..."
mkdir -p ~/.config/systemd/user/

# 复制服务文件
echo "复制服务文件..."
cp ~/YATA/backend/services/yata-backend.service ~/.config/systemd/user/
cp ~/YATA/backend/services/yata-tiny-frontend.service ~/.config/systemd/user/

# 启用 linger
echo "启用 linger..."
sudo loginctl enable-linger $USER

# 启动服务
echo "启动服务..."
systemctl --user daemon-reload
systemctl --user enable yata-backend.service
systemctl --user enable yata-tiny-frontend.service
systemctl --user start yata-backend.service
systemctl --user start yata-tiny-frontend.service

# 检查状态
echo ""
echo "===== 后端服务状态 ====="
systemctl --user status yata-backend.service --no-pager

echo ""
echo "===== 前端服务状态 ====="
systemctl --user status yata-tiny-frontend.service --no-pager

echo ""
echo "部署完成！"
echo "后端地址: http://localhost:8000"
echo "前端地址: http://localhost:8501"
echo ""
echo "查看日志:"
echo "  journalctl --user -u yata-backend.service -f"
echo "  journalctl --user -u yata-tiny-frontend.service -f"
```

运行：

```bash
chmod +x deploy-user-service.sh
./deploy-user-service.sh
```

## 常用管理命令

### 系统级服务

```bash
# 查看状态
sudo systemctl status yata-backend.service

# 启动/停止/重启
sudo systemctl start yata-backend.service
sudo systemctl stop yata-backend.service
sudo systemctl restart yata-backend.service

# 查看日志
sudo journalctl -u yata-backend.service -f

# 启用/禁用开机自启
sudo systemctl enable yata-backend.service
sudo systemctl disable yata-backend.service
```

### 用户级服务

```bash
# 查看状态
systemctl --user status yata-backend.service

# 启动/停止/重启
systemctl --user start yata-backend.service
systemctl --user stop yata-backend.service
systemctl --user restart yata-backend.service

# 查看日志
journalctl --user -u yata-backend.service -f

# 启用/禁用开机自启
systemctl --user enable yata-backend.service
systemctl --user disable yata-backend.service
```

## 验证服务正常运行

### 1. 检查服务状态

```bash
# 系统级
sudo systemctl status yata-backend.service

# 用户级
systemctl --user status yata-backend.service
```

状态应该显示 `Active: active (running)`

### 2. 检查端口监听

```bash
# 检查后端端口 8000
sudo ss -tlnp | grep 8000

# 检查前端端口 8501
sudo ss -tlnp | grep 8501
```

### 3. 测试 API

```bash
# 测试后端 API
curl http://localhost:8000/health

# 或在浏览器访问
# http://<EC2-Public-IP>:8000
# http://<EC2-Public-IP>:8501
```

## 配置 AWS 安全组

如果需要从外部访问，记得在 AWS 控制台配置安全组：

1. 进入 EC2 控制台
2. 选择你的实例
3. 点击 "Security" → "Security groups"
4. 点击安全组 ID
5. "Inbound rules" → "Edit inbound rules" → "Add rule"
   - **后端**: Type: Custom TCP, Port: 8000, Source: 根据需求
   - **前端**: Type: Custom TCP, Port: 8501, Source: 根据需求

## 推荐方案

对于 AWS EC2 个人项目，我**强烈推荐使用用户级服务（方案二）**，原因：

- ✅ 无需修改配置文件
- ✅ 更安全（以当前用户身份运行）
- ✅ 更简单（自动处理路径和用户名）
- ✅ 更容易管理和调试

只需要记住使用 `systemctl --user` 而不是 `sudo systemctl` 即可。
