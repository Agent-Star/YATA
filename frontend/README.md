# YATA 前端项目

这是 YATA (Yet Another Travel Agent) 项目的前端部分，基于 Next.js 构建，提供 AI 旅行规划聊天体验与账户登录流程。

## 技术栈   

- **Next.js**: React 框架，用于服务端渲染和静态站点生成
- **Semi UI**: 字节跳动开源的企业级设计系统和 React 组件库
- **React & Context API**: 构建组件与应用状态管理
- **react-markdown**: 渲染 AI 返回的 Markdown 回复
- **OpenAI API**: 提供多轮对话能力，支持上下文保持的旅行规划

## 项目结构

```
frontend/
├── components/       # 可复用组件
│   ├── auth/         # 认证相关组件
│   ├── chat/         # 聊天相关组件
│   ├── common/       # 通用组件
│   ├── dashboard/    # 仪表盘组件
│   └── layout/       # 布局组件
├── data/             # 静态数据
├── lib/              # 工具函数、服务、自定义 Hooks
│   ├── hooks/        # 自定义 React Hooks
│   ├── i18n/         # 国际化配置
│   └── services/     # API 服务
├── modules/          # 功能模块
├── pages/            # 页面组件
│   ├── api/          # API 路由
│   └── planner/      # 旅行规划页面
├── store/            # 状态管理
│   ├── chatContext.js # 聊天上下文管理
│   └── plannerContext.js # 规划器状态管理
└── styles/           # 全局样式
```

## 核心功能

- **AI 旅行助手**：通过 OpenAI API 提供智能旅行规划，支持多轮对话和上下文保持。
- **Markdown 渲染**：使用 react-markdown 渲染 AI 返回的格式化回复，提升阅读体验。
- **快速问题模板**：预定义旅行场景快速触发对话，如周末城市游、家庭旅行等。
- **账户登录与注册**：未登录时显示提示面板，登录后展示聊天，并在顶部显示昵称与登出按钮。
- **多语言界面**：支持中文与英文切换，提供本地化的用户体验。
- **流式响应**：支持 AI 回复的流式显示，提升用户体验。

## 开始使用

### 环境变量

在项目根目录创建 `.env.local`（用于本地开发），填入 OpenAI API 凭据：

```
OPENAI_API_KEY=your_api_key_here
# 可选：覆盖默认配置
OPENAI_API_URL=https://api.openai.com/v1/chat/completions
OPENAI_API_MODEL=gpt-3.5-turbo
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
- OpenAI API 集成位于 `lib/services/openaiService.js`，可根据需要调整请求模型、系统提示或错误处理。
- 聊天上下文管理位于 `store/chatContext.js`，负责维护多轮对话的消息历史。
- 旅行规划逻辑封装在 `lib/hooks/useTravelPlanner.js` 中，提供了生成和修改旅行计划的功能。
- 运行 `npm run lint` 时 Next.js 会提示初始化 ESLint，请按需完成设置。

## 最近更新

- 集成 OpenAI API 实现多轮对话功能
- 添加旅行规划上下文管理
- 优化聊天界面，支持 Markdown 渲染
- 实现流式响应，提升用户体验
- 添加多语言支持
