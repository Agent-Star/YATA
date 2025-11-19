# 追加: 为 frontend 配置 systemd 服务

很好, 你已经成功地为 NLU 和 RAG 配置了 `user-wide` 的 `systemd` 服务 (效仿对 backend 的处理). 现在, 请你进一步为 frontend 也配置 systemd 服务, 置于目录 @backend/systemd-config/frontend/ 中. frontend 的 README 文件为 @backend/docs/cross-module-readmes/Frontend-README.md . 如你所见, frontend 并不是 python 实现的, 而是 JavaScript 实现的 (使用 npm 进行包管理).

不过在你正式为 frontend 配置 systemd 服务之前, 你需要先 checkout 到 feat/frontend 分支上, 了解 frontend/ 目录中的对应实现, 为我分析到底应该是使用 `npm run dev` 还是 `npm start` (假设我已经提前进行了 `npm run build`) 启动 frontend 服务. 在我做出选择后, 才正式地为 frontend 配置 systemd 服务.
