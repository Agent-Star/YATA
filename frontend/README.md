# YATA 前端项目

这是 YATA (Yet Another Travel Agent) 项目的前端部分，基于 Next.js 构建。

## 技术栈   

- **Next.js**: React 框架，用于服务端渲染和静态网站生成
- **Semi UI**: 字节跳动开源的企业级设计系统和 React 组件库
- **React**: 用户界面库
- **Context API**: 状态管理

## 项目结构

```
frontend/
├── components/       # 可复用组件
│   ├── chat/         # 聊天相关组件
│   ├── common/       # 通用组件
│   ├── dashboard/    # 仪表盘组件
│   └── layout/       # 布局组件
├── data/             # 静态数据
├── lib/              # 工具函数和服务
│   ├── hooks/        # 自定义 React Hooks
│   └── services/     # API 服务
├── modules/          # 功能模块
├── pages/            # 页面组件
├── store/            # 状态管理
└── styles/           # 全局样式
```

## 开始使用

### 安装依赖

```bash
npm install
```

### 开发环境运行

```bash
npm run dev
```

应用将在 [http://localhost:3000](http://localhost:3000) 启动。

### 构建生产版本

```bash
npm run build
```

### 运行生产版本

```bash
npm start
```

## 注意事项

- 本项目使用 Semi UI 组件库，已配置相关样式导入
- 使用 Next.js 的 API 路由功能与后端通信
- 全局状态通过 Context API 管理