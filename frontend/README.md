# YATA 前端项目

这是 YATA (Yet Another Travel Agent) 项目的前端部分，基于 Next.js 构建，提供 AI 旅行规划聊天体验、收藏管理、旅行统计以及灵感/指南等多场景页面。

## 技术栈

- **Next.js**: React 框架，用于服务端渲染和静态站点生成
- **Semi UI**: 字节跳动开源的企业级设计系统和 React 组件库
- **React & Context API**: 构建组件与应用状态管理
- **react-markdown**: 渲染 AI 返回的 Markdown 回复
- **自研 AI Planner API**：通过 `/planner/*` 接口实现流式旅行规划（SSE），支持上下文保持

## 项目结构

```txt
frontend/
├── components/       # 可复用组件
│   ├── auth/         # 认证相关组件
│   ├── chat/         # 聊天相关组件
│   ├── common/       # 通用组件（Topbar、LanguageSwitcher 等）
│   └── layout/       # 布局
├── data/             # 静态数据
├── lib/              # 工具函数、服务、自定义 Hooks
│   ├── hooks/        # 自定义 React Hooks
│   ├── i18n/         # 国际化配置
│   └── services/     # API 服务
├── modules/          # 功能模块 (chat / dashboard / saved / inspiration / guides)
├── pages/            # Next.js 页面
│   └── api/          # 服务端接口 (planner/plan/stream 等)
├── store/            # 状态管理 (plannerContext)
└── styles/           # 全局样式
```

## 核心功能

- **AI 旅行助手**：通过 `planner/plan/stream` SSE 接口获取实时回复，完整保留历史上下文。
- **快捷提问与语音输入**：支持 Quick Actions、浏览器 Web Speech API 语音转文字，并可手动开启/停止录音。
- **收藏与 Saved Trips**：聊天消息支持收藏（带收藏按钮反馈），Saved Trips 页面可查看/取消收藏。
- **旅行统计 / 灵感 / 指南**：仪表盘展示旅行统计，Travel Inspiration & City Guides 提供静态灵感卡片（可跳转到 AI 规划）。
- **滚动体验**：聊天记录支持自动跟随／手动锁定、顶部/底部快捷按钮。
- **多语言**：全局使用 i18next，可在顶栏切换中英文。

## 开始使用

### 环境变量

前端默认通过 `NEXT_PUBLIC_API_BASE_URL` 调用后端。可在 `frontend/.env.*` 中配置，例如：

```txt
NEXT_PUBLIC_API_BASE_URL=http://localhost:3000/api
```

若不配置则使用同域接口（Next.js API Routes）。

### 安装依赖

```bash
npm install
```

### 开发环境运行

```bash
npm run dev
```

应用将在 [http://localhost:3000](http://localhost:3000) 启动。首次进入需注册或登录（数据通过 `/auth/*` 接口返回）。

### 构建生产版本

```bash
npm run build
```

### 运行生产版本

```bash
npm start
```

## 开发提示

- 所有接口封装在 `lib/services/apiClient.js` 与 `lib/services/aiPlanner.js` 中，可根据后端实际地址调整。
- 业务状态集中在 `store/plannerContext` + `lib/hooks/usePlanner`，任何新页面若需要规划器数据可直接调用 `usePlanner()`。
- 收藏操作会实时请求 `/planner/favorites`，如需真实数据请确保后端实现对应接口。
- 旅行统计/灵感/指南目前为静态数据，后续可对接真实分析结果。
- 语音输入依赖浏览器 `SpeechRecognition` API，非 Chrome 浏览器可能不支持。

## 最近更新

- 引入旅行统计（Dashboard）、旅行灵感与城市指南模块。
- 新增收藏功能 + Saved Trips 页面，支持与后端收藏接口同步。
- 集成浏览器语音转文字，提供录音状态与权限提示。
- 优化聊天历史自动滚动、顶部/底部定位按钮、收藏状态与提示文案。
- 清理未使用的 i18n 文案，并扩充 dashboard/inspiration/guides 相关翻译。
