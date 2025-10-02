# YATA 前端项目

这是 YATA (Yet Another Travel Agent) 项目的前端部分，基于 Next.js 构建，提供 AI 旅行规划聊天体验与账户登录流程。

## 技术栈   

- **Next.js**: React 框架，用于服务端渲染和静态站点生成
- **Semi UI**: 字节跳动开源的企业级设计系统和 React 组件库
- **React & Context API**: 构建组件与应用状态管理
- **react-markdown**: 渲染 AI 返回的 Markdown 回复

## 项目结构

```
frontend/
├── components/       # 可复用组件
│   ├── chat/         # 聊天相关组件
│   ├── common/       # 通用组件
│   ├── dashboard/    # 仪表盘组件
│   └── layout/       # 布局组件
├── data/             # 静态数据
├── lib/              # 工具函数、服务、自定义 Hooks
├── modules/          # 功能模块
├── pages/            # 页面组件
├── store/            # 状态管理
└── styles/           # 全局样式
```

## 核心功能

- **AI 旅行助手**：通过 `/api/chat` 代理调用大模型 API，支持 Markdown 结果展示。
- **快速问题模板**：预定义旅行场景快速触发对话。
- **账户登陆与注册**：未登录时显示提示面板，登录后展示聊天，并在顶部显示昵称与登出按钮。
- **多语言界面**：支持中文与英文切换。

## 开始使用

### 环境变量

在项目根目录创建 `.env.local`（用于本地开发），填入大模型 API 凭据：

```
ZMON_API_KEY=your_api_key_here
# 可选：覆盖默认配置
ZMON_API_URL=https://api.zmon.me/v1/chat/completions
ZMON_API_MODEL=glm-4-air
```

设置后需重启开发服务器以生效。

### 安装依赖

```bash
npm install
```

### 开发环境运行

```bash
npm run dev
```

应用将在 [http://localhost:3000](http://localhost:3000) 启动。首次进入需要注册或登录一个账号才可使用聊天功能（账户信息仅保存在当前会话中）。

### 构建生产版本

```bash
npm run build
```

### 运行生产版本

```bash
npm start
```

## 开发提示

- 账户数据与会话状态目前仅存于内存，刷新页面后会重置，可按需扩展到后端或 `localStorage`。
- 大模型代理位于 `pages/api/chat.js`，可根据需要调整请求模型、系统提示或错误处理。
- 聊天历史使用 `react-markdown` 渲染，若要支持高亮可引入 `rehype-highlight` 等插件。
- 运行 `npm run lint` 时 Next.js 会提示初始化 ESLint，请按需完成设置。
