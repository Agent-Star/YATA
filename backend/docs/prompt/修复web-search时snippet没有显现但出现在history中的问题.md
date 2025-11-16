# 修复 web-search 时 snippet 没有显现但出现在 history 中的问题

## 约定

请你注意, 如果我要求你先对接下来的某些步骤进行规划, 那么请你将你的规划以 markdown 文件的格式输出到 @backend/docs/gen 中, 而且是分门别类的存放到对应的子文件夹中 (如果缺乏对应的类别, 必要时你可以自行创建子文件夹, 目前的 docs/gen 规则详见 @backend/docs/gen/README.md ). 同时, 无论是做规划, 还是之后具体实现代码时, 这里请你注意几点:

1. 新代码的风格应该与旧代码完全保持一致 (必要的注释, 注释可以是中英文混杂的, 但是一定要采用英文标点, 而且中文和英文之前应该用空格隔开; 必要的类型标注, 目前我给 pyright 指定的 type check level 为 standard, 在这个 check level 下, 请你务必保证不要犯低级的类型错误, 一定要写出 lint-error-free 和 bug-free 的代码, 而且尽量避免使用 #type: ignore 这样的注释绕过类型检查来规避错误)
   - pyright typecheck level 详见 @backend/pyrightconfig.json , 也就是说你可以在通过 `./.venv/bin/activate` 激活虚拟环境后, 对实现的代码直接使用 pyright 指令进行 lint, 如果你要在 backend 层面全局使用 pyright, 那么也请你只关注改动或者新实现的代码的相关 lint error 其他的暂时忽略就好.
2. 请你一定要注意, 实现的新功能如无必要请一定不要大改目前的项目架构 (比如说严格遵循 DTO 添加更多 layer), 这只是一个可用性高的 prototype, 不是企业级应用, 不应该让项目本身变得过于臃肿, 应该更务实更敏捷的以现有的架构为基础以直接实现新功能为导向.
3. 如有必要, 请你使用互联网搜索服务获取你想要的相关文档.

接下来我的需求, 一定是围绕着 @backend/ 中已经实现的所有功能 (如你所见, backend 采用 uv + venv 进行包管理和虚拟环境隔离) 展开的, 即 `基于现有 @backend/ 实现, 追加某些功能, 或是修复某些潜在的 bug`. 因此, 请你在规划或是实现我的需求前, 务必仔细地阅读并理解 @backend/ 中已经实现的所有功能, 并把握其架构设计细节.

## 问题描述

首先先请你仔细阅读并深入理解当前后端 @backend/ 的架构和实现. 我发现, 如果说我的对话, 触发了 research-assistant 的 web-search 流程, 那么在调用 `GET /planner/history` (具体的前后端交互接口详见 @backend/docs/api/前后端-接口文档.md ) 时, 会显示出 `snippet` 对话记录 (详见 @backend/docs/bug-desc/history-dump.json ). 但我在通过前端调用 `POST /planner/plan/stream` 时这些 `snippet` 并不会显现, 而且像是 history-dump.json 中 "...并了解它们未来7天的天气预报。请稍等。" 和 "很抱歉，我无法直接从搜索结果中提取到热门温暖海滨城市未来7天的天气预报。..." 两条信息之间也不会分开显示, 而是在 `请稍等` 后过一小会, 直接继续渲染 `很抱歉`.

为了更全面的了解问题的来龙去脉, 你可以 `git checkout` 到 `feat/frontend`, 在 frontend/ 目录下阅读并理解前端的实现.

对 backend 和 frontend 的架构和实现有了深入的理解之后, 请你分析导致这个问题的原因是什么. 随后请你规划两种修复方案: 第一种, 能不能直接不让 `GET /planner/history` 显示 `snippet` (消息隔断不用在意, 这个是小问题); 第二种, backend 和 frontend 做出调整, 使得可以在 `POST /planner/plan/stream` 时就正确的处理像是 `消息隔断` 或是 `snippet` 这样的情况, 同时让 `GET /planner/history` 也能够返回顺序正确的完整对话. 其中, 第一种方案的修改不能涉及前端, 第二种方案的修改则在必要时可以涉及前端. 不过这两种方案的规划, 都应在当前的 `feat/backend` 分支上进行.

现在请你按照我的要求, 开始规划 `修复该 bug` 以及 `改进(前)后端实现, 从而规避该 bug` 的方案.
