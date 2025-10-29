# PostgreSQL 在 Amazon Linux 2023 上的完整安装配置指南

> **适用环境**: Amazon Linux 2023 (测试环境 & 生产环境)  
> **目标**: 从零开始安装 PostgreSQL，创建项目所需的用户和数据库，配置远程访问

---

## 📋 目录

1. [环境准备](#1-环境准备)
2. [安装 PostgreSQL](#2-安装-postgresql)
3. [初始化和启动服务](#3-初始化和启动服务)
4. [创建项目用户和数据库](#4-创建项目用户和数据库)
5. [配置远程访问](#5-配置远程访问)
6. [防火墙配置](#6-防火墙配置)
7. [验证和测试](#7-验证和测试)
8. [生产环境安全加固](#8-生产环境安全加固)
9. [常见问题排查](#9-常见问题排查)
10. [附录](#10-附录)

---

## 1. 环境准备

### 1.1 检查系统版本

```bash
cat /etc/os-release
```

确认输出包含：

```
NAME="Amazon Linux"
VERSION="2023"
```

### 1.2 更新系统软件包

```bash
sudo dnf update -y
```

**为什么要更新？**

- 确保安装最新的安全补丁
- 避免软件包依赖冲突
- 获取最新的 PostgreSQL 版本

### 1.3 检查可用的 PostgreSQL 版本

```bash
dnf search postgresql-server
```

**预期输出**（示例）：

```
postgresql15-server.x86_64 : PostgreSQL 15 server
postgresql16-server.x86_64 : PostgreSQL 16 server (推荐)
```

---

## 2. 安装 PostgreSQL

### 2.1 安装 PostgreSQL 服务器和扩展

```bash
# 安装 PostgreSQL 服务器（默认安装最新稳定版，通常是 15 或 16）
sudo dnf install postgresql-server postgresql-contrib -y
```

**软件包说明**：

- `postgresql-server`: PostgreSQL 数据库服务器
- `postgresql-contrib`: 额外的扩展和工具（如 uuid-ossp, pg_stat_statements 等）

### 2.2 验证安装

```bash
# 检查 PostgreSQL 版本
psql --version
```

**预期输出**：

```
psql (PostgreSQL) 15.x 或 16.x
```

---

## 3. 初始化和启动服务

### 3.1 初始化数据库集群

```bash
sudo postgresql-setup --initdb
```

**这一步做了什么？**

- 创建数据目录：`/var/lib/pgsql/data/`
- 生成配置文件：`postgresql.conf`、`pg_hba.conf`
- 初始化系统数据库（template0, template1, postgres）

**预期输出**：

```
Initializing database ... OK
```

### 3.2 启动 PostgreSQL 服务

```bash
# 启动服务
sudo systemctl start postgresql

# 设置开机自启
sudo systemctl enable postgresql

# 检查服务状态
sudo systemctl status postgresql
```

**预期输出**（部分）：

```
● postgresql.service - PostgreSQL database server
   Active: active (running) since ...
```

---

## 4. 创建项目用户和数据库

> **参考**: 根据项目 `env.example` 配置

### 4.1 设置 postgres 超级用户密码（可选但推荐）

```bash
# 切换到 postgres 用户并进入 psql
sudo -u postgres psql
```

**在 psql 提示符下执行**：

```sql
-- 为 postgres 超级用户设置密码（生产环境强烈推荐）
ALTER USER postgres WITH PASSWORD '您的超级管理员密码';

-- 退出
\q
```

### 4.2 创建项目数据库和用户

**方式 1: 交互式创建（推荐新手）**

```bash
# 切换到 postgres 用户
sudo -u postgres psql
```

**在 psql 提示符下依次执行**：

```sql
-- 创建用户（根据 env.example 中的 POSTGRES_USER）
CREATE USER yata WITH PASSWORD '<your-postgres-password>';

-- 创建数据库（根据 env.example 中的 POSTGRES_DB）
CREATE DATABASE yata_db OWNER yata;

-- 授予所有权限
GRANT ALL PRIVILEGES ON DATABASE yata_db TO yata;

-- 【PostgreSQL 15+ 必需】授予 public schema 权限
\c yata_db
GRANT ALL ON SCHEMA public TO yata;

-- 验证创建结果
\l       -- 列出所有数据库
\du      -- 列出所有用户

-- 退出
\q
```

**方式 2: 一键脚本（推荐生产环境）**

创建脚本 `setup_db.sh`：

```bash
#!/bin/bash

# 配置变量（从 env.example 读取）
DB_USER="yata"
DB_PASSWORD="<your-postgres-password>"  # 替换为实际密码
DB_NAME="yata_db"

# 创建 SQL 脚本
cat << EOF | sudo -u postgres psql
-- 创建用户
CREATE USER $DB_USER WITH PASSWORD '$DB_PASSWORD';

-- 创建数据库
CREATE DATABASE $DB_NAME OWNER $DB_USER;

-- 授予数据库权限
GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;

-- 连接到新数据库并授予 schema 权限
\c $DB_NAME
GRANT ALL ON SCHEMA public TO $DB_USER;

-- 显示结果
\l
\du
EOF

echo "✅ 数据库和用户创建完成！"
```

执行脚本：

```bash
chmod +x setup_db.sh
./setup_db.sh
```

### 4.3 验证用户权限

```bash
# 使用新创建的用户登录测试
psql -U yata -d yata_db -h localhost -W
```

输入密码后，应该能成功登录。执行测试：

```sql
-- 创建测试表
CREATE TABLE test (id SERIAL PRIMARY KEY, name TEXT);

-- 插入数据
INSERT INTO test (name) VALUES ('Hello PostgreSQL');

-- 查询数据
SELECT * FROM test;

-- 删除测试表
DROP TABLE test;

-- 退出
\q
```

---

## 5. 配置远程访问

> **⚠️ 注意**: 远程访问配置需谨慎，生产环境应限制特定 IP

### 5.1 修改监听地址

编辑 PostgreSQL 主配置文件：

```bash
sudo vi /var/lib/pgsql/data/postgresql.conf
```

**找到以下行（约在第 59 行）**：

```conf
#listen_addresses = 'localhost'
```

**修改为**：

```conf
# 开发/测试环境：监听所有 IP
listen_addresses = '*'

# 生产环境（推荐）：只监听特定 IP
# listen_addresses = 'localhost,172.31.0.0/16'  # 例如：本地 + VPC 内网
```

**其他可选调优参数**：

```conf
# 最大连接数（根据应用需求调整）
max_connections = 100

# 共享内存缓冲区（建议设为系统内存的 25%）
shared_buffers = 256MB

# 工作内存（用于排序和哈希操作）
work_mem = 4MB
```

保存并退出（`:wq`）。

### 5.2 配置客户端认证

编辑认证配置文件：

```bash
sudo vi /var/lib/pgsql/data/pg_hba.conf
```

**在文件末尾添加**（根据环境选择）：

**开发/测试环境**：

```conf
# 允许所有 IPv4 地址使用密码认证
host    all             all             0.0.0.0/0               md5

# 允许所有 IPv6 地址使用密码认证
host    all             all             ::/0                    md5
```

**生产环境（推荐 - 限制特定 IP）**：

```conf
# 允许本地连接
host    all             all             127.0.0.1/32            md5
host    all             all             ::1/128                 md5

# 允许 VPC 内网访问（示例：AWS VPC CIDR 172.31.0.0/16）
host    all             all             172.31.0.0/16           md5

# 允许特定应用服务器 IP（示例）
host    yata_db         yata            203.0.113.100/32        md5

# 拒绝其他所有连接
host    all             all             0.0.0.0/0               reject
```

**认证方法说明**：

- `md5`: 加密密码认证（推荐）
- `scram-sha-256`: 更安全的密码认证（PostgreSQL 10+）
- `trust`: 无密码认证（⚠️ 仅用于本地开发）
- `reject`: 拒绝连接

保存并退出。

### 5.3 重启 PostgreSQL 服务

```bash
sudo systemctl restart postgresql

# 检查服务状态
sudo systemctl status postgresql

# 检查监听端口
sudo ss -tlnp | grep 5432
```

**预期输出**：

```
LISTEN  0  128  0.0.0.0:5432  0.0.0.0:*  users:(("postmaster",pid=1234,...))
```

---

## 6. 防火墙配置

### 6.1 系统防火墙（firewalld）

**检查防火墙状态**：

```bash
sudo systemctl status firewalld
```

**开放 PostgreSQL 端口**：

```bash
# 添加 5432 端口（永久生效）
sudo firewall-cmd --add-port=5432/tcp --permanent

# 或添加 PostgreSQL 服务（推荐）
sudo firewall-cmd --add-service=postgresql --permanent

# 重新加载防火墙规则
sudo firewall-cmd --reload

# 验证规则
sudo firewall-cmd --list-all
```

**预期输出包含**：

```
ports: 5432/tcp
services: ... postgresql
```

**生产环境：限制来源 IP（推荐）**：

```bash
# 只允许特定 IP 访问 5432 端口
sudo firewall-cmd --permanent --add-rich-rule='
  rule family="ipv4"
  source address="203.0.113.100/32"
  port protocol="tcp" port="5432" accept'

sudo firewall-cmd --reload
```

### 6.2 AWS 安全组配置（EC2 环境）

> **⚠️ 重要**: 系统防火墙 + AWS 安全组需同时配置

**登录 AWS 控制台**：

1. 打开 **EC2 控制台** → **安全组**
2. 找到您 EC2 实例关联的安全组
3. 点击 **编辑入站规则** → **添加规则**

**配置入站规则**：

| 类型 | 协议 | 端口范围 | 来源 | 说明 |
|------|------|---------|------|------|
| PostgreSQL | TCP | 5432 | `0.0.0.0/0` | ⚠️ 开发环境（不推荐生产） |
| PostgreSQL | TCP | 5432 | `您的本地IP/32` | ✅ 生产环境（限制 IP） |
| PostgreSQL | TCP | 5432 | `sg-xxxxxxxx` | ✅ 同一 VPC 的安全组 |

**最佳实践**：

- 生产环境：只允许应用服务器的安全组或特定 IP
- 使用堡垒机（Bastion Host）进行数据库管理
- 考虑使用 VPC 私有子网部署数据库

### 6.3 验证防火墙配置

**从远程机器测试连接**：

```bash
# 使用 telnet 测试端口连通性
telnet <EC2-Public-IP> 5432

# 或使用 nc (netcat)
nc -zv <EC2-Public-IP> 5432
```

**成功输出**：

```
Connection to <IP> 5432 port [tcp/postgresql] succeeded!
```

---

## 7. 验证和测试

### 7.1 本地连接测试

```bash
# 使用项目配置的用户连接
psql -h localhost -U yata -d yata_db
```

### 7.2 远程连接测试

**从开发机器连接**（需要安装 `postgresql-client`）：

```bash
# 替换 <EC2-Public-IP> 为您的 EC2 实例公网 IP
psql -h <EC2-Public-IP> -U yata -d yata_db -p 5432
```

**或使用连接字符串**（用于应用配置）：

```bash
psql postgresql://yata:<your-postgres-password>@<EC2-Public-IP>:5432/yata_db
```

### 7.3 应用程序测试

**更新项目 `.env` 文件**：

```bash
# 如果后端与数据库在同一台服务器
POSTGRES_HOST=localhost

# 如果后端与数据库分离
POSTGRES_HOST=<数据库服务器IP>

POSTGRES_PORT=5432
POSTGRES_USER=yata
POSTGRES_PASSWORD=<your-postgres-password>
POSTGRES_DB=yata_db
```

**启动应用测试**：

```bash
cd backend
source .venv/bin/activate  # 激活虚拟环境
python src/run_service.py
```

观察日志，确认数据库连接成功。

---

## 8. 生产环境安全加固

### 8.1 密码策略

```sql
-- 设置密码过期时间
ALTER USER yata VALID UNTIL '2026-12-31';

-- 强制密码复杂度（需要安装 passwordcheck 扩展）
CREATE EXTENSION IF NOT EXISTS passwordcheck;
```

### 8.2 启用 SSL/TLS 连接

**生成自签名证书**（或使用 Let's Encrypt）：

```bash
# 切换到 postgres 用户
sudo -u postgres bash

# 生成私钥和证书
cd /var/lib/pgsql/data
openssl req -new -x509 -days 365 -nodes -text \
  -out server.crt -keyout server.key \
  -subj "/CN=<your-domain-or-ip>"

# 设置权限
chmod 600 server.key
exit
```

**修改 `postgresql.conf`**：

```conf
ssl = on
ssl_cert_file = 'server.crt'
ssl_key_file = 'server.key'
```

**修改 `pg_hba.conf`**（强制 SSL）：

```conf
hostssl    all             all             0.0.0.0/0               md5
```

**重启服务**：

```bash
sudo systemctl restart postgresql
```

### 8.3 限制连接数

```conf
# postgresql.conf
max_connections = 50  # 根据实际需求调整

# 为特定用户限制连接数
ALTER USER yata CONNECTION LIMIT 20;
```

### 8.4 启用审计日志

```conf
# postgresql.conf
logging_collector = on
log_directory = 'log'
log_filename = 'postgresql-%Y-%m-%d_%H%M%S.log'
log_statement = 'all'  # 记录所有 SQL（开发环境）
# log_statement = 'mod'  # 仅记录修改操作（生产环境）
log_connections = on
log_disconnections = on
log_duration = on
```

### 8.5 定期备份

**创建备份脚本** `backup_db.sh`：

```bash
#!/bin/bash

BACKUP_DIR="/var/backups/postgresql"
DATE=$(date +%Y%m%d_%H%M%S)
DB_NAME="yata_db"
DB_USER="yata"

mkdir -p $BACKUP_DIR

# 使用 pg_dump 备份
sudo -u postgres pg_dump -U $DB_USER $DB_NAME | gzip > \
  $BACKUP_DIR/${DB_NAME}_${DATE}.sql.gz

# 删除 7 天前的备份
find $BACKUP_DIR -name "*.sql.gz" -mtime +7 -delete

echo "✅ 备份完成: ${DB_NAME}_${DATE}.sql.gz"
```

**添加到 crontab**（每天凌晨 2 点备份）：

```bash
sudo crontab -e

# 添加以下行
0 2 * * * /path/to/backup_db.sh >> /var/log/pg_backup.log 2>&1
```

---

## 9. 常见问题排查

### 9.1 连接被拒绝（Connection refused）

**问题**：

```
psql: error: connection to server at "xxx", port 5432 failed: Connection refused
```

**排查步骤**：

1. **检查 PostgreSQL 是否运行**：

   ```bash
   sudo systemctl status postgresql
   ```

2. **检查监听地址**：

   ```bash
   sudo ss -tlnp | grep 5432
   # 应显示 0.0.0.0:5432 而非 127.0.0.1:5432
   ```

3. **检查防火墙**：

   ```bash
   sudo firewall-cmd --list-all | grep 5432
   ```

4. **检查 AWS 安全组**（如适用）

### 9.2 密码认证失败（Password authentication failed）

**问题**：

```
FATAL: password authentication failed for user "yata"
```

**排查步骤**：

1. **确认用户存在**：

   ```sql
   sudo -u postgres psql -c "\du"
   ```

2. **重置密码**：

   ```sql
   sudo -u postgres psql
   ALTER USER yata WITH PASSWORD 'new_password';
   ```

3. **检查 `pg_hba.conf` 认证方法**：

   ```bash
   sudo cat /var/lib/pgsql/data/pg_hba.conf | grep -v "^#" | grep -v "^$"
   ```

### 9.3 权限不足（Permission denied）

**问题**：

```
ERROR: permission denied for schema public
```

**解决方案**（PostgreSQL 15+）：

```sql
sudo -u postgres psql -d yata_db
GRANT ALL ON SCHEMA public TO yata;
GRANT ALL ON ALL TABLES IN SCHEMA public TO yata;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO yata;
```

### 9.4 连接数耗尽

**问题**：

```
FATAL: sorry, too many clients already
```

**解决方案**：

```sql
-- 查看当前连接数
SELECT count(*) FROM pg_stat_activity;

-- 查看每个用户的连接数
SELECT usename, count(*) FROM pg_stat_activity GROUP BY usename;

-- 增加最大连接数
sudo vi /var/lib/pgsql/data/postgresql.conf
# max_connections = 200

sudo systemctl restart postgresql
```

### 9.5 查看日志

```bash
# 查看 PostgreSQL 日志
sudo tail -f /var/lib/pgsql/data/log/postgresql-*.log

# 或通过 journalctl
sudo journalctl -u postgresql -f
```

---

## 10. 附录

### 10.1 常用 PostgreSQL 命令

**psql 内部命令**：

| 命令 | 说明 |
|------|------|
| `\l` | 列出所有数据库 |
| `\du` | 列出所有用户/角色 |
| `\dt` | 列出当前数据库的所有表 |
| `\d <table>` | 查看表结构 |
| `\c <dbname>` | 切换数据库 |
| `\q` | 退出 psql |
| `\?` | 查看所有命令帮助 |
| `\h <SQL>` | 查看 SQL 语法帮助 |

**系统管理命令**：

```bash
# 检查 PostgreSQL 版本
psql --version

# 查看配置文件位置
sudo -u postgres psql -c "SHOW config_file;"
sudo -u postgres psql -c "SHOW hba_file;"

# 重新加载配置（无需重启）
sudo -u postgres psql -c "SELECT pg_reload_conf();"

# 查看活动连接
sudo -u postgres psql -c "SELECT * FROM pg_stat_activity;"

# 终止特定连接
sudo -u postgres psql -c "SELECT pg_terminate_backend(<pid>);"
```

### 10.2 项目 `.env` 完整配置示例

```bash
# PostgreSQL 配置（根据实际环境修改）
DATABASE_TYPE=postgres
POSTGRES_USER=yata
POSTGRES_PASSWORD=your_secure_password_here  # 修改为强密码
POSTGRES_HOST=localhost  # 或数据库服务器 IP
POSTGRES_PORT=5432
POSTGRES_DB=yata_db

# 可选：连接池配置
POSTGRES_MIN_CONNECTIONS_PER_POOL=1
POSTGRES_MAX_CONNECTIONS_PER_POOL=10
POSTGRES_APPLICATION_NAME=yata-backend
```

### 10.3 连接字符串格式

```bash
# 标准格式
postgresql://用户名:密码@主机:端口/数据库名

# 项目示例
postgresql://yata:your_password@localhost:5432/yata_db

# 带 SSL（生产环境）
postgresql://yata:your_password@example.com:5432/yata_db?sslmode=require

# Python SQLAlchemy 格式（项目使用）
postgresql+asyncpg://yata:your_password@localhost:5432/yata_db
```

### 10.4 性能调优参考

**根据服务器规格调整** `postgresql.conf`：

```conf
# 4GB 内存服务器示例
shared_buffers = 1GB
effective_cache_size = 3GB
maintenance_work_mem = 256MB
checkpoint_completion_target = 0.9
wal_buffers = 16MB
default_statistics_target = 100
random_page_cost = 1.1  # SSD 存储
effective_io_concurrency = 200
work_mem = 10MB
min_wal_size = 1GB
max_wal_size = 4GB
```

**使用 [PGTune](https://pgtune.leopard.in.ua/) 生成推荐配置**。

### 10.5 监控脚本

**创建简单监控脚本** `monitor_pg.sh`：

```bash
#!/bin/bash

echo "=== PostgreSQL 监控 ==="
echo "服务状态:"
systemctl status postgresql | grep Active

echo -e "\n连接数:"
sudo -u postgres psql -t -c "SELECT count(*) FROM pg_stat_activity;"

echo -e "\n数据库大小:"
sudo -u postgres psql -t -c "
  SELECT pg_database.datname,
         pg_size_pretty(pg_database_size(pg_database.datname)) AS size
  FROM pg_database
  ORDER BY pg_database_size(pg_database.datname) DESC;"

echo -e "\n慢查询 (>1s):"
sudo -u postgres psql -t -c "
  SELECT pid, usename, query_start, query
  FROM pg_stat_activity
  WHERE state = 'active' AND query_start < now() - interval '1 second'
  LIMIT 5;"
```

---

## 🎯 快速启动检查清单

完成安装后，使用此检查清单验证：

- [ ] PostgreSQL 服务已启动并设置开机自启
- [ ] 创建了 `yata` 用户和 `yata_db` 数据库
- [ ] 可以使用 `yata` 用户本地登录数据库
- [ ] `postgresql.conf` 中 `listen_addresses` 已配置
- [ ] `pg_hba.conf` 中已添加客户端认证规则
- [ ] 防火墙已开放 5432 端口
- [ ] AWS 安全组已配置入站规则（EC2 环境）
- [ ] 可以从远程机器连接数据库
- [ ] 应用程序可以成功连接数据库
- [ ] 已设置定期备份计划（生产环境）
- [ ] 已启用 SSL/TLS（生产环境）

---

## 📚 参考资源

- [PostgreSQL 官方文档](https://www.postgresql.org/docs/)
- [Amazon Linux 2023 文档](https://docs.aws.amazon.com/linux/)
- [PostgreSQL Security Best Practices](https://www.postgresql.org/docs/current/security.html)
- [AWS RDS PostgreSQL 安全最佳实践](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/CHAP_PostgreSQL.html)

---

**文档版本**: 1.0  
**最后更新**: 2025-01-27  
**适用 PostgreSQL 版本**: 15.x, 16.x
