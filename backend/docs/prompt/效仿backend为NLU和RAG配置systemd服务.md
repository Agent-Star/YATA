# 效仿 backend 为 NLU 和 RAG 模块配置 systemd 服务

我们小组正在开发一个 `旅行规划智能体` 项目, 我负责 `后端` 的开发以及所有的 `运维` 事宜. 如你所见, 我开发的 @backend/ 模块 (使用 uv + venv 进行包管理和虚拟环境隔离), 已经在 @backend/systemd-config/backend/ 中正确的配置了 `system-wide` 和 `user-wide` 两种 `systemd config` 并附上了部署说明.

目前 NLU 和 RAG 模块与 backend 模块一样, 都是采用 uv + venv 进行包管理和虚拟环境隔离的. 因此, 我想请你效仿我对 `backend systemd-service` 的配置方式, 参考 @backend/docs/cross-module-readmes/NLU-README.md 和 @backend/docs/cross-module-readmes/RAG-README.md 中的内容, 为 NLU 和 RAG 模块分别部署 `user-wide` 的 `systemd config` 并附上部署说明, 分别分门别类的置于 @backend/systemd-config/NLU/ 和 @backend/systemd-config/RAG/ 目录中.

如果你需要确认 NLU 和 RAG 的具体实现, 你可以 checkout 到 feat/algorithms 分支上, 然后分别于 algorithms/NLU/ 和 algorithms/RAG_chroma 目录中找到 NLU 和 RAG 的实现. 但是请你务必注意, 最终你生成的所有 systemd-service 配置文件, 应该是在当前分支 `feat/backend` 上完成的, 而不是在 `feat/algorithms` 分支上完成的.
